import fresenius

import threading
import time
import sys
from decimal import Decimal

#fresbase.sendCommand('0DC')
#fresbase.sendCommand('1DC')
#fresbase.sendCommand('1DE;dg')
#fresbase.sendCommand('1AE')

logfile = open('seringues.log', 'w')
DOLOG = [False]
prompt = '> '

port = sys.argv[1]
fresbase = fresenius.FreseniusComm(port = port)

def printrx():
    while True:
        origin, msg = fresbase.recvOne()
        print("{}:{}\n{}".format(origin, msg, prompt))
        print(prompt)
        if DOLOG[-1]:
            logfile.write("{}:{}:{}\n".format(Decimal(time.time()), origin, msg))

def queryloop():
    Ts = .15
    tbase = time.time()
    while True:
        tnew = time.time()
        if tnew - tbase > Ts:
            # d = flow rate, r = infused volume
            fresbase.sendCommand('1LE;dr')
            tbase = tnew
            time.sleep(Ts / 4)

printthread = threading.Thread(target = printrx)
printthread.daemon = True
printthread.start()

querythread = threading.Thread(target = queryloop)
querythread.daemon = True
#querythread.start()

def startlogging():
    DOLOG.append(True)

def stoplogging():
    DOLOG.append(False)

while True:
    cmd = raw_input(prompt)
    if cmd == 'quit':
        break
    elif cmd == 'startlog':
        startlogging()
    elif cmd == 'stoplog':
        stoplogging()
    elif cmd == 'genvar':
        fresbase.sendCommand('1DE;r')
        fresbase.sendCommand('2DE;r')
    elif cmd == 'novar':
        fresbase.sendCommand('1AE')
        fresbase.sendCommand('2AE')
    elif cmd == 'qloop':
        querythread.start()
    elif cmd == 'qlen':
        print(fresbase.cmdq.qsize())
    elif cmd == 'fastloop':
        for i in range(100): fresbase.sendCommand('1LE;d')
    else:
        fresbase.sendCommand(cmd)

fresbase.sendCommand('1FC')
fresbase.sendCommand('0FC')

logfile.close()
