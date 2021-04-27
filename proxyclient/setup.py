import serial, os, struct, sys, time
from proxy import *
from tgtypes import *
from utils import *

iface = UartInterface()
p = M1N1Proxy(iface, debug=False)

try:
    iface.dev.timeout = 0.15
    iface.nop()
    p.set_baud(1500000)
except UartTimeout:
    iface.dev.baudrate = 1500000
    iface.nop()

iface.dev.timeout = 3

u = ProxyUtils(p)
mon = RegMonitor(u)

iface.nop()

fb = u.ba.video.base

EL0_REGION = 0x8000000000

print("Base at: 0x%x" % u.base)
print("FB at: 0x%x" % fb)
