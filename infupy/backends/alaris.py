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
    rxmsg, chk = rxbytes.split(b'|', 1)

    # Fields are seperated by caret (HL7 style)
    fields = rxmsg.split(b'^')

    ret = fields[1:]
    return (ret, chk == genCheckSum(rxmsg))

class Looper(threading.Thread):
    def __init__(self, syringe, delay=0.5, stopevent=None):
        super().__init__()
        if stopevent is None:
            stopevent = threading.Event()
        self.stopped = stopevent
        self.delay = delay
        self.syringe = syringe

    def run(self):
        syringe = self.syringe
        while not self.stopped.wait(self.delay):
            syringe.execCommand(Command.remotectrl, [b'ENABLED', syringe.securitycode])
            syringe.execCommand(Command.remotecfg, [b'ENABLED', syringe.securitycode])
        # Disable on exit
        syringe.execCommand(Command.remotectrl, [b'DISABLED'])
        syringe.execCommand(Command.remotecfg, [b'DISABLED'])

class AlarisSyringe(Syringe):
    def __init__(self, comm):
        super().__init__()
        self._comm = comm
        self.__seccode = None
        self.stopKeepalive = threading.Event()
        self.launchKeepAlive()

    def __del__(self):
        self.disconnect()

    def execRawCommand(self, msg, retry=True):
        def qTimeout():
            self._comm.recvq.put(Reply(error = True, value = Error.ETIMEOUT))
            self._comm.cmdq.task_done()

        cmd = genFrame(msg)
        self._comm.cmdq.put(cmd)

        # Time out after 1 second in case of communication failure.
        t = threading.Timer(1, qTimeout)
        t.start()
        self._comm.cmdq.join()
        t.cancel()

        reply = self._comm.recvq.get()
        return reply

    def execCommand(self, command, fields=[]):
        cmdfields = [command.value] + fields
        commandraw = b'^'.join(cmdfields)
        return self.execRawCommand(commandraw)

    def connect(self):
        return True

    def disconnect(self):
        self.stopKeepalive.set()

    def launchKeepAlive(self):
        looper = Looper(self, delay=1, stopevent=self.stopKeepalive)
        looper.start()

    @property
    def securitycode(self):
        if self.__seccode is None:
            reply = self.execCommand(Command.getserialno)
            if reply.error:
                raise CommandError(reply.value)
            self.__seccode = genCheckSum(reply.value)
        return self.__seccode

    def readRate(self):
        reply = self.execCommand(Command.rate)
        if reply.error:
            raise CommandError(reply.value)
        return reply.value

    def readVolume(self):
        reply = self.execCommand(Command.queryvolume)
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

    def __repr__(self):
        return "Alaris Reply: Value={}, Error={}".format(self.value, self.error)

ESC = b'\x1B'

class Command(Enum):
    getserialno = b'INST_SERIALNO'
    remotecfg   = b'REMOTE_CFG'
    remotectrl  = b'REMOTE_CTRL'
    queryvolume = b'INF_VI'
    rate        = b'INF_RATE'
    infstart    = b'INF_START'
    infstop     = b'INF_STOP'

# Errors
@unique
class Error(Enum):
    EUNDEF   = '?'
    ETIMEOUT = b'\x35'
