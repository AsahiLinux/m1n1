import serial, os, struct, sys, time
from proxy import *
from tgtypes import *
from utils import *

uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")

def setup_connect():
    this_uart = serial.Serial(uartdev, 115200)

    intf = UartInterface(this_uart, debug=False)
    proxy = M1N1Proxy(intf, debug=False)

    try:
        this_uart.timeout = 0.15
        intf.nop()
        proxy.set_baud(1500000)
    except UartTimeout:
        serial.baudrate = 1500000
        intf.nop()

    this_uart.timeout = 3


    proxy_u = ProxyUtils(proxy)
    regmon = RegMonitor(proxy_u)

    return this_uart,intf,proxy,proxy_u,regmon

uart,iface,p,u,mon=setup_connect()


iface.nop()

fb = u.ba.video.base

EL0_REGION = 0x8000000000

print("Base at: 0x%x" % u.base)
print("FB at: 0x%x" % fb)
