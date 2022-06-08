# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum

__all__ = ["I2C", "I2CRegs"]


class R_MTXFIFO(Register32):
    READ    = 10        # Read (DATA=count)
    STOP    = 9         # Issue START before
    START   = 8         # Issue STOP after
    DATA    = 7, 0      # Byte to send or count

class R_MRXFIFO(Register32):
    EMPTY   = 8         # FIFO empty
    DATA    = 7, 0      # FIFO data

class R_MCNT(Register32):
    S_RXCNT = 31, 24    # Slave RX count
    S_TXCNT = 23, 16    # Slave TX count
    M_RXCNT = 15, 8     # Master RX count
    M_TXCNT = 7, 0      # Master TX count

class E_MST(IntEnum):
    IDLE    = 0
    FRD1    = 1
    FRD2    = 2
    COMMAND = 3
    START   = 4
    WRITE   = 5
    READ    = 6
    ACK     = 7
    STOP    = 8
    BAD     = 15

class E_SST(IntEnum):
    IDLE    = 0
    START   = 1
    ST_ACK  = 2
    DATA    = 3
    ACK     = 4

class R_XFSTA(Register32):
    MST     = 27, 24, E_MST # Master controller state
    SRD     = 20            # Slave read in progress
    SWR     = 19            # Slave write in progress
    SST     = 18, 16, E_SST # Slave controller state
    XFIFO   = 9, 8          # FIFO number for error
    XFCNT   = 7, 0          # Number of bytes in current xfer

class R_SADDR(Register32):
    DEB     = 31            # Enable SDA/SCL read debug
    DIR     = 30            # Direct (bitbang) mode
    ENS     = 29            # Enable slave interface
    RST_STX = 28            # Reset slave TX FIFO
    RST_SRX = 27            # Reset master RX fifo (if ^ both, controller too)
    PEN     = 26            # Promiscuous mode (slave)
    AAE     = 25            # SALT/ALTMASK enable
    SAE     = 24            # SADDR enable
    ALTMASK = 23, 16        # MASK for SALT bits
    SALT    = 15, 8         # Alt slave address
    SADDR   = 7, 0          # Slave address

class R_SMSTA(Register32):
    XIP     = 28            # Xaction in progress
    XEN     = 27            # Xaction ended
    UJF     = 26            # UnJam failure
    JMD     = 25            # Jam ocurred
    JAM     = 24            # Currently jammed
    MTO     = 23            # Master timeout
    MTA     = 22            # Master arb lost
    MTN     = 21            # Master received NACK
    MRF     = 20            # Master RX fifo full
    MRNE    = 19            # Master RX fifo not empty
    MTF     = 17            # Master TX fifo full
    MTE     = 16            # Master RX fifo empty
    STO     = 15            # Slave timeout
    STA     = 14            # Slave arb lost
    STN     = 13            # Slave received NACK
    SRF     = 12            # Slave RX fifo full
    SRNE    = 11            # Slave RX fifo not empty
    STR     = 10            # Slave transmit required
    STF     = 9             # Slave TX fifo full
    STE     = 8             # Slave TX fifo empty
    TOS     = 7             # Timeout due to slave FIFO
    TOM     = 6             # Timeout due to master FIFO
    TOE     = 5             # Slave timeout due to ext clock stretch
    DCI     = 4             # Direct clock in
    DDI     = 3             # Direct data in
    DCO     = 2             # Direct clock out
    DDO     = 1             # Direct data out
    NN      = 0             # NACK next (slave)

class R_CTL(Register32):
    MSW     = 26, 16        # Maximum slave write size
    ENABLE  = 11            # Unknown enable bit (clock sel? Apple thing)
    MRR     = 10            # Master receive FIFO reset
    MTR     = 9             # Master transmit FIFO reset
    UJM     = 8             # Enable auto unjam machine
    CLK     = 7, 0          # Clock divider

class R_STXFIFO(Register32):
    DATA    = 7, 0          # Data

class R_SRXFIFO(Register32):
    N       = 12            # NACK received after this byte
    P       = 11            # Stop received, data not valid
    S       = 10            # Start received before
    O       = 9             # Overflow (promisc only)
    E       = 8             # Empty (data not valid)
    DATA    = 7, 0          # Data

# Apple reg
class R_FIFOCTL(Register32):
    HALT    = 0             # Halt machinery

