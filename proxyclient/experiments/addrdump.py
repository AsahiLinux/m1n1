#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

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
		d = p.read32(a)
		v = "%08x: %08x"%(a, d)
	print(v)
	if of:
		of.write(v+"\n")

if of:
	of.close()
