# vim: set fileencoding=utf-8 :

from PyQt4 import QtCore, QtGui

import infupy.backends.fresenius as fresenius
from infupy.gui.syringorecueil_ui import Ui_wndMain

import sys, time, csv, io, threading

# In addition to the GUI, two threads are running.
# - A device connection thread, checking the connection to the base and
#   the syringes every 5 seconds.
# - A logger thread, reading the event queue every 1 second and logging
#   perfused volumes to the csv file.

class LogWorker(QtCore.QObject):
    def __init__(self, eventq):
        self.eventq = eventq
        self.flock = threading.Lock()
        self.csvfd = io.IOBase() # ensure close() method is present.
        self.csv = None

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.loop)

    def __del__(self):
        self.stop()

    def start(self):
        with flock:
            filename = time.strftime('%Y%m%d-%H%M.csv')
            self.csvfd = open(filename, 'w', newline='')
            self.csv = csv.DictWriter(self.csvfd, fieldnames = ['datetime', 'syringe', 'volume'])
            self.csv.writeheader()
        self.timer.start(1000) # 1 seconds

    def stop(self):
        self.timer.stop()
        self.loop() # Run once more to empty queue.
        with self.flock:
            self.csvfd.close()

    def loop(self):
        try: # Ensure file is open and writable.
            if not self.csvfd.writable():
                raise IOError
        except IOError:
            return

        with self.flock:
            while True:
                try:
                    timestamp, origin, msg = self.eventq.get_nowait()
                except queue.Empty:
                    break

                try:
                    volume = fresenius.extractVolume(msg)
                except ValueError:
                    print("Failed to decode volume value")
                    continue

                print("{}:{}".format(origin, volume))
                self.csv.writerow({'datetime' : timestamp,
                                   'syringe'  : origin,
                                   'volume'   : volume})


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
        self.logger = None
        self.syringes = dict()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.loop)

    def start(self):
        self.timer.start(5000) # 5 seconds

    def stop(self):
        self.timer.stop()

    def setport(self, port):
        self.port = port

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
            self.reportError("Failed to connect to base: {}".format(e))
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
                s.registerEvent(fresenius.VarId.volume)
                self.syringes[modid] = s

    def onConnected(self):
        self.sigConnected.emit()
        self.logger = LogWorker(self.conn.eventq)

    def onDisconnected(self):
        self.sigDisconnected.emit()
        try:
            self.logger.stop()
        except AttributeError:
            pass

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
