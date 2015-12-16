import threading
import fresenius
import readline
import time
import sys
from decimal import Decimal

logfile = open('seringues.log', 'w')
DOLOG = [False]
prompt = '> '

port = sys.argv[1]
fresbase = fresenius.FreseniusComm(port = port)

def printrx():
    while True:
        origin, msg = fresbase.recvq.get()
        print msg + "\n" + prompt,
        if DOLOG[-1]:
            logfile.write("{};{}\n".format(Decimal(time.time()), msg))

def queryloop():
    Ts = 5  # 2 Hz sample rate
    tbase = time.time()
    print DOLOG
    while DOLOG[-1]:
        tnew = time.time()
        if tnew - tbase > Ts:
            # d = flow rate, g = infused volume
            fresbase.sendCommand('1LE;dg')
            tbase = tnew

printthread = threading.Thread(target = printrx)
printthread.daemon = True
printthread.start()

querythread = threading.Thread(target = queryloop)
querythread.daemon = True

def startlogging():
    #fresbase.sendCommand('0DC')
    #fresbase.sendCommand('1DC')
    #fresbase.sendCommand('1DE;dg')
    DOLOG.append(True)
    querythread.start()

def stoplogging():
    DOLOG.append(False)
    fresbase.sendCommand('1AE')

while True:
    cmd = raw_input(prompt)
    if cmd == 'quit':
        break
    elif cmd == 'log':
        startlogging()
    elif cmd == 'stoplog':
        stoplogging()
    else:
        fresbase.sendCommand(cmd)

logfile.close()
fresbase.stop()
