# SPDX-License-Identifier: MIT
import struct
from construct import *
from copy import deepcopy

def round_up(x, y): return ((x + (y - 1)) & (-y))
def round_down(x, y): return (x - (x % y))

AOPBootargsItem = Struct(
    "key" / PaddedString(4, "utf8"),
    "size" / Int32ul,
)

class AOPBootargs:
    def __init__(self, bytes_):
        self.blob = bytearray(bytes_)
        self.index = self.build_index(self.blob)

    def build_index(self, blob):
        off = 0
        fields = []
        while off < len(blob):
            item = AOPBootargsItem.parse(blob[off:off+AOPBootargsItem.sizeof()])
            off += AOPBootargsItem.sizeof()
            fields.append((item.key, (off, item.size)))
            off += item.size
        if off > len(blob):
            raise ValueError('blob overran during parsing')
        return dict(fields)

    def items(self):
        for key, span in self.index.items():
            off, length = span
            yield key, self.blob[off:off + length]

    def __getitem__(self, key):
        off, length = self.index[key]
        return bytes(self.blob[off:off + length])

    def __setitem__(self, key, value):
        off, length = self.index[key]
        if type(value) is int:
            value = int.to_bytes(value, length, byteorder='little')
        elif type(value) is str:
            value = value.encode('ascii')
        if len(value) > length:
            raise ValueError(f'field {key:s} overflown')
        self.blob[off:off + length] = value

    def update(self, keyvals):
        for key, val in keyvals.items():
            self[key] = val

    def keys(self):
        return self.index.keys()

    def dump(self, logger):
        for key, val in self.items():
            logger(f"{key:4s} = {val}")

    def dump_diff(self, other, logger):
        assert self.index == other.index
        for key in self.keys():
            if self[key] != other[key]:
                logger(f"\t{key:4s} = {self[key]} -> {other[key]}")

    def to_bytes(self):
        return bytes(self.blob)

class AOPBase:
    def __init__(self, u):
        self.u = u
        self.nub_base = u.adt["/arm-io/aop/iop-aop-nub"].region_base
        if u.adt["arm-io"].compatible[0] == "arm-io,t6000":
            # argh
            self.nub_base -= 0x2_0000_0000

    @property
    def _bootargs_span(self):
        """
        [cpu1] MMIO: R.4   0x24ac0022c (aop[2], offset 0x22c) = 0xaffd8 // offset
        [cpu1] MMIO: R.4   0x24ac00230 (aop[2], offset 0x230) = 0x2ae // size
        [cpu1] MMIO: R.4   0x24ac00234 (aop[2], offset 0x234) = 0x82000 // va? low
        [cpu1] MMIO: R.4   0x24ac00238 (aop[2], offset 0x238) = 0x0 // va? high
        [cpu1] MMIO: R.4   0x24ac0023c (aop[2], offset 0x23c) = 0x4ac82000 // phys low
        [cpu1] MMIO: R.4   0x24ac00240 (aop[2], offset 0x240) = 0x2 // phys high
        [cpu1] MMIO: W.4   0x24acaffd8 (aop[2], offset 0xaffd8) = 0x53544b47 // start of bootargs
        [cpu1] MMIO: W.4   0x24acaffdc (aop[2], offset 0xaffdc) = 0x8
        [cpu1] MMIO: W.4   0x24acaffe0 (aop[2], offset 0xaffe0) = 0x73eed2a3
        ...
        [cpu1] MMIO: W.4   0x24acb0280 (aop[2], offset 0xb0280) = 0x10000
        [cpu1] MMIO: W.4   0x24acb0284 (aop[2], offset 0xb0284) = 0x0 // end of bootargs
        """
        offset = self.u.proxy.read32(self.nub_base + 0x22c) # 0x224 in 12.3
        size = self.u.proxy.read32(self.nub_base + 0x230) # 0x228 in 12.3
        return (self.nub_base + offset, size)

    def read_bootargs(self):
        addr, size = self._bootargs_span
        blob = self.u.proxy.iface.readmem(addr, size)
        return AOPBootargs(blob)

    def write_bootargs(self, args):
        base, _ = self._bootargs_span
        self.u.proxy.iface.writemem(base, args.to_bytes())

    def update_bootargs(self, keyval, logger=print):
        args = self.read_bootargs()
        old = deepcopy(args)
        args.update(keyval)
        self.write_bootargs(args)
        old.dump_diff(args, logger)
