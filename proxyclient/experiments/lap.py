#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, time, random, array
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

PAGE_SIZE = 16384

REPETITIONS = 1000

TEST_ECORE = 1
TEST_PCORE = 5

S = 8
ITERS = 1024
SIZE_DATA_ARRAY = ITERS * S * 4

WRITE_MAX = SIZE_DATA_ARRAY // 4

seq_data_buf = u.memalign(PAGE_SIZE, SIZE_DATA_ARRAY)
random_data_buf = u.memalign(PAGE_SIZE, SIZE_DATA_ARRAY)

seq_data = [0] * WRITE_MAX
for i in range(0, WRITE_MAX, S):
    seq_data[i] = i + S

random_data = [0] * WRITE_MAX
order = list(range(1, ITERS))
random.shuffle(order)
off = 0
for i in range(ITERS - 1):
    next_off = order[i]
    assert random_data[S * off] == 0
    random_data[S * off] = S * next_off
    off = next_off

print(f"Seq data buf: {seq_data_buf:#x}")
print(f"Random data buf: {random_data_buf:#x}")

iface.writemem(seq_data_buf, array.array('I', seq_data).tobytes())
iface.writemem(random_data_buf, array.array('I', random_data).tobytes())

freq = u.mrs(CNTFRQ_EL0)
code = u.malloc(0x1000)

util = asm.ARMAsm(f"""
test:
    mov x6, x2
    mov x5, x0
    mov x7, #0
    mov x4, #0
    mov x2, x1
    mov x3, #0
1:
    ldr w3, [x5, x3, lsl #2]
    subs x2, x2, #1
    b.ne 1b

3:
    mov x2, x1
    mov x3, #0

    dsb sy
    isb
    mrs x9, S3_2_c15_c0_0
    isb

2:
    ldr w3, [x5, x3, lsl #2]
    subs x2, x2, #1
    b.ne 2b

    dsb sy
    isb
    mrs x10, S3_2_c15_c0_0
    isb

    sub x0, x10, x9
    add x7, x7, x0

    subs x6, x6, #1
    b.ne 3b

    mov x0, x7
    ret
""", code)
iface.writemem(code, util.data)
p.dc_cvau(code, len(util.data))
p.ic_ivau(code, len(util.data))

# Set higher cpufreq pstate on all clusters
p.cpufreq_init()

p.smp_start_secondaries()
p.smp_set_wfe_mode(False)

def cpu_call(cpu, x, *args):
    return p.smp_call_sync(cpu, x | REGION_RX_EL1, *args)

def init_core(cpu):
    p.mmu_init_secondary(cpu)

    def mrs(x):
        return u.mrs(x, call=lambda x, *args: cpu_call(cpu, x, *args))
    def msr(x, v):
        u.msr(x, v, call=lambda x, *args: cpu_call(cpu, x, *args))

    msr(SPRR_CONFIG_EL1, 1)

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

    v = mrs(CNTKCTL_EL1)
    v |= 3
    msr(CNTKCTL_EL1, v)

    # Enable user cache ops
    v = mrs(SCTLR_EL1)
    v |= (1 << 26)
    msr(SCTLR_EL1, v)

def cpu_msr(cpu, x, v):
    u.msr(x, v, call=lambda x, *args: cpu_call(cpu, x, *args))

init_core(TEST_ECORE)
init_core(TEST_PCORE)

# Enable DC MVA ops
v = u.mrs(EHID4_EL1)
v &= ~(1 << 11)
u.msr(EHID4_EL1, v)

def test_cpu(cpu, buf, iters):
    elapsed = p.smp_call_sync(cpu, util.test | REGION_RX_EL1, buf, iters, REPETITIONS)
    return elapsed / iters / REPETITIONS

def run_tests():
    a = test_cpu(TEST_ECORE, seq_data_buf, ITERS)
    b = test_cpu(TEST_ECORE, random_data_buf, ITERS)
    c = test_cpu(TEST_PCORE, seq_data_buf, ITERS)
    d = test_cpu(TEST_PCORE, random_data_buf, ITERS)
    print(f"    ECore seq: {a:.02f}, ECore random: {b:.02f}")
    print(f"    PCore seq: {c:.02f}, PCore random: {d:.02f}")

print("Testing with SSBS=1 (load/store speculation permitted)")
for cpu in (TEST_ECORE, TEST_PCORE):
    cpu_msr(cpu, SSBS, 1<<12)

run_tests()
print("Testing with SSBS=0 (load/store speculation disallowed)")
for cpu in (TEST_ECORE, TEST_PCORE):
    cpu_msr(cpu, SSBS, 0)

run_tests()
