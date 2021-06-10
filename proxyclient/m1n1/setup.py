# SPDX-License-Identifier: MIT
import os, struct, sys, time

from .hv import HV
from .proxy import *
from .proxyutils import *
from .sysreg import *
from .tgtypes import *
from .utils import *

iface = UartInterface()
p = M1N1Proxy(iface, debug=False)
bootstrap_port(iface, p)

u = ProxyUtils(p)
mon = RegMonitor(u)
hv = HV(iface, p, u)

fb = u.ba.video.base

print(f"m1n1 base: 0x{u.base:x}")
