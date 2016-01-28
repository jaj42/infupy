class CommunicationError(Exception):
    def __str__(self):
        return "Communication error. Reason: {}".format(self.args)

class CommandError(Exception):
    def __str__(self):
        return "Command error. {}".format(self.args)

class Syringe():
    _events = set()

    def __init__(self):
        pass

    def execRawCommand(self, msg):
        """
        Send command and read reply.
        """
        pass

    # Read Perfusion related values
    def readRate(self):
        return 0

    def readVolume(self):
        return 0

    # Infusion control
    def setRate(self, rate):
        pass

    def bolus(self, volume, rate):
        pass

    # Events
    def registerEvent(self, event):
        self._events |= set([event])

    def unregisterEvent(self, event):
        self._events -= set([event])

    def clearEvents(self):
        self._events = set()
