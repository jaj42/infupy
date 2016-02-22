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
        wndMain.resize(377, 305)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(wndMain.sizePolicy().hasHeightForWidth())
        wndMain.setSizePolicy(sizePolicy)
        self.centralwidget = QtGui.QWidget(wndMain)
        self.centralwidget.setObjectName(_fromUtf8("centralwidget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.comboCom = QtGui.QComboBox(self.centralwidget)
        self.comboCom.setEditable(True)
        self.comboCom.setObjectName(_fromUtf8("comboCom"))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.comboCom.addItem(_fromUtf8(""))
        self.verticalLayout.addWidget(self.comboCom)
        self.groupBox = QtGui.QGroupBox(self.centralwidget)
        self.groupBox.setObjectName(_fromUtf8("groupBox"))
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.lstSyringes = QtGui.QListWidget(self.groupBox)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lstSyringes.sizePolicy().hasHeightForWidth())
        self.lstSyringes.setSizePolicy(sizePolicy)
        self.lstSyringes.setObjectName(_fromUtf8("lstSyringes"))
        self.verticalLayout_2.addWidget(self.lstSyringes)
        self.verticalLayout.addWidget(self.groupBox)
        wndMain.setCentralWidget(self.centralwidget)
        self.statusBar = QtGui.QStatusBar(wndMain)
        self.statusBar.setObjectName(_fromUtf8("statusBar"))
        wndMain.setStatusBar(self.statusBar)

        self.retranslateUi(wndMain)
        QtCore.QMetaObject.connectSlotsByName(wndMain)

    def retranslateUi(self, wndMain):
        wndMain.setWindowTitle(_translate("wndMain", "SyRe", None))
        self.comboCom.setItemText(0, _translate("wndMain", "COM1", None))
        self.comboCom.setItemText(1, _translate("wndMain", "COM2", None))
        self.comboCom.setItemText(2, _translate("wndMain", "COM3", None))
        self.comboCom.setItemText(3, _translate("wndMain", "COM4", None))
        self.comboCom.setItemText(4, _translate("wndMain", "COM5", None))
        self.comboCom.setItemText(5, _translate("wndMain", "COM6", None))
        self.comboCom.setItemText(6, _translate("wndMain", "COM7", None))
        self.comboCom.setItemText(7, _translate("wndMain", "/dev/ttyUSB0", None))
        self.comboCom.setItemText(8, _translate("wndMain", "/dev/ttyUSB1", None))
        self.groupBox.setTitle(_translate("wndMain", "Syringe Pumps", None))

