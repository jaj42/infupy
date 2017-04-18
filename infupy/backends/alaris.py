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
    # The checksum is seperated by a pipe
    rxmsg, chk = rxmsg.split(b'|', 1)

    # Fields are seperated by caret (HL7 style)
    fields = rxmsg.split(b'^')

    return (fields, chk == genCheckSum(rxmsg))

clas AlarisSyringe(Syringe):
    def __init__(self, comm):
        super().__init__()
        self._comm = comm
        self.connect()

    def __del__(self):
        if self._comm is not None:
            self.disconnect()

    def execRawCommand(self, msg, retry=True):
        cmd = genFrame(msg)
        self._comm.cmdq.put(cmd)

        reply = self._comm.recvq.get()
        if not reply.error:
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
        return True

    def disconnect(self):
        pass

    def readRate(self):
        reply = self.execCommand(Command.readvar, flags=[VarId.rate])
        if reply.error:
            raise CommandError(reply.value)
        return reply.value

    def readVolume(self):
        reply = self.execCommand(Command.readvar, flags=[VarId.volume])
        if reply.error:
            raise CommandError(reply.value)
        return reply.value

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

class AlarisComm(serial.Serial):
    def __init__(self, port, baudrate = 38400):
        # These settings come from Alaris documentation
        super().__init__(port     = port,
                         baudrate = baudrate,
                         bytesize = serial.EIGHTBITS,
                         parity   = serial.PARITY_NONE,
                         stopbits = serial.STOPBITS_ONE)
        if DEBUG:
            self.logfile = open('alaris_raw.log', 'wb')

        self.recvq = queue.LifoQueue()
        self.cmdq  = queue.Queue(maxsize = 10)

        # Write lock to make sure only one source writes at a time
        self.__rxthread = RecvThread(comm  = self,
                                     recvq = self.recvq,
                                     cmdq  = self.cmdq)

        self.__txthread = SendThread(comm  = self,
                                     cmdq  = self.cmdq)

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
    def __init__(self, comm, recvq, cmdq):
        super().__init__(daemon=True)
        self.__comm   = comm
        self.__recvq  = recvq
        self.__cmdq   = cmdq
        self.__buffer = b''

    def allowNewCmd(self):
        try:
            self.__cmdq.task_done()
        except ValueError as e:
            printerr("State machine got confused: {}", e)

    def processRxBuffer(self):
        fields, check = parseReply(self.__buffer)
        self.__buffer = b''
        reply = Reply(b' '.join(fields))
        self.__recvq.put(reply)
        self.allowNewCmd()

    def run(self):
        insideNAKerr = False
        insideCommand = False
        while True:
            c = self.__comm.read(1)
            if c == ESC:
                # Premature termination
                self.__buffer = b""
                insideCommand = False
            elif c == b'!':
                # Start of command marker
                insideCommand = True
            elif c == b'\r':
                # End of command marker
                insideCommand = False
                self.processRxBuffer()
            elif insideCommand:
                self.__buffer += c
            elif c == b'':
                pass
            else:
                printerr("Unexpected char received: {}", ord(c))

class SendThread(threading.Thread):
    def __init__(self, comm, cmdq):
        super().__init__(daemon=True)
        self.__comm = comm
        self.__cmdq = cmdq

    def run(self):
        while True:
            msg = self.__cmdq.get()
            self.__comm.write(msg)

class Reply(object):
    __slots__ = ('value', 'error')
    def __init__(self, value = '', error = False):
        self.value = value
        self.error = error

    def __str__(self):
        return "Alaris Reply: Value={}, Error={}".format(self.value, self.error)

ESC = b'\x1B'

class Command(Enum):
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
