# SPDX-License-Identifier: MIT
import struct

from ..utils import *

__all__ = ["SPMI"]

CMD_RESET       = 0x10
CMD_SLEEP       = 0x11
CMD_SHUTDOWN    = 0x12
CMD_WAKEUP      = 0x13

CMD_SLAVE_DESC  = 0x1c

CMD_EXT_WRITE   = 0x00
CMD_EXT_READ    = 0x20
CMD_EXT_WRITEL  = 0x30
CMD_EXT_READL   = 0x38
CMD_WRITE       = 0x40
CMD_READ        = 0x60
CMD_ZERO_WRITE  = 0x80

class R_CMD(Register32):
    EXTRA       = 31, 16
    ACTIVE      = 15
    SLAVE_ID    = 14, 8
    CMD         = 7, 0

class R_REPLY(Register32):
    FRAME_PARITY = 31, 16
    ACK          = 15
    SLAVE_ID     = 14, 8
    CMD          = 7, 0

class R_STATUS(Register32):
    RX_EMPTY    = 24
    RX_COUNT    = 23, 16
    TX_EMPTY    = 8
    TX_COUNT    = 7, 0

class SPMIRegs(RegMap):
    STATUS      = 0x00, R_STATUS
    CMD         = 0x04, R_CMD
    REPLY       = 0x08, R_REPLY
    IRQ_FLAG    = 0x80, Register32

class SPMI:
    def __init__(self, u, adt_path):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.base = u.adt[adt_path].get_reg(0)[0]
        self.regs = SPMIRegs(u, self.base)

    def raw_read(self) -> int:
        for _ in range(1000):
            if not self.regs.STATUS.reg.RX_EMPTY:
                return self.regs.REPLY.val
        raise Exception('timeout waiting for data on RX FIFO')

    def raw_command(self, slave: int, cmd: int, extra=0, data=b"", size=0, active=True):
        while not self.regs.STATUS.reg.RX_EMPTY:
            print(">", self.regs.REPLY.val)

        assert 0 <= slave < 16 and 0 <= cmd < 256 and 0 <= extra < 0x10000
        self.regs.CMD.reg = R_CMD(EXTRA=extra, ACTIVE=active, SLAVE_ID=slave, CMD=cmd)

        while data:
            blk = (data[:4] + b"\0\0\0")[:4]
            self.regs.CMD.val = struct.unpack("<I", blk)[0]
            data = data[4:]

        reply = R_REPLY(self.raw_read())
        assert reply.SLAVE_ID == slave and reply.CMD == cmd

        buf = b""
        left = size
        while left > 0:
            buf += struct.pack("<I", self.raw_read())
            left -= 4

        if reply.FRAME_PARITY != (1 << size) - 1:
            raise Exception(f'some response frames failed parity check: {reply.FRAME_PARITY:b}')
        assert not any(buf[size:])
        return reply.ACK, buf[:size]

    # for these commands, extra is empty

    def reset(self, slave: int):
        return self.raw_command(slave, CMD_RESET)[0]

    def sleep(self, slave: int):
        return self.raw_command(slave, CMD_SLEEP)[0]

    def shutdown(self, slave: int):
        return self.raw_command(slave, CMD_SHUTDOWN)[0]

    def wakeup(self, slave: int):
        return self.raw_command(slave, CMD_WAKEUP)[0]

    def get_descriptor(self, slave: int):
        return self.raw_command(slave, CMD_SLAVE_DESC, size=10)[1]

    # for these commands: extra[7..0] = register address, extra[15..8] = value

    def read_reg(self, slave: int, reg: int):
        ''' perform a register read command '''
        assert 0 <= reg < 32
        cmd = CMD_READ | reg
        return self.raw_command(slave, cmd, reg, size=1)[1][0]

    def write_reg(self, slave: int, reg: int, value: int):
        ''' perform a register write command '''
        assert 0 <= reg < 32 and 0 <= value < 0x100
        cmd = CMD_WRITE | reg
        return self.raw_command(slave, cmd, reg | value << 8)[0]

    def write_zero(self, slave: int, value: int):
        ''' perform a register 0 write command '''
        assert 0 <= value < 0x80
        cmd = CMD_ZERO_WRITE | value
        return self.raw_command(slave, cmd, value << 8)[0]

    # for these commands, extra = register address

    def read_ext(self, slave: int, reg: int, size: int):
        ''' perform an extended read command '''
        assert 1 <= size <= 16 and 0 <= reg < 0x100
        cmd = CMD_EXT_READ | (size - 1)
        return self.raw_command(slave, cmd, reg, size=size)[1]

    def write_ext(self, slave: int, reg: int, data: bytes):
        ''' perform an extended write command '''
        size = len(data)
        assert 1 <= size <= 16 and 0 <= reg < 0x100
        cmd = CMD_EXT_WRITE | (size - 1)
        return self.raw_command(slave, cmd, reg, data=data)[0]

    def read_extl(self, slave: int, reg: int, size: int):
        ''' perform an extended read long command '''
        assert 1 <= size <= 8 and 0 <= reg < 0x10000
        cmd = CMD_EXT_READL | (size - 1)
        return self.raw_command(slave, cmd, reg, size=size)[1]

    def write_extl(self, slave: int, reg: int, data: bytes):
        ''' perform an extended write long command '''
        size = len(data)
        assert 1 <= size <= 8 and 0 <= reg < 0x10000
        cmd = CMD_EXT_WRITEL | (size - 1)
        return self.raw_command(slave, cmd, reg, data=data)[0]

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
