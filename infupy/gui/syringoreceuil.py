from PyQt4 import QtGui
from PyQt4.QtCore import Qt

from infupy.gui.syringorecueil_ui import Ui_wndMain

import infupy.backends.fresenius as fresenius

import time

def printValues(origin, msg):
    vals = fresenius.parseVars(msg)
    print("{}:{}".format(origin, vals))

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

    def disconnect(self):
        self.syringes = []
        self.base = None
        self.statusBar.setStyleSheet("QStatusBar{background:None;}") 
        self.statusBar.showMessage('Déconnecté')

    def connect(self):
        port = self.comboCom.currentText()
        try:
            self.conn = fresenius.FreseniusComm(port)
            self.base = fresenius.FreseniusBase(self.conn)
            self.statusBar.setStyleSheet("QStatusBar{background:green;}") 
            self.statusBar.showMessage('Connexion ok')
        except:
            self.conn = None
            self.statusBar.setStyleSheet("QStatusBar{background:red;}") 
            self.statusBar.showMessage('Erreur de connexion')

    def updatelist(self):
        self.syringes = []
        self.lstSyringes.clear()
        if self.base is None: return
        modids = self.base.listModules()
        for modid in modids:
            s = fresenius.FreseniusSyringe(self.conn, modid)
            s.addCallback(printValues)
            self.syringes.append(s)
            drugname = s.readDrug()
            liststr = "Seringue {} ({})".format(modid, drugname)
            self.lstSyringes.addItem(liststr)

    def start(self):
        for s in self.syringes:
            s.registerEvent(fresenius.VarId.volume)

    def stop(self):
        for s in self.syringes:
            s.clearEvents()
