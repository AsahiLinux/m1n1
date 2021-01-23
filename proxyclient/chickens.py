from setup import *



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

H13_MIGSTS = (3, 4, 15, 0, 4)

APSTS_EL1 = (3, 6, 15, 12, 4)

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

    print("OSLAR")
    u.msr(OSLAR_EL1, 0)
    print("s3_6_c15_c1_0")
    u.msr(s3_6_c15_c1_0, 1)
    print("tlbi_vmalle1")
    u.inst(tlbi_vmalle1)

    v = u.mrs(s3_6_c15_c1_6)
    print("s3_6_c15_c1_6 == 0x%x" % v)
    v = 0x2020a505f020f0f0
    print("s3_6_c15_c1_6 <= 0x%x" % v)
    u.msr(s3_6_c15_c1_6, v)

    u.msr(s3_6_c15_c1_0, 0)
    u.inst(tlbi_vmalle1)
    print("Wait1")
    while not (u.mrs(APSTS_EL1) & 1):
        pass
    print("OK")

    v = u.mrs(H13_MIGSTS)
    print("H13_MIGSTS == 0x%x" % v)
    v &= ~6
    v |= 0x11
    print("H13_MIGSTS <= 0x%x" % v)
    u.msr(H13_MIGSTS, v)

    v = u.mrs(H13_MIGSTS)
    print("H13_MIGSTS == 0x%x" % v)
    if not (u.mrs(H13_MIGSTS) & 0x10):
        v |= 2
        print("H13_MIGSTS <= 0x%x" % v)
        u.msr(H13_MIGSTS, v)

    for reg, clearb, setb in h13e_chickenbits:
        v = u.mrs(sys_regs[reg])
        print("%r == 0x%x" % (reg, v))
        v &= ~clearb
        v |= setb
        print("%r <= 0x%x" % (reg, v))
        u.msr(sys_regs[reg], v)

    v = u.mrs(s3_4_c15_c5_0)
    print("s3_4_c15_c5_0 == 0x%x" % v)
    print("s3_4_c15_c5_0 <= 0x%x" % (mpidr & 3))
    u.msr(s3_4_c15_c5_0, mpidr & 3)

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
    v |= 0x12
    print("CYC_CFG <= 0x%x" % v)
    u.msr(CYC_CFG, v)

    u.msr(L2C_ERR_STS, 0)

h13e_init()

