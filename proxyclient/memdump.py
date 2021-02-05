#!/usr/bin/env python3

import sys
from setup import *

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
