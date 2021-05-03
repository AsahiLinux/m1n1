import os, struct, sys, time
from proxy import *
from tgtypes import *
from proxyutils import *
from utils import *
from hv import HV

iface = UartInterface()
p = M1N1Proxy(iface, debug=False)
bootstrap_port(iface, p)

u = ProxyUtils(p)
mon = RegMonitor(u)
hv = HV(iface, p, u)

fb = u.ba.video.base

EL0_REGION = 0x8000000000

print("Base at: 0x%x" % u.base)
print("FB at: 0x%x" % fb)
