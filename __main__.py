import threading
import fresenius
import readline

comm = fresenius.FreseniusComm(port = "/dev/ttyp2")
rx = fresenius.RxThread(comm)
tx = fresenius.TxThread(comm)

rx.start()
tx.start()

def printRx():
    while True:
        print rx.queue.get()

printthread = threading.Thread(target = printRx)
printthread.daemon = True
printthread.start()

while True:
    cmd = raw_input('> ')
    if cmd == 'quit': break
    tx.queue.put(cmd)

print 'Waiting for Rx to terminate'
rx.terminate()
rx.join()
print 'Waiting for Tx to terminate'
tx.terminate()
tx.join()
