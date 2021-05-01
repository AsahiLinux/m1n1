#!/usr/bin/env python3

import argparse, pathlib

parser = argparse.ArgumentParser(description='Run a Mach-O payload under the hypervisor')
parser.add_argument('payload', type=pathlib.Path)
args = parser.parse_args()

from proxy import *
from proxyutils import *
from utils import *
from hv import HV

iface = UartInterface()
p = M1N1Proxy(iface, debug=False)
bootstrap_port(iface, p)
u = ProxyUtils(p, heap_size = 128 * 1024 * 1024)

hv = HV(iface, p, u)

hv.init()
hv.load_macho(args.payload.read_bytes())
hv.start()