"""
cpuinit:
    msr oslar_el1, xzr

    mrs x18, midr_el1
    and x18, x18, #0xfff0
    cmp x18, #0x0220
    beq cpuinit_h13e
    cmp x18, #0x0230
    beq cpuinit_h13p

cpuinit_h13e:
    msr oslar_el1, xzr
    mov x0, #1
    msr s3_6_c15_c1_0, x0
    tlbi vmalle1
    ldr x0, =0x2020a505f020f0f0
    msr s3_6_c15_c1_6, x0
    msr s3_6_c15_c1_0, xzr
    tlbi vmalle1
1:  mrs x0, s3_6_c15_c12_4
    tbz x0, #0, 1b
    mrs x0, SR_H13_MIGSTS
    bic x0, x0, #6
    orr x0, x0, #0x10
    orr x0, x0, #0x1
    msr SR_H13_MIGSTS, x0
    mrs x0, SR_H13_MIGSTS
    tbnz x0, #4, 1f
    orr x0, x0, #2
    msr SR_H13_MIGSTS, x0
1:

    mrs x0, SR_H13_EHID4
    orr x0, x0, #0x800
    orr x0, x0, #0x100000000000
    msr SR_H13_EHID4, x0

    mrs x0, SR_H13_HID5
    orr x0, x0, #0x2000000000000000
    msr SR_H13_HID5, x0
    mrs x0, SR_H13_EHID10
    orr x0, x0, #0x100000000
    orr x0, x0, #0x2000000000000
    msr SR_H13_EHID10, x0
    mrs x0, s3_0_c15_c1_2
    orr x0, x0, #0x100
    msr s3_0_c15_c1_2, x0
    mrs x0, s3_0_c15_c9_1
    bic x0, x0, #0x20
    msr s3_0_c15_c9_1, x0
    mrs x0, s3_0_c15_c1_2
    orr x0, x0, #0x8000
    msr s3_0_c15_c1_2, x0
    mrs x0, s3_0_c15_c1_2
    orr x0, x0, #0x10000
    msr s3_0_c15_c1_2, x0
    mrs x0, s3_0_c15_c1_2
    orr x0, x0, #0x600000
    msr s3_0_c15_c1_2, x0
    mrs x0, mpidr_el1
    and x0, x0, #3
    msr s3_4_c15_c5_0, x0
    mov x0, #0x100
    msr s3_4_c15_c1_4, x0
    mrs x0, SR_H13_CYC_OVRD
    bic x0, x0, #0xf00000
    msr SR_H13_CYC_OVRD, x0
    mrs x0, actlr_el1
    orr x0, x0, #0x200 /* something to do with dsb? */
    msr actlr_el1, x0
    mrs x0, SR_H13_CYC_CFG
    orr x0, x0, #12
    msr SR_H13_CYC_CFG, x0
    msr SR_H13_LLC_ERR_STS, xzr

    ret

cpuinit_h13p:
    msr oslar_el1, xzr
    mov x0, #1
    msr s3_6_c15_c1_0, x0
    tlbi vmalle1
    ldr x0, =0x2020a505f020f0f0
    msr s3_6_c15_c1_6, x0
    msr s3_6_c15_c1_0, xzr
    tlbi vmalle1
    mrs x0, s3_0_c15_c14_0
    bic x0, x0, 0xf000000000000000
    orr x0, x0, 0xc000000000000000
    msr s3_0_c15_c14_0, x0
    mrs x0, s3_0_c15_c15_0
    orr x0, x0, 0x100000000
    msr s3_0_c15_c15_0, x0
1:  mrs x0, s3_6_c15_c12_4
    tbz x0, #0, 1b
    mrs x0, SR_H13_MIGSTS
    bic x0, x0, #6
    orr x0, x0, #0x10
    orr x0, x0, #0x1
    msr SR_H13_MIGSTS, x0
    mrs x0, SR_H13_MIGSTS
    tbnz x0, #4, 1f
    orr x0, x0, #2
    msr SR_H13_MIGSTS, x0
1:  mrs x0, SR_H13_HID4
    orr x0, x0, #0x800
    orr x0, x0, #0x100000000000
    msr SR_H13_HID4, x0
    mrs x0, SR_H13_HID5
    orr x0, x0, #0x2000000000000000
    msr SR_H13_HID5, x0
    mrs x0, s3_0_c15_c14_0
    bic x0, x0, #0x3c000
    orr x0, x0, #0x10000
    msr s3_0_c15_c14_0, x0
    mrs x0, SR_H13_HID0
    orr x0, x0, #0x200000000000
    msr SR_H13_HID0, x0
    mrs x0, SR_H13_HID3
    bic x0, x0, #0x8000000000000000
    bic x0, x0, #0x100000000000
    msr SR_H13_HID3, x0
    mrs x0, SR_H13_HID1
    orr x0, x0, #0x40000000000000
    msr SR_H13_HID1, x0
    mrs x0, s3_0_c15_c15_2
    orr x0, x0, #0x100000000000000
    orr x0, x0, #0x800000000000000
    orr x0, x0, #0x2000000000000000
    orr x0, x0, #0x4000000000000000
    msr s3_0_c15_c15_2, x0
    mrs x0, SR_H13_HID9
    orr x0, x0, #0x4000000
    msr SR_H13_HID9, x0
    mrs x0, SR_H13_HID4
    orr x0, x0, #0x30000000000
    msr SR_H13_HID4, x0
    mrs x0, SR_H13_HID11
    orr x0, x0, #0x800000000000000
    msr SR_H13_HID11, x0
    mrs x0, SR_H13_HID0
    orr x0, x0, #0x10000000
    orr x0, x0, #0x1000000000
    msr SR_H13_HID0, x0
    mrs x0, SR_H13_HID6
    bic x0, x0, #0x3e0
    msr SR_H13_HID6, x0
    mrs x0, SR_H13_HID7
    orr x0, x0, #0x100000
    orr x0, x0, #0x80000
    orr x0, x0, #0x3000000
    msr SR_H13_HID7, x0
    mrs x0, SR_H13_HID9
    orr x0, x0, #0x1000000000000
    orr x0, x0, #0x20000000
    msr SR_H13_HID9, x0
    mrs x0, s3_0_c15_c11_2
    orr x0, x0, #0x4000
    msr s3_0_c15_c11_2, x0
    mrs x0, s3_0_c15_c1_3
    bic x0, x0, #0x80000
    msr s3_0_c15_c1_3, x0
    mrs x0, SR_H13_HID4
    orr x0, x0, #0x2000000000000
    orr x0, x0, #0x20000000000000
    msr SR_H13_HID4, x0
    mrs x0, SR_H13_HID9
    orr x0, x0, #0x80000000000000
    msr SR_H13_HID9, x0
    mrs x0, SR_H13_HID11
    orr x0, x0, #0x8000
    msr SR_H13_HID11, x0
    mrs x0, SR_H13_HID1
    orr x0, x0, #0x400000000000000
    orr x0, x0, #0x1000000000000000
    msr SR_H13_HID1, x0
    mrs x0, s3_0_c15_c1_3
    orr x0, x0, #0x2000000000000
    msr s3_0_c15_c1_3, x0
    mrs x0, mpidr_el1
    and x0, x0, #3
    msr s3_4_c15_c5_0, x0
    mov x0, #0x100
    msr s3_4_c15_c1_4, x0
    mrs x0, SR_H13_CYC_OVRD
    bic x0, x0, #0xf00000
    msr SR_H13_CYC_OVRD, x0
    mrs x0, actlr_el1
    orr x0, x0, #0x200 /* something to do with dsb? */
    msr actlr_el1, x0
    mrs x0, SR_H13_CYC_CFG
    orr x0, x0, #12
    msr SR_H13_CYC_CFG, x0
    msr SR_H13_LLC_ERR_STS, xzr

    ret

"""
