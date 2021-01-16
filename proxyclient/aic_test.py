#!/usr/bin/python
from setup import *

AIC = 0x23b100000
AIC_TB = 0x23b108000
AIC_TGT_DST = AIC + 0x3000
AIC_SW_GEN_SET = AIC + 0x4000
AIC_SW_GEN_CLR = AIC + 0x4080
AIC_MASK_SET = AIC + 0x4100
AIC_MASK_CLR = AIC + 0x4180

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

p.memset32(AIC_MASK_SET, 0xffffffff, 0x80)
p.memset32(AIC_SW_GEN_CLR, 0xffffffff, 0x80)
p.memset32(AIC_TGT_DST, 1, 0x1000)

mon.add(AIC + 0x0000, 0x100)
mon.add(AIC + 0x1000, 0x100)
mon.add(AIC + 0x2008, 0x0f8)
mon.add(AIC + 0x3000, 0x400)
mon.add(AIC + 0x4000, 0x400)
mon.add(AIC + 0x8000, 0x20)
mon.add(AIC + 0x8030, 0xd0)

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

    u.msr(CNTP_CTL_EL0, 0)
    u.msr(CNTP_TVAL_EL0, freq * 2)
    u.msr(CNTP_CTL_EL0, 1)

    while True:
        p.nop()
        time.sleep(0.3)
        print(". %x" % u.mrs(CNTP_CTL_EL0))

test_ipi()
test_timer()
