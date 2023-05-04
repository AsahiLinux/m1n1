#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.proxy import REGION_RX_EL1
from m1n1.setup import *
from m1n1 import asm

p.smp_start_secondaries()
for i in range(1, 10):
    p.mmu_init_secondary(i)

aic = u.adt["arm-io/aic"].get_reg(0)[0]

mon.add(aic, 0xc000)

hacr = 0x1f000000056c01#0#xffffffff_ffffffff

hcr = HCR(u.mrs(HCR_EL2))
hcr.TIDCP = 0
hcr.TGE = 0
hcr.AMO = 1
hcr.IMO = 1
hcr.FMO = 1
print(hcr)
u.msr(HCR_EL2, hcr.value)
u.msr(HACR_EL2, hacr)
u.inst(0xd5033fdf) # isb

AIC_NR_IRQ = aic + 0x04
AIC_RST = aic + 0x10
AIC_CFG = aic + 0x14

AIC_CFG_ENABLE = 1 << 0
AIC_CFG_PREFER_PCORES = 1 << 28

AIC_RR_DELAY = aic + 0x28
AIC_CLUSTER_ENABLE_CFG = aic + 0x30
AIC_SOME_CNT = aic + 0x3c

AIC_DELAYS = aic + 0x100

AIC_IDLE_CLUSTERS = aic + 0x340

AIC_TIMESTAMPS = 0x28e101800

AIC_IRQ_CFG = aic + 0x2000
# AIC_IRQ_ROUTE: bits 3:0 ? only 0 works.
# AIC_IRQ_CFG_DELAY: bits 7:5

AIC_SW_GEN_SET = aic + 0x6000
AIC_SW_GEN_CLR = aic + 0x6200
AIC_MASK_SET = aic + 0x6400
AIC_MASK_CLR = aic + 0x6600
AIC_HW_STATE = aic + 0x6800

AIC_IRQ_CFG_2 = aic + 0x6a00
AIC_MASK2_SET = aic + 0xae00
AIC_MASK2_CLR = aic + 0xb000
AIC_HW2_STATE = aic + 0xb200

AIC_INTERRUPT_ACK = aic + 0xc000

num_irq = p.read32(AIC_NR_IRQ) & 0xffff

code = u.malloc(0x1000)

c = asm.ARMAsm("""
write32_ts:
    isb
    mrs x2, CNTPCT_EL0
    str w1, [x0]
    mov x0, x2
    isb
    ret

en_and_spin:
    msr DAIFSet, 7
    msr DAIFClr, 2
    isb
    b 1f

en_and_spin_sec:
    msr DAIFSet, 7
    #msr DAIFClr, 2
    isb
    b 1f

1:
    cmp x0, #0
    beq 2f
    sub x0, x0, #1
    b 1b
2:
    msr DAIFSet, 7
    msr DAIFClr, 2
    isb
    ret

""", code)

iface.writemem(code, c.data)
p.dc_cvau(code, len(c.data))
p.ic_ivau(code, len(c.data))

def cpoll():
    mon.poll()
    mon.poll()

def init():
    cpoll()

    p.set32(AIC_RST, 1)
    p.set32(AIC_CFG, 1 | AIC_CFG_PREFER_PCORES)
    
    cpoll()

def test_irq_routing():
    irq = 24

    p.write32(AIC_SW_GEN_CLR, 1 << irq)
    p.write32(AIC_MASK_CLR, 1 << irq)

    cpoll()
    ts = p.call(c.write32_ts, AIC_SW_GEN_SET, 1 << irq)
    print(f"IRQ triggered at time {ts:#x}")
    p.nop()

    print("w")
    cpoll()
    cpoll()
    time.sleep(0.1)

    #p.write32(AIC_SW_GEN_CLR, 1 << irq)

    cpoll()

def get_irq_state(irq):
    v = p.read32(AIC_HW_STATE + 4* (irq//32))
    return bool(v & 1<<(irq%32))


TEST_CPU = 2

u.msr(DAIF, 0)
for i in range(1, 10):
    u.msr(DAIF, 0x140, call=lambda x, *args: p.smp_call_sync(i, x | REGION_RX_EL1, *args))
    u.msr(DAIF, 0x1c0, call=lambda x, *args: p.smp_call_sync(i, x | REGION_RX_EL1, *args))
    u.msr((3,4,15,10,4), 0, call=lambda x, *args: p.smp_call_sync(i, x | REGION_RX_EL1, *args));
    mpidr = u.mrs(MIDR_EL1, call=lambda x, *args: p.smp_call_sync(i, x | REGION_RX_EL1, args[0], args[1]));
    print(i, hex(mpidr))

init()

def sec_call(x, *args):
    return p.smp_call_sync(TEST_CPU, x | REGION_RX_EL1, *args)

def cpu_call(cpu, x, *args):
    return p.smp_call_sync(cpu, x | REGION_RX_EL1, *args)

u.msr(HCR_EL2, hcr.value, call=sec_call)
u.msr(HACR_EL2, hacr, call=sec_call)

daif = u.mrs(DAIF)
print("DAIF: %x" % daif)
daif |= 0x1c0
print("DAIF: %x" % daif)
u.msr(DAIF, daif)

p.smp_call(TEST_CPU, c.en_and_spin, 0x10000000)
test_irq_routing()
p.smp_wait(TEST_CPU)

p.smp_call(TEST_CPU, c.en_and_spin, 0x10000000)
test_irq_routing()
p.smp_wait(TEST_CPU)

print(hex(c.en_and_spin))

daif = u.mrs(DAIF)
print("DAIF: %x" % daif)
daif &= ~0x1c0
print("DAIF: %x" % daif)
u.msr(DAIF, daif)

print("DAIF: %x" % daif)
daif &= ~0x1c0
u.msr(DAIF, daif)
print("DAIF: %x" % daif)
print("ISR", hex(u.mrs(ISR_EL1)))
print("ISR #2", hex(u.mrs(ISR_EL1, call=sec_call)))
u.msr(DAIF, daif)
print("test")
# test_irq_routing()
daif = u.mrs(DAIF)
print("ISR", hex(u.mrs(ISR_EL1)))
print("ISR #2", hex(u.mrs(ISR_EL1, call=sec_call)))
print("DAIF: %x" % daif)
daif &= ~0x1c0
u.msr(DAIF, daif)
print("DAIF: %x" % daif)
print("ISR", hex(u.mrs(ISR_EL1)))
print("ISR #2", hex(u.mrs(ISR_EL1, call=sec_call)))

for i in range(0, 10):
    if i == 0:
        isr = u.mrs(ISR_EL1)
    else:
        isr = u.mrs(ISR_EL1, call=lambda x, *args: cpu_call(i, x, *args))
    print(f"{i}: {isr:#x}")

u.msr(DAIF, 0x1c0)
print("call")
p.smp_call_el1(TEST_CPU, c.en_and_spin_sec, 0x20000000)
print("test")
print(time.time())
test_irq_routing()
print(time.time())
print("wait")
p.smp_wait(TEST_CPU)
print("-")

for i in range(1, 10):
    u.msr(DAIF, 0x140, call=lambda x, *args: p.smp_call_sync(i, x | REGION_RX_EL1, *args))

for i in range(0, 10):
    if i == 0:
        isr = u.mrs(ISR_EL1)
    else:
        isr = u.mrs(ISR_EL1, call=lambda x, *args: cpu_call(i, x, *args))
    print(f"{i}: {isr:#x}")

cpoll()
p.set32(AIC_RST, 1)
cpoll()
