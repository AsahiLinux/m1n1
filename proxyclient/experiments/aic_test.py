#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

ULCON = 0x235200000
UCON = 0x235200004
UFCON = 0x235200008
UTRSTAT = 0x235200010

AIC = 0x23b100000

AIC_RST = AIC + 0xc
AIC_CFG = AIC + 0x10

AIC_TB = 0x23b108000
AIC_TGT_DST = AIC + 0x3000
AIC_SW_GEN_SET = AIC + 0x4000
AIC_SW_GEN_CLR = AIC + 0x4080
AIC_MASK_SET = AIC + 0x4100
AIC_MASK_CLR = AIC + 0x4180
AIC_HW_STATE = AIC + 0x4200

AIC_INTERRUPT_ACK = AIC + 0x2004
AIC_IPI_SET = AIC + 0x2008
AIC_IPI_CLR = AIC + 0x200c

AIC_IPI_MASK_SET = AIC + 0x2024
AIC_IPI_MASK_CLR = AIC + 0x2028

daif = u.mrs(DAIF)
print("DAIF: %x" % daif)
daif &= ~0x3c0
#daif |= 0x3c0
u.msr(DAIF, daif)
print("DAIF: %x" % u.mrs(DAIF))

def cpoll():
    mon.poll()
    print("<")
    mon.poll()
    print(">")

p.write32(AIC + 0xc, 1)
p.write32(AIC + 0x10, 0xe0777971)
p.write32(AIC + 0x18, 0)
p.write32(AIC + 0x20, 0xffffffff)
p.write32(AIC + 0x24, 0xffffffff)
p.write32(AIC + 0x28, 0xffffffff)
p.write32(AIC + 0x2c, 0xffffffff)
p.write32(AIC + 0x30, 0xffffffff)
p.write32(AIC + 0x34, 0xffffffff)
p.write32(AIC + 0x38, 0xffffffff)
p.write32(AIC + 0x3c, 0xffffffff)
p.write32(AIC + 0x40, 0xffffffff)
p.write32(AIC + 0x38, 0xffffffff)
#p.write32(AIC + 0xc, 0)

p.memset32(AIC_MASK_SET, 0xffffffff, 0x80)
p.memset32(AIC_SW_GEN_CLR, 0xffffffff, 0x80)
p.memset32(AIC_TGT_DST, 0x1, 0x1000)
#p.memset32(AIC_MASK_CLR, 0xffffffff, 0x80)

#p.write32(AIC + 0x10, 0xe0777971)

mon.add(AIC + 0x0000, 0x1000)
mon.add(AIC + 0x2080, 0x040)
mon.add(AIC + 0x4000, 0x200)
mon.add(AIC + 0x5000, 0x080)
mon.add(AIC + 0x5080, 0x080)
mon.add(AIC + 0x5100, 0x080)
mon.add(AIC + 0x5180, 0x080)
mon.add(AIC + 0x5200, 0x080)
mon.add(AIC + 0x5280, 0x080)
mon.add(AIC + 0x5300, 0x080)
mon.add(AIC + 0x5380, 0x080)
#mon.add(AIC + 0x3000, 0x400)
#mon.add(AIC + 0x4000, 0x400)
#mon.add(AIC + 0x8000, 0x20)
#mon.add(AIC + 0x8030, 0xd0)
#mon.add(0x235200000, 0x20)

def test_ipi():
    cpoll()

    print("Set IPI")

    p.write32(AIC_IPI_SET, 1)

    cpoll()
    cpoll()

    print("Read ACK reg")

    reason = p.read32(AIC_INTERRUPT_ACK)
    print("reason: 0x%x" % reason)

    cpoll()

    print("Write reason")
    p.write32(AIC_INTERRUPT_ACK, reason)

    cpoll()

    reason = p.read32(AIC_INTERRUPT_ACK)
    print("reason: 0x%x" % reason)

    cpoll()

    print("Write ACK reg")
    p.write32(AIC_INTERRUPT_ACK, reason)
    cpoll()

    print("Clear IPI")

    p.write32(AIC_IPI_CLR, 1)
    cpoll()

    print("Read ACK reg")

    reason = p.read32(AIC_INTERRUPT_ACK)

    print("reason: 0x%x" % reason)

    cpoll()

    print("Write IPI ACK")

    p.write32(AIC_IPI_MASK_CLR, 1)

    cpoll()

