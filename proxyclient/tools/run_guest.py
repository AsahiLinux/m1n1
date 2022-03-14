#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, traceback
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

parser = argparse.ArgumentParser(description='Run a Mach-O payload under the hypervisor')
parser.add_argument('-s', '--symbols', type=pathlib.Path)
parser.add_argument('-m', '--script', type=pathlib.Path, action='append', default=[])
parser.add_argument('-c', '--command', action="append", default=[])
parser.add_argument('-S', '--shell', action="store_true")
parser.add_argument('-e', '--hook-exceptions', action="store_true")
parser.add_argument('-d', '--debug-xnu', action="store_true")
parser.add_argument('-l', '--logfile', type=pathlib.Path)
parser.add_argument('-C', '--cpus', default=None)
parser.add_argument('payload', type=pathlib.Path)
parser.add_argument('boot_args', default=[], nargs="*")
args = parser.parse_args()

from m1n1.proxy import *
from m1n1.proxyutils import *
from m1n1.utils import *
from m1n1.shell import run_shell
from m1n1.hv import HV

iface = UartInterface()
p = M1N1Proxy(iface, debug=False)
bootstrap_port(iface, p)
u = ProxyUtils(p, heap_size = 128 * 1024 * 1024)

hv = HV(iface, p, u)

hv.hook_exceptions = args.hook_exceptions

hv.init()

if args.cpus:
    avail = [i.name for i in hv.adt["/cpus"]]
    want = set(f"cpu{i}" for i in args.cpus)
    for cpu in avail:
        if cpu in want:
            continue
        try:
            del hv.adt[f"/cpus/{cpu}"]
            print(f"Disabled {cpu}")
        except KeyError:
            continue

if args.debug_xnu:
    hv.adt["chosen"].debug_enabled = 1

if args.logfile:
    hv.set_logfile(args.logfile.open("w"))

if len(args.boot_args) > 0:
    boot_args = " ".join(args.boot_args)
    hv.set_bootargs(boot_args)

symfile = None
if args.symbols:
    symfile = args.symbols.open("rb")
hv.load_macho(args.payload.open("rb"), symfile=symfile)

for i in args.script:
    try:
        hv.run_script(i)
    except:
        traceback.print_exc()
        args.shell = True

for i in args.command:
    try:
        hv.run_code(i)
    except:
        traceback.print_exc()
        args.shell = True

if args.shell:
    run_shell(hv.shell_locals, "Entering hypervisor shell. Type `start` to start the guest.")
else:
    hv.start()
