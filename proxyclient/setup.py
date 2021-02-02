import serial, os, struct, sys, time
from proxy import *
from tgtypes import *
from utils import *

uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")
uart = serial.Serial(uartdev, 115200)

iface = UartInterface(uart, debug=False)
p = M1N1Proxy(iface, debug=False)

try:
    uart.timeout = 0.15
    iface.nop()
    p.set_baud(1500000)
except UartTimeout:
    uart.baudrate = 1500000
    iface.nop()

u = ProxyUtils(p)
mon = RegMonitor(u)

iface.nop()

fb = u.ba.video.base

print("Base at: 0x%x" % u.base)
print("FB at: 0x%x" % fb)
