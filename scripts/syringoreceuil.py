# vim: set fileencoding=utf-8 :

from PyQt4 import QtCore, QtGui

import infupy.backends.fresenius as fresenius
from infupy.gui.syringorecueil_ui import Ui_wndMain

import sys, time, csv

class DeviceWorker(QtCore.QObject):
    sigConnected      = QtCore.pyqtSignal()
    sigDisconnected   = QtCore.pyqtSignal()
    sigUpdateSyringes = QtCore.pyqtSignal(list)
    sigError          = QtCore.pyqtSignal(str)

    def __init__(self):
        super(DeviceWorker, self).__init__()
        self.port = ""
        self.conn = None
        self.base = None
        self.csvfd = None
        self.csv = None
        self.syringes = dict()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.loop)

    def setport(self, port):
        self.port = port

    def start(self):
        self.timer.start(5000) # 5 seconds

    def stop(self):
        self.timer.stop()

    def loop(self):
        if not self.checkCOMPort():
            if not self.tryCOMPort(): return
        if not self.checkBase():
            if not self.tryConnectBase(): return
        self.checkSyringes()
        self.findNewSyringes()

    def checkCOMPort(self):
        try:
            self.conn.name
        except Exception as e:
            self.reportError("Serial port exception: {}".format(e))
            self.conn = None
            return False
        else:
            return True

    def tryCOMPort(self):
        try:
            self.conn = fresenius.FreseniusComm(self.port)
        except Exception as e:
            self.onDisconnected()
            self.reportError("Failed to open COM port: {}".format(e))
            return False
        else:
            return True

    def checkBase(self):
        try:
            self.base.readDeviceType()
        except Exception as e:
            self.base = None
            self.onDisconnected()
            self.reportError("Lost base: {}".format(e))
            return False
        else:
            return True

    def tryConnectBase(self):
        try:
            self.base = fresenius.FreseniusBase(self.conn)
        except Exception as e:
            #self.reportError("Failed to connect to base: {}".format(e))
            return False
        else:
            sleep(1)
            self.onConnected()
            return True

    def checkSyringes(self):
        for i, s in self.syringes.iteritems():
            try:
                s.readDeviceType()
            except Exception as e:
                self.reportError("Lost syringe {}".format(i))
                del self.syringes[i]
            else:
                # Register the event in case the syringe got reset.
                # If the event was already registered, this is a no-op.
                s.registerEvent(fresenius.VarId.volume)

    def findNewSyringes(self):
        modids = self.base.listModules()
        self.sigUpdateSyringes.emit(modids)
        for modid in modids:
            if not modid in self.syringes.keys():
                s = fresenius.FreseniusSyringe(self.conn, modid)
                s.addCallback(self.cbLogValues)
                s.registerEvent(fresenius.VarId.volume)
                self.syringes[modid] = s

    def newFile(self):
        if self.csvfd is not None:
            self.csvfd.close()
        filename = time.strftime('%Y%m%d-%H%M.csv')
        self.csvfd = open(filename, 'w', newline='')
        self.csv = csv.DictWriter(self.csvfd, fieldnames = ['time', 'syringe', 'volume'])
        self.csv.writeheader()

    def cbLogValues(self, origin, msg):
        try:
            volume = fresenius.extractVolume(msg)
        except ValueError:
            self.reportError("Failed to decode volume value")
            return

        print("{}:{}".format(origin, volume))
        self.csv.writerow({'time'    : time.time(),
                           'syringe' : origin,
                           'volume'  : volume})

    def onConnected(self):
        self.sigConnected.emit()
        self.newFile()

    def onDisconnected(self):
        self.sigDisconnected.emit()
        if self.csvfd is not None:
            self.csvfd.close()
            self.csvfd = None

    def reportError(self, err):
        print(err)
        self.sigError.emit(str(err))


class MainUi(QtGui.QMainWindow, Ui_wndMain):
    def __init__(self, parent = None):
        super(MainUi, self).__init__(parent = parent)
        self.setupUi(self)

        # Init worker
        self.__workerthread = QtCore.QThread()
        self.__worker = DeviceWorker()

        # Worker callbacks and signals
        self.comboCom.editTextChanged.connect(self.__worker.setport)
        self.__worker.setport(self.comboCom.currentText())

        self.__worker.sigConnected.connect(self.connected)
        self.__worker.sigDisconnected.connect(self.disconnected)
        self.__worker.sigUpdateSyringes.connect(self.updateSyringeList)
        self.__worker.sigError.connect(self.showStatusError)

        self.__worker.moveToThread(self.__workerthread)
        self.__worker.start()


    def showStatusError(self, errstr):
        # Show for 2 seconds
        self.statusBar.showMessage("Error: {}".format(errstr), 2000)

    def connected(self):
        self.statusBar.setStyleSheet("QStatusBar{background : green;}")
        self.statusBar.showMessage("Connection ok")

    def disconnected(self):
        self.lstSyringes.clear()
        self.statusBar.setStyleSheet("QStatusBar{background : red;}")
        self.statusBar.showMessage("Disconnected")

    def updateSyringeList(self, slist):
        self.lstSyringes.clear()
        for modid in slist:
            liststr = "Seringue {}".format(modid)
            self.lstSyringes.addItem(liststr)


qApp = QtGui.QApplication(sys.argv)

wMain = MainUi()
wMain.show()

sys.exit(qApp.exec_())
