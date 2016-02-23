import threading
import queue
import time

from enum import Enum
from datetime import datetime

import serial

from infupy.backends.common import *

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

def parseReply(rxbytes):
    # The checksum is in the last two bytes
    chk   = rxbytes[-2:]
    rxmsg = rxbytes[:-2]

    # Partition the string
    splt   = rxmsg.split(b';', 1)
    meta = splt[0]
    if len(splt) > 1:
        msg = splt[1]
    else:
        msg = None

    # Read meta data
    if len(meta) > 1:
        origin = meta[0:1]
        status = meta[1:2]
    else:
        origin = None
        status = meta[0:1]

    try:
        restat = ReplyStatus(status)
    except ValueError:
        restat = ReplyStatus.incorrect

    return (restat, origin, msg, chk == genCheckSum(rxmsg))

def parseVars(msg):
    ret = dict()
    if msg is None:
        return ret
    for repvar in msg.split(b';'):
        idbytes = repvar[0:1]
        value = repvar[1:]
        try:
            ident = VarId(idbytes)
        except ValueError:
            continue
        ret[ident] = value
    return ret

def extractRate(msg):
    vals = parseVars(msg)
    if VarId.rate in vals.keys():
        vol = vals[VarId.rate]
    else:
        raise ValueError
    n = int(vol, 16)
    return (10**-1 * n)

def extractVolume(msg):
    vals = parseVars(msg)
    if VarId.volume in vals.keys():
        vol = vals[VarId.volume]
    else:
        raise ValueError
    n = int(vol, 16)
    return (10**-3 * n)

class FreseniusSyringe(Syringe):
    def __init__(self, comm, index):
        super(FreseniusSyringe, self).__init__()
        if not isinstance(comm, FreseniusComm):
            self.__comm = None
            raise CommunicationError("Serial link error")
        else:
            self.__comm = comm
        if isinstance(index, bytes):
            self.__index = index
        else:
            self.__index = str(index).encode('ASCII')
        self.connect()

    def __del__(self):
        if self.__comm is not None:
            self.disconnect()

    def execRawCommand(self, msg):
        def qTimeout():
            self.__comm.recvq.put(Reply(error = True, value = "Timeout"))
            self.__comm.cmdq.task_done()
        
        cmd = genFrame(self.__index + msg)
        self.__comm.cmdq.put(cmd)

        # Time out after 1 second in case of communication failure.
        t = threading.Timer(1, qTimeout)
        t.start()
        self.__comm.cmdq.join()
        t.cancel()

        reply = self.__comm.recvq.get()
        if reply.error and reply.value == "Timeout":
            raise CommunicationError(reply.value)
        return reply

    def execCommand(self, command, flags=[], args=[]):
        if len(flags) > 0:
            flagvals = map(lambda x: x.value, flags)
            flagbytes = b''.join(flagvals)
            commandraw = command.value + b';' + flagbytes
        elif len(args) > 0:
            argbytes = b';'.join(args)
            commandraw = command.value + b';' + argbytes
        else:
            commandraw = command.value
        return self.execRawCommand(commandraw)

    def connect(self):
        return self.execCommand(Command.connect)

    def disconnect(self):
        try:
            self.execCommand(Command.disconnect)
        except CommunicationError:
            pass # CommunicationError means we're already disconnected.

    def readRate(self):
        reply = self.execCommand(Command.readvar, flags=[VarId.rate])
        if reply.error:
            raise CommandError(reply.value)
        return extractRate(reply.value)

    def readVolume(self):
        reply = self.execCommand(Command.readvar, flags=[VarId.volume])
        if reply.error:
            raise CommandError(reply.value)
        return extractVolume(reply.value)

    def readDrug(self):
        reply = self.execCommand(Command.readdrug)
        if reply.error:
            raise CommandError(reply.value)
        return reply.value

    def resetVolume(self):
        reply = self.execCommand(Command.resetvolume)
        if reply.error:
            raise CommandError(reply.value)

    def readDeviceType(self):
        reply = self.execCommand(Command.readfixed, flags=[FixedVarId.devicetype])
        if reply.error:
            raise CommandError(reply.value)
        return reply.value

    # Spontaneous variable handling
    def registerEvent(self, event):
        super(FreseniusSyringe, self).registerEvent(event)
        reply = self.execCommand(Command.enspont, flags=self._events)
        if reply.error:
            raise CommandError(reply.value)

    def unregisterEvent(self, event):
        super(FreseniusSyringe, self).unregisterEvent(event)
        reply = self.execCommand(Command.disspont)
        if reply.error:
            raise CommandError(reply.value)
        reply = self.execCommand(Command.enspont, flags=self._events)
        if reply.error:
            raise CommandError(reply.value)

    def clearEvents(self):
        super(FreseniusSyringe, self).clearEvents()
        reply = self.execCommand(Command.disspont)
        if reply.error:
            raise CommandError(reply.value)

    @property
    def index(self):
        return int(self.__index)


