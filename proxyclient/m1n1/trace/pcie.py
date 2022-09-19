from . import Tracer, TraceMode
from ..utils import *

class R_BAR(Register32):
    BASE        = 31, 4
    PREFETCH    = 3
    ADDR64      = 2
    BELOW_1M    = 1
    SPACE       = 0

class PCICfgSpace(RegMap):
    VENDOR_ID   = 0x00, Register16
    PRODUCT_ID  = 0x02, Register16
    COMMAND     = 0x04, Register16
    STATUS      = 0x06, Register16

    BAR         = irange(0x10, 6, 4), R_BAR
    ROMADDR     = 0x30, Register32

class PCIeDevTracer(Tracer):
    CFGMAP = PCICfgSpace
    BARMAPS = []
    NAMES = []
    PREFIXES = []

    def __init__(self, hv, apcie, bus, dev, fn, verbose=False):
        super().__init__(hv, verbose=verbose, ident=f"{type(self).__name__}@{apcie}/{bus:02x}:{dev:02x}.{fn:1x}")
        self.busn = bus
        self.devn = dev
        self.fn = fn
        self.ecam_off = (bus << 20) | (dev << 15) | (fn << 12)
        self.apcie = hv.adt[apcie]
        self.bars = [0] * 6
        self.bar_ranges = [None] * 6
        self.cfg_space = self.CFGMAP(hv.u, self.apcie.get_reg(0)[0] + self.ecam_off)
        self.verbose = 3

    def init_state(self):
        self.state.bars = [R_BAR(0) for i in range(6)]
        self.state.barsize = [None] * 6

    @classmethod
    def _reloadcls(cls, force=False):
        cls.BARMAPS = [i._reloadcls(force) if i else None for i in cls.BARMAPS]
        return super()._reloadcls(force)

    def r_cfg_BAR(self, val, index):
        if self.state.bars[index].BASE == 0xfffffff:
            size = (0x10000000 - val.BASE) << 4
            self.log(f"BAR{index} size = {size:#x}")
            self.state.barsize[index] = size

    def w_cfg_BAR(self, val, index):
        self.state.bars[index] = val
        self.update_tracers(val, index)

    def update_tracers(self, val = None, index = None):
        self.hv.clear_tracers(self.ident)
        ecam = self.apcie.get_reg(0)[0]
        self.trace_regmap(ecam + self.ecam_off, 0x1000, self.CFGMAP, prefix="cfg",
                          mode=TraceMode.WSYNC)
        i = 0
        while i < 6:
            idx = i
            if i == index:
                bar = val
            else:
                bar = self.cfg_space.BAR[i].reg
            addr = bar.BASE << 4
            if bar.ADDR64 and i != 5:
                if i + 1 == index:
                    barh = val
                else:
                    barh = self.cfg_space.BAR[i + 1].reg
                addr |= barh.value << 32
                i += 2
            else:
                i += 1

            if addr in (0, 0xfffffff0, 0xffffffff00000000, 0xfffffffffffffff0):
                continue

            size = self.state.barsize[idx]

            if not size:
                self.log(f"BAR{idx} size is unknown!")
                continue

            # Add in PCIe DT addr flags to get the correct translation
            start = self.apcie.translate(addr | (0x02 << 88))

            self.log(f"Tracing BAR{idx} : {addr:#x} -> {start:#x}..{start+size-1:#x}")
            self.bar_ranges[idx] = irange(start, size)
            self.trace_bar(idx, start, size)

    def trace_bar(self, idx, start, size):
        if idx >= len(self.BARMAPS) or (regmap := self.BARMAPS[idx]) is None:
            return
        prefix = name = None
        if idx < len(self.NAMES):
            name = self.NAMES[i]
        if idx < len(self.PREFIXES):
            prefix = self.PREFIXES[i]

        self.trace_regmap(start, size, regmap, name=name, prefix=prefix)

    def start(self):
        self.update_tracers()
