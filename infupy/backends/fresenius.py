import serial
import threading
import Queue

DEBUG = False

# Frame markers
STX = '\x02'
ETX = '\x03'

# Delivery control
ACK = '\x06'
NAK = '\x15'

# Keep-alive
ENQ = '\x05'
DC4 = '\x14'

# Allowed command characters
CHROK = map(chr, range(0x20 , 0x7E))

# Errors
ERRdata = {
    '\x31' : "Character Reception Problem",
    '\x32' : "Incorrect Check-sum",
#    '\x33' : "NOT USED",
    '\x34' : "Incorrect Address",
    '\x35' : "End of [ACK] Character time-out",
    '\x36' : "Receiver not Ready",
    '\x37' : "Incorrect Frame Length",
    '\x38' : "Presence of Control Code"
}

ERRcmd = {
    '01' : "Unknown Command",
    '02' : "Command disabled in the current Mode",
    '03' : "Command disabled in this status",
    '04' : "Syntax Error",
    '05' : "Operating Mode not Authorized",
    '06' : "Operating Mode already active",
    '07' : "New operating mode disabled in this mode",
    '08' : "Parameter out off limit",
    '09' : "New operating mode disabled in this status",
    '0A' : "Identifier not used",
    '0B' : "Identifier incorrect",                          # a-z
    '0C' : "Message too long",                              # <= 80
    '0D' : "Communication session with the base not open",
    '0E' : "Communication with module impossible",
#    '0F' : "RESERVED",
#    '11' : "RESERVED",
    '12' : "Presence of an Alarm",
#    '13' : "RESERVED",
    '14' : "Attempt to launch infusion before flow rate selection",
    '15' : "Insufficient Volume to launch a bolus",
    '16' : "Impossible to launch the empy Syringe mode",
#    '17' : "RESERVED",
#    '18' : "RESERVED",
#    '19' : "RESERVED",
    '1A' : "Recorded event number incorrect",               # 1-64
#    '1B' : "RESERVED",
#    '1C' : "RESERVED",
#    '1D' : "RESERVED",
    '1E' : "The Communication with the module is not open",
#    '1F' : "The Communication with the module is already open",
    '1F' : "One of the modules is not in the manual mode",
    '20' : "Command not authorized with this Port",
    '22' : "New mode unauthorized",
    '24' : "Connection Mode incorrect",
    '25' : "Drug number incorrect"
}

def hexToBinArray(hexstr):
    bindict = {'0' : False, '1' : True}
    binstr = "{:0>16b}".format(int(hexstr, 16))
    return map(lambda x: bindict[x], binstr)

def genCheckSum(msg):
    asciivalues = map(ord, msg)
    asciisum = sum(asciivalues)
    high, low = divmod(asciisum, 0x100)
    checksum = 0xFF - low
    checkstr = "{:02X}".format(checksum)
    return checkstr

def genFrame(msg):
    """
    Generate a frame to send to the device.
    """
    return STX + msg + genCheckSum(msg) + ETX

class FreseniusComm(serial.Serial):
    def __init__(self, port, baudrate = 19200):
        # These settings come from Fresenius documentation
        super(FreseniusComm, self).__init__(port     = port,
                                            baudrate = baudrate,
                                            bytesize = serial.SEVENBITS,
                                            parity   = serial.PARITY_EVEN,
                                            stopbits = serial.STOPBITS_ONE)
        if DEBUG:
            self.logfile = open('fresenius_raw.log', 'wb')

        self.recvq  = Queue.Queue()
        self.cmdq   = Queue.Queue(maxsize = 20)

        # Write lock to make sure only one source writes at a time
        self.__txlock = threading.Lock()
        # Semaphore ensures that we wait for answers before sending new commands
        self.__sem = threading.BoundedSemaphore(value = 1)

        self.rxthread = RecvThread(self, recvq  = self.recvq,
                                         cmdq   = self.cmdq,
                                         txlock = self.__txlock,
                                         sem    = self.__sem)

        self.txthread = SendThread(self, cmdq   = self.cmdq,
                                         txlock = self.__txlock,
                                         sem    = self.__sem)

        self.rxthread.daemon = True
        self.rxthread.start()

        self.txthread.daemon = True
        self.txthread.start()

    if DEBUG:
        def read(self, size=1):
            data = super(FreseniusComm, self).read(size)
            self.logfile.write(data)
            return data

        def write(self, data):
            self.logfile.write(data)
            return super(FreseniusComm, self).write(data)

    def __del__(self):
        self.cmdq.join()
        self.txthread.terminate()
        self.rxthread.terminate()

    def execCommand(self, msg):
        """
        High-level access to send commands and read replies.
        The reply is a tuple of (origin, message), where origin identifies the
        device.
        Mixing low-level and high-level commands can lead to race conditions.
        """
        self.cmdq.put(genFrame(msg))
        self.cmdq.join()
        return self.recvq.get()

    def sendCommand(self, msg, block = False):
        """
        Low level sending of commands.
        A maximum of 20 commands can be queued.
        This function will return False when the queue is full, and block is
        False. It will return True otherwise.
        Mixing low-level and high-level commands can lead to race conditions.
        """
        try:
            self.cmdq.put(genFrame(msg), block = block)
            return True
        except Queue.Full:
            return False

     def recvOne(self, block = True):
        """
        Low-level reading of device replies.
        The reply is a tuple of (origin, message), where origin identifies the
        device.
        If block is False and the queue is empty, None is returned.
        Mixing low-level and high-level commands can lead to race conditions.
        """
        try:
            m = self.recvq.get(block = block)
            return m
        except Queue.Empty:
            return None

     def recvAll(self):
        """
        Low-level reading of device replies.
        This function returns a list of all queued replies.
        The replies are tuples of (origin, message), where origin identifies
        the device.
        You should not mix low-level and high-level access.
        """
        while not self.recvq.empty():
            try:
                m = self.recvq.get(block = False)
                yield m
            except Queue.Empty:
                break


