import serial, os, struct, sys, time
from proxy import *
from tgtypes import *
from utils import *

uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")
usbuart = serial.Serial(uartdev, 115200)

iface = UartInterface(usbuart, debug=False)
p = M1N1Proxy(iface, debug=False)
u = ProxyUtils(p)
mon = RegMonitor(u)

p.set_baud(1500000)

iface.nop()

fb = u.ba.video.base

print("Base at: 0x%x" % u.base)
print("FB at: 0x%x" % fb)
