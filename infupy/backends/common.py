import sys
from abc import ABCMeta, abstractmethod

def printerr(msg, e=''):
    msg = "Backend: " + str(msg)
    print(msg.format(e), file=sys.stderr)

class CommandError(Exception):
    def __str__(self):
        return "Command error: {}".format(self.args)

class Syringe(metaclass=ABCMeta):
    _events = set()

    @abstractmethod
    def execCommand(self, msg):
        """
        Send command and read reply.
        """
        pass

    # Read Perfusion related values
    @abstractmethod
    def readRate(self):
        return 0

    @abstractmethod
    def readVolume(self):
        return 0

    # Infusion control
    def setRate(self, rate):
        pass

    # Events
    def registerEvent(self, event):
        self._events |= set([event])

    def unregisterEvent(self, event):
        self._events -= set([event])

    def clearEvents(self):
        self._events = set()
