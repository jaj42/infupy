import sys, os.path, time, csv, io, queue

from PyQt4 import QtCore, QtGui

import infupy.backends.fresenius as fresenius
from infupy.gui.syringorecueil_ui import Ui_wndMain

DEBUG = True

class Worker(QtCore.QObject):
    sigConnected      = QtCore.pyqtSignal()
    sigDisconnected   = QtCore.pyqtSignal()
    sigUpdateSyringes = QtCore.pyqtSignal(list)
    sigError          = QtCore.pyqtSignal(str)

    def __init__(self):
        super(Worker, self).__init__()
        self.destfolder = os.path.expanduser("~")
        self.port = ""
        self.conn = None
        self.base = None
        self.logger = None
        self.syringes = dict()
        self.csvfd = io.IOBase()
        self.csv = None
        self.shouldrun = False

        self.conntimer = QtCore.QTimer()
        self.conntimer.timeout.connect(self.connectionLoop)

        self.logtimer = QtCore.QTimer()
        self.logtimer.timeout.connect(self.logLoop)

        self.conntimer.start(5000) # 5 seconds

    @QtCore.pyqtSlot()
    def start(self):
        self.shouldrun = True

    @QtCore.pyqtSlot()
    def stop(self):
        self.shouldrun = False

    @QtCore.pyqtSlot(str)
    def setport(self, port):
        self.port = port

    @QtCore.pyqtSlot(str)
    def setfolder(self, folder):
        self.destfolder = folder

    def connectionLoop(self):
        if not self.shouldrun:
            self.onDisconnected()
            return

        if not self.checkSerial():
            self.connectSerial()
        if not self.checkBase():
            if self.connectBase():
                self.onConnected()
            else:
                self.onDisconnected()
                return
        self.checkSyringes()
        self.attachNewSyringes()

    def logLoop(self):
        try: # Ensure file is open and writable.
            if not self.csvfd.writable():
                raise IOError("Not writable")
        except (IOError, ValueError) as e:
            if self.shouldrun:
                self.reportUI("File: {}".format(e))
            return

        while True: # Dump the whole queue to csv
            try:
                timestamp, origin, msg = self.conn.eventq.get_nowait()
            except queue.Empty:
                break

            try:
                volume = fresenius.extractVolume(msg)
            except ValueError:
                self.reportUI("Failed to decode volume value")
                continue

            if DEBUG: print("{}:{}:{}".format(timestamp, origin, volume), file=sys.stderr)
            self.csv.writerow({'datetime' : timestamp,
                               'syringe'  : origin,
                               'volume'   : volume})

    def onConnected(self):
        self.sigConnected.emit()
        filename = time.strftime('%Y%m%d-%H%M.csv')
        filepath = os.path.join(self.destfolder, filename)
        if not self.csvfd.writable():
            self.csvfd.close()
            self.csvfd = open(filepath, 'w', newline='')
            self.reportUI("Opened file: {}".format(filepath))
            self.csv = csv.DictWriter(self.csvfd, fieldnames = ['datetime', 'syringe', 'volume'])
            self.csv.writeheader()
        self.logtimer.start(1000) # 1 second

    def onDisconnected(self):
        self.sigDisconnected.emit()
        # Clean up
        self.syringes = dict()
        self.base = None
        self.sigUpdateSyringes.emit([])
        # Stop csv logging
        self.logtimer.stop()
        self.logLoop() # Call once more to empty the queue.
        if not self.shouldrun:
            self.csvfd.close()
            self.reportUI("Closed file: {}".format(filepath))

    def checkSyringes(self):
        for i, s in self.syringes.copy().items():
            try:
                dtype = s.readDeviceType()
                if DEBUG: print("Device: {}".format(dtype), file=sys.stderr)
            except Exception as e:
                self.reportUI("Syringe {} error: {}".format(i, e))
                del self.syringes[i]
            else:
                # Register volume event in case the syringe got reset.
                # If the event was already registered, this is a no-op.
                s.registerEvent(fresenius.VarId.volume)

    def attachNewSyringes(self):
        try:
            modids = self.base.listModules()
            self.sigUpdateSyringes.emit(modids)
            for modid in modids:
                if not modid in self.syringes.keys():
                    s = fresenius.FreseniusSyringe(self.conn, modid)
                    s.registerEvent(fresenius.VarId.volume)
                    self.syringes[modid] = s
        except fresenius.CommunicationError as e:
            self.reportUI("Attach syringe error: {}".format(e))

    def checkSerial(self):
        try:
            self.conn.name
        except Exception as e:
            self.reportUI("Serial port exception: {}".format(e))
            return False
        else:
            return True

    def connectSerial(self):
        try:
            self.conn = fresenius.FreseniusComm(self.port)
        except Exception as e:
            self.reportUI("Failed to open serial port: {}".format(e))
            return False
        else:
            return True

    def checkBase(self):
        try:
            dtype = self.base.readDeviceType()
            if DEBUG: print("Device: {}".format(dtype), file=sys.stderr)
        except Exception as e:
            self.reportUI("Base error: {}".format(e))
            return False
        else:
            return True

    def connectBase(self):
        try:
            self.base = fresenius.FreseniusBase(self.conn)
        except Exception as e:
            self.reportUI("Failed to connect to base: {}".format(e))
            return False
        else:
            return True

    def reportUI(self, err):
        if DEBUG: print(err, file=sys.stderr)
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

        # Continue UI initialization
        self.txtFolder.textChanged.connect(self.__worker.setfolder)
        self.btnBrowse.clicked.connect(self.browsefolder)
        self.btnStart.clicked.connect(self.__worker.start)
        self.btnStop.clicked.connect(self.__worker.stop)

    def browsefolder(self):
        destfolder = QtGui.QFileDialog.getExistingDirectory(self, "Choose destination Folder")
        self.txtFolder.setText(destfolder)

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
