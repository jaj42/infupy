import serial
import threading
import queue
import time

from enum import Enum

from common import *

DEBUG = False

def genCheckSum(msg):
    asciisum = sum(msg)
    high, low = divmod(asciisum, 0x100)
    checksum = 0xFF - low
    # Needs Python >= 3.5
    #checkbytes = b"%02X" % checksum
    checkbytes = ("%02X" % checksum).encode('ASCII')
    return checkbytes

def genFrame(msg):
    return STX + msg + genCheckSum(msg) + ETX

class FreseniusSyringe(Syringe):
    def __init__(self, comm, index = ''):
        super(FreseniusSyringe, self).__init__()
        self.__comm  = comm
        self.__index = str(index).encode('ASCII')
        self.connect()

    def execRawCommand(self, msg):
        def qTimeout():
            self.__comm.recvq.put(Reply(error = True, value = "Timeout"))
            self.__comm.cmdq.task_done()
        
        cmd = genFrame(self.__index + msg)
        self.__comm.cmdq.put(cmd)

        # Time out after 2 seconds in case of communication failure.
        t = threading.Timer(2, qTimeout)
        t.start()
        self.__comm.cmdq.join()
        t.cancel()

        result = self.__comm.recvq.get()
        if result.error == True:
            raise CommError(result.value)
        return result

    def connect(self):
        return self.execRawCommand(Commmand.connect.value)

    def disconnect(self):
        return self.execRawCommand(Commmand.disconnect.value)

    def readRate(self):
        reply = self.execRawCommand(Commmand.readvar.value + b';'
                                  + VarId.rate.value)
        # XXX handle error condition
        n = int(reply.value[1:], 16)
        return (10**-1 * n)

    def readVolume(self):
        reply = self.execRawCommand(Commmand.readvar.value + b';'
                                  + VarId.volume.value)
        # XXX handle error condition
        n = int(reply.value[1:], 16)
        return (10**-3 * n)

class FreseniusBase(FreseniusSyringe):
    def __init__(self, comm):
        super(FreseniusBase, self).__init__(comm, 0)

    def __del__(self):
        self.disconnect()

    def connectedModules(self):
        modules = []
        reply = self.execRawCommand(Commmand.readvar.value + b';'
                                  + BaseId.modules.value)
        # XXX handle error condition
        binmods = int(reply.value[1:], 16)
        for i in range(5):
            if (1 << i) & binmods:
                modules.append(i + 1)
        return modules

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

        self.recvq = queue.Queue()
        self.cmdq  = queue.Queue(maxsize = 10)

        # Write lock to make sure only one source writes at a time
        self.txlock = threading.Lock()

        self.__rxthread = RecvThread(comm   = self,
                                     recvq  = self.recvq,
                                     cmdq   = self.cmdq,
                                     txlock = self.txlock)

        self.__txthread = SendThread(comm   = self,
                                     cmdq   = self.cmdq,
                                     txlock = self.txlock)

        self.__rxthread.daemon = True
        self.__rxthread.start()

        self.__txthread.daemon = True
        self.__txthread.start()

    if DEBUG:
        def read(self, size=1):
            data = super(FreseniusComm, self).read(size)
            self.logfile.write(data)
            return data

        def write(self, data):
            self.logfile.write(data)
            return super(FreseniusComm, self).write(data)


class RecvThread(threading.Thread):
    def __init__(self, comm, recvq, cmdq, txlock):
        super(RecvThread, self).__init__()
        self.__comm   = comm
        self.__recvq  = recvq
        self.__cmdq   = cmdq
        self.__txlock = txlock
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
            self.__recvq.put(Reply(origin, errmsg, error = True))
            if DEBUG: print("Commmand error: {}".format(errmsg))

        elif origin.endswith(b'E') or origin.endswith(b'M'):
            # Spontaneously generated information. We need to acknowledge.
            # Do not allowNewCmd() here.
            self.sendSpontReply(origin)
            self.__recvq.put(Reply(origin, msg))

        else:
            # This is a reply to one of our commands 
            self.__recvq.put(Reply(origin, msg))
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
                self.__recvq.put(Reply(error= True, value = errmsg))
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
    def __init__(self, comm, cmdq, txlock):
        super(SendThread, self).__init__()
        self.__comm   = comm
        self.__cmdq   = cmdq
        self.__txlock = txlock

    def run(self):
        while True:
            msg = self.__cmdq.get()

            with self.__txlock:
                self.__comm.write(msg)


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

class Reply(object):
    __slots__ = ('origin', 'value', 'error')
    def __init__(self, origin = None, value = None, error = False):
        self.origin = origin
        self.value  = value
        self.error  = error

    def __str__(self):
        return "Fresenius Reply: Origin={}, Value={}, Error={}".format(self.origin, self.value, self.error)

class Commands(Enum):
    connect      = b'DC'
    disconnect   = b'FC'
    mode         = b'MO'
    reset        = b'RZ'
    off          = b'OF'
    silence      = b'SI'
    setdrug      = b'EP'
    readdrug     = b'LP'
    showdrug     = b'AP'
    setid        = b'EN'
    readid       = b'LN'
    enspont      = b'DE'
    disspont     = b'AE'
    readvar      = b'LE'
    enspontadj   = b'DM'
    disspontadj  = b'AM'
    readadj      = b'LM'
    readfixed    = b'LF'
    setrate      = b'PR'
    setpause     = b'PO'
    setbolus     = b'PB'
    setempty     = b'PF'
    setlimvolume = b'PV'
    resetvolume  = b'RV'
    pressurelim  = b'PP'
    dynpressure  = b'PS'

class VarId(Enum):
    alarm   = b'a'
    preal   = b'b'
    error   = b'e'
    mode    = b'm'
    rate    = b'd'
    volume  = b'r'
    bolrate = b'k'
    bolvol  = b's'

class BaseId(Enum):
    alarm   = b'a'
    mode    = b'm'
    nummods = b'i'
    modules = b'b'
    module1 = b'c'
    module2 = b'd'
    module3 = b'e'
    module4 = b'f'
    module5 = b'g'
    module6 = b'h'

class ReplyStatus(Enum):
    correct   = b'C'
    incorrect = b'I'
    spont     = b'E'
    spontadj  = b'M'

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
