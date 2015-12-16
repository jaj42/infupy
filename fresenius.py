import serial
import Queue
import threading

DEBUG = True

# Frame markers
#STX = 'x'
#ETX = 'y'
STX = '\x02'
ETX = '\x03'

# Delivery control
#ACK  = 'q'
#NACK = 'r'
ACK  = '\x06'
NACK = '\x15'

# Keep-alive
#ENQ = 'v'
#DC4 = 'w'
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
    '\x01' : "Unknown Command",
    '\x02' : "Command disabled in the current Mode",
    '\x03' : "Command disabled in this status",
    '\x04' : "Syntax Error",
    '\x05' : "Operating Mode not Authorized",
    '\x06' : "Operating Mode already active",
    '\x07' : "New operating mode disabled in this mode",
    '\x08' : "Parameter out off limit",
    '\x09' : "New operating mode disabled in this status",
    '\x0A' : "Identifier not used",
    '\x0B' : "Identifier incorrect",                          # a-z
    '\x0C' : "Message too long",                              # <= 80
    '\x0D' : "Communication session with the base not open",
    '\x0E' : "Communication with module impossible",
#    '\x0F' : "RESERVED",
#    '\x11' : "RESERVED",
    '\x12' : "Presence of an Alarm",
#    '\x13' : "RESERVED",
    '\x14' : "Attempt to launch infusion before flow rate selection",
    '\x15' : "Insufficient Volume to launch a bolus",
    '\x16' : "Impossible to launch the empy Syringe mode",
#    '\x17' : "RESERVED",
#    '\x18' : "RESERVED",
#    '\x19' : "RESERVED",
    '\x1A' : "Recorded event number incorrect",               # 1-64
#    '\x1B' : "RESERVED",
#    '\x1C' : "RESERVED",
#    '\x1D' : "RESERVED",
    '\x1E' : "The Communication with the Syringe is not open",
    '\x1F' : "The Communication with the Syringe is already open",
    '\x20' : "Command not authorized with this Port",
    '\x22' : "New mode unauthorized",
    '\x24' : "Connection Mode incorrect",
    '\x25' : "Drug number incorrect"
}

def hexToBinArray(hexstr):
    bindict = {'0' : False, '1' : True}
    binstr = "{:0>16b}".format(int(hexstr, 16))
    return map(lambda x: bindict[x], binstr)

def genCheckSum(msg):
    """
    Generate the check sum.
    """
    asciivalues = map(ord, msg)
    asciisum = sum(asciivalues)
    high, low = divmod(asciisum, 0x100)
    checksum = 0xFF - low
    checkstr = "{:02X}".format(checksum)
    return checkstr

def genFrame(msg, syringe = None):
    if syringe is not None:
        msg = str(syringe) + msg
    return STX + msg + genCheckSum(msg) + ETX

class FreseniusComm(serial.Serial):
    def __init__(self, port, baudrate = 19200):
        super(FreseniusComm, self).__init__(port     = port,
                                            baudrate = baudrate,
                                            bytesize = serial.SEVENBITS,
                                            parity   = serial.PARITY_EVEN,
                                            stopbits = serial.STOPBITS_ONE)
        self.recvq  = Queue.Queue()
        self.cmdq   = Queue.Queue()
        self.txlock = threading.Lock()

        # Semaphore ensures that we wait for answers before sending new commands
        self.__sem = threading.BoundedSemaphore(value = 1)

        self.rxthread = RecvThread(self, recvq  = self.recvq,
                                         txlock = self.txlock,
                                         sem    = self.__sem)
        self.rxthread.daemon = True

        self.txthread = SendThread(self, cmdq   = self.cmdq,
                                         txlock = self.txlock,
                                         sem    = self.__sem)
        self.txthread.daemon = True

        self.start()

    def start(self):
        self.rxthread.start()
        self.txthread.start()

    def stop(self):
        self.txthread.terminate()
        self.rxthread.terminate()

    def sendCommand(self, msg):
        self.cmdq.put(genFrame(msg))

class RecvThread(threading.Thread):
    def __init__(self, comm, recvq, txlock, sem):
        super(RecvThread, self).__init__()
        self.__comm   = comm
        self.__recvq  = recvq
        self.__txlock = txlock
        self.__sem    = sem
        self.__terminate = False
        self.__buffer = ""

    def sendKeepalive(self):
        with self.__txlock:
            self.__comm.write(DC4)

    def sendCtrlReply(self, msg):
        with self.__txlock:
            self.__comm.write(msg)

    def sendSpontReply(self, msg):
        with self.__txlock:
            self.__comm.write(genFrame(msg))

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
        try:
            self.__sem.release()
        except ValueError:
            pass

    def enqueueRxBuffer(self):
        origin, msg, check = self.extractMessage(self.__buffer)
        self.__buffer = ""
        self.sendCtrlReply(ACK)

        if len(origin) == 0:
            pass

        elif origin[-1] == 'I':
            # Error condition
            if msg in ERRcmd:
                errmsg = ERRcmd[msg]
            else:
                errmsg = "Unknown Error code: {}".format(msg)
            self.allowNewCmd()
            print "Commmand error: {}".format(errmsg)
            return

        elif origin[-1] in ['E', 'M']:
            # Spontaneously generated information. We need to acknowledge.
            self.sendSpontReply(origin)
            if msg is not None: self.__recvq.put((origin, msg))

        else:
            # This is a reply to one of our commands 
            if msg is not None: self.__recvq.put((origin, msg))
            # We received the reply to the last command, allow to send one more
            self.allowNewCmd()

    def run(self):
        # We need to read byte by byte because ENQ/DC4 line monitoring
        # can happen any time and we need to reply quickly
        insideNACKerr = False
        insideCommand = False
        while not self.__terminate:
            c = self.__comm.read(1)
            if c == ENQ:
                self.sendKeepalive()
            elif insideNACKerr:
                if c in ERRdata:
                    errmsg = ERRdata[c]
                else:
                    errmsg = "Unknown Protocol Error code: {}".format(c)
                print "Protocol error: {}".format(errmsg)
                self.allowNewCmd()
                insideNACKerr = False
            elif c == ACK:
                pass
            elif c == STX:
                # Start of command marker
                insideCommand = True
            elif c == ETX:
                # End of command marker
                insideCommand = False
                self.enqueueRxBuffer()
            elif c == NACK:
                insideNACKerr = True
            elif insideCommand:
                self.__buffer += c


class SendThread(threading.Thread):
    def __init__(self, comm, cmdq, txlock, sem):
        super(SendThread, self).__init__()
        self.__comm = comm
        self.__cmdq = cmdq
        self.__txlock = txlock
        self.__sem  = sem
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
