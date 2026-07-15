# SPDX-License-Identifier: MIT
from ..utils import *

class R_CMD(Register32):
    EXTRA       = 31, 16
    ALERT       = 15
    SLAVE_ID    = 11, 8
    OPCODE      = 7, 0

class R_REPLY(Register32):
    FRAME_PARITY = 31, 16
    ACK          = 15
    SLAVE_ID     = 14, 8
    OPCODE       = 7, 0

class R_STATUS(Register32):
    RX_FULL     = 25
    RX_EMPTY    = 24
    RX_COUNT    = 23, 16
    TX_FULL     = 9
    TX_EMPTY    = 8
    TX_COUNT    = 7, 0

class R_CURSORS(Register32):
    RX_CURSOR_R    = 29, 24
    RX_CURSOR_W    = 21, 16
    TX_CURSOR_R    = 13,  8
    TX_CURSOR_W    =  5,  0

class R_PEEK_POS(Register32):
    BUFFER_POS = 23, 16
    ''' buffer position to read (0..capacity-1) '''
    FIFO_IDX = 8
    ''' FIFO to read from (0 = TX, 1 = RX) '''

class R_ACTION(Register32):
    CLEAR_FIFOS    = 0

class IRQs(Register32):
    ALERT       = 0  # a command with the ALERT flag completed

    UNK_4       = 4
    UNK_5       = 5
    READ_FAIL_1 = 6  # read command failed
    ACK_FAIL    = 7  # command was not ACKed
    UNK_8       = 8
    UNK_9       = 9
    UNK_10      = 10
    READ_FAIL_2 = 11 # read command failed
    UNK_12      = 12
    UNK_13      = 13

    UNK_16      = 16
    UNK_17      = 17

    FATAL       = 27 # read from RX FIFO while empty. level/sticky interrupt

class SPMI1Regs(RegMap):
    STATUS            = 0x00, R_STATUS
    ''' [RO] status about the RX and TX FIFOs '''
    CMD               = 0x04, R_CMD
    ''' [WO] write 32 bits to the TX FIFO '''
    REPLY             = 0x08, R_REPLY
    ''' [RO] consume 32 bits from the RX FIFO '''

    # setting a bit in one of these registers causes the IRQ line
    # to be asserted whenever the same bit at the register at
    # address +0x40 (see below) is set. clearing a bit only masks
    # the interrupt, but doesn't prevent the bit from being set or
    # cleared in register +0x40. these are zero on boot.
    BUS_EVENTS_0_MASK = 0x20, Register32
    BUS_EVENTS_1_MASK = 0x24, Register32
    BUS_EVENTS_2_MASK = 0x28, Register32
    BUS_EVENTS_3_MASK = 0x2c, Register32
    BUS_EVENTS_4_MASK = 0x30, Register32
    BUS_EVENTS_5_MASK = 0x34, Register32
    BUS_EVENTS_6_MASK = 0x38, Register32
    BUS_EVENTS_7_MASK = 0x3c, Register32
    IRQ_MASK          = 0x40, IRQs

    # bits in these registers are set in response to an event
    # and can be cleared by writing a 1 to them. IRQ_FLAG is
    # for events of the SPMI peripheral itself, while
    # BUS_EVENTS_* is for generic events that can be triggered
    # by other devices in the bus using (I presume) master
    # commands against us, and allow the SPMI peripheral to
    # also act as an interrupt controller
    BUS_EVENTS_0_FLAG = 0x60, Register32
    BUS_EVENTS_1_FLAG = 0x64, Register32
    BUS_EVENTS_2_FLAG = 0x68, Register32
    BUS_EVENTS_3_FLAG = 0x6c, Register32
    BUS_EVENTS_4_FLAG = 0x70, Register32
    BUS_EVENTS_5_FLAG = 0x74, Register32
    BUS_EVENTS_6_FLAG = 0x78, Register32
    BUS_EVENTS_7_FLAG = 0x7c, Register32
    IRQ_FLAG          = 0x80, IRQs

    CONFIG1           = 0xa0, Register32
    ''' [RO] unknown, bits 2..0 settable in T6031, set to 0x6 or 0x7 on boot. master address? '''
    ACTION1           = 0xa4, R_ACTION
    ''' [WO] always reads 0, but writing a 1 to certain bits triggers bit-specific actions '''

    CURSORS           = 0xb0, R_CURSORS
    ''' [RO] read and write cursors for the two FIFOs '''
    PEEK_POS          = 0xb4, R_PEEK_POS
    ''' [RW] selects word to peek '''
    PEEK_VALUE        = 0xb8, Register32
    ''' [RO] current value at word selected by PEEK_POS '''
    STATUS_2          = 0xbc, Register32
    ''' [RO] only bit 0 seen, seems to indicate inability to talk on the bus '''

