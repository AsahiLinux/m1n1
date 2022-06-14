# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *
from ..hw import i2c
from . import ADTDevTracer

class I2CTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.ASYNC
    REGMAPS = [i2c.I2CRegs]
    NAMES = ["i2c"]

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose=verbose)
        self.default_dev = I2CDevTracer()
        self.default_dev.i2c_tracer = self

    def init_state(self):
        self.state.txn = []
        self.state.devices = {}

    def w_MTXFIFO(self, mtxfifo):
        if self.state.txn is None:
            self.state.txn = []

        d = mtxfifo.DATA
        if mtxfifo.START:
            self.state.txn += ["S"]
        if mtxfifo.READ:
            self.state.txn += [None] * d
        else:
            self.state.txn.append(d)
        
        if mtxfifo.STOP:
            self.state.txn.append("P")
            self.flush_txn()

    def r_MRXFIFO(self, mrxfifo):
        if mrxfifo.EMPTY:
            self.log(f"Read while FIFO empty")
            return

        if not self.state.txn:
            self.log(f"Stray read: {mrxfifo}")
            return

        try:
            pos = self.state.txn.index(None)
            self.state.txn[pos] = mrxfifo.DATA
        except ValueError:
            self.log(f"Stray read: {mrxfifo}")

        self.flush_txn()

    def flush_txn(self):
        if not self.state.txn:
            return

        if self.state.txn[-1] != "P":
            return

        if not any(i is None for i in self.state.txn):
            self.handle_txn(self.state.txn)
            self.state.txn = None

    def handle_txn(self, txn):
        st = False
        dev = self.default_dev
        read = False
        for i in txn:
            if i == "S":
                st = True
                continue
            if st:
                addr = i >> 1
                dev = self.state.devices.get(addr, self.default_dev)
                read = bool(i & 1)
                dev.start(addr, read=read)
            elif i == "P":
                dev.stop()
            elif read:
                dev.read(i)
            else:
                dev.write(i)
            st = False

    def add_device(self, addr, device):
        device.hv = self.hv
        device.i2c_tracer = self
        self.state.devices[addr] = device

class I2CDevTracer(Reloadable):
    def __init__(self, addr=None, name=None, verbose=True):
        self.addr = addr
        self.name = name
        self.verbose = verbose
        self.txn = []

    def log(self, msg, *args, **kwargs):
        if self.name:
            msg = f"[{self.name}] {msg}"
        self.i2c_tracer.log(msg, *args, **kwargs)

    def start(self, addr, read):
        self.txn.append("S")
        if read:
            self.txn.append(f"{addr:02x}.r")
        else:
            self.txn.append(f"{addr:02x}.w")

    def stop(self):
        self.txn.append("P")
        if self.verbose:
            self.log(f"Txn: {' '.join(self.txn)}")
        self.txn = []

    def read(self, data):
        self.txn.append(f"{data:02x}")

    def write(self, data):
        self.txn.append(f"{data:02x}")

class I2CRegCache:
    def __init__(self):
        self.cache = {}

    def update(self, addr, data):
        self.cache[addr] = data

    def read(self, addr, width):
        data = self.cache.get(addr, None)
        if data is None:
            print(f"I2CRegCache: no cache for {addr:#x}")
        return data

    def write(self, addr, data, width):
        raise NotImplementedError("No write on I2CRegCache")

class I2CRegMapTracer(I2CDevTracer):
    REGMAP = RegMap
    ADDRESSING = (0, 1)

    def __init__(self, verbose=False, **kwargs):
        super().__init__(verbose=verbose, **kwargs)
        self._cache = I2CRegCache()
        self.regmap = self.REGMAP(self._cache, 0)
        self.page = 0x0
        self.reg = None
        self.regbytes = []

        self.npagebytes, nimmbytes = self.ADDRESSING
        self.pageshift = 8 * nimmbytes
        self.paged = self.npagebytes != 0

    def _reloadme(self):
        self.regmap._reloadme()
        return super()._reloadme()

    def start(self, addr, read):
        if not read:
            self.reg = None
            self.regbytes = []
        super().start(addr, read)

    def stop(self):
        super().stop()

    def handle_addressing(self, data):
        if self.reg is not None:
            return False

        self.regbytes.append(data)
        if len(self.regbytes)*8 >= self.pageshift:
            immediate = int.from_bytes(bytes(self.regbytes),
                                    byteorder="big")
            self.reg = self.page << self.pageshift | immediate
        return True

    @property
    def reg_imm(self):
        '''Returns the 'immediate' part of current register address'''
        return self.reg & ~(~0 << self.pageshift)

    def handle_page_register(self, data):
        if not self.paged:
            return False

        if self.reg_imm >= self.npagebytes:
            return False

        shift = 8 * self.reg_imm
        self.page &= ~(0xff << shift)
        self.page |= data << shift
        return True

    def write(self, data):
        if self.handle_addressing(data):
            return
        elif self.handle_page_register(data):
            pass
        else:
            self.regwrite(self.reg, data)

        self.reg += 1
        super().write(data)

    def read(self, data):
        if self.reg_imm >= self.npagebytes:
            self.regread(self.reg, data)
        self.reg += 1
        super().read(data)

    def regwrite(self, reg, val):
        self.regevent(reg, val, False)

    def regread(self, reg, val):
        self.regevent(reg, val, True)

    def regevent(self, reg, val, read):
        self._cache.update(reg, val)
        r, index, rcls = self.regmap.lookup_addr(reg)
        val = rcls(val) if rcls is not None else f"{val:#x}"
        regname = self.regmap.get_name(reg) if r else f"{reg:#x}"
        t = "R" if read else "W"
        self.log(f"REG: {t.upper()}.8  {regname} = {val!s}")
