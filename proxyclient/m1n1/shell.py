# SPDX-License-Identifier: MIT
import atexit, serial, os, struct, code, traceback, readline, rlcompleter, sys
import __main__
import builtins

from .proxy import *
from .proxyutils import *
from .utils import *
from . import sysreg

__all__ = ["ExitConsole", "run_shell"]

class HistoryConsole(code.InteractiveConsole):
    def __init__(self, locals=None, filename="<console>",
                 histfile=os.path.expanduser("~/.m1n1-history")):
        code.InteractiveConsole.__init__(self, locals, filename)
        self.histfile = histfile
        self.init_history(histfile)

    def init_history(self, histfile):
        readline.parse_and_bind("tab: complete")
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(histfile)
            except FileNotFoundError:
                pass

    def save_history(self):
        readline.set_history_length(10000)
        readline.write_history_file(self.histfile)

    def showtraceback(self):
        type, value, tb = sys.exc_info()
        traceback.print_exception(type, value, tb)

    def runcode(self, code):
        super().runcode(code)
        if "mon" in self.locals:
            try:
                self.locals["mon"].poll()
            except Exception as e:
                print(f"mon.poll() failed: {e!r}")
        if "u" in self.locals:
            self.locals["u"].push_simd()


class ExitConsole(SystemExit):
    pass

def run_shell(locals, msg=None, exitmsg=None):
    saved_display = sys.displayhook
    try:
        def display(val):
            if isinstance(val, int):
                builtins._ = val
                print(hex(val))
            elif callable(val):
                val()
            else:
                saved_display(val)

        sys.displayhook = display

        # convenience
        locals["h"] = hex
        locals["sysreg"] = sysreg

        if "proxy" in locals and "p" not in locals:
            locals["p"] = locals["proxy"]
        if "utils" in locals and "u" not in locals:
            locals["u"] = locals["utils"]

        for obj_name in ("iface", "p", "u"):
            obj = locals.get(obj_name)
            obj_class = type(obj)
            if obj is None:
                continue

            for attr in dir(obj_class):
                if attr in locals or attr.startswith('_'):
                    continue

                member = getattr(obj_class, attr)
                if callable(member) and not isinstance(member, property):
                    locals[attr] = getattr(obj, attr)

        for attr in dir(sysreg):
            locals[attr] = getattr(sysreg, attr)

        try:
            con = HistoryConsole(locals)
            con.interact(msg, exitmsg)
        except ExitConsole as e:
            if len(e.args):
                return e.args[0]
            else:
                return
        finally:
            con.save_history()

    finally:
        sys.displayhook = saved_display

if __name__ == "__main__":
    from .setup import *
    locals = dict(__main__.__dict__)

    run_shell(locals, msg="Have fun!")
