# SPDX-License-Identifier: MIT
from ..utils import *

__all__ = ["SGXRegs"]

class R_FAULT_INFO(Register64):
    ADDR        = 63, 24
    UNK_23      = 23
    CONTEXT     = 22, 17
    UNK_0       = 16, 0

class SGXRegs(RegMap):
    FAULT_INFO      = 0x17030, R_FAULT_INFO

#0xdeadbecb854f11
#  0xdeadbecbff4f11
#0xefdeadbecbff4f11

#0x14f11 <- unmapped
#0x14e19 <- permission fault?

#0b10100111100010001
#0b10100111000011001
#0x11ccdead227e6291


# encoder fault
# ADDR=0x0dead0544b, UNK_23=1, CONTEXT=0x3f, UNK_0=0x14f11

# pipeline fault
# ADDR=0x11ccdead22, UNK_23=0, CONTEXT=0x3f, UNK_0=0x6291

# depth buffer fault
# ADDR=0xdedef031, UNK_23=1, CONTEXT=0x3f, UNK_0=0x7d01

