#!/usr/bin/python

import serial, os, struct, sys, time
from proxy import *
from tgtypes import *

uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")
usbuart = serial.Serial(uartdev, 115200)

iface = UartInterface(usbuart, debug=False)
proxy = M1N1Proxy(iface, debug=False)

proxy.set_baud(1500000)

payload = open(sys.argv[1], "rb").read()

base = proxy.get_base()
ba_addr = proxy.get_bootargs()

ba = iface.readstruct(ba_addr, BootArgs)

new_base = base + ((ba.top_of_kernel_data + 0xffff) & ~0xffff) - ba.phys_base

print("Loading %d bytes to 0x%x" % (len(payload), new_base))

iface.writemem(new_base + 0x4000, payload[0x4000:], True)

entry = new_base + 0x4000

print("Jumping to 0x%x" % entry)

proxy.vector(entry, ba_addr)

iface.nop()
print("Proxy is alive again")
