from setup import *
from find_regs import find_regs
import asm

p.iodev_set_usage(IODEV.FB, 0)

all_regs = set()
for reg in [SPRR_CONFIG_EL1, GXF_CONFIG_EL1]:
    old_regs = find_regs(u)
    u.msr(reg, 1)
    new_regs = find_regs(u)

    all_regs = all_regs.union(new_regs)

    diff_regs = new_regs - old_regs

    print(reg)
    for r in sorted(diff_regs):
        print("  %s --> %lx" % (list(r), u.mrs(r)))

u.msr(GXF_CONFIG_EL1, 0)
u.msr(SPRR_CONFIG_EL1, 0)

gxf_regs = find_regs(u, call="gl2")

print("GL2")
for r in sorted(gxf_regs - all_regs):
    print("  %s -> %lx" % (list(r), u.mrs(r, call="gl2")))

gxf_regs = find_regs(u, call="gl1")

print("GL1")
for r in sorted(gxf_regs - all_regs):
    print("  %s -> %lx" % (list(r), u.mrs(r, call="gl1")))
