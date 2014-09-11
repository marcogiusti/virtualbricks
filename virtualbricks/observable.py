# Virtualbricks - a vde/qemu gui written in python and GTK/Glade.
# Copyright (C) 2013 Virtualbricks team

class Observable:

    def __init__(self, *names):
        self.__events = {}
        for name in names:
            self.add_event(name)

    def add_event(self, name):
        if name in self.__events:
            raise ValueError("Event %s already present" % name)
        self.__events[name] = []

    def add_observer(self, name, callback, args, kwds):
        if name not in self.__events:
            raise ValueError("Event %s not present" % name)
        if not callable(callback):
            raise TypeError("%r is not callable" % (callback, ))
        self.__events[name].append((callback, args, kwds))

    def remove_observer(self, name, callback, args, kwds):
        if name not in self.__events:
            raise ValueError("Event %s not present" % name)
        if not callable(callback):
            raise TypeError("%r is not callable" % (callback, ))
        self.__events[name].remove((callback, args, kwds))

    def notify(self, name, emitter):
        if name not in self.__events:
            raise ValueError("Event %s not present" % name)
        for callback, args, kwds in self.__events[name]:
            callback(emitter, *args, **kwds)

    def __len__(self):
        return len(self.__events)

    def __bool__(self):
        return bool(self.__events)


class Event:

    def __init__(self, observable, name):
        self.__observable = observable
        self.__name = name

    def connect(self, callback, *args, **kwds):
        if not callable(callback):
            raise TypeError("%r is not callable" % (callback, ))
        self.__observable.add_observer(self.__name, callback, args, kwds)

    def disconnect(self, callback, *args, **kwds):
        if not callable(callback):
            raise TypeError("%r is not callable" % (callback, ))
        self.__observable.remove_observer(self.__name, callback, (), {})
