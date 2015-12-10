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
#ENQ = 'w'
#DC4 = 'v'
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
        # 3 Priorities defined: 0  -> keepalive,
        #                       5  -> reply to Base spontaneous message,
        #                       10 -> command to send
        self.txq = Queue.PriorityQueue()
        self.rxq = Queue.Queue()

        # Semaphore ensures that we wait for answers before sending new commands
        self.__sem = threading.Semaphore(value = 1)

        self.rxthread = RxThread(self, self.rxq, self.txq, self.__sem)
        self.rxthread.daemon = True

        self.txthread = TxThread(self, self.rxq, self.txq, self.__sem)
        self.txthread.daemon = True

        self.start()

    def start(self):
        self.rxthread.start()
        self.txthread.start()

    def stop(self):
        # XXX disconnect the proper syringes
        self.txthread.terminate()
        self.rxthread.terminate()

    def sendCommand(self, cmd):
        self.txq.put((10, cmd))

class RxThread(threading.Thread):
    def __init__(self, comm, rxq, txq, sem):
        super(RxThread, self).__init__()
        self.__comm = comm
        self.__rxq = rxq
        self.__txq = txq
        self.__sem = sem
        self.__terminate = False
        self.__buffer = ""

    def extractMessage(self, rxstr):
        # The checksum is in the last two bytes
        chk   = rxstr[-2:]
        rxstr = rxstr[:-2]
        # Partition the string
        splt   = rxstr.split(';')
        origin = splt[0]
        if len(splt) > 1:
            msg = splt[1]
        else:
            msg = None
        return (origin, msg, chk == genCheckSum(rxstr))

    def terminate(self):
        self.__terminate = True

    def enqueueTxBuffer(self, msg):
        self.__txq.put(msg)
        self.__sem.release()

    def enqueueRxBuffer(self):
        # XXX do actual error checking before sending ACK
        # XXX also handle error messages
        origin, msg, check = self.extractMessage(self.__buffer)
        self.__buffer = ""
        if not check:
            if DEBUG: print 'Sending NACK Wrong checksum: Origin: {}, Message: {}'.format(origin, msg)
            self.enqueueTxBuffer((0, NACK + '\x32'))
            self.__sem.release()
            return
        else:
            self.enqueueTxBuffer((0, ACK))

        if len(origin) == 0:
            pass
        elif origin[-1] == 'I':
            # Error condition
            if msg in ERRcmd:
                errmsg = ERRcmd[msg]
            else:
                errmsg = "Unknown Error"
            print "Commmand error: {}".format(errmsg)
        elif origin[-1] in ['E', 'M']:
            # We need to reply to spontaneously generated variables
            self.enqueueTxBuffer((5, origin))

        if msg is not None:
            self.__rxq.put((origin, msg))

        # We received the reply to the last command, allow to send one more
        self.__sem.release()

    def run(self):
        # We need to read byte by byte because ENQ/DC4 line monitoring
        # can happen any time and we need to reply quickly
        insideNACKerr = False
        insideCommand = False
        while not self.__terminate:
            c = self.__comm.read(1)
            if insideNACKerr:
                if c in ERRdata:
                    errmsg = ERRdata[c]
                else:
                    errmsg = "Unknown Error"
                print "Protocol error: {}".format(errmsg)
                self.__sem.release()
                insideNACKerr = False
            elif c == ENQ:
                self.enqueueTxBuffer((0, DC4))
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
                if c in CHROK
                    self.__buffer += c
                else:
                    if DEBUG: print "Sending NACK Control code in Command"
                    self.enqueueTxBuffer((0, NACK + '\x38'))
            else:
                if DEBUG: print "Sending NACK unknown char"
                self.enqueueTxBuffer((0, NACK + '\x31'))


class TxThread(threading.Thread):
    def __init__(self, comm, rxq, txq, sem):
        super(TxThread, self).__init__()
        self.__comm = comm
        self.__terminate = False
        self.__rxq = rxq
        self.__txq = txq
        self.__sem = sem

    def terminate(self):
        self.__terminate = True

    def run(self):
        while not self.__terminate:
            try:
                # The timeout ensures we can exit the thread
                prio, msg = self.__txq.get(timeout = 2)
            except Queue.Empty:
                continue
            # Priority 0 (important) messages are flow control and are sent raw (unframed)
            # Also they are sent first, which is why we have the priority queue
            self.__sem.acquire()
            if DEBUG:
                print "Semaphore: {}, TxQ: {}, RxQ: {}".format(self.__sem._Semaphore__value, self.__txq.qsize(), self.__rxq.qsize())
            if prio <= 0:
                self.__comm.write(msg)
            else:
                self.__comm.write(genFrame(msg))
