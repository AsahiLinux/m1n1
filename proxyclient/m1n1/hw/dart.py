# SPDX-License-Identifier: MIT

import struct

from enum import IntEnum
from ..utils import *
from ..malloc import Heap

__all__ = ["DARTRegs", "DART"]

class R_ERROR(Register32):
    FLAG = 31
    STREAM = 27, 24
    CODE = 23, 0
    NO_DAPF_MATCH = 11
    WRITE = 10
    SUBPAGE_PROT = 7
    PTE_READ_FAULT = 6
    READ_FAULT = 4
    WRITE_FAULT = 3
    NO_PTE = 2
    NO_PMD = 1
    NO_TTBR = 0

class R_STREAM_COMMAND(Register32):
    INVALIDATE = 20
    BUSY = 2

class R_TCR(Register32):
    BYPASS_DAPF = 12
    BYPASS_DART = 8
    TRANSLATE_ENABLE = 7

class R_TTBR(Register32):
    VALID = 31
    ADDR = 30, 0

class R_REMAP(Register32):
    MAP3 = 31, 24
    MAP2 = 23, 16
    MAP1 = 15, 8
    MAP0 = 7, 0

class PTE_T8020(Register64):
    SP_START = 63, 52
    SP_END = 51, 40
    OFFSET = 39, 14
    SP_PROT_DIS = 1
    VALID = 0

class PTE_T6000(Register64):
    SP_START = 63, 52
    SP_END = 51, 40
    OFFSET = 39, 10
    SP_PROT_DIS = 1
    VALID = 0

class R_CONFIG(Register32):
    LOCK = 15

class R_DAPF_LOCK(Register32):
    LOCK = 0

class DARTRegs(RegMap):
    STREAM_COMMAND  = 0x20, R_STREAM_COMMAND
    STREAM_SELECT   = 0x34, Register32
    ERROR           = 0x40, R_ERROR
    ERROR_ADDR_LO   = 0x50, Register32
    ERROR_ADDR_HI   = 0x54, Register32
    CONFIG          = 0x60, R_CONFIG
    REMAP           = irange(0x80, 4, 4), R_REMAP

    DAPF_LOCK       = 0xf0, R_DAPF_LOCK
    UNK1            = 0xf8, Register32
    ENABLED_STREAMS = 0xfc, Register32

    TCR             = irange(0x100, 16, 4), R_TCR
    TTBR            = (irange(0x200, 16, 16), range(0, 16, 4)), R_TTBR

PTE_TYPES = {
    "dart,t8020": PTE_T8020,
    "dart,t6000": PTE_T6000,
}

