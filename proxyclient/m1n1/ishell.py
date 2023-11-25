# SPDX-License-Identifier: MIT
import builtins
import sys

import __main__
from IPython import embed
from traitlets.config import get_config

c = get_config()
c.InteractiveShellEmbed.colors = "Linux"
from inspect import signature

from . import sysreg
from .proxy import *
from .proxyutils import *
from .utils import *

__all__ = ["run_ishell"]


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
    """Set debug level to integer %d(none)...%d(extreme debug)""" % (
        DBL_NONE,
        DBL_EDEBUG,
    )
    global db_level
    if db:
        db_level = db
    print("debug level=%d" % db_level)


def help_cmd(arg=None):
    if db_level >= DBL_DEBUG:
        print("arg=%s" % repr(arg))
    if arg:
        # cmd = arg.__qualname__
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
                print("subcmd_list[%s] = %s" % (repr(cmd), repr(clist)))
        else:
            print("command %s is not documented" % cmd)
            return
    else:
        clist = cmd_list
        aname = "top level"
        print("Note: To display a category's commands quote the name e.g. help('HV')")
    print("List of %s commands:" % aname)
    for cmd in clist.keys():
        hinfo = clist[cmd]
        if isinstance(hinfo, str):
            msg = hinfo.strip().split("\n", 1)[0]
        elif isinstance(hinfo, int):
            msg = "%s category - %d subcommands" % (cmd, hinfo)
        else:
            print("%s ?" % cmd)
            continue
        if len(cmd) <= 10:
            print("%-10s : %s" % (cmd, msg))
        else:
            print("%s:\n             %s" % (cmd, msg))


# commands is a dictionary for constructing the
# InteractiveConsole with. It adds in the callables
# in proxy utils iface and sysreg into commands
def run_ishell(commands, msg=""):
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
        commands["h"] = hex
        commands["sysreg"] = sysreg

        if "proxy" in commands and "p" not in commands:
            commands["p"] = commands["proxy"]
        if "utils" in commands and "u" not in commands:
            commands["u"] = commands["utils"]

        for obj_name in ("iface", "p", "u"):
            obj = commands.get(obj_name)
            obj_class = type(obj)
            if obj is None:
                continue

            for attr in dir(obj_class):
                if attr in commands or attr.startswith("_"):
                    continue

                member = getattr(obj_class, attr)
                if callable(member) and not isinstance(member, property):
                    cmd = getattr(obj, attr)
                    commands[attr] = cmd

        for attr in dir(sysreg):
            commands[attr] = getattr(sysreg, attr)

        commands["help"] = help_cmd
        commands["debug"] = debug_cmd
        for obj_name in commands.keys():
            obj = commands.get(obj_name)
            if obj is None or obj_name.startswith("_"):
                continue
            if callable(obj) and not isinstance(obj, property):
                try:
                    desc = obj_name + str(signature(obj))
                except:
                    continue
                qn = obj.__qualname__
                if qn.find(".") > 0:
                    a = qn.split(".")
                    if a[0] not in subcmd_list:
                        subcmd_list[a[0]] = {}
                    if a[0] not in cmd_list:
                        cmd_list[a[0]] = 1
                    else:
                        cmd_list[a[0]] += 1
                    clist = subcmd_list[a[0]]
                else:
                    clist = None
                if commands[obj_name].__doc__:
                    desc += " - " + commands[obj_name].__doc__
                    cmd_list[obj_name] = desc
                if isinstance(clist, dict):
                    clist[obj_name] = desc

        embed(config=c, extensions=["m1n1.ishell_ext"], header=msg, user_ns=commands)
    finally:
        sys.displayhook = saved_display


if __name__ == "__main__":
    from .setup import *

    commands = dict(__main__.__dict__)

    run_ishell(commands, msg="Have fun!")
