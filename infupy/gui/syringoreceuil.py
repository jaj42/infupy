from PyQt4 import QtGui
from PyQt4.QtCore import Qt

from infupy.gui.syringorecueil_ui import Ui_wndMain
import infupy.backends.fresenius as fresenius

import time,csv

class MainUi(QtGui.QMainWindow, Ui_wndMain):
    def __init__(self, parent=None):
        super(MainUi, self).__init__(parent=parent)
        self.setupUi(self)

        self.conn = None
        self.base = None
        self.syringes = []

        self.statusBar.showMessage('Déconnecté')

        # Connect callbacks
        self.btnConnect.clicked.connect(self.connect)
        self.btnDisconnect.clicked.connect(self.disconnect)
        self.btnStart.clicked.connect(self.start)
        self.btnStop.clicked.connect(self.stop)
        self.btnSUpdate.clicked.connect(self.updatelist)

    def connect(self):
        port = self.comboCom.currentText()
        try:
            self.conn = fresenius.FreseniusComm(port)
            self.base = fresenius.FreseniusBase(self.conn)
        except:
            self.conn = None
            self.statusBar.setStyleSheet("QStatusBar{background : red;}")
            self.statusBar.showMessage('Erreur de connexion')
        else:
            self.statusBar.setStyleSheet("QStatusBar{background : green;}")
            self.statusBar.showMessage('Connexion ok')
            self.filename = time.strftime('%Y%m%d-%H%M.csv')
            self.file = open(self.filename, 'w', newline='')
            self.csv = csv.DictWriter(self.file, fieldnames = ['time', 'syringe', 'volume'])
            self.csv.writeheader()
            self.updatelist()

    def disconnect(self):
        self.syringes = []
        self.base = None
        time.sleep(1)
        self.file.close()
        self.conn.close()
        self.conn = None
        self.statusBar.setStyleSheet("QStatusBar{background:None;}") 
        self.statusBar.showMessage('Déconnecté')

    def updatelist(self):
        def logValues(origin, msg):
            try:
                volume = fresenius.extractVolume(msg)
            except ValueError:
                volume = 0
            if origin is not None and origin.isdigit():
                syringe = int(origin)
            else:
                syringe = 0
            print("{}:{}".format(syringe, volume))
            self.csv.writerow({'time'    : time.time(),
                               'syringe' : syringe,
                               'volume'  : volume})

        self.syringes = []
        self.lstSyringes.clear()
        if self.base is None: return
        modids = self.base.listModules()
        for modid in modids:
            s = fresenius.FreseniusSyringe(self.conn, modid)
            s.addCallback(logValues)
            self.syringes.append(s)
            #drugname = s.readDrug()
            liststr = "Seringue {}".format(modid)
            self.lstSyringes.addItem(liststr)

    def start(self):
        for s in self.syringes:
            s.registerEvent(fresenius.VarId.volume)

    def stop(self):
        for s in self.syringes:
            s.clearEvents()
