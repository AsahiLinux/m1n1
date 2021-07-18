# SPDX-License-Identifier: MIT
import atexit, serial, os, struct, code, traceback, readline, rlcompleter, sys
import __main__
import builtins
import re

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
cmd_list = {}

def help_cmd(arg=None):
    if arg:
        if not callable(arg):
            print("Unknown command: %s" % repr(arg))
            return
        cmd = arg.__name__
        if cmd not in cmd_list:
            print("Undocumented command %s" % cmd)
            return
        hinfo = cmd_list[cmd]
        print("%-10s : %s" % (cmd, hinfo))
        return
    print("List of Commands:")
    for cmd in cmd_list.keys():
        hinfo = cmd_list[cmd]
        if not hinfo:
            print("%s ?" % cmd)
        else:
            msg = hinfo.strip().split('\n', 1)[0]
            if len(cmd) <= 10:
                print("%-10s : %s" % (cmd, msg))
            else:
                print("%s:\n             %s" % (cmd, msg))
#locals is a dictionary for constructing the
# InteractiveConsole with. It adds in the callables
# in proxy utils iface and sysreg into locals
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
                    cmd = getattr(obj, attr)
                    locals[attr] = cmd

        for attr in dir(sysreg):
            locals[attr] = getattr(sysreg, attr)

        for obj_name in locals.keys():
            obj = locals.get(obj_name)
            if obj is None:
                continue
            if callable(obj) and not isinstance(obj, property):
                desc = locals[obj_name].__doc__
                if not desc:
                    desc = repr(locals[obj_name])
                    desc = re.sub("<bound method ", "", desc)
                    desc = re.sub(" object at 0x[0-9a-fA-F]*>>", "", desc)
                    desc = re.sub('<', '', desc)
                    b = re.split(' ', desc)
                    if len(b) == 3:
                        desc = ".".join([b[2], re.split('\.', b[0])[-1]])
                cmd_list[obj_name] = desc
        locals['help'] = help_cmd

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
