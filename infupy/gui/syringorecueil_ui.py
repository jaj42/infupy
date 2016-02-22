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
        wndMain.resize(466, 468)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(wndMain.sizePolicy().hasHeightForWidth())
        wndMain.setSizePolicy(sizePolicy)
        self.centralwidget = QtGui.QWidget(wndMain)
        self.centralwidget.setObjectName(_fromUtf8("centralwidget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.groupBox_3 = QtGui.QGroupBox(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy)
        self.groupBox_3.setObjectName(_fromUtf8("groupBox_3"))
        self.verticalLayout_4 = QtGui.QVBoxLayout(self.groupBox_3)
        self.verticalLayout_4.setObjectName(_fromUtf8("verticalLayout_4"))
        self.comboCom = QtGui.QComboBox(self.groupBox_3)
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
        self.verticalLayout_4.addWidget(self.comboCom)
        self.verticalLayout.addWidget(self.groupBox_3)
        self.groupBox_2 = QtGui.QGroupBox(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setObjectName(_fromUtf8("groupBox_2"))
        self.verticalLayout_3 = QtGui.QVBoxLayout(self.groupBox_2)
        self.verticalLayout_3.setObjectName(_fromUtf8("verticalLayout_3"))
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.txtFolder = QtGui.QLineEdit(self.groupBox_2)
        self.txtFolder.setObjectName(_fromUtf8("txtFolder"))
        self.horizontalLayout.addWidget(self.txtFolder)
        self.btnBrowse = QtGui.QPushButton(self.groupBox_2)
        self.btnBrowse.setObjectName(_fromUtf8("btnBrowse"))
        self.horizontalLayout.addWidget(self.btnBrowse)
        self.verticalLayout_3.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.btnStart = QtGui.QPushButton(self.groupBox_2)
        self.btnStart.setObjectName(_fromUtf8("btnStart"))
        self.horizontalLayout_2.addWidget(self.btnStart)
        self.btnStop = QtGui.QPushButton(self.groupBox_2)
        self.btnStop.setObjectName(_fromUtf8("btnStop"))
        self.horizontalLayout_2.addWidget(self.btnStop)
        self.verticalLayout_3.addLayout(self.horizontalLayout_2)
        self.verticalLayout.addWidget(self.groupBox_2)
        self.groupBox = QtGui.QGroupBox(self.centralwidget)
        self.groupBox.setObjectName(_fromUtf8("groupBox"))
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.lstSyringes = QtGui.QListWidget(self.groupBox)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
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
        self.groupBox_3.setTitle(_translate("wndMain", "Serial Port", None))
        self.comboCom.setItemText(0, _translate("wndMain", "COM1", None))
        self.comboCom.setItemText(1, _translate("wndMain", "COM2", None))
        self.comboCom.setItemText(2, _translate("wndMain", "COM3", None))
        self.comboCom.setItemText(3, _translate("wndMain", "COM4", None))
        self.comboCom.setItemText(4, _translate("wndMain", "COM5", None))
        self.comboCom.setItemText(5, _translate("wndMain", "COM6", None))
        self.comboCom.setItemText(6, _translate("wndMain", "COM7", None))
        self.comboCom.setItemText(7, _translate("wndMain", "/dev/ttyUSB0", None))
        self.comboCom.setItemText(8, _translate("wndMain", "/dev/ttyUSB1", None))
        self.groupBox_2.setTitle(_translate("wndMain", "Destination Folder", None))
        self.btnBrowse.setText(_translate("wndMain", "Browse", None))
        self.btnStart.setText(_translate("wndMain", "Start", None))
        self.btnStop.setText(_translate("wndMain", "Stop", None))
        self.groupBox.setTitle(_translate("wndMain", "Syringe Pumps", None))

