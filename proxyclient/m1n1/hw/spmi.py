# SPDX-License-Identifier: MIT
import struct

from ..utils import *

__all__ = ["SPMI"]

OPC_RESET       = 0x10
OPC_SLEEP       = 0x11
OPC_SHUTDOWN    = 0x12
OPC_WAKEUP      = 0x13

OPC_SLAVE_DESC  = 0x1c

OPC_EXT_WRITE   = 0x00
OPC_EXT_READ    = 0x20
OPC_EXT_WRITEL  = 0x30
OPC_EXT_READL   = 0x38
OPC_WRITE       = 0x40
OPC_READ        = 0x60
OPC_ZERO_WRITE  = 0x80

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

class SPMIRegs(RegMap):
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

class SPMI:
    def __init__(self, u, adt_path):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.adt = u.adt[adt_path]
        self.base = self.adt.get_reg(0)[0]
        self.regs = SPMIRegs(u, self.base)

    def raw_read(self) -> int:
        for _ in range(1000):
            if not self.regs.STATUS.reg.RX_EMPTY:
                return self.regs.REPLY.val
        raise Exception('timeout waiting for data on RX FIFO')

    def raw_command(self, slave: int, opc: int, extra=0, data=b"", size=0, alert=True):
        while not self.regs.STATUS.reg.RX_EMPTY:
            print(">", self.regs.REPLY.val)

        assert 0 <= slave < 16 and 0 <= opc < 256 and 0 <= extra < 0x10000
        self.regs.CMD.reg = R_CMD(EXTRA=extra, ALERT=alert, SLAVE_ID=slave, OPCODE=opc)

        while data:
            blk = (data[:4] + b"\0\0\0")[:4]
            self.regs.CMD.val = struct.unpack("<I", blk)[0]
            data = data[4:]

        reply = R_REPLY(self.raw_read())
        assert reply.SLAVE_ID == slave and reply.OPCODE == opc

        buf = b""
        left = size
        while left > 0:
            buf += struct.pack("<I", self.raw_read())
            left -= 4

        if reply.FRAME_PARITY != (1 << size) - 1:
            raise Exception(f'some response frames were not received correctly: {reply.FRAME_PARITY:b}')
        assert not any(buf[size:])
        if not size != bool(reply.ACK):
            raise Exception(f'command not acknowledged')
        return buf[:size] or None

    # for these commands, extra is empty

    def reset(self, slave: int):
        return self.raw_command(slave, OPC_RESET)

    def sleep(self, slave: int):
        return self.raw_command(slave, OPC_SLEEP)

    def shutdown(self, slave: int):
        return self.raw_command(slave, OPC_SHUTDOWN)

    def wakeup(self, slave: int):
        return self.raw_command(slave, OPC_WAKEUP)

    def get_descriptor(self, slave: int):
        return self.raw_command(slave, OPC_SLAVE_DESC, size=10)

    # for these commands: extra[7..0] = register address, extra[15..8] = value

    def read_reg(self, slave: int, reg: int):
        ''' perform a register read command '''
        assert 0 <= reg < 32
        opc = OPC_READ | reg
        return self.raw_command(slave, opc, reg, size=1)[0]

    def write_reg(self, slave: int, reg: int, value: int):
        ''' perform a register write command '''
        assert 0 <= reg < 32 and 0 <= value < 0x100
        opc = OPC_WRITE | reg
        return self.raw_command(slave, opc, reg | value << 8)

    def write_zero(self, slave: int, value: int):
        ''' perform a register 0 write command '''
        assert 0 <= value < 0x80
        opc = OPC_ZERO_WRITE | value
        return self.raw_command(slave, opc, value << 8)

    # for these commands, extra = register address

    def read_ext(self, slave: int, reg: int, size: int):
        ''' perform an extended read command '''
        assert 1 <= size <= 16 and 0 <= reg < 0x100
        opc = OPC_EXT_READ | (size - 1)
        return self.raw_command(slave, opc, reg, size=size)

    def write_ext(self, slave: int, reg: int, data: bytes):
        ''' perform an extended write command '''
        size = len(data)
        assert 1 <= size <= 16 and 0 <= reg < 0x100
        opc = OPC_EXT_WRITE | (size - 1)
        return self.raw_command(slave, opc, reg, data=data)

    def read_extl(self, slave: int, reg: int, size: int):
        ''' perform an extended read long command '''
        assert 1 <= size <= 8 and 0 <= reg < 0x10000
        opc = OPC_EXT_READL | (size - 1)
        return self.raw_command(slave, opc, reg, size=size)

    def write_extl(self, slave: int, reg: int, data: bytes):
        ''' perform an extended write long command '''
        size = len(data)
        assert 1 <= size <= 8 and 0 <= reg < 0x10000
        opc = OPC_EXT_WRITEL | (size - 1)
        return self.raw_command(slave, opc, reg, data=data)

    # convenience functions

    def read8(self, slave, reg):
        return struct.unpack("<B", self.read_extl(slave, reg, 1))[0]

    def read16(self, slave, reg):
        return struct.unpack("<H", self.read_extl(slave, reg, 2))[0]

    def read32(self, slave, reg):
        return struct.unpack("<I", self.read_extl(slave, reg, 4))[0]

    def read64(self, slave, reg):
        return struct.unpack("<Q", self.read_extl(slave, reg, 8))[0]

    def write8(self, slave, reg, val):
        return self.write_extl(slave, reg, struct.pack("<B", val))

    def write16(self, slave, reg, val):
        return self.write_extl(slave, reg, struct.pack("<H", val))

    def write32(self, slave, reg, val):
        return self.write_extl(slave, reg, struct.pack("<I", val))

    def write64(self, slave, reg, val):
        return self.write_extl(slave, reg, struct.pack("<Q", val))

    # FIFO debug interfaces

    def clear_fifos(self):
        self.regs.ACTION1.val = R_ACTION(CLEAR_FIFOS=1)

    def peek(self, fifo_idx: int, cursor: int) -> int:
        assert 0 <= fifo_idx < 2
        assert 0 <= cursor < 64
        self.regs.PEEK_POS.val = R_PEEK_POS(FIFO_IDX=fifo_idx, BUFFER_POS=cursor)
        return self.regs.PEEK_VALUE.val
