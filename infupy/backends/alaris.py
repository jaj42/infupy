import threading
import queue
import time

from enum import Enum, unique
from datetime import datetime

import serial
import crcmod

from infupy.backends.common import *

DEBUG = False

crcccitt = crcmod.predefined.mkCrcFun('crc-ccitt-false')
def genCheckSum(msg):
    crcval = crcccitt(msg)
    checkbytes = b'%04X' % crcval
    return checkbytes

def genFrame(msg):
    return b'!' + msg + b'|' + genCheckSum(msg) + b'\r'

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
    return round(10**-1 * n, 1)

def extractVolume(msg):
    vals = parseVars(msg)
    if VarId.volume in vals.keys():
        vol = vals[VarId.volume]
    else:
        raise ValueError
    n = int(vol, 16)
    return round(10**-3 * n, 3)

class AlarisSyringe(Syringe):
    def __init__(self, comm, index):
        super().__init__()
        if not isinstance(comm, AlarisComm):
            self._comm = None
            raise CommunicationError("Serial link error")
        else:
            self._comm = comm
        if isinstance(index, bytes):
            self.__index = index
        else:
            self.__index = str(index).encode('ASCII')
        self.connect()

    def __del__(self):
        if self._comm is not None:
            self.disconnect()

    def execRawCommand(self, msg, retry=True):
        def qTimeout():
            self._comm.recvq.put(Reply(error = True, value = Error.ETIMEOUT))
            self._comm.cmdq.task_done()
        
        cmd = genFrame(self.__index + msg)
        self._comm.cmdq.put(cmd)

        # Time out after 1 second in case of communication failure.
        t = threading.Timer(1, qTimeout)
        t.start()
        self._comm.cmdq.join()
        t.cancel()

        reply = self._comm.recvq.get()
        if not reply.error:
            return reply

        if retry and reply.value in [Error.ERNR, Error.ETIMEOUT]:
            printerr("Error: {}. Retrying command.", reply.value)
            return self.execRawCommand(msg, retry=False)
        elif reply.value == Error.ETIMEOUT:
            raise CommunicationError(reply.value)
        else:
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
        super().registerEvent(event)
        reply = self.execCommand(Command.enspont, flags=self._events)
        if reply.error:
            raise CommandError(reply.value)

    def unregisterEvent(self, event):
        super().unregisterEvent(event)
        reply = self.execCommand(Command.disspont)
        if reply.error:
            raise CommandError(reply.value)
        reply = self.execCommand(Command.enspont, flags=self._events)
        if reply.error:
            raise CommandError(reply.value)

    def clearEvents(self):
        super().clearEvents()
        reply = self.execCommand(Command.disspont)
        if reply.error:
            raise CommandError(reply.value)

    @property
    def index(self):
        return int(self.__index)

class AlarisComm(serial.Serial):
    def __init__(self, port, baudrate = 38400):
        # These settings come from Alaris documentation
        super().__init__(port     = port,
                         baudrate = baudrate,
                         bytesize = serial.EIGHTBITS,
                         parity   = serial.PARITY_NONE,
                         stopbits = serial.STOPBITS_ONE)
        if DEBUG:
            self.logfile = open('fresenius_raw.log', 'wb')

        self.recvq  = queue.LifoQueue()
        self.cmdq   = queue.Queue(maxsize = 10)
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

        self.__rxthread.start()
        self.__txthread.start()

    if DEBUG:
        # Write all data exchange to file
        def read(self, size=1):
            data = super().read(size)
            self.logfile.write(data)
            return data

        def write(self, data):
            self.logfile.write(data)
            return super().write(data)

class RecvThread(threading.Thread):
    def __init__(self, comm, recvq, cmdq, txlock):
        super().__init__(daemon=True)
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
            printerr("State machine got confused: {}", e)

    def enqueueReply(self, reply):
            self.__recvq.put(reply)
            self.allowNewCmd()

    def processRxBuffer(self):
        status, origin, msg, check = parseReply(self.__buffer)
        self.__buffer = b""
        self.sendACK()

        if status is ReplyStatus.incorrect:
            # Error condition
            try:
                error = Error(msg)
            except ValueError:
                error = Error.EUNDEF
            self.enqueueReply(Reply(origin, error, error = True))
            printerr("Command error: {}", error)

        elif status is ReplyStatus.correct:
            # This is a reply to one of our commands
            self.enqueueReply(Reply(origin, msg))

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
                try:
                    error = Error(c)
                except:
                    error = Error.EUNDEF
                self.enqueueReply(Reply(error = True, value = error))
                printerr("Protocol error: {}", error)
                insideNAKerr = False
            elif c == ACK:
                pass
            elif c == STX:
                # Start of command marker
                insideCommand = True
            elif c == ETX:
                # End of command marker
                insideCommand = False
                self.processRxBuffer()
            elif c == NAK:
                insideNAKerr = True
            elif insideCommand:
                self.__buffer += c
            elif c == '':
                pass # comm got closed
            else:
                printerr("Unexpected char received: {}", ord(c))

