import serial
import Queue
import threading

# Frame markers
STX = '\x02'
ETX = '\x03'

# Delivery control
ACK  = '\x06'
NACK = '\x15'

# Keep-alive
ENQ = '\x05'
DC4 = '\x14'

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
    '\x1E' : "The Communication with the Pilot is not open",
    '\x1F' : "The Communication with the Pilot is already open",
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
                                            stopbits = serial.STOPBITS_ONE,
                                            timeout  = 2)

class RxThread(threading.Thread):
    def __init__(self, comm):
        super(RxThread, self).__init__()
        self.__comm = comm
        self.queue = Queue.Queue()
        self.__terminate = False
        self.__buffer = ""

    def terminate(self):
        self.__terminate = True

    def enqueueBuffer(self):
        self.queue.put(self.__buffer)
        # XXX do actual error checking before sending ACK
        self.__comm.write(ACK)
        self.__buffer = ""

    def sendKeepAlive(self):
        self.__comm.write(DC4)

    def run(self):
        while not self.__terminate:
            # We need to read byte by byte because ENQ/DC4 line monitoring
            # can happen any time and we need to reply quickly
            c = self.__comm.read(1)
            if c == ENQ:
                self.sendKeepAlive()
                continue
            if c == ETX:
                self.enqueueBuffer()
                continue
            self.__buffer += c


class TxThread(threading.Thread):
    def __init__(self, comm):
        super(TxThread, self).__init__()
        self.__comm = comm
        self.__terminate = False
        self.queue = Queue.Queue()

    def terminate(self):
        self.__terminate = True

    def run(self):
        while not self.__terminate:
            try:
                msg = self.queue.get(timeout = 2)
            except Queue.Empty:
                continue
            self.__comm.write(genFrame(msg))


#message valid chars: 0x20 - 0x7E
#[STX]PR;1F4047[ETX]
# message: "PR;1F40"
# checksum: 47

# take ASCII hex value of each caracter
# sum of values
# 8 bits of the sum
# FF - this value
