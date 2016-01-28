import sys
from PyQt4 import QtCore, QtGui

from infupy.backends.fresenius import *
import infupy.gui.syringoreceuil as gui

qApp = QtGui.QApplication(sys.argv)

wMain = gui.MainUi()
wMain.show()

sys.exit(qApp.exec_())
