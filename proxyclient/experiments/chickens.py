#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

sys_regs = dict([
    ("HID0", (3, 0, 15, 0, 0)),
    ("HID1", (3, 0, 15, 1, 0)),
    ("EHID20", (3, 0, 15, 1, 2)),
    ("HID2", (3, 0, 15, 2, 0)),
    ("HID3", (3, 0, 15, 3, 0)),
    ("HID4", (3, 0, 15, 4, 0)),
    ("EHID4", (3, 0, 15, 4, 1)),
    ("HID5", (3, 0, 15, 5, 0)),
    ("HID6", (3, 0, 15, 6, 0)),
    ("HID7", (3, 0, 15, 7, 0)),
    ("HID8", (3, 0, 15, 8, 0)),
    ("HID9", (3, 0, 15, 9, 0)),
    ("EHID9", (3, 0, 15, 9, 1)),
    ("HID10", (3, 0, 15, 10, 0)),
    ("EHID10", (3, 0, 15, 10, 1)),
    ("HID11", (3, 0, 15, 11, 0)),
])

CYC_OVRD = (3, 5, 15, 5, 0)
CYC_CFG = (3, 5, 15, 4, 0)

L2C_ERR_STS = (3, 3, 15, 8, 0)

s3_6_c15_c1_0 = (3, 6, 15, 1, 0)
s3_6_c15_c1_6 = (3, 6, 15, 1, 6)

s3_4_c15_c1_4 = (3, 4, 15, 1, 4)
s3_4_c15_c5_0 = (3, 4, 15, 5, 0)

h13e_chickenbits = [
    ("EHID4", 0x100000000800, 0),
    ("HID5", 0x2000000000000000, 0),
    ("EHID10", 0x2000100000000, 0),
    ("EHID20", 0x100, 0),
    ("EHID9", 0, 0x20),
    ("EHID20", 0x8000, 0),
    ("EHID20", 0x10000, 0),
    ("EHID20", 0x600000, 0),

]

tlbi_vmalle1 = 0xd508871f

def h13e_init():
    mpidr = u.mrs(MPIDR_EL1)
    print("mpidr = 0x%x" % mpidr)

    #print("OSLAR")
    #u.msr(OSLAR_EL1, 0)
    #print("s3_6_c15_c1_0")
    #u.msr(s3_6_c15_c1_0, 1)
    #print("tlbi_vmalle1")
    #u.inst(tlbi_vmalle1)

    ## This looks like APRR stuff?
    #v = u.mrs(s3_6_c15_c1_6)
    #print("s3_6_c15_c1_6 == 0x%x" % v)
    #v = 0x2020a505f020f0f0
    #print("s3_6_c15_c1_6 <= 0x%x" % v)
    #u.msr(s3_6_c15_c1_6, v)

    #u.msr(s3_6_c15_c1_0, 0)

    for reg, setb, clearb in h13e_chickenbits:
        v = u.mrs(sys_regs[reg])
        print("%r == 0x%x" % (reg, v))
        v &= ~clearb
        v |= setb
        print("%r <= 0x%x" % (reg, v))
        u.msr(sys_regs[reg], v)

    v = u.mrs(s3_4_c15_c5_0)
    print("s3_4_c15_c5_0 == 0x%x" % v)
    print("s3_4_c15_c5_0 <= 0x%x" % (mpidr & 0xff))
    u.msr(s3_4_c15_c5_0, mpidr & 0xff)

    u.msr(s3_4_c15_c1_4, 0x100)

    v = u.mrs(CYC_OVRD)
    print("CYC_OVRD == 0x%x" % v)
    v &= ~0xf00000
    print("CYC_OVRD <= 0x%x" % v)
    u.msr(CYC_OVRD, v)

    v = u.mrs(ACTLR_EL1)
    print("ACTLR_EL1 == 0x%x" % v)
    v |= 0x200
    print("ACTLR_EL1 <= 0x%x" % v)
    u.msr(ACTLR_EL1, v)

    v = u.mrs(CYC_CFG)
    print("CYC_CFG == 0x%x" % v)
    v |= 0xc
    print("CYC_CFG <= 0x%x" % v)
    u.msr(CYC_CFG, v)

    print("L2C_ERR_STS = %x" %  u.mrs(L2C_ERR_STS))
    u.msr(L2C_ERR_STS, 0)

h13e_init()
