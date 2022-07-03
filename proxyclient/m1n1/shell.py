# SPDX-License-Identifier: MIT
import atexit, serial, os, struct, code, traceback, readline, rlcompleter, sys
import __main__
import builtins
import re

from .proxy import *
from .proxyutils import *
from .utils import *
from . import sysreg
from inspect import isfunction, signature

__all__ = ["ExitConsole", "run_shell"]

class HistoryConsole(code.InteractiveConsole):
    def __init__(self, locals=None, filename="<console>",
                 histfile=os.path.expanduser("~/.m1n1-history")):
        code.InteractiveConsole.__init__(self, locals, filename)
        self.histfile = histfile
        self.init_history(histfile)
        self.poll_func = None

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
        if self.poll_func:
            self.poll_func()
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
subcmd_list = {}
# Debug levels
DBL_NONE = 0
DBL_INFO = 1
DBL_TRACE = 2
DBL_DEBUG = 3
DBL_EDEBUG = 4

db_level = DBL_NONE

def debug_cmd(db=None):
    '''Set debug level to integer %d(none)...%d(extreme debug)''' % (DBL_NONE, DBL_EDEBUG)
    global db_level
    if db:
        db_level = db
    print("debug level=%d" % db_level)

def help_cmd(arg=None):
    if db_level >= DBL_DEBUG:
        print("arg=%s" % repr(arg))
    if arg:
        #cmd = arg.__qualname__
        if callable(arg):
            cmd = arg.__name__
        elif isinstance(arg, str):
            cmd = arg
        else:
            print("Unknown command: %s" % repr(arg))
            return
        if db_level >= DBL_DEBUG:
            print("cmd=%s" % repr(cmd))
        if cmd not in cmd_list:
            print("Undocumented command %s" % cmd)
            return
        hinfo = cmd_list[cmd]
        if isinstance(hinfo, str):
            print("%-10s : %s" % (cmd, hinfo))
            return
        if cmd in subcmd_list:
            clist = subcmd_list[cmd]
            aname = cmd
            if db_level >= DBL_DEBUG:
                print("subcmd_list[%s] = %s" %
                    (repr(cmd), repr(clist)))
        else:
            print("command %s is not documented" % cmd)
            return
    else:
        clist = cmd_list
        aname = 'top level'
        print("Note: To display a category's commands quote the name e.g. help('HV')")
    print("List of %s commands:" % aname)
    for cmd in clist.keys():
        hinfo = clist[cmd]
        if isinstance(hinfo, str):
            msg = hinfo.strip().split('\n', 1)[0]
        elif isinstance(hinfo, int):
            msg = "%s category - %d subcommands" % (cmd, hinfo)
        else:
            print("%s ?" % cmd)
            continue
        if len(cmd) <= 10:
            print("%-10s : %s" % (cmd, msg))
        else:
            print("%s:\n             %s" % (cmd, msg))

#locals is a dictionary for constructing the
# InteractiveConsole with. It adds in the callables
# in proxy utils iface and sysreg into locals
def run_shell(locals, msg=None, exitmsg=None, poll_func=None):
    saved_display = sys.displayhook
    try:
        def display(val):
            if isinstance(val, int) and not isinstance(val, bool):
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

        locals['help'] = help_cmd
        locals['debug'] = debug_cmd
        for obj_name in locals.keys():
            obj = locals.get(obj_name)
            if obj is None or obj_name.startswith('_'):
                continue
            if callable(obj) and not isinstance(obj, property):
                try:
                    desc = obj_name + str(signature(obj))
                except:
                    continue
                qn = obj.__qualname__
                if qn.find('.') > 0:
                    a = qn.split('.')
                    if a[0] not in subcmd_list:
                        subcmd_list[a[0]] = {}
                    if a[0] not in cmd_list:
                        cmd_list[a[0]] = 1
                    else:
                        cmd_list[a[0]] += 1
                    clist = subcmd_list[a[0]] 
                else:
                    clist = None
                if locals[obj_name].__doc__:
                    desc += " - " + locals[obj_name].__doc__
                    cmd_list[obj_name] = desc
                if isinstance(clist, dict):
                    clist[obj_name] = desc

        con = HistoryConsole(locals)
        con.poll_func = poll_func
        try:
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
