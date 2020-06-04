import threading
import queue
import time

from enum import Enum, unique
from datetime import datetime

import serial

from infupy.backends.common import Syringe, CommandError, printerr

DEBUG = False

def genCheckSum(msg):
    asciisum = sum(msg)
    _, low = divmod(asciisum, 0x100)
    checksum = 0xFF - low
    return b'%02X' % checksum

def genFrame(dest, msg):
    if dest is None:
        dest = b''
    destmsg = dest + msg
    return STX + destmsg + genCheckSum(destmsg) + ETX

def parseReply(rxbytes):
    # The checksum is in the last two bytes
    chk   = rxbytes[-2:]
    rxmsg = rxbytes[:-2]

    # Partition the string
    splt = rxmsg.split(b';', 1)
    meta = splt[0]
    msg = splt[1] if len(splt) > 1 else None
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
    ret = {}
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
    if VarId.rate not in vals.keys():
        raise ValueError
    rate = vals[VarId.rate]
    n = int(rate, 16)
    return round(n * 1e-1, 1)

def extractVolume(msg):
    vals = parseVars(msg)
    if VarId.volume not in vals.keys():
        raise ValueError
    vol = vals[VarId.volume]
    n = int(vol, 16)
    return round(n * 1e-3, 3)

class FreseniusModule(Syringe):
    def __init__(self, comm, index=None):
        super().__init__()
        self.comm = comm
        if index is None:
            # Standalone syringe
            index = b''
        self._index = index if isinstance(index, bytes) else str(index).encode('ASCII')
        self.connect()

    def execRawCommand(self, msg, retry=True):
        def qTimeout():
            self.comm.recvq.put(Reply(error=True, value=Error.ETIMEOUT))
            self.comm.allowNewCmd()

        cmd = genFrame(self._index, msg)
        self.comm.cmdq.put(cmd)

        # Time out after 1 second in case of communication failure.
        t = threading.Timer(1, qTimeout)
        t.start()
        self.comm.cmdq.join()
        t.cancel()

        reply = self.comm.recvq.get()
        if reply.error and reply.value is Error.ECOMMODULE:
            printerr("Error: {}. Lost connection. Trying to reconnect.", reply.value)
            self.connect()
            return self.execRawCommand(msg, retry=False)
        elif reply.error and retry and reply.value in [Error.ERNR, Error.ETIMEOUT]:
            # Temporary error. Try once more
            printerr("Error: {}. Retrying command.", reply.value)
            return self.execRawCommand(msg, retry=False)
        else:
            return reply

    def execCommand(self, command, flags=[], args=[]):
        if len(flags) > 0:
            flagvals = [f.value for f in flags]
            flagbytes = b''.join(flagvals)
            commandraw = command.value + b';' + flagbytes
        elif len(args) > 0:
            argbytes = b';'.join(args)
            commandraw = command.value + b';' + argbytes
        else:
            commandraw = command.value
        return self.execRawCommand(commandraw)

    def connect(self):
        reply = self.execCommand(Command.connect)
        if reply.error:
            raise CommandError(reply.value)
        return reply.value

    def disconnect(self):
        self.execCommand(Command.disconnect)

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
        try:
            i = int(self._index)
        except ValueError:
            i = None
        return i


class FreseniusBase(FreseniusModule):
    def __init__(self, comm, wait=True):
        super().__init__(comm, 0)
        self.syringes = {}
        if wait:
            time.sleep(1)

    def connectSyringe(self, index):
        s = FreseniusSyringe(self.comm, index)
        self.syringes[index] = s
        return s

    def listModules(self):
        reply = self.execCommand(Command.readvar, flags=[VarId.modules])
        if reply.error:
            raise CommandError(reply.value)
        results = parseVars(reply.value)
        binmods = int(results[VarId.modules], 16)
        return [i + 1 for i in range(5) if (1 << i) & binmods]

    def readVolume(self):
        raise NotImplementedError

    def readRate(self):
        raise NotImplementedError


class FreseniusSyringe(FreseniusModule):
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

    def remoteControl(self, doctrl):
        #1 : manual, 2 : PC control
        newmode = b'2' if doctrl else b'1'
        reply = self.execCommand(Command.mode, args=[newmode])
        if reply.error:
            raise CommandError(reply.value)

    def stopInfusion(self):
        reply = self.execCommand(Command.setpause)
        if reply.error:
            raise CommandError(reply.value)


