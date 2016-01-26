class Syringe():
    _callbacks = []
    _comm = None

    def __init__(self, comm):
        self._comm = comm

    def execRawCommand(self, msg):
        """
        Send command and read reply.
        """
        pass

    # Read Perfusion related values
    def readRate(self):
        pass

    def readVolume(self):
        pass

    # Infusion control
    def setRate(self, rate):
        pass

    def bolus(self, volume, rate):
        pass

    # Events
    def registerEvent(self, event):
        pass

    def addCallback(self, func):
        self.callbacks.append(func)
