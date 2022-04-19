#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

#for i in (0x28e580350, 0x28e580328, 0x28e580380, 0x28e580378):
    #p.write32(i, 0)

sts = p.read32(0x20002100c)
print(f"status: {sts:#x}")
p.write32(0x200021010, 0)
p.write32(0x20002100c, 0xfff)
time.sleep(0.1)
sts = p.read32(0x20002100c)
print(f"status: {sts:#x}")

print(f"ERRLOG0: {p.read32(0x20000070c):#x}")
print(f"ERRLOG1: {p.read32(0x200000710):#x}")
print(f"ERRLOG2: {p.read32(0x200000714):#x}")
print(f"ERRLOG3: {p.read32(0x200000718):#x}")
print(f"ERRLOG4: {p.read32(0x20000071c):#x}")

p.write32(0x20000070c, 0xffffffff)

#p.fb_shutdown()
u.inst("tlbi vmalle1is")

#p.memset32(fb, 0xffffffff, 3024 * 1964 * 4)
#p.dc_cvac(fb, 3024 * 1964 * 4)

#p.memset32(0x100_80000000, 0xffffffff, 0x80000000)

#p.memcpy32(fb, fb + 0x1000, 0x800)
#p.memset32(fb, 0xfffff, 3024 * 1964 * 4)
#p.memset32(fb, 0xffffffff, 3024 * 1964 * 4)
#p.memcpy32(0x100_80000000, fb + 0x1000, 0x1800)
#p.read8(fb + 0x10)
#p.write8(fb + 0x200, 0xdeadbeef)
#p.memset32(fb, 0xfffffff, 3024 * 1964 * 4)

#p.iodev_write(IODEV.FB, "test\n", 5)
