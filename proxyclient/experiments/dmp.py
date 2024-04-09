#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

REPETITIONS = 64

PAGE_SIZE = 16384

TEST_ECORE = 1
TEST_PCORE = 4

L2_LINE_SIZE = 128
PNRG_a = 75
PRNG_m = 31337
rnd_idx = 8

def prng(x):
    return (PNRG_a * x) % PRNG_m

SIZE_DATA_ARRAY = (PRNG_m * L2_LINE_SIZE)

data_buf_addr = u.memalign(PAGE_SIZE, SIZE_DATA_ARRAY)
p.memset64(data_buf_addr, 0x5555555555555555, SIZE_DATA_ARRAY)
aop_addr = u.memalign(PAGE_SIZE, PAGE_SIZE)
p.memset64(aop_addr, 0x5555555555555555, PAGE_SIZE)

freq = u.mrs(CNTFRQ_EL0)
code = u.malloc(0x1000)

util = asm.ARMAsm("""
test:
    dc civac, x0
    dc civac, x1
    isb sy

    mov x7, #0x8000
1:
    add x2, x2, #1
    mul x2, x2, x2
    sub x7, x7, #1
    cbnz x7, 1b
    and x2, x2, #(15 << 60)

    add x1, x1, x2
    ldrb w2, [x1, #512]
    and x2, x2, #(15 << 60)

    add x0, x0, x2

    dsb sy
    isb
    mrs x9, S3_2_c15_c0_0 // PMC0_EL1
    isb
    ldr x2, [x0, x2]
    isb
    mrs x10, S3_2_c15_c0_0
    sub x5, x10, x9

    and x2, x2, #(15 << 60)
    mov x7, #0x4000
1:
    add x2, x2, #1
    mul x2, x2, x2
    sub x7, x7, #1
    cbnz x7, 1b

    and x2, x2, #(15 << 60)

    dsb sy
    isb
    mrs x9, S3_2_c15_c0_0
    isb
    ldr x2, [x1, x2]
    isb
    mrs x10, S3_2_c15_c0_0
    sub x0, x10, x9

    isb sy

    lsl x5, x5, #32
    orr x0, x0, x5
    ret
""", code)
for i in util.disassemble():
    print(i)
iface.writemem(code, util.data)
p.dc_cvau(code, len(util.data))
p.ic_ivau(code, len(util.data))

# Set higher cpufreq pstate on all clusters
p.cpufreq_init()
p.smp_start_secondaries()
p.smp_set_wfe_mode(True);

def cpu_call(cpu, x, *args):
    return p.smp_call_sync(cpu, x | REGION_RX_EL1, *args)

def init_core(cpu):
    p.mmu_init_secondary(cpu)

    def mrs(x):
        return u.mrs(x, call=lambda x, *args: cpu_call(cpu, x, *args))
    def msr(x, v):
        u.msr(x, v, call=lambda x, *args: cpu_call(cpu, x, *args))

    is_ecore = not (mrs(MPIDR_EL1) & (1 << 16))
    # Enable DC MVA ops
    v = mrs(EHID4_EL1 if is_ecore else HID4_EL1)
    v &= ~(1 << 11)
    msr(EHID4_EL1 if is_ecore else HID4_EL1, v)

    # Enable PMU
    v = mrs(PMCR0_EL1)
    v |= 1 | (1<<30)
    msr(PMCR0_EL1, v)
    msr(PMCR1_EL1, 0xffffffffffffffff)

    # Enable TBI
    v = mrs(TCR_EL1)
    v |= (1 << 37)
    msr(TCR_EL1, v)

    # Enable user cache ops
    v = mrs(SCTLR_EL1)
    v |= (1 << 26)
    msr(SCTLR_EL1, v)

init_core(TEST_ECORE)
init_core(TEST_PCORE)

# Enable DC MVA ops
v = u.mrs(EHID4_EL1)
v &= ~(1 << 11)
u.msr(EHID4_EL1, v)

def test_cpu(cpu, mask):
    global rnd_idx

    total_aop = total_ptr = 0
    p.memset64(data_buf_addr, 0x5555555555555555, SIZE_DATA_ARRAY)
    p.memset64(aop_addr, 0x5555555555555555, PAGE_SIZE)
    for i in range(REPETITIONS):
        test_offset = L2_LINE_SIZE * rnd_idx
        test_addr = data_buf_addr + test_offset

        p.write64(aop_addr, test_addr | mask | REGION_RWX_EL0)
        p.dc_civac(aop_addr, L2_LINE_SIZE)
        # p.dc_civac(data_buf_addr, SIZE_DATA_ARRAY)

        elapsed = p.smp_call_sync_el0(cpu, util.test | REGION_RWX_EL0, aop_addr | REGION_RWX_EL0, test_addr | REGION_RWX_EL0, 7 << 60)
        time_aop = elapsed >> 32
        time_ptr = elapsed & 0xffffffff
        total_aop += time_aop
        total_ptr += time_ptr

        rnd_idx = prng(rnd_idx)

    return total_aop, total_ptr


print("ECore plain:", test_cpu(TEST_ECORE, 0))
print("ECore mask: ", test_cpu(TEST_ECORE, 0xaaaaaaaa00000000))
print("PCore plain:", test_cpu(TEST_PCORE, 0))
print("PCore mask: ", test_cpu(TEST_PCORE, 0xaaaaaaaa00000000))

for reg in (
    # "HID0_EL1",
    # "HID1_EL1",
    # "HID2_EL1",
    # "HID3_EL1",
    "HID4_EL1",
    # "HID5_EL1",
    # "HID6_EL1",
    # "HID7_EL1",
    # "HID8_EL1",
    # "HID9_EL1",
    # "HID10_EL1",
    "HID11_EL1",
    # "HID13_EL1",
    # "HID14_EL1",
    # "HID16_EL1",
    # "HID17_EL1",
    # "HID18_EL1",
    "HID21_EL1",
    # "HID26_EL1",
    # "HID27_EL1",
):

    cpu = TEST_PCORE
    hid = u.mrs(reg, call=lambda x, *args: cpu_call(cpu, x, *args))

    for i in range(64):
        if (reg, i) not in (
            ("HID4_EL1", 4),
            ("HID11_EL1", 30),
            ("HID21_EL1", 40),
            ):
            continue

        bit = (1 << i)
        print(f"Test {reg} bit {i}:", end=" ")

        u.msr(reg, hid ^ bit, call=lambda x, *args: cpu_call(cpu, x, *args))

        tval = test_cpu(cpu, 0)[1]
        control = test_cpu(cpu, 0xaaaaaaaa00000000)[1]


        if tval < (0.75 * control):
            print(f"DMP active {tval} {control}")
        else:
            print(f"DMP INACTIVE {tval} {control}")

    u.msr(reg, hid, call=lambda x, *args: cpu_call(cpu, x, *args))

