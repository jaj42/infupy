import threading
import fresenius
import readline
import time
import sys

prompt = '> '

port = sys.argv[1]
fresbase = fresenius.FreseniusComm(port = port)

logfile = open('seringues.log', 'w')

def printrx():
    while not logfile.closed:
        origin, msg = fresbase.recvq.get()
        logfile.write("{};{}\n".format(time.time(), msg))
        print msg + "\n" + prompt,

def queryloop():
    Ts = 0.5  # 2 Hz sample rate
    tbase = time.time()
    while not logfile.closed:
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

if False:
    # Start querying for the flow
    fresbase.sendCommand('0DC')
    fresbase.sendCommand('1DC')
    fresbase.sendCommand('1DE;dg')
    querythread.start()

while True:
    cmd = raw_input(prompt)
    if cmd == 'quit': break
    fresbase.sendCommand(cmd)

logfile.close()
fresbase.stop()
