"""
Base components for connecting model to view.
"""

class MVCEvent(object):
    """Abstract base class for events"""

    def __init__(self, subject: any) -> None:
        """The 'subject' is the object announcing the event"""
        self.subject = subject


class MVCObserver(object):
    """Abstract base class.
    Extend this and override the notify method.
    """

    def notify(self, MVCEvent) -> None:
        """Override this method in observers"""
        raise NotImplementedError("The notify method should be overridden in {}".format(self.__class__))

class MVCObservable(object):
    """A model object that a view object can observe."""

    def __init__(self):
        self.observers = [ ]

    def register_observer(self, observer: MVCObserver) -> None:
        self.observers.append(observer)

    def notify_all(self, event: MVCEvent) -> None:
        for observer in self.observers:
            observer.notify(event)

