#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

parser = argparse.ArgumentParser(description='Run a Mach-O payload under the hypervisor')
parser.add_argument('-s', '--symbols', type=pathlib.Path)
parser.add_argument('payload', type=pathlib.Path)
parser.add_argument('boot_args', default=[], nargs="*")
args = parser.parse_args()

from m1n1.proxy import *
from m1n1.proxyutils import *
from m1n1.utils import *
from m1n1.hv import HV

iface = UartInterface()
p = M1N1Proxy(iface, debug=False)
bootstrap_port(iface, p)
u = ProxyUtils(p, heap_size = 128 * 1024 * 1024)

hv = HV(iface, p, u)

hv.init()

if len(args.boot_args) > 0:
    boot_args = " ".join(args.boot_args)
    hv.set_bootargs(boot_args)

symfile = None
if args.symbols:
    symfile = args.symbols.open("rb")
hv.load_macho(args.payload.open("rb"), symfile=symfile)
hv.start()