class SendThread(threading.Thread):
    def __init__(self, comm, cmdq, txlock):
        super().__init__(daemon=True)
        self.__comm   = comm
        self.__cmdq   = cmdq
        self.__txlock = txlock

    def run(self):
        while True:
            msg = self.__cmdq.get()
            with self.__txlock:
                self.__comm.write(msg)

class Reply(object):
    __slots__ = ('origin', 'value', 'error')
    def __init__(self, origin = None, value = '', error = False):
        if origin is None:
            self.origin = 0
        else:
            self.origin = int(origin)
        self.value = value
        self.error = error

    def __str__(self):
        return "Alaris Reply: Origin={}, Value={}, Error={}".format(self.origin, self.value, self.error)

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
@unique
class Error(Enum):
    EUNDEF   = '?'
    # Link layer errors
    ECHAR    = b'\x31'
    ECHKSUM  = b'\x32'
    EADDR    = b'\x34'
    ETIMEOUT = b'\x35'
    ERNR     = b'\x36'
    EFRAME   = b'\x37'
    ECTRL    = b'\x38'
    # Application layer errors
    EUNKNOWN    = b'01'
    ECMDMODE    = b'02'
    ECMDSTAT    = b'03'
    ESYNTAX     = b'04'
    EMODEAUTH   = b'05'
    EMODEAGAIN  = b'06'
    EMODEMODE   = b'07'
    ELIMIT      = b'08'
    EMODESTAT   = b'09'
    EIDENTU     = b'0A'
    EIDENTI     = b'0B'
    EMSGLONG    = b'0C'
    ECOMBASE    = b'0D'
    ECOMMODULEI = b'0E'
    EALARM      = b'12'
    ERATE       = b'14'
    EVOLUME     = b'15'
    EEMPTYMODE  = b'16'
    EEVENT      = b'1A'
    ECOMMODULE  = b'1E'
    ENMAN       = b'1F'
    EPORTAUTH   = b'20'
    ENMODEAUTH  = b'22'
    ECONMODEI   = b'24'
    EDRUG       = b'25'

    def __str__(self):
        return ERRdescr[self]

ERRdescr = {
    Error.EUNDEF   : "Unknown Error",
    # Link layer errors
    Error.ECHAR    : "Character Reception Problem",
    Error.ECHKSUM  : "Incorrect Check-sum",
    Error.EADDR    : "Incorrect Address",
    Error.ETIMEOUT : "End of [ACK] Character time-out",
    Error.ERNR     : "Receiver not Ready",
    Error.EFRAME   : "Incorrect Frame Length",
    Error.ECTRL    : "Presence of Control Code",
    # Application layer errors
    Error.EUNKNOWN    : "Unknown Command",
    Error.ECMDMODE    : "Command disabled in the current Mode",
    Error.ECMDSTAT    : "Command disabled in this status",
    Error.ESYNTAX     : "Syntax Error",
    Error.EMODEAUTH   : "Operating Mode not Authorized",
    Error.EMODEAGAIN  : "Operating Mode already active",
    Error.EMODEMODE   : "New operating mode disabled in this mode",
    Error.ELIMIT      : "Parameter out off limit",
    Error.EMODESTAT   : "New operating mode disabled in this status",
    Error.EIDENTU     : "Identifier not used",
    Error.EIDENTI     : "Identifier incorrect",                          # a-z
    Error.EMSGLONG    : "Message too long",                              # <= 80
    Error.ECOMBASE    : "Communication session with the base not open",
    Error.ECOMMODULEI : "Communication with module impossible",
    Error.EALARM      : "Presence of an Alarm",
    Error.ERATE       : "Attempt to launch infusion before flow rate selection",
    Error.EVOLUME     : "Insufficient Volume to launch a bolus",
    Error.EEMPTYMODE  : "Impossible to launch the empty Syringe mode",
    Error.EEVENT      : "Recorded event number incorrect",               # 1-64
    Error.ECOMMODULE  : "The Communication with the module is not open",
    Error.ENMAN       : "One of the modules is not in the manual mode",
    Error.EPORTAUTH   : "Command not authorized with this Port",
    Error.ENMODEAUTH  : "New mode unauthorized",
    Error.ECONMODEI   : "Connection Mode incorrect",
    Error.EDRUG       : "Drug number incorrect"
}