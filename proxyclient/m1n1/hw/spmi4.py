# SPDX-License-Identifier: GPL-2.0-or-later
from ..utils import *
from .spmi1 import R_CMD, R_REPLY, R_ACTION, R_PEEK_POS, IRQs

class R_STATUS(Register32):
    RX_FULL     = 31
    RX_EMPTY    = 30
    RX_COUNT    = 23, 16
    TX_FULL     = 15
    TX_EMPTY    = 14
    TX_COUNT    = 7, 0

class R_CURSORS(Register32):
    CURSOR_R    = 21, 16
    CURSOR_W    =  5,  0

class SPMI4Regs(RegMap):
    CONFIG1           = 0x0, Register32
    ''' [RO] unknown, set to 0x6 or 0x7 on boot. master address? '''
    ACTION1           = 0x4, R_ACTION
    ''' [WO] always reads 0, but writing a 1 to certain bits triggers bit-specific actions '''

    STATUS            = 0x200, R_STATUS
    ''' [RO] status about the RX and TX FIFOs '''
    CMD               = 0x210, R_CMD
    ''' [WO] write 32 bits to the TX FIFO '''
    REPLY             = 0x220, R_REPLY
    ''' [RO] consume 32 bits from the RX FIFO '''

    # setting a bit in one of these registers causes the IRQ line
    # to be asserted whenever the same bit at the register at
    # address +0x200 (see below) is set. clearing a bit only masks
    # the interrupt, but doesn't prevent the bit from being set or
    # cleared in register +0x200. these are zero on boot.
    BUS_EVENTS_0_MASK = 0x400, Register32
    BUS_EVENTS_1_MASK = 0x404, Register32
    BUS_EVENTS_2_MASK = 0x408, Register32
    BUS_EVENTS_3_MASK = 0x40c, Register32
    BUS_EVENTS_4_MASK = 0x410, Register32
    BUS_EVENTS_5_MASK = 0x414, Register32
    BUS_EVENTS_6_MASK = 0x418, Register32
    BUS_EVENTS_7_MASK = 0x41c, Register32
    IRQ_MASK          = 0x420, IRQs

    # bits in these registers are set in response to an event
    # and can be cleared by writing a 1 to them. IRQ_FLAG is
    # for events of the SPMI peripheral itself, while
    # BUS_EVENTS_* is for generic events that can be triggered
    # by other devices in the bus using (I presume) master
    # commands against us, and allow the SPMI peripheral to
    # also act as an interrupt controller
    BUS_EVENTS_0_FLAG = 0x600, Register32
    BUS_EVENTS_1_FLAG = 0x604, Register32
    BUS_EVENTS_2_FLAG = 0x608, Register32
    BUS_EVENTS_3_FLAG = 0x60c, Register32
    BUS_EVENTS_4_FLAG = 0x610, Register32
    BUS_EVENTS_5_FLAG = 0x614, Register32
    BUS_EVENTS_6_FLAG = 0x618, Register32
    BUS_EVENTS_7_FLAG = 0x61c, Register32
    IRQ_FLAG          = 0x620, IRQs

    CURSORS_TX        = 0x800, R_CURSORS
    ''' [RO] write cursors for the two FIFOs '''
    CURSORS_RX        = 0x804, R_CURSORS
    ''' [RO] read cursors for the two FIFOs '''
    PEEK_POS          = 0x808, R_PEEK_POS
    ''' [RW] selects word to peek '''
    PEEK_VALUE        = 0x80c, Register32
    ''' [RO] current value at word selected by PEEK_POS '''
