# SPDX-License-Identifier: MIT
from ...utils import *

# System endpoints
def msg_handler(message, regtype=None):
    def f(x):
        x.is_message = True
        x.message = message
        x.regtype = regtype
        return x

    return f

class ASCMessage1(Register64):
    EP = 7, 0

class ASCTimeout(Exception):
    pass

class ASCBaseEndpoint:
    BASE_MESSAGE = Register64
    SHORT = None

    def __init__(self, asc, epnum, name=None):
        self.asc = asc
        self.epnum = epnum
        self.name = name or self.SHORT or f"{type(self).__name__}@{epnum:#x}"

        self.msghandler = {}
        self.msgtypes = {}
        for name in dir(self):
            i = getattr(self, name)
            if not callable(i):
                continue
            if not getattr(i, "is_message", False):
                continue
            self.msghandler[i.message] = i
            self.msgtypes[i.message] = i.regtype if i.regtype else self.BASE_MESSAGE

    def handle_msg(self, msg0, msg1):
        msg0 = self.BASE_MESSAGE(msg0)
        handler = self.msghandler.get(msg0.TYPE, None)
        regtype = self.msgtypes.get(msg0.TYPE, self.BASE_MESSAGE)

        if handler is None:
            return False
        return handler(regtype(msg0.value))

    def send(self, msg):
        self.asc.send(msg, ASCMessage1(EP=self.epnum))

    def start(self):
        pass

    def stop(self):
        pass

    def log(self, msg):
        print(f"[{self.name}] {msg}")