class FreseniusBase(FreseniusSyringe):
    def __init__(self, comm, wait = True):
        super(FreseniusBase, self).__init__(comm, 0)
        if wait:
            time.sleep(1)

    def listModules(self):
        modules = []
        reply = self.execCommand(Command.readvar, flags=[VarId.modules])
        if reply.error:
            raise CommandError(reply.value)
        results = parseVars(reply.value)
        binmods = int(results[VarId.modules], 16)
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
        self.eventq = queue.Queue()

        # Write lock to make sure only one source writes at a time
        self.__txlock = threading.Lock()

        self.__rxthread = RecvThread(comm   = self,
                                     recvq  = self.recvq,
                                     cmdq   = self.cmdq,
                                     txlock = self.__txlock)

        self.__txthread = SendThread(comm   = self,
                                     cmdq   = self.cmdq,
                                     txlock = self.__txlock)

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

    def sendSpontReply(self, origin, status):
        with self.__txlock:
            self.__comm.write(genFrame(origin + status.value))

    def allowNewCmd(self):
        try:
            self.__cmdq.task_done()
        except ValueError as e:
            if DEBUG: print("State machine got confused: " + str(e))

    def enqueueRxBuffer(self):
        status, origin, msg, check = parseReply(self.__buffer)
        self.__buffer = b""
        self.sendACK()

        if status is ReplyStatus.incorrect:
            # Error condition
            if msg in ERRcmd:
                errmsg = ERRcmd[msg]
            else:
                errmsg = "Unknown Error code {}".format(msg)
            self.allowNewCmd()
            self.__recvq.put(Reply(origin, errmsg, error = True))
            if DEBUG: print("Command error: {}".format(errmsg))

        elif status is ReplyStatus.correct:
            # This is a reply to one of our commands
            self.__recvq.put(Reply(origin, msg))
            self.allowNewCmd()

        elif status is ReplyStatus.spont or status is ReplyStatus.spontadj:
            # Spontaneously generated information. We need to acknowledge.
            self.sendSpontReply(origin, status)
            if origin is None or not origin.isdigit():
                return
            iorigin = int(origin)
            self.__comm.eventq.put((datetime.now(), iorigin, msg))

        else:
            pass

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
    def __init__(self, origin = None, value = '', error = False):
        if origin is None:
            self.origin = 0
        else:
            self.origin = int(origin)
        self.value  = value
        self.error  = error

    def __str__(self):
        return "Fresenius Reply: Origin={}, Value={}, Error={}".format(self.origin, self.value, self.error)

class Command(Enum):
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
    error   = b'e'
    mode    = b'm'
    rate    = b'd'
    volume  = b'r'
    bolrate = b'k'
    bolvol  = b's'
    nummods = b'i'
    modules = b'b'

class FixedVarId(Enum):
    devicetype = b'b'

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