class RecvThread(threading.Thread):
    def __init__(self, comm, recvq, cmdq, txlock, sem):
        super(RecvThread, self).__init__()
        self.__comm   = comm
        self.__recvq  = recvq
        self.__cmdq   = cmdq
        self.__txlock = txlock
        self.__sem    = sem
        self.__terminate = False
        self.__buffer = ""

    def sendKeepalive(self):
        with self.__txlock:
            self.__comm.write(DC4)

    def sendACK(self):
        with self.__txlock:
            self.__comm.write(ACK)

    def sendSpontReply(self, origin):
        with self.__txlock:
            self.__comm.write(genFrame(origin))

    def extractMessage(self, rxstr):
        # The checksum is in the last two bytes
        chk   = rxstr[-2:]
        rxstr = rxstr[:-2]
        # Partition the string
        splt   = rxstr.split(';', 1)
        origin = splt[0]
        if len(splt) > 1:
            msg = splt[1]
        else:
            msg = None
        return (origin, msg, chk == genCheckSum(rxstr))

    def terminate(self):
        self.__terminate = True

    def allowNewCmd(self):
        self.__cmdq.task_done()
        self.__sem.release()

    def enqueueRxBuffer(self):
        origin, msg, check = self.extractMessage(self.__buffer)
        self.__buffer = ""
        self.sendACK()

        if len(origin) == 0:
            # This should actually not happen
            # XXX we should probably raise an error
            pass

        elif origin[-1] == 'I':
            # Error condition
            if msg in ERRcmd:
                errmsg = ERRcmd[msg]
            else:
                errmsg = "Unknown Error code {}".format(msg)
            self.allowNewCmd()
            print "Commmand error: {}".format(errmsg)

        # XXX look if this is correct (others ending in E/M ?)
        elif origin[-1] in ['E', 'M']:
            # Spontaneously generated information. We need to acknowledge.
            # Do not allowNewCmd() here
            self.sendSpontReply(origin)
            self.__recvq.put((origin, msg))

        else:
            # This is a reply to one of our commands 
            self.__recvq.put((origin, msg))
            self.allowNewCmd()

    def run(self):
        # We need to read byte by byte because ENQ/DC4 line monitoring
        # can happen any time and we need to reply quickly
        insideNAKerr = False
        insideCommand = False
        while not self.__terminate:
            c = self.__comm.read(1)
            if c == ENQ:
                self.sendKeepalive()
            elif insideNAKerr:
                if c in ERRdata:
                    errmsg = ERRdata[c]
                else:
                    errmsg = "Unknown Error code {}".format(c)
                print "Protocol error: {}".format(errmsg)
                self.allowNewCmd()
                insideNAKerr = False
            elif c == ACK:
                pass
            elif c == STX:
                # Start of command marker
                insideCommand = True
            elif c == ETX:
                # End of command marker
                insideCommand = False
                self.enqueueRxBuffer()
            elif c == NAK:
                insideNAKerr = True
            elif insideCommand:
                self.__buffer += c
            else:
                if DEBUG: print "Unexpected char received: {}".format(c)


class SendThread(threading.Thread):
    def __init__(self, comm, cmdq, txlock, sem):
        super(SendThread, self).__init__()
        self.__comm   = comm
        self.__cmdq   = cmdq
        self.__txlock = txlock
        self.__sem    = sem
        self.__terminate = False

    def terminate(self):
        self.__terminate = True

    def run(self):
        while not self.__terminate:
            try:
                msg = self.__cmdq.get(timeout = 2)
            except Queue.Empty:
                continue

            self.__sem.acquire()
            with self.__txlock:
                self.__comm.write(msg)