class FreseniusComm(serial.Serial):
    def __init__(self, port):
        # These settings come from Fresenius documentation
        super().__init__(port     = port,
                         baudrate = 19200,
                         bytesize = serial.SEVENBITS,
                         parity   = serial.PARITY_EVEN,
                         stopbits = serial.STOPBITS_ONE)
        if DEBUG:
            self.logrx = open('fresenius_rx.log', 'wb', buffering=0)
            self.logtx = open('fresenius_tx.log', 'wb', buffering=0)

        self.recvq  = queue.LifoQueue()
        self.cmdq   = queue.Queue(maxsize=10)
        self.eventq = queue.Queue(maxsize=1e4)

        # Write lock to make sure only one source writes at a time
        self.__rxthread = RecvThread(self)
        self.__txthread = SendThread(self)

        self.__rxthread.start()
        self.__txthread.start()

    def __del__(self):
        if DEBUG:
            close(self.logrx)
            close(self.logtx)

    if DEBUG:
        # Write all data exchange to file
        def read(self, size=1):
            data = super().read(size)
            self.logrx.write(data)
            return data

        def write(self, data):
            self.logtx.write(data)
            return super().write(data)

    def allowNewCmd(self):
        try:
            self.cmdq.task_done()
        except ValueError as e:
            printerr("State machine got confused: {}", e)


class RecvThread(threading.Thread):
    def __init__(self, comm):
        super().__init__(daemon=True)
        self.comm = comm
        self.__buffer = b''

    def acknowledgeEvent(self, origin, status):
        self.comm.cmdq.put(genFrame(origin, status.value))
        self.comm.allowNewCmd()

    def enqueueReply(self, reply):
        self.comm.recvq.put(reply)
        self.comm.allowNewCmd()

    def processRxBuffer(self):
        status, origin, msg, chk = parseReply(self.__buffer)
        self.__buffer = b''
        if chk:
            # Send ACK
            self.comm.cmdq.put(ACK)
            self.comm.allowNewCmd()
        else:
            # Send NAK
            printerr("Checksum error: {}", msg)
            self.comm.cmdq.put(NAK + Error.ECHKSUM.value)
            self.comm.allowNewCmd()
            return

        if status is ReplyStatus.incorrect:
            # Error condition
            try:
                error = Error(msg)
            except ValueError:
                error = Error.EUNDEF
            self.enqueueReply(Reply(origin, error, error=True))
            printerr("Command error: {}", error)

        elif status is ReplyStatus.correct:
            # This is a reply to one of our commands
            self.enqueueReply(Reply(origin, msg))

        elif status is ReplyStatus.spont or status is ReplyStatus.spontadj:
            # Spontaneously generated event. We need to acknowledge.
            self.acknowledgeEvent(origin, status)
            if origin is None or not origin.isdigit():
                return
            iorigin = int(origin)
            self.comm.eventq.put((datetime.now(), iorigin, msg))

    def run(self):
        insideNAKerr = False
        insideCommand = False
        while True:
            c = self.comm.read(1)
            if c == ENQ:
                # Send keep-alive
                self.comm.cmdq.put(DC4)
                self.comm.allowNewCmd()
            elif insideNAKerr:
                try:
                    error = Error(c)
                except:
                    error = Error.EUNDEF
                self.enqueueReply(Reply(error=True, value=error))
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
            elif c != b'':
                printerr("Unexpected char received: {}", ord(c))


class SendThread(threading.Thread):
    def __init__(self, comm):
        super().__init__(daemon=True)
        self.comm = comm

    def run(self):
        while True:
            msg = self.comm.cmdq.get()
            self.comm.write(msg)


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
CHROK = [chr(c) for c in range(0x20 , 0x7E)]

class Reply(object):
    __slots__ = ('origin', 'value', 'error')
    def __init__(self, origin=None, value='', error=False):
        self.origin = 0 if origin is None else int(origin)
        self.value = value
        self.error = error

    def __repr__(self):
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
@unique
class Error(Enum):
    EUNDEF   = b'?'
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

    def __repr__(self):
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
