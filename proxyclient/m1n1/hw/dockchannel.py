# SPDX-License-Identifier: MIT
import struct

from ..utils import *

__all__ = ["DockChannel"]

# DockChannel layout:
# 00000 : Global regs

# 08000 : IRQ regs (0)
# 0c000 : IRQ regs (1)
# 10000 : IRQ regs (2)
# 14000 : IRQ regs (3) -> AIC #0
# 18000 : IRQ regs (4) -> AIC #1
# 1c000 : IRQ regs (5) (not always present)

# 28000 : FIFO regs (1A)
# 2c000 : Data regs (1A)
# 30000 : FIFO regs (1B)
# 34000 : Data regs (1B)
# 38000 : FIFO regs (2A)
# 3c000 : Data regs (2A)
# 40000 : FIFO regs (2B)
# 44000 : Data regs (2B)
# (possibly more)

class R_RX_DATA(Register32):
    DATA        = 31, 8
    COUNT       = 7, 0

class DockChannelIRQRegs(RegMap):
    IRQ_MASK    = 0x0, Register32
    IRQ_FLAG    = 0x4, Register32

class DockChannelConfigRegs(RegMap):
    TX_THRESH   = 0x0, Register32
    RX_THRESH   = 0x4, Register32

class DockChannelDataRegs(RegMap):
    TX_8        = 0x4, Register32
    TX_16       = 0x8, Register32
    TX_24       = 0xc, Register32
    TX_32       = 0x10, Register32
    TX_FREE     = 0x14, Register32
    RX_8        = 0x1c, R_RX_DATA
    RX_16       = 0x20, R_RX_DATA
    RX_24       = 0x24, R_RX_DATA
    RX_32       = 0x28, Register32
    RX_COUNT    = 0x2c, Register32

class DockChannel:
    def __init__(self, u, irq_base, fifo_base, irq_idx):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.config = DockChannelConfigRegs(u, fifo_base)
        self.data = DockChannelDataRegs(u, fifo_base + 0x4000)
        self.irq = DockChannelIRQRegs(u, irq_base)
        self.irq_idx = irq_idx
        self.irq.IRQ_MASK.val = 3 << (irq_idx * 2)

    @property
    def tx_irq(self):
        self.irq.IRQ_FLAG.val = 1 << (self.irq_idx * 2)
        return self.irq.IRQ_FLAG.val & (1 << (self.irq_idx * 2))

    @property
    def rx_irq(self):
        self.irq.IRQ_FLAG.val = 2 << (self.irq_idx * 2)
        return self.irq.IRQ_FLAG.val & (2 << (self.irq_idx * 2))

    @property
    def rx_count(self):
        return self.data.RX_COUNT.val

    @property
    def tx_free(self):
        return self.data.TX_FREE.val

    def set_tx_thresh(self, v):
        self.config.TX_THRESH.val = v

    def set_rx_thresh(self, v):
        self.config.RX_THRESH.val = v

    def write(self, data):
        p = 0
        left = len(data)
        while left >= 4:
            while self.tx_free < 4:
                pass
            d = struct.unpack("<I", data[p:p+4])[0]
            self.data.TX_32.val = d
            p += 4
            left -= 4
        while left >= 1:
            while self.tx_free < 1:
                pass
            self.data.TX_8.val = data[p]
            p += 1
            left -= 1

    def read(self, count):
        data = []
        left = count
        while left >= 4:
            while self.rx_count < 4:
                pass
            data.append(struct.pack("<I", self.data.RX_32.val))
            left -= 4
        while left >= 1:
            while self.rx_count < 1:
                pass
            data.append(bytes([self.data.RX_8.DATA]))
            left -= 1
        return b"".join(data)

    def read_all(self):
        return self.read(self.rx_count)
