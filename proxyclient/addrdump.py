#!/usr/bin/env python3

import serial, os
from proxy import *

uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")
usbuart = serial.Serial(uartdev, 115200)

iface = UartInterface(usbuart, debug=False)
proxy = M1N1Proxy(iface, debug=False)

SCRATCH = 0x24F00000

blacklist = []

print("Dumping address space...")
of = None
if len(sys.argv) > 1:
	of = open(sys.argv[1],"w")
	print("Also dumping to file %s")

for i in range(0x0000, 0x10000):
	if i in blacklist:
		v = "%08x: SKIPPED"%(i<<16)
	else:
		a = (i<<16) + 0x1000
		d = proxy.read32(a)
		v = "%08x: %08x"%(a, d)
	print(v)
	if of:
		of.write(v+"\n")

if of:
	of.close()