def test_timer():
    cpoll()

    freq = u.mrs(CNTFRQ_EL0)
    print("Timer freq: %d" % freq)

    #u.msr(CNTP_CTL_EL0, 0)
    #u.msr(CNTP_TVAL_EL0, freq * 2)
    #u.msr(CNTP_CTL_EL0, 1)
    #u.msr(CNTV_CTL_EL0, 0)
    #u.msr(CNTV_TVAL_EL0, freq * 2)
    #u.msr(CNTV_CTL_EL0, 1)
    #u.msr(CNTHV_CTL_EL2, 0)
    #u.msr(CNTHV_TVAL_EL2, freq * 2)
    #u.msr(CNTHV_CTL_EL2, 1)
    u.msr(CNTHP_CTL_EL2, 0)
    u.msr(CNTHP_TVAL_EL2, freq * 2)
    u.msr(CNTHP_CTL_EL2, 1)

    iface.ttymode()

    #while True:
        #p.nop()
        #time.sleep(0.3)
        #print(". %x" % u.mrs(CNTP_CTL_EL0))

def get_irq_state(irq):
    v = p.read32(AIC_HW_STATE + 4* (irq//32))
    return bool(v & 1<<(irq%32))

def test_uart_irq():
    cpoll()
    #p.memset32(AIC_MASK_CLR, 0xffffffff, 0x80)

    print("cleanup")
    p.write32(UCON, 5)
    p.write32(UFCON, 0x11)
    p.write32(UTRSTAT, 0xfff)

    cpoll()

    for irq in range(600, 610):
        #print("S: ", get_irq_state(irq))
        p.write32(AIC_SW_GEN_CLR + 4* (irq//32), 1<<(irq%32))
        #print("S: ", get_irq_state(irq))
        #print("a")
        #print("S: ", get_irq_state(irq))
        p.write32(AIC_MASK_CLR + 4* (irq//32), 1<<(irq%32))
        #print("S: ", get_irq_state(irq))
        #print("b")

    irq = 605

    cpoll()
    print("a")
    print("S: ", get_irq_state(irq))
    print("ucon: %x" %p.read32(UCON))

    TX_IRQ_EN = 0x1000

    RX_IRQ_ENABLE = 0x20000
    RX_IRQ_UNMASK = 0x10000

    RX_IRQ_ENA = 0x20000
    RX_IRQ_MASK = 0x4000 # defer?

    code = u.malloc(0x1000)

    c = asm.ARMAsm("""
        ldr x1, =0x235200000

        ldr x3, =0xc000000
1:
        subs x3, x3, #1
        bne 1b
        mov x2, 'A'
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]
        #str w2, [x1, #0x20]

        mov x3, #0x3ff
        str w3, [x1, #0x10]
        #str w2, [x1, #0x20]
        str w0, [x1, #4]
        ldr w0, [x1, #0x10]

        ldr x3, =0xc00000
1:
        subs x3, x3, #1
        bne 1b

        #mov x3, #0x3ff
        #str w3, [x1, #0x10]
        #ldr w2, [x1, #4]
        #mov x2, #0x205
        #str w2, [x1, #4]
        #str w0, [x1, #4]
        ##ldr w0, [x1, #0x10]

        #ldr x3, =0xc00000
#1:
        #subs x3, x3, #1
        #bne 1b

        ldr w0, [x1, #0x10]
        #mov w0, w2
        ret
""", code)
    iface.writemem(code, c.data)
    p.dc_cvau(code, len(c.data))
    p.ic_ivau(code, len(c.data))

    #RX_IRQ_

    """
UCON    UTRSTAT
00200           TX FIFO thresh IRQ delivery enable
00080   0200    TX FIFO threshold IRQ unmask
20000   0100    RX IRQ unmask
10000           RX IRQ delivery enable
"""

    # edge triggered
    TX_FIFO_THRESH_CROSSED_IRQ_UNMASK = 0x2000

    TX_IRQ_UNMASK = 0x200
    TX_EVENT_ENABLE = 0x80
    RX_EVENT_ENABLE = 0x20000
    RX_IRQ_UNMASK = 0x10000

    #flags = 0x7ffc0
    crash = 0x180000
    no_irqs = 0x21c5c0
    instant_irqs = 0x3a00
    #flags = no_irqs | 0x0000
    #flags = 0x2e5c0
    #flags = 0x2000

    #flags = 0x30000
    #flags = 0x80
    flags = 0x7ff80


    val = flags | 0x005
    #print("ucon<-%x" % val)
    #p.write32(UCON, val)
    p.write32(UTRSTAT, 0xfff)
    print("utrstat=%x" % p.read32(UTRSTAT))
    ret = p.call(code, val)
    print("utrstat::%x" % ret)
    print("utrstat=%x" % p.read32(UTRSTAT))
    time.sleep(0.5)
    iface.dev.write(b'1')
    #print(iface.dev.read(1))
    time.sleep(0.1)
    print("ucon: %x" %p.read32(UCON))
    print("delay")
    try:
        p.udelay(500000)
    except:
        pass
    iface.dev.write(bytes(64))
    p.nop()
    print("ucon: %x" %p.read32(UCON))
    print("S: ", get_irq_state(irq))

    #while True:
        #print("S: ", get_irq_state(irq))
        #p.write32(UTRSTAT, 0xfff)
        #print("utrstat=%x" % p.read32(UTRSTAT))
        #print("ucon: %x" %p.read32(UCON))
        #print(">S: ", get_irq_state(irq))
        #p.write32(UCON, flags | 0x005)
        #print(">ucon: %x" %p.read32(UCON))
        #time.sleep(0.1)



def test_smp_ipi():
    p.smp_start_secondaries()

    code = u.malloc(0x1000)

    c = asm.ARMAsm("""
#define sys_reg(op0, op1, CRn, CRm, op2) s##op0##_##op1##_c##CRn##_c##CRm##_##op2
#define SYS_CYC_OVRD           sys_reg(3, 5, 15, 5, 0)

        msr DAIFClr, 7
        ldr x1, =0x000000
        msr SYS_CYC_OVRD, x1
        mrs x0, SYS_CYC_OVRD
        mov x1, #0x1000000
1:
        subs x1, x1, #1
        mrs x0, HCR_EL2
        bne 1b
        ret
""", code)

    iface.writemem(code, c.data)
    p.dc_cvau(code, len(c.data))
    p.ic_ivau(code, len(c.data))

    print("Enable IRQs on secondaries")
    for i in range(1, 8):
        ret = p.smp_call_sync(i, code)
        print("0x%x"%ret)

    #e0477971
    #p.write32(AIC + 0x10, 0xe0777971)
    #p.write32(AIC + 0x28, 0xffffffff)

    cpoll()

    print("Clear IPI")
    p.write32(AIC_IPI_CLR, 0xffffffff)
    p.write32(AIC_IPI_MASK_CLR, 0xffffffff)
    for i in range(8):
        p.write32(AIC_IPI_CLR+0x3000+i*0x80, 0xffffffff)
        p.write32(AIC_IPI_MASK_CLR+0x3000+i*0x80, 0xffffffff)

    cpoll()

    print("Set IPI")
    #p.write32(AIC_IPI_SET, 0x00000004)
    #p.write32(AIC_IPI_SET, 0x00000000)

    cpoll()
    print("Clear IPI")
    p.write32(AIC_IPI_CLR, 0xffffffff)
    p.write32(AIC_IPI_MASK_CLR, 0xffffffff)
    for i in range(8):
        p.write32(AIC_IPI_CLR+0x3000+i*0x80, 1)
        p.write32(AIC_IPI_MASK_CLR+0x3000+i*0x80, 1)

def test_smp_affinity():
    p.write32(AIC_TGT_DST, 0x6)
    p.write32(AIC_TGT_DST+4, 0xfe)
    p.write32(AIC_TGT_DST+8, 0xfe)
    p.write32(AIC_TGT_DST+12, 0x6)
    p.write32(AIC_SW_GEN_SET,0x8);
    p.write32(AIC_MASK_CLR,0x8);

#test_ipi()
#test_timer()
#test_uart_irq()
test_smp_ipi()
test_smp_affinity()
