#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

p = 0x800000000
limit = u.base
block = 0x40000

while p < limit:
    f = "mem/0x%x.bin" % p
    if os.path.exists(f):
        p += block
        continue

    print("dumping 0x%x..." % p)

    data = iface.readmem(p, block)
    open(f, "wb").write(data)
    p += block
