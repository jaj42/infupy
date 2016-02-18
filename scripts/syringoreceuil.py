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
        if self.conn is None:
            try:
                self.conn = fresenius.FreseniusComm(self.port)
            except:
                self.conn = None
                self.onDisconnected()
                return

        if self.base is None:
            try:
                self.base = fresenius.FreseniusBase(self.conn)
            except:
                self.onDisconnected()
                self.sigError.emit("Failed to connect to base")
            else:
                self.onConnected()

    def onConnected(self):
        self.sigConnected.emit()
        self.newFile()
        self.connectSyringes()

    def onDisconnected(self):
        self.sigDisconnected.emit()
        if self.csvfd is not None:
            self.csvfd.close()

    def connectSyringes(self):
        modids = self.base.listModules()
        self.sigUpdateSyringes.emit(modids)
        for modid in modids:
            if modid in syringes.keys():
                s = syringes[modid]
                try:
                    s.readDeviceType()
                except fresenius.CommandError:
                    s.connect()
                except fresenius.CommunicationError:
                    self.sigError.emit("Lost syringe {}".format(modid))
                    syringes.remove(modid)
                    continue
            else:
                s = fresenius.FreseniusSyringe(self.conn, modid)
                s.addCallback(self.cbLogValues)
                self.syringes[modid] = s
            # Always register the event in case the syringe got reset.
            # If the event was already registered, this is a no-op.
            s.registerEvent(fresenius.VarId.volume)

    def newFile(self):
        if self.csvfd is not None:
            self.csvfd.close()
        filename = time.strftime('%Y%m%d-%H%M.csv')
        self.csvfd = open(filename, 'w', newline='')
        self.csv = csv.DictWriter(self.csvfd, fieldnames = ['time', 'syringe', 'volume'])
        self.csv.writeheader()

    def cbLogValues(origin, msg):
        try:
            volume = fresenius.extractVolume(msg)
        except ValueError:
            return

        if origin is not None and origin.isdigit():
            syringe = int(origin)
        else:
            return

        #print("{}:{}".format(syringe, volume))
        self.csv.writerow({'time'    : time.time(),
                           'syringe' : syringe,
                           'volume'  : volume})


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
        self.statusBar.setStyleSheet("QStatusBar{background : orange;}")
        self.statusBar.showMessage("Erreur: {}".format(errstr))

    def connected(self):
        self.statusBar.setStyleSheet("QStatusBar{background : green;}")
        self.statusBar.showMessage("Connexion ok")

    def disconnected(self):
        self.lstSyringes.clear()
        self.statusBar.setStyleSheet("QStatusBar{background : red;}")
        self.statusBar.showMessage("DÃ©connectÃ©")

    def updateSyringeList(self, slist):
        self.lstSyringes.clear()
        for modid in slist:
            liststr = "Seringue {}".format(modid)
            self.lstSyringes.addItem(liststr)


qApp = QtGui.QApplication(sys.argv)

wMain = MainUi()
wMain.show()

sys.exit(qApp.exec_())