class I2CRegs(RegMap):
    MTXFIFO = 0x00, R_MTXFIFO
    MRXFIFO = 0x04, R_MRXFIFO
    MCNT    = 0x08, R_MCNT
    XFSTA   = 0x0c, R_XFSTA
    SADDR   = 0x10, R_SADDR
    SMSTA   = 0x14, R_SMSTA
    IMASK   = 0x18, R_SMSTA
    CTL     = 0x1c, R_CTL
    STXFIFO = 0x20, R_STXFIFO
    SRXFIFO = 0x20, R_SRXFIFO
    FIFOCTL = 0x44, R_FIFOCTL


class I2C:
    def __init__(self, u, adt_path):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.base = u.adt[adt_path].get_reg(0)[0]
        self.regs = I2CRegs(u, self.base)
        self.devs = []

    def clear_fifos(self):
        self.regs.CTL.set(MTR=1, MRR=1)

    def clear_status(self):
        self.regs.SMSTA.val = 0xffffffff

    def _fifo_read(self, nbytes):
        read = []
        for _ in range(nbytes):
            val = self.regs.MRXFIFO.reg
            timeout = 10000
            while val.EMPTY and timeout > 0:
                val = self.regs.MRXFIFO.reg
                timeout -= 1
            if timeout == 0:
                raise Exception("timeout")
            read.append(int(val) & 0xff)
        return bytes(read)

    def _fifo_write(self, buf, stop=False):
        for no, byte in enumerate(buf):
            sending_stop = stop and no == len(buf) - 1
            self.regs.MTXFIFO.set(DATA=byte, STOP=int(sending_stop))

        if not stop:
            return

        timeout = 10000
        while not self.regs.SMSTA.reg.XEN and timeout > 0:
            timeout -= 1
        if timeout == 0:
            raise Exception("timeout")

    def write_reg(self, addr, reg, data, regaddrlen=1):
        self.clear_fifos()
        self.clear_status()

        self.regs.CTL.set(ENABLE=1, CLK=0x4)
        self.regs.MTXFIFO.set(DATA=addr << 1, START=1)
        regbytes = int.to_bytes(reg, regaddrlen, byteorder="big")
        self._fifo_write(regbytes + bytes(data), stop=True)
        self.regs.CTL.set(ENABLE=0, CLK=0x4)

    def read_reg(self, addr, reg, nbytes, regaddrlen=1):
        self.clear_fifos()
        self.clear_status()

        self.regs.CTL.set(ENABLE=1, CLK=0x4)
        self.regs.MTXFIFO.set(DATA=addr << 1, START=1)
        regbytes = int.to_bytes(reg, regaddrlen, byteorder="big")
        self._fifo_write(regbytes, stop=False)
        self.regs.MTXFIFO.set(DATA=(addr << 1) | 1, START=1)
        self.regs.MTXFIFO.set(DATA=nbytes, STOP=1, READ=1)
        data = self._fifo_read(nbytes)
        self.regs.CTL.set(ENABLE=0, CLK=0x4)
        return data

class I2CRegMapDev:
    REGMAP = None
    ADDRESSING = (0, 1)

    def __init__(self, bus, addr, name=None):
        self.bus = bus
        self.addr = addr
        self.curr_page = None
        self.name = name

        self.paged, self.regimmbytes = self.ADDRESSING
        if self.REGMAP is not None:
            self.regs = self.REGMAP(self, 0)

    @classmethod
    def from_adt(cls, bus, path):
        node = bus.u.adt[path]
        addr = node.reg[0] & 0xff
        return cls(bus, addr, node.name)

    def _switch_page(self, page):
        assert self.paged
        self.bus.write_reg(self.addr, 0, bytes([page]),
                            regaddrlen=self.regimmbytes)
        self.curr_page = page

    def _snip_regaddr(self, addr):
        pageshift = self.regimmbytes * 8
        page = addr >> pageshift
        immediate = addr & ~(~0 << pageshift)
        return (page, immediate)

    def write(self, reg, val, width=8):
        page, imm = self._snip_regaddr(reg)

        if self.paged and page != self.curr_page:
            self._switch_page(page)

        valbytes = val.to_bytes(width//8, byteorder="little")
        self.bus.write_reg(self.addr, imm, valbytes,
                            regaddrlen=self.regimmbytes)

    def read(self, reg, width=8):
        page, imm = self._snip_regaddr(reg)

        if self.paged and page != self.curr_page:
            self._switch_page(page)

        data = self.bus.read_reg(self.addr, imm, width//8,
                                    regaddrlen=self.regimmbytes)
        return int.from_bytes(data, byteorder='little')

    def __repr__(self):
        label = self.name or f"@ {self.addr:02x}"
        return f"<{type(self).__name__} {label}>"
