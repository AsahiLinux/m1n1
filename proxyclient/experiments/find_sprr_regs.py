#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.find_regs import *
from m1n1 import asm

p.iodev_set_usage(IODEV.FB, 0)

if u.mrs(SPRR_CONFIG_EL1):
    u.msr(GXF_CONFIG_EL12, 0)
    u.msr(SPRR_CONFIG_EL12, 0)
    u.msr(GXF_CONFIG_EL1, 0)
    u.msr(SPRR_CONFIG_EL1, 0)

# Set up HCR_EL2 for EL1, since we can't do it after enabling GXF
u.inst("nop", call="el1")

all_regs = set()
for reg in [SPRR_CONFIG_EL1, GXF_CONFIG_EL1, SPRR_CONFIG_EL12, GXF_CONFIG_EL12]:
    old_regs = set(find_regs(u, values=False))
    u.msr(reg, 1)
    el2_items = set(find_regs(u))
    el2_vals = dict(el2_items)
    new_regs = set(k for k, v in el2_items)

    all_regs = all_regs.union(new_regs)

    diff_regs = new_regs - old_regs

    print(reg)
    for r in sorted(diff_regs):
        print("  %s --> %lx" % (sysreg_name(r), u.mrs(r)))

gl2_items = list(find_regs(u, regs=static_regs,call="gl2"))
gl2_vals = dict(gl2_items)
gl2_regs = set(k for k, v in gl2_items)

print("GL2")
for reg in sorted(gl2_regs - all_regs):
    print("  %s -> %lx" % (sysreg_name(reg), gl2_vals[reg]))
for reg in sorted(gl2_regs):
    if reg in el2_vals and gl2_vals[reg] != el2_vals[reg]:
        print("  ! %s %lx -> %lx" % (sysreg_name(reg), el2_vals[reg], gl2_vals[reg]))

u.msr(GXF_CONFIG_EL12, 0)
u.msr(SPRR_CONFIG_EL12, 0)
u.msr(GXF_CONFIG_EL1, 0)
u.msr(SPRR_CONFIG_EL1, 0)

gl1_items = list(find_regs(u, regs=static_regs, call="gl1"))
gl1_vals = dict(gl1_items)
gl1_regs = set(k for k, v in gl1_items)

print("GL1")
for reg in sorted(gl1_regs - all_regs):
    val = gl1_vals[reg]
    print("  %s -> %lx" % (sysreg_name(reg), val))

    cval = u.mrs(reg, call="gl1", silent=False)
    print("    cur: 0x%lx" % (cval))

    try:
        u.msr(reg, cval, call="gl1", silent=False)
    except:
        print(">RO")
        continue

    gl2_vals = dict(find_regs(u, regs=static_regs,call="gl2"))
    u.msr(reg, cval ^ 0xffff, call="gl1", silent=True)

    for r, v in find_regs(u, regs=static_regs, call="gl2"):
        if v != gl2_vals[r]:
            print("     GL2 access: %s %lx -> %lx" % (sysreg_name(r), gl2_vals[r], v))

    u.msr(reg, cval, call="gl1", silent=True)

for reg in sorted(gl1_regs):
    if reg in el2_vals and gl1_vals[reg] != el2_vals[reg]:
        print("  ! %s %lx -> %lx" % (sysreg_name(reg), el2_vals[reg], gl1_vals[reg]))
