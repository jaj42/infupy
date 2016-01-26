import serial
import threading
import queue

DEBUG = False

# Frame markers
STX = b'\x02'
ETX = b'\x03'

# Delivery control
ACK = b'\x06'
NAK = b'\x15'

# Keep-alive
ENQ = b'\x05'
DC4 = b'\x14'

# Allowed command characters
#CHROK = map(chr, range(0x20 , 0x7E))

# Errors
ERRdata = {
    b'\x31' : "Character Reception Problem",
    b'\x32' : "Incorrect Check-sum",
#    b'\x33' : "NOT USED",
    b'\x34' : "Incorrect Address",
    b'\x35' : "End of [ACK] Character time-out",
    b'\x36' : "Receiver not Ready",
    b'\x37' : "Incorrect Frame Length",
    b'\x38' : "Presence of Control Code"
}

ERRcmd = {
    b'01' : "Unknown Command",
    b'02' : "Command disabled in the current Mode",
    b'03' : "Command disabled in this status",
    b'04' : "Syntax Error",
    b'05' : "Operating Mode not Authorized",
    b'06' : "Operating Mode already active",
    b'07' : "New operating mode disabled in this mode",
    b'08' : "Parameter out off limit",
    b'09' : "New operating mode disabled in this status",
    b'0A' : "Identifier not used",
    b'0B' : "Identifier incorrect",                          # a-z
    b'0C' : "Message too long",                              # <= 80
    b'0D' : "Communication session with the base not open",
    b'0E' : "Communication with module impossible",
#    b'0F' : "RESERVED",
#    b'11' : "RESERVED",
    b'12' : "Presence of an Alarm",
#    b'13' : "RESERVED",
    b'14' : "Attempt to launch infusion before flow rate selection",
    b'15' : "Insufficient Volume to launch a bolus",
    b'16' : "Impossible to launch the empy Syringe mode",
#    b'17' : "RESERVED",
#    b'18' : "RESERVED",
#    b'19' : "RESERVED",
    b'1A' : "Recorded event number incorrect",               # 1-64
#    b'1B' : "RESERVED",
#    b'1C' : "RESERVED",
#    b'1D' : "RESERVED",
    b'1E' : "The Communication with the module is not open",
#    b'1F' : "The Communication with the module is already open",
    b'1F' : "One of the modules is not in the manual mode",
    b'20' : "Command not authorized with this Port",
    b'22' : "New mode unauthorized",
    b'24' : "Connection Mode incorrect",
    b'25' : "Drug number incorrect"
}

def genCheckSum(msg):
    asciisum = sum(msg)
    high, low = divmod(asciisum, 0x100)
    checksum = 0xFF - low
    #checkbytes = b"%02X" % checksum
    checkbytes = ("%02X" % checksum).encode('ASCII')
    return checkbytes

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

        self.recvq  = queue.Queue()
        self.cmdq   = queue.Queue(maxsize = 20)

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
        except queue.Full:
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
        except queue.Empty:
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
            except queue.Empty:
                break


class RecvThread(threading.Thread):
    def __init__(self, comm, recvq, cmdq, txlock, sem):
        super(RecvThread, self).__init__()
        self.__comm   = comm
        self.__recvq  = recvq
        self.__cmdq   = cmdq
        self.__txlock = txlock
        self.__sem    = sem
        self.__buffer = b""

    def sendKeepalive(self):
        with self.__txlock:
            self.__comm.write(DC4)

    def sendACK(self):
        with self.__txlock:
            self.__comm.write(ACK)

    def sendSpontReply(self, origin):
        with self.__txlock:
            self.__comm.write(genFrame(origin))

    def extractMessage(self, rxbytes):
        # The checksum is in the last two bytes
        chk   = rxbytes[-2:]
        rxbytes = rxbytes[:-2]
        # Partition the string
        splt   = rxbytes.split(b';', 1)
        origin = splt[0]
        if len(splt) > 1:
            msg = splt[1]
        else:
            msg = None
        return (origin, msg, chk == genCheckSum(rxbytes))

    def allowNewCmd(self):
        self.__cmdq.task_done()
        self.__sem.release()

    def enqueueRxBuffer(self):
        origin, msg, check = self.extractMessage(self.__buffer)
        self.__buffer = b""
        self.sendACK()

        if origin.endswith(b'I'):
            # Error condition
            if msg in ERRcmd:
                errmsg = ERRcmd[msg]
            else:
                errmsg = "Unknown Error code {}".format(msg)
            self.allowNewCmd()
            self.__recvq.put((b'E' + origin, errmsg))
            if DEBUG: print("Commmand error: {}".format(errmsg))

        elif origin.endswith(b'E') or origin.endswith(b'M'):
            # Spontaneously generated information. We need to acknowledge.
            # Do not allowNewCmd() here.
            self.sendSpontReply(origin)
            self.__recvq.put((origin, msg))

        else:
            # This is a reply to one of our commands 
            self.__recvq.put((origin, msg))
            self.allowNewCmd()

    def run(self):
        # We need to read byte by byte because ENQ/DC4 line monitoring
        # can happen any time and we need to reply quickly.
        insideNAKerr = False
        insideCommand = False
        while True:
            c = self.__comm.read(1)
            if c == ENQ:
                self.sendKeepalive()
            elif insideNAKerr:
                if c in ERRdata:
                    errmsg = ERRdata[c]
                else:
                    errmsg = "Unknown Error code {}".format(c)
                print("Protocol error: {}".format(errmsg))
                self.__recvq.put((b'E', errmsg))
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
                if DEBUG: print("Unexpected char received: {}".format(c))


class SendThread(threading.Thread):
    def __init__(self, comm, cmdq, txlock, sem):
        super(SendThread, self).__init__()
        self.__comm   = comm
        self.__cmdq   = cmdq
        self.__txlock = txlock
        self.__sem    = sem

    def run(self):
        while True:
            msg = self.__cmdq.get()

            self.__sem.acquire()
            with self.__txlock:
                self.__comm.write(msg)
