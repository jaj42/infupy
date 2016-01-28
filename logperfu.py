import fresenius

import time
#from decimal import Decimal

def printSpont(origin, msg):
	print("{}:{}".format(origin, msg))

c = fresenius.FreseniusComm('/dev/ttyUSB0')
b = fresenius.FreseniusBase(c)
time.sleep(1)

syringes = []
modids = b.listModules()
print(modids)
for modid in modids:
	s = fresenius.FreseniusSyringe(c, modid)
	syringes.append(s)
	print(s.execCommand(fresenius.Command.setdrug, args=[b'Noradrenaline']))
	print(s.execCommand(fresenius.Command.readdrug))
	print(s.execCommand(fresenius.Command.readvar, flags=[fresenius.VarId.volume]))
	print(s.execCommand(fresenius.Command.showdrug))

time.sleep(1)
b.disconnect()
