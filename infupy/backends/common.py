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
        raise NotImplementedError

    # Read Perfusion related values
    @abstractmethod
    def readRate(self):
        raise NotImplementedError

    @abstractmethod
    def readVolume(self):
        raise NotImplementedError

    # Infusion control
    def setRate(self, rate):
        raise NotImplementedError

    # Events
    def registerEvent(self, event):
        self._events |= set([event])

    def unregisterEvent(self, event):
        self._events -= set([event])

    def clearEvents(self):
        self._events = set()
