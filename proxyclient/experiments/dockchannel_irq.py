#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.dockchannel import DockChannel

NUM_IRQS=4096
ITER=10
candidates = set(range(NUM_IRQS))


aic = u.adt["/arm-io/aic"]
if "aic,3" in aic.compatible:
    MASK_SET = aic.get_reg(0)[0] + 0x10000 + 0x4400
    MASK_CLR = aic.get_reg(0)[0] + 0x10000 + 0x4600
    AIC_HW_STATE = aic.get_reg(0)[0] + 0x10000 + 0x4800
elif "aic,2" in aic.compatible:
    MASK_SET = aic.get_reg(0)[0] + 0x2000 + 0x4400
    MASK_CLR = aic.get_reg(0)[0] + 0x2000 + 0x4600
    AIC_HW_STATE = aic.get_reg(0)[0] + 0x2000 + 0x4800
else:
    raise Exception("Your AIC version is not supported by this script")

p.write32(aic.get_reg(0)[0] + 0x14, p.read32(aic.get_reg(0)[0] + 0x14) | 0x1) # Enable AIC


dc = DockChannel(
    u,
    u.adt["/arm-io/dockchannel-uart"].get_reg(1)[0],
    u.adt["/arm-io/dockchannel-uart"].get_reg(0)[0],
    0
)
dc.irq.IRQ_MASK = 2 # Only RX

def trigger_dockchannel_irq():
    dc.irq.IRQ_FLAG.val = -1
    dc.set_rx_thresh(0)
    assert(dc.rx_irq)

def reset_dockchannel_irq():
    dc.set_rx_thresh(0x800)
    dc.irq.IRQ_FLAG.val = -1
    assert(not dc.rx_irq)

def eliminate_candidates(active: bool):
    for i in range(NUM_IRQS//32):
        v = p.read32(AIC_HW_STATE + i * 4)
        for j in range(32):
            if bool(v & (1<<j)) != active:
                candidates.discard(i * 32 + j)

for _ in range(ITER):
    reset_dockchannel_irq()
    eliminate_candidates(False)
    trigger_dockchannel_irq()
    eliminate_candidates(True)
    if len(candidates) <= 1:
        break
    print(f"{len(candidates)} candidates left")


print(candidates)
