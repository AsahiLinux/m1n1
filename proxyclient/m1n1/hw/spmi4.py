# SPDX-License-Identifier: MIT
from ..utils import *
from .spmi1 import R_CMD, R_REPLY

class R_STATUS(Register32):
    RX_FULL     = 31
    RX_EMPTY    = 30
    RX_COUNT    = 23, 16
    TX_FULL     = 15
    TX_EMPTY    = 14
    TX_COUNT    = 7, 0

class SPMI4Regs(RegMap):
    STATUS            = 0x200, R_STATUS
    ''' [RO] status about the RX and TX FIFOs '''
    CMD               = 0x210, R_CMD
    ''' [WO] write 32 bits to the TX FIFO '''
    REPLY             = 0x220, R_REPLY
    ''' [RO] consume 32 bits from the RX FIFO '''
