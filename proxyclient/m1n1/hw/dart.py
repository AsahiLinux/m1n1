# SPDX-License-Identifier: MIT

import struct

from enum import IntEnum
from ..utils import *
from ..malloc import Heap

from .dart8020 import DART8020, DART8020Regs
from .dart8110 import DART8110, DART8110Regs

__all__ = ["DART"]

class DART(Reloadable):
    PAGE_BITS = 14
    PAGE_SIZE = 1 << PAGE_BITS

    def __init__(self, iface, regs, util=None, compat="dart,t8020", iova_range=(0x80000000, 0x90000000)):
        self.iface = iface
        self.iova_allocator = [Heap(iova_range[0], iova_range[1], self.PAGE_SIZE)
                               for i in range(16)]
        if compat in ["dart,t8020", "dart,t6000"]:
            self.dart = DART8020(iface, regs, util, compat)
        elif compat in ["dart,t8110"]:
            self.dart = DART8110(iface, regs, util)
        else:
            raise TypeError(compat)

    @classmethod
    def from_adt(cls, u, path, instance=0, **kwargs):
        dart_addr = u.adt[path].get_reg(instance)[0]
        compat = u.adt[path].compatible[0]
        if compat in ["dart,t8020", "dart,t6000"]:
            regs = DART8020Regs(u, dart_addr)
        elif compat in ["dart,t8110"]:
            regs = DART8110Regs(u, dart_addr)
        return cls(u.iface, regs, u, compat, **kwargs)

    def ioread(self, stream, base, size):
        if size == 0:
            return b""

        ranges = self.iotranslate(stream, base, size)

        iova = base
        data = []
        for addr, size in ranges:
            if addr is None:
                raise Exception(f"Unmapped page at iova {iova:#x}")
            data.append(self.iface.readmem(addr, size))
            iova += size

        return b"".join(data)

    def iowrite(self, stream, base, data):
        if len(data) == 0:
            return

        ranges = self.iotranslate(stream, base, len(data))

        iova = base
        p = 0
        for addr, size in ranges:
            if addr is None:
                raise Exception(f"Unmapped page at iova {iova:#x}")
            self.iface.writemem(addr, data[p:p + size])
            p += size
            iova += size

    def iomap(self, stream, addr, size):
        iova = self.iova_allocator[stream].malloc(size)

        self.iomap_at(stream, iova, addr, size)
        return iova

    def iomap_at(self, stream, iova, addr, size):
        self.dart.iomap_at(stream, iova, addr, size)

    def iotranslate(self, stream, start, size):
        return self.dart.iotranslate(stream, start, size)

    def initialize(self):
        self.dart.initialize()

    def show_error(self):
        self.dart.show_error()

    def invalidate_streams(self, streams=0xffffffff):
        self.dart.invalidate_streams(streams)

    def invalidate_cache(self):
        self.dart.invalidate_cache()

    def dump_device(self, idx):
        self.dart.dump_device(idx)

    def dump_all(self):
        for i in range(16):
            self.dump_device(i)

    def dump_params(self):
        self.dart.dump_params()
