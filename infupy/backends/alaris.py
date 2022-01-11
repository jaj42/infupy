import threading
import queue

from enum import Enum, auto

import serial
import crcmod

from infupy.backends.common import Syringe, CommandError, printerr

DEBUG = False

crcccitt = crcmod.predefined.mkCrcFun('crc-ccitt-false')
def genCheckSum(msg):
    crcval = crcccitt(msg)
    return b'%04X' % crcval

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
    def __init__(self, syringe, delay, stopevent):
        super().__init__(daemon=True)
        self.stopped = stopevent
        self.delay = delay
        self.syringe = syringe

    def run(self):
        # Need to 'enable' continuously for keep-alive
        while not self.stopped.wait(self.delay):
            self.enable()
        self.disable()

    def enable(self):
        s = self.syringe
        s.execCommand(Command.remotectrl, [b'ENABLED', s.securitycode])
        s.execCommand(Command.remotecfg, [b'ENABLED', s.securitycode])

    def disable(self):
        s = self.syringe
        s.execCommand(Command.remotectrl, [b'DISABLED'])
        s.execCommand(Command.remotecfg, [b'DISABLED'])

class AlarisSyringe(Syringe):
    def __init__(self, comm):
        super().__init__()
        self.comm = comm
        self.__seccode = None
        self.__kastopper = threading.Event()
        self.launchKeepAlive()

    def __del__(self):
        self.stopKeepAlive()

    def execRawCommand(self, msg, retry=True):
        def qTimeout():
            self.comm.recvq.put(Reply(error = True, value = Error.ETIMEOUT))
            self.comm.allowNewCmd()

        cmd = genFrame(msg)
        self.comm.cmdq.put(cmd)

        # Time out after .5 seconds in case we get no reply.
        t = threading.Timer(.5, qTimeout)
        t.start()
        self.comm.cmdq.join()
        t.cancel()

        reply = self.comm.recvq.get()
        if reply.error and retry and reply.value is Error.ETIMEOUT:
            # Temporary error. Try once more
            printerr("Error: {}. Retrying command.", reply.value)
            return self.execRawCommand(msg, retry=False)
        else:
            return reply

    def execCommand(self, command, fields=[]):
        cmdfields = [command.value] + fields
        commandraw = b'^'.join(cmdfields)
        return self.execRawCommand(commandraw)

    def launchKeepAlive(self):
        looper = Looper(self, delay=1, stopevent=self.__kastopper)
        looper.start()

    def stopKeepAlive(self):
        self.__kastopper.set()

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

    def setRate(self, newrate):
        brate = str(newrate).encode('ASCII')
        fields = [brate, b'ml/h']
        reply = self.execCommand(Command.rate, fields)
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

        self.__rxthread = RecvThread(comm = self)
        self.__txthread = SendThread(comm = self)

        self.__rxthread.start()
        self.__txthread.start()

    def allowNewCmd(self):
        try:
            self.cmdq.task_done()
        except ValueError as e:
            printerr("State machine got confused: {}", e)

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
    def __init__(self, comm):
        super().__init__(daemon=True)
        self.comm   = comm
        self.__buffer = b''

    def processRxBuffer(self):
        fields, _ = parseReply(self.__buffer)
        self.__buffer = b''
        reply = Reply(b' '.join(fields))
        self.comm.recvq.put(reply)
        self.comm.allowNewCmd()

    def run(self):
        insideCommand = False
        while True:
            c = self.comm.read(1)
            if c == b'\x1B':
                # Premature termination, b'\x1B' = ESC
                self.__buffer = b''
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

class Reply(object):
    __slots__ = ('value', 'error')
    def __init__(self, value = '', error = False):
        self.value = value
        self.error = error

    def __repr__(self):
        return "Alaris Reply: Value={}, Error={}".format(self.value, self.error)

class Command(Enum):
    getserialno = b'INST_SERIALNO'
    remotecfg   = b'REMOTE_CFG'
    remotectrl  = b'REMOTE_CTRL'
    queryvolume = b'INF_VI'
    rate        = b'INF_RATE'
    infstart    = b'INF_START'
    infstop     = b'INF_STOP'

# Errors
class Error(Enum):
    ETIMEOUT = auto()
    EUNDEF  = auto()
