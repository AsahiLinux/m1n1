from ..utils import *

__all__ = ["I2C", "I2CRegs"]


class R_FIFO_TX(Register32):
    READ  = 10
    STOP  = 9
    START = 8
    DATA  = 7, 0

class R_FIFO_RX(Register32):
    EMPTY = 8
    DATA  = 7, 0

class R_STATUS(Register32):
    XFER_READY = 27

class R_CONTROL(Register32):
    ENABLE   = 11
    CLEAR_RX = 10
    CLEAR_TX = 9
    CLOCK    = 7, 0

class I2CRegs(RegMap):
    FIFO_TX = 0x00, R_FIFO_TX
    FIFO_RX = 0x04, R_FIFO_RX
    STATUS  = 0x14, R_STATUS
    CONTROL = 0x1c, R_CONTROL


class I2C:
    def __init__(self, u, adt_path):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.base = u.adt[adt_path].get_reg(0)[0]
        self.regs = I2CRegs(u, self.base)

    def clear_fifos(self):
        self.regs.CONTROL.set(CLEAR_TX=1, CLEAR_RX=1)

    def clear_status(self):
        self.regs.STATUS.val = 0xffffffff

    def _fifo_read(self, nbytes):
        read = []
        for _ in range(nbytes):
            val = self.regs.FIFO_RX.reg
            timeout = 10000
            while val.EMPTY and timeout > 0:
                val = self.regs.FIFO_RX.reg
                timeout -= 1
            if timeout == 0:
                raise Exception("timeout")
            read.append(int(val) & 0xff)
        return bytes(read)

    def _fifo_write(self, buf, stop=False):
        for no, byte in enumerate(buf):
            sending_stop = stop and no == len(buf) - 1
            self.regs.FIFO_TX.set(DATA=byte, STOP=int(sending_stop))

        if not stop:
            return

        timeout = 10000
        while not self.regs.STATUS.reg.XFER_READY and timeout > 0:
            timeout -= 1
        if timeout == 0:
            raise Exception("timeout")

    def write_reg(self, addr, reg, data):
        self.clear_fifos()
        self.clear_status()

        self.regs.CONTROL.set(ENABLE=1, CLOCK=0x4)
        self.regs.FIFO_TX.set(DATA=addr << 1, START=1)
        self._fifo_write(bytes([reg]) + bytes(data), stop=True)
        self.regs.CONTROL.set(ENABLE=0, CLOCK=0x4)

    def read_reg(self, addr, reg, nbytes):
        self.clear_fifos()
        self.clear_status()

        self.regs.CONTROL.set(ENABLE=1, CLOCK=0x4)
        self.regs.FIFO_TX.set(DATA=addr << 1, START=1)
        self._fifo_write(bytes([reg]), stop=True)
        self.regs.FIFO_TX.set(DATA=(addr << 1) | 1, START=1)
        self.regs.FIFO_TX.set(DATA=nbytes, STOP=1, READ=1)
        data = self._fifo_read(nbytes)
        self.regs.CONTROL.set(ENABLE=0, CLOCK=0x4)
        return data
