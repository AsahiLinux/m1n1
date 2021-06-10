#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

code_len = 12 * 16 * 8 + 4
data_len = 8 * 16 * 8

if u.mrs(SPRR_CONFIG_EL1):
    u.msr(GXF_CONFIG_EL12, 0)
    u.msr(SPRR_CONFIG_EL12, 0)
    u.msr(GXF_CONFIG_EL1, 0)
    u.msr(SPRR_CONFIG_EL1, 0)

u.msr(HACR_EL2, 0)

hcr = HCR(u.mrs(HCR_EL2))
hcr.TIDCP = 0
hcr.TGE = 0
u.msr(HCR_EL2, hcr.value)
u.inst(0xd5033fdf) # isb

ACTLR_DEFAULT = 0xc00
ACTLR_AFP = 1 << 5
u.msr(ACTLR_EL1, ACTLR_DEFAULT | ACTLR_AFP)

code_buffer = p.malloc(code_len)
data_buffer = p.malloc(data_len)

template = asm.ARMAsm("""
    mov x2, x0
    mrs x2, s3_0_c0_c0_0
    str x2, [x1], #8
    ret
""", code_buffer)

mov, mrs, st, ret = struct.unpack("4I", template.data)

data = []

BAD = 0xacce5515abad1dea

AUX = [
    ACTLR_EL1,
    ACTLR_EL2,
    AFSR0_EL1,
    AFSR0_EL2,
    AFSR1_EL1,
    AFSR1_EL2,
    AIDR_EL1,
    AIDR2_EL1,
    AMAIR_EL1,
    AMAIR_EL2,
    APCTL_EL1,
    APSTS_EL1,
]

def test():
    u.msr(SPRR_CONFIG_EL1, 1)
    u.msr(GXF_CONFIG_EL1, 1)
    u.msr(SPRR_CONFIG_EL12, 1)
    u.msr(GXF_CONFIG_EL12, 1)

    for op1 in range(1 << 3):
        for CRn in (0b1011, 0b1111):
            mrs0 = mrs | (op1 << 16) | (CRn << 12)
            insns = []
            for CRm in range(1 << 4):
                for op2 in range(1 << 3):
                    insns.extend((mov, mrs0 | (CRm << 8) | (op2 << 5), st))
            insns.append(ret)
            iface.writemem(code_buffer, struct.pack("<385I", *insns))
            p.dc_cvau(code_buffer, code_len)
            p.ic_ivau(code_buffer, code_len)

            p.set_exc_guard(GUARD.SILENT | GUARD.SKIP)
            p.el1_call(code_buffer, BAD, data_buffer)
            cnt = p.get_exc_count()

            data = iface.readmem(data_buffer, data_len)
            d = struct.unpack("<128Q", data)
            i = 0
            for CRm in range(1 << 4):
                for op2 in range(1 << 3):
                    v = d[i]
                    if v != BAD:
                        yield (3, op1, CRn, CRm, op2)
                    i += 1
    for enc in AUX:
        try:
            v = u.mrs(enc, call="el1", silent=True)
            if v != BAD:
                yield enc
        except:
            continue

    u.msr(GXF_CONFIG_EL12, 0)
    u.msr(SPRR_CONFIG_EL12, 0)
    u.msr(GXF_CONFIG_EL1, 0)
    u.msr(SPRR_CONFIG_EL1, 0)

baseline = set(test())

for bit in range(64):
    print()
    print ("## HACR_EL2[%d]" % bit)
    u.msr(HACR_EL2, 1<<bit)
    u.inst(0xd5033fdf) # isb

    new = set(test())

    added = new - baseline
    removed = baseline - new

    if added:
        print("Untraps:")
        for enc in sorted(added):
            print(f"{sysreg_name(enc)} ({', '.join(str(i) for i in enc)})")

    if removed:
        print("Traps:")
        for enc in sorted(removed):
            print(f"{sysreg_name(enc)} ({', '.join(str(i) for i in enc)})")

p.set_exc_guard(GUARD.OFF)
