#!/usr/bin/python

import atexit, serial, os, struct, code, traceback, readline, rlcompleter
from proxy import *
import __main__
import builtins

class HistoryConsole(code.InteractiveConsole):
    def __init__(self, locals=None, filename="<console>",
                 histfile=os.path.expanduser("~/.m1n1-history")):
        code.InteractiveConsole.__init__(self, locals, filename)
        self.init_history(histfile)

    def init_history(self, histfile):
        readline.parse_and_bind("tab: complete")
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(histfile)
            except FileNotFoundError:
                pass
            atexit.register(self.save_history, histfile)

    def save_history(self, histfile):
        readline.set_history_length(1000)
        readline.write_history_file(histfile)

    def showtraceback(self):
        type, value, tb = sys.exc_info()
        traceback.print_exception(type, value, tb)

saved_display = sys.displayhook

def display(val):
    global saved_display
    if isinstance(val, int) or isinstance(val, int):
        builtins._ = val
        print(hex(val))
    else:
        saved_display(val)

sys.displayhook = display

# convenience
h = hex

uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")
usbuart = serial.Serial(uartdev, 115200)

iface = UartInterface(usbuart, debug=False)
iface.nop()
proxy = M1N1Proxy(iface, debug=False)
proxy.nop()

locals = __main__.__dict__

for attr in dir(iface):
    locals[attr] = getattr(iface,attr)
for attr in dir(proxy):
    locals[attr] = getattr(proxy,attr)
del attr

from armutils import *
from tgtypes import *

base = proxy.get_base()
ba_addr = proxy.get_bootargs()
ba = iface.readstruct(ba_addr, BootArgs)

HistoryConsole(locals).interact("Have fun!")

