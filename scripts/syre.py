import sys, time, csv, io, queue

from PyQt4 import QtCore, QtGui

import infupy.backends.fresenius as fresenius
from infupy.gui.syringorecueil_ui import Ui_wndMain

class Worker(QtCore.QObject):
    sigConnected      = QtCore.pyqtSignal()
    sigDisconnected   = QtCore.pyqtSignal()
    sigUpdateSyringes = QtCore.pyqtSignal(list)
    sigError          = QtCore.pyqtSignal(str)

    def __init__(self):
        super(Worker, self).__init__()
        self.port = ""
        self.conn = None
        self.base = None
        self.logger = None
        self.syringes = dict()
        self.csvfd = io.IOBase() # ensure close() method is present.
        self.csv = None

        self.conntimer = QtCore.QTimer()
        self.conntimer.timeout.connect(self.connectionLoop)

        self.logtimer = QtCore.QTimer()
        self.logtimer.timeout.connect(self.logLoop)

    def start(self):
        self.conntimer.start(5000) # 5 seconds

    def stop(self):
        self.conntimer.stop()

    def setport(self, port):
        self.port = port

    def connectionLoop(self):
        if not self.checkSerial(): self.connectSerial()
        if not self.checkBase():
            self.onDisconnected()
            if self.connectBase():
                self.onConnected()
            else:
                return
        self.checkSyringes()
        self.attachNewSyringes()

    def logLoop(self):
        try: # Ensure file is open and writable.
            if not self.csvfd.writable():
                raise IOError
        except IOError:
            return

        while True: # Dump the whole queue to csv
            try:
                timestamp, origin, msg = self.conn.eventq.get_nowait()
            except queue.Empty:
                break

            try:
                volume = fresenius.extractVolume(msg)
            except ValueError:
                self.reportError("Failed to decode volume value")
                continue

            print("{}:{}".format(origin, volume))
            self.csv.writerow({'datetime' : timestamp,
                               'syringe'  : origin,
                               'volume'   : volume})

    def onConnected(self):
        self.sigConnected.emit()
        filename = time.strftime('%Y%m%d-%H%M.csv')
        self.csvfd = open(filename, 'w', newline='')
        self.csv = csv.DictWriter(self.csvfd, fieldnames = ['datetime', 'syringe', 'volume'])
        self.csv.writeheader()
        self.logtimer.start(1000) # 1 seconds

    def onDisconnected(self):
        self.sigDisconnected.emit()
        self.logtimer.stop()
        self.logLoop() # Call once more to empty the queue.
        self.csvfd.close()

    def checkSyringes(self):
        for i, s in self.syringes.iteritems():
            try:
                s.readDeviceType()
            except Exception as e:
                self.reportError("Syringe {} error: {}".format(i, e))
                del self.syringes[i]
            else:
                # Register volume event in case the syringe got reset.
                # If the event was already registered, this is a no-op.
                s.registerEvent(fresenius.VarId.volume)

    def attachNewSyringes(self):
        modids = self.base.listModules()
        self.sigUpdateSyringes.emit(modids)
        for modid in modids:
            if not modid in self.syringes.keys():
                s = fresenius.FreseniusSyringe(self.conn, modid)
                s.registerEvent(fresenius.VarId.volume)
                self.syringes[modid] = s

    def checkSerial(self):
        try:
            self.conn.name
        except Exception as e:
            self.reportError("Serial port exception: {}".format(e))
            return False
        else:
            return True

    def connectSerial(self):
        try:
            self.conn = fresenius.FreseniusComm(self.port)
        except Exception as e:
            self.reportError("Failed to open serial port: {}".format(e))
            return False
        else:
            return True

    def checkBase(self):
        try:
            self.base.readDeviceType()
        except Exception as e:
            self.reportError("Base error: {}".format(e))
            return False
        else:
            return True

    def connectBase(self):
        try:
            self.base = fresenius.FreseniusBase(self.conn)
        except Exception as e:
            self.reportError("Failed to connect to base: {}".format(e))
            return False
        else:
            return True

    def reportError(self, err):
        print(err)
        self.sigError.emit(str(err))


class MainUi(QtGui.QMainWindow, Ui_wndMain):
    def __init__(self, parent = None):
        super(MainUi, self).__init__(parent = parent)
        self.setupUi(self)

        # Add Connection label to statusbar
        self.connStatusLabel = QtGui.QLabel()
        self.connStatusLabel.setMargin(2)
        self.statusBar.addPermanentWidget(self.connStatusLabel)

        # Init worker
        self.__workerthread = QtCore.QThread()
        self.__worker = Worker()

        # Worker callbacks and signals
        self.comboCom.editTextChanged.connect(self.__worker.setport)
        self.__worker.setport(self.comboCom.currentText())

        self.__worker.sigConnected.connect(self.connected)
        self.__worker.sigDisconnected.connect(self.disconnected)
        self.__worker.sigUpdateSyringes.connect(self.updateSyringeList)
        self.__worker.sigError.connect(self.showStatusError)

        self.__worker.moveToThread(self.__workerthread)
        self.__workerthread.start()
        self.__worker.start()

    def showStatusError(self, errstr):
        # Show for 3 seconds
        self.statusBar.showMessage(errstr, 3000)

    def connected(self):
        self.connStatusLabel.setStyleSheet("QLabel{background : green;}")
        self.connStatusLabel.setText("Connected")

    def disconnected(self):
        self.lstSyringes.clear()
        self.connStatusLabel.setStyleSheet("QLabel{background : red;}")
        self.connStatusLabel.setText("Disconnected")

    def updateSyringeList(self, slist):
        self.lstSyringes.clear()
        for modid in slist:
            liststr = "Seringue {}".format(modid)
            self.lstSyringes.addItem(liststr)


if __name__ == '__main__':
    qApp = QtGui.QApplication(sys.argv)

    wMain = MainUi()
    wMain.show()

    sys.exit(qApp.exec_())
