#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

FPCR_FZ = 1 << 24

ACTLR_DEFAULT = 0xc00
ACTLR_AFP = 1 << 5

AFPCR = (3,6,15,2,5)
AFPCR_DAZ = 1 << 0
AFPCR_FTZ = 1 << 1

code_buffer = p.malloc(0x1000)
data_buffer = p.malloc(0x1000)

code = asm.ARMAsm("""
    ldr s0, [x0, #0]
    ldr s1, [x0, #4]
    fmul s0, s1, s0
    str s0, [x0, #8]

    ldr s0, [x0, #12]
    ldr s1, [x0, #16]
    fmul s0, s1, s0
    str s0, [x0, #20]

    # to test EL0 access
    # mrs x0, s3_6_c15_c2_5
    ret
""", code_buffer)

iface.writemem(code_buffer, code.data)
p.dc_cvau(code_buffer, code.len)
p.ic_ivau(code_buffer, code.len)

def test_denormals():

    data = [
        0x00400000, # a denormal
        0x40000000, # 2
        0,
        0x00800000, # smallest non-denormal
        0x3f000000, # 0.5
        0,
    ]

    iface.writemem(data_buffer, struct.pack("<%dI" % len(data), *data))

    p.set_exc_guard(GUARD.SKIP)
    ret = p.el0_call(code_buffer, data_buffer | REGION_RW_EL0)
    p.set_exc_guard(GUARD.OFF)

    v1 = p.read32(data_buffer + 8)
    v2 = p.read32(data_buffer + 20)

    print(" Input:", end=" ")
    if v1 == 0:
        print("FLUSH ", end=" ")
    elif v1 == 0x00800000:
        print("NORMAL", end=" ")
    else:
        print("0x08x?" % v1, end=" ")

    print("Output:", end=" ")
    if v2 == 0:
        print("FLUSH ", end=" ")
    elif v2 == 0x00400000:
        print("NORMAL", end=" ")
    else:
        print("0x08x?" % v2, end=" ")
    print("r = 0x%x" % ret)


print("Testing normal mode")
u.msr(ACTLR_EL1, ACTLR_DEFAULT)
u.msr(AFPCR, 0)

u.msr(FPCR, 0)
print("FPCR.FZ = 0")
test_denormals()

u.msr(FPCR, FPCR_FZ)
print("FPCR.FZ = 1")
test_denormals()

print()
print("Testing Apple mode")
u.msr(ACTLR_EL1, ACTLR_DEFAULT | ACTLR_AFP)
u.msr(AFPCR, 0)

u.msr(FPCR, 0)
print("FPCR.FZ = 0")
test_denormals()

u.msr(FPCR, FPCR_FZ)
print("FPCR.FZ = 1")
test_denormals()

u.msr(AFPCR, AFPCR_DAZ)
print("AFPCR.<FTZ, DAZ> = 0, 1")
test_denormals()

u.msr(AFPCR, AFPCR_FTZ)
print("AFPCR.<FTZ, DAZ> = 1, 0")
test_denormals()

u.msr(AFPCR, AFPCR_FTZ | AFPCR_DAZ)
print("AFPCR.<FTZ, DAZ> = 1, 1")
test_denormals()