class DART(Reloadable):
    PAGE_BITS = 14
    PAGE_SIZE = 1 << PAGE_BITS

    L0_SIZE = 4 # TTBR count
    L0_OFF = 36
    L1_OFF = 25
    L2_OFF = 14

    IDX_BITS = 11
    Lx_SIZE = (1 << IDX_BITS)
    IDX_MASK = Lx_SIZE - 1

    def __init__(self, iface, regs, util=None, compat="dart,t8020", iova_range=(0x80000000, 0x90000000)):
        self.iface = iface
        self.regs = regs
        self.u = util
        self.pt_cache = {}
        self.enabled_streams = regs.ENABLED_STREAMS.val
        self.iova_allocator = [Heap(iova_range[0], iova_range[1], self.PAGE_SIZE)
                               for i in range(16)]
        self.ptecls = PTE_TYPES[compat]

    @classmethod
    def from_adt(cls, u, path, instance=0, **kwargs):
        dart_addr = u.adt[path].get_reg(instance)[0]
        regs = DARTRegs(u, dart_addr)
        dart = cls(u.iface, regs, u, **kwargs)
        dart.ptecls = PTE_TYPES[u.adt[path].compatible[0]]
        return dart

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
        if size == 0:
            return

        if not (self.enabled_streams & (1 << stream)):
            self.enabled_streams |= (1 << stream)
            self.regs.ENABLED_STREAMS.val |= self.enabled_streams

        tcr = self.regs.TCR[stream].reg

        if tcr.BYPASS_DART and not tcr.TRANSLATE_ENABLE:
            raise Exception("Stream is bypassed in DART")

        if tcr.BYPASS_DART or not tcr.TRANSLATE_ENABLE:
            raise Exception(f"Unknown DART mode {tcr}")

        if addr & (self.PAGE_SIZE - 1):
            raise Exception(f"Unaligned PA {addr:#x}")

        if iova & (self.PAGE_SIZE - 1):
            raise Exception(f"Unaligned IOVA {iova:#x}")

        start_page = align_down(iova, self.PAGE_SIZE)
        end = iova + size
        end_page = align_up(end, self.PAGE_SIZE)

        dirty = set()

        for page in range(start_page, end_page, self.PAGE_SIZE):
            paddr = addr + page - start_page

            l0 = page >> self.L0_OFF
            assert l0 < self.L0_SIZE
            ttbr = self.regs.TTBR[stream, l0].reg
            if not ttbr.VALID:
                l1addr = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
                self.pt_cache[l1addr] = [0] * self.Lx_SIZE
                ttbr.VALID = 1
                ttbr.ADDR = l1addr >> 12
                self.regs.TTBR[stream, l0].reg = ttbr

            cached, l1 = self.get_pt(ttbr.ADDR << 12)
            l1idx = (page >> self.L1_OFF) & self.IDX_MASK
            l1pte = self.ptecls(l1[l1idx])
            if not l1pte.VALID:
                l2addr = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
                self.pt_cache[l2addr] = [0] * self.Lx_SIZE
                l1pte = self.ptecls(
                    OFFSET=l2addr >> self.PAGE_BITS, VALID=1, SP_PROT_DIS=1)
                l1[l1idx] = l1pte.value
                dirty.add(ttbr.ADDR << 12)
            else:
                l2addr = l1pte.OFFSET << self.PAGE_BITS

            dirty.add(l1pte.OFFSET << self.PAGE_BITS)
            cached, l2 = self.get_pt(l2addr)
            l2idx = (page >> self.L2_OFF) & self.IDX_MASK
            self.pt_cache[l2addr][l2idx] = self.ptecls(
                SP_START=0, SP_END=0xfff,
                OFFSET=paddr >> self.PAGE_BITS, VALID=1, SP_PROT_DIS=1).value

        for page in dirty:
            self.flush_pt(page)

    def iotranslate(self, stream, start, size):
        if size == 0:
            return []

        tcr = self.regs.TCR[stream].reg

        if tcr.BYPASS_DART and not tcr.TRANSLATE_ENABLE:
            return [(start, size)]

        if tcr.BYPASS_DART or not tcr.TRANSLATE_ENABLE:
            raise Exception(f"Unknown DART mode {tcr}")

        start = start & 0xffffffff

        start_page = align_down(start, self.PAGE_SIZE)
        start_off = start - start_page
        end = start + size
        end_page = align_up(end, self.PAGE_SIZE)
        end_size = end - (end_page - self.PAGE_SIZE)

        pages = []

        for page in range(start_page, end_page, self.PAGE_SIZE):
            l0 = page >> self.L0_OFF
            assert l0 < self.L0_SIZE
            ttbr = self.regs.TTBR[stream, l0].reg
            if not ttbr.VALID:
                pages.append(None)
                continue

            cached, l1 = self.get_pt(ttbr.ADDR << 12)
            l1pte = self.ptecls(l1[(page >> self.L1_OFF) & self.IDX_MASK])
            if not l1pte.VALID and cached:
                cached, l1 = self.get_pt(ttbr.ADDR << 12, uncached=True)
                l1pte = self.ptecls(l1[(page >> self.L1_OFF) & self.IDX_MASK])
            if not l1pte.VALID:
                pages.append(None)
                continue

            cached, l2 = self.get_pt(l1pte.OFFSET << self.PAGE_BITS)
            l2pte = self.ptecls(l2[(page >> self.L2_OFF) & self.IDX_MASK])
            if not l2pte.VALID and cached:
                cached, l2 = self.get_pt(l1pte.OFFSET << self.PAGE_BITS, uncached=True)
                l2pte = self.ptecls(l2[(page >> self.L2_OFF) & self.IDX_MASK])
            if not l2pte.VALID:
                pages.append(None)
                continue

            pages.append(l2pte.OFFSET << self.PAGE_BITS)

        ranges = []

        for page in pages:
            if not ranges:
                ranges.append((page, self.PAGE_SIZE))
                continue
            laddr, lsize = ranges[-1]
            if ((page is None and laddr is None) or
                (page is not None and laddr == (page - lsize))):
                ranges[-1] = laddr, lsize + self.PAGE_SIZE
            else:
                ranges.append((page, self.PAGE_SIZE))

        ranges[-1] = (ranges[-1][0], ranges[-1][1] - self.PAGE_SIZE + end_size)

        if start_off:
            ranges[0] = (ranges[0][0] + start_off if ranges[0][0] else None,
                         ranges[0][1] - start_off)

        return ranges

    def get_pt(self, addr, uncached=False):
        cached = True
        if addr not in self.pt_cache or uncached:
            cached = False
            self.pt_cache[addr] = list(
                struct.unpack(f"<{self.Lx_SIZE}Q", self.iface.readmem(addr, self.PAGE_SIZE)))

        return cached, self.pt_cache[addr]

    def flush_pt(self, addr):
        assert addr in self.pt_cache
        self.iface.writemem(addr, struct.pack(f"<{self.Lx_SIZE}Q", *self.pt_cache[addr]))

    def initialize(self):
        for i in range(15):
            self.regs.TCR[i].reg = R_TCR(TRANSLATE_ENABLE=1)
        self.regs.TCR[15].reg = R_TCR(BYPASS_DART=1)

        for i in range(16):
            for j in range(4):
                self.regs.TTBR[i, j].reg = R_TTBR(VALID = 0)

        self.regs.ERROR.val = 0xffffffff
        self.regs.UNK1.val = 0
        self.regs.ENABLED_STREAMS.val = 0
        self.enabled_streams = 0

        self.invalidate_streams()

    def show_error(self):
        if self.regs.ERROR.reg.FLAG:
            print(f"ERROR: {self.regs.ERROR.reg!s}")
            print(f"ADDR: {self.regs.ERROR_ADDR_HI.val:#x}:{self.regs.ERROR_ADDR_LO.val:#x}")
            self.regs.ERROR.val = 0xffffffff

    def invalidate_streams(self, streams=0xffffffff):
        self.regs.STREAM_SELECT.val = streams
        self.regs.STREAM_COMMAND.val = R_STREAM_COMMAND(INVALIDATE=1)
        while self.regs.STREAM_COMMAND.reg.BUSY:
            pass

    def invalidate_cache(self):
        self.pt_cache = {}

    def dump_table2(self, base, l1_addr):

        def print_block(base, pte, start, last):
            pgcount = last - start
            pte.OFFSET -= pgcount
            print("    page (%4d): %08x ... %08x -> %016x [%d%d]" % (
                    start, base + start*0x4000, base + (start+1)*0x4000,
                    pte.OFFSET << self.PAGE_BITS, pte.SP_PROT_DIS, pte.VALID))
            if start < last:
                print("     ==> (%4d):          ... %08x -> %016x size: %08x" % (
                    last, base + (last+1)*0x4000,
                    (pte.OFFSET + pgcount - 1) << self.PAGE_BITS, pgcount << self.PAGE_BITS))

        cached, tbl = self.get_pt(l1_addr)

        unmapped = False
        start = 0
        next_pte = self.ptecls(VALID=0)

        for i, pte in enumerate(tbl):
            pte = self.ptecls(pte)
            if not pte.VALID:
                if not unmapped:
                    if next_pte.VALID:
                        print_block(base, next_pte, start, i)
                    print("  ...")
                    unmapped = True
                    next_pte = pte
                continue

            unmapped = False

            if int(pte) != int(next_pte):
                if next_pte.VALID:
                    print_block(base, next_pte, start, i)
                start = i

            next_pte = pte
            next_pte.OFFSET += 1

        if next_pte.VALID:
            print_block(base, next_pte, start, 2048)

    def dump_table(self, base, l1_addr):
        cached, tbl = self.get_pt(l1_addr)

        unmapped = False
        for i, pte in enumerate(tbl):
            pte = self.ptecls(pte)
            if not pte.VALID:
                if not unmapped:
                    print("  ...")
                    unmapped = True
                continue

            unmapped = False

            print("  table (%d): %08x ... %08x -> %016x [%d%d]" % (
                i, base + i*0x2000000, base + (i+1)*0x2000000,
                pte.OFFSET << self.PAGE_BITS, pte.SP_PROT_DIS, pte.VALID))
            self.dump_table2(base + i*0x2000000, pte.OFFSET << self.PAGE_BITS)

    def dump_ttbr(self, idx, ttbr):
        if not ttbr.VALID:
            return

        l1_addr = (ttbr.ADDR) << 12
        print("  TTBR%d: %09x" % (idx, l1_addr))

        self.dump_table(0, l1_addr)

    def dump_device(self, idx):
        tcr = self.regs.TCR[idx].reg
        ttbrs = self.regs.TTBR[idx, :]
        print(f"dev {idx:02x}: TCR={tcr!s} TTBRs = [{', '.join(map(str, ttbrs))}]")

        if tcr.TRANSLATE_ENABLE and tcr.BYPASS_DART:
            print("  mode: INVALID")
        elif tcr.TRANSLATE_ENABLE:
            print("  mode: TRANSLATE")

            for idx, ttbr in enumerate(ttbrs):
                self.dump_ttbr(idx, ttbr.reg)
        elif tcr.BYPASS_DART:
            print("  mode: BYPASS")
        else:
            print("  mode: UNKNOWN")

    def dump_all(self):
        for i in range(16):
            self.dump_device(i)
