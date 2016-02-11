# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'syringorecueil.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_wndMain(object):
    def setupUi(self, wndMain):
        wndMain.setObjectName(_fromUtf8("wndMain"))
        wndMain.resize(377, 388)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(wndMain.sizePolicy().hasHeightForWidth())
        wndMain.setSizePolicy(sizePolicy)
        self.centralwidget = QtGui.QWidget(wndMain)
        self.centralwidget.setObjectName(_fromUtf8("centralwidget"))
        self.groupBox = QtGui.QGroupBox(self.centralwidget)
        self.groupBox.setGeometry(QtCore.QRect(20, 60, 341, 151))
        self.groupBox.setObjectName(_fromUtf8("groupBox"))
        self.lstSyringes = QtGui.QListWidget(self.groupBox)
        self.lstSyringes.setGeometry(QtCore.QRect(10, 20, 321, 91))
        self.lstSyringes.setObjectName(_fromUtf8("lstSyringes"))
        self.btnSUpdate = QtGui.QPushButton(self.groupBox)
        self.btnSUpdate.setGeometry(QtCore.QRect(10, 120, 83, 24))
        self.btnSUpdate.setObjectName(_fromUtf8("btnSUpdate"))
        self.comboCom = QtGui.QComboBox(self.centralwidget)
        self.comboCom.setGeometry(QtCore.QRect(20, 20, 121, 22))
        self.comboCom.setEditable(True)
        self.comboCom.setObjectName(_fromUtf8("comboCom"))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.btnConnect = QtGui.QPushButton(self.centralwidget)
        self.btnConnect.setGeometry(QtCore.QRect(160, 20, 91, 24))
        self.btnConnect.setObjectName(_fromUtf8("btnConnect"))
        self.lblSpin = QtGui.QLabel(self.centralwidget)
        self.lblSpin.setGeometry(QtCore.QRect(340, 340, 16, 16))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lblSpin.sizePolicy().hasHeightForWidth())
        self.lblSpin.setSizePolicy(sizePolicy)
        self.lblSpin.setFrameShape(QtGui.QFrame.Box)
        self.lblSpin.setText(_fromUtf8(""))
        self.lblSpin.setObjectName(_fromUtf8("lblSpin"))
        self.btnStart = QtGui.QPushButton(self.centralwidget)
        self.btnStart.setGeometry(QtCore.QRect(20, 340, 83, 24))
        self.btnStart.setObjectName(_fromUtf8("btnStart"))
        self.btnStop = QtGui.QPushButton(self.centralwidget)
        self.btnStop.setGeometry(QtCore.QRect(120, 340, 83, 24))
        self.btnStop.setObjectName(_fromUtf8("btnStop"))
        self.groupBox_2 = QtGui.QGroupBox(self.centralwidget)
        self.groupBox_2.setGeometry(QtCore.QRect(20, 219, 341, 101))
        self.groupBox_2.setObjectName(_fromUtf8("groupBox_2"))
        self.listWidget = QtGui.QListWidget(self.groupBox_2)
        self.listWidget.setGeometry(QtCore.QRect(10, 20, 321, 71))
        self.listWidget.setObjectName(_fromUtf8("listWidget"))
        self.btnDisconnect = QtGui.QPushButton(self.centralwidget)
        self.btnDisconnect.setGeometry(QtCore.QRect(270, 20, 91, 24))
        self.btnDisconnect.setObjectName(_fromUtf8("btnDisconnect"))
        wndMain.setCentralWidget(self.centralwidget)
        self.statusBar = QtGui.QStatusBar(wndMain)
        self.statusBar.setObjectName(_fromUtf8("statusBar"))
        wndMain.setStatusBar(self.statusBar)

        self.retranslateUi(wndMain)
        QtCore.QMetaObject.connectSlotsByName(wndMain)

    def retranslateUi(self, wndMain):
        wndMain.setWindowTitle(_translate("wndMain", "SyringoReceuil", None))
        self.groupBox.setTitle(_translate("wndMain", "Seringues", None))
        self.btnSUpdate.setText(_translate("wndMain", "Update", None))
        self.comboCom.setItemText(0, _translate("wndMain", "COM1", None))
        self.comboCom.setItemText(1, _translate("wndMain", "COM2", None))
        self.comboCom.setItemText(2, _translate("wndMain", "COM3", None))
        self.comboCom.setItemText(3, _translate("wndMain", "COM4", None))
        self.btnConnect.setText(_translate("wndMain", "Connecter", None))
        self.btnStart.setText(_translate("wndMain", "Start", None))
        self.btnStop.setText(_translate("wndMain", "Stop", None))
        self.groupBox_2.setTitle(_translate("wndMain", "Tubes", None))
        self.btnDisconnect.setText(_translate("wndMain", "Deconnecter", None))

