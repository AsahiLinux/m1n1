# SPDX-License-Identifier: MIT

import struct

from enum import IntEnum
from ..utils import *
from ..malloc import Heap

__all__ = ["DART8110Regs", "DART8110"]

class R_PARAMS_0(Register32):
    CLIENT_PARTITIONS_SUPPORTED = 29
    LOG2_PGSZ = 27, 24
    LOG2_TE_COUNT = 22, 20
    TLB_SET_COUNT = 11, 0

class R_PARAMS_4(Register32):
    LOG2_NUM_WAYS = 30, 28
    NUM_ASCS = 25, 24
    NUM_W_PORTS = 22, 20
    NUM_R_PORTS = 18, 16
    NUM_APFS = 15, 8
    SUPPORT_STT_PREFETCH = 6
    SUPPORT_TLB_PREFETCH = 5
    SUPPORT_CTC_PREFETCH = 4
    SUPPORT_HW_FLUSH = 3
    SUPPORT_TZ_TAGGER = 2
    SUPPORT_REG_LOCK = 1
    SUPPORT_FULL_BYPASS = 0

class R_PARAMS_8(Register32):
    PA_WIDTH = 29, 24
    VA_WIDTH = 21, 16
    VERS_MAJ = 15, 8
    VERS_MIN = 7, 0

class R_PARAMS_C(Register32):
    NUM_CLIENTS = 24, 16
    NUM_SIDS = 8, 0

class R_ERROR(Register32):
    FLAG = 31
    SMMU = 30
    REGION_PROTECT = 29
    WRITE_nREAD = 28
    SID = 27, 20
    SECONDARY = 19
    FILL_REGION = 18
    BPF_REJECT = 14
    EXTERNAL = 13
    STT_FLUSH = 12
    STT_MISMATCH = 11
    APF_REJECT = 10
    DROP_PROTECT = 9
    CTRR_WRITE_PROTECT = 8
    AXI_ERROR = 7
    AXI_DECODE = 6
    READ_FAULT = 5
    WRITE_FAULT = 4
    NO_PTE = 3
    NO_PMD = 2  # "STE"
    NO_PGD = 1  # "CTE"
    NO_TTBR = 0

class R_TLB_OP(Register32):
    BUSY = 31

    # None of these bits are supported on hwrev 1
    HARDWARE_FLUSH = 30
    FLUSH_VA_RANGE = 14
    ENABLE_STT_FLUSH = 13
    DISABLE_STC_FLUSH = 12

    # 0 = flush all
    # 1 = flush SID
    # 2 = TLB read
    # 3 = TLB write????
    # 4 = flush unlock, definitely not supported on hwrev 1
    OP = 10, 8
    STREAM = 7, 0

class R_TLB_OP_IDX(Register32):
    SET = 13, 8
    WAY = 6, 4
    TE = 2, 0

class R_PROTECT(Register32):
    LOCK_TZ_SELECT = 4
    LOCK_TZ_CONFIG = 3
    # This bit can be set, but unknown what it protects
    _BIT2 = 2
    LOCK_REG_4xx = 1
    LOCK_TCR_TTBR = 0

class R_DIAG_LOCK(Register32):
    # FIXME: how does this work exactly?
    LOCK_ON_ERR = 1
    LOCK = 0

class R_TCR(Register32):
    REMAP = 11, 8
    REMAP_EN = 7
    FOUR_LEVELS = 3     # not supported on hwrev 1
    BYPASS_DAPF = 2
    BYPASS_DART = 1
    TRANSLATE_ENABLE = 0

class R_TTBR(Register32):
    ADDR = 29, 2
    VALID = 0

class PTE(Register64):
    SP_START = 63, 52
    SP_END = 51, 40
    OFFSET = 37, 10
    RDPROT = 3
    WRPROT = 2
    UNCACHABLE = 1
    VALID = 0

class DART8110Regs(RegMap):
    PARAMS_0 = 0x000, R_PARAMS_0
    PARAMS_4 = 0x004, R_PARAMS_4
    PARAMS_8 = 0x008, R_PARAMS_8
    PARAMS_C = 0x00C, R_PARAMS_C
    # Unknown RO
    REG_0x10 = 0x010, Register32
    REG_0x14 = 0x014, Register32    # hwrev 2 only

    TLB_OP      = 0x080, R_TLB_OP
    TLP_OP_IDX  = 0x084, R_TLB_OP_IDX
    TLB_TAG_LO  = 0x088, Register32
    TLB_TAG_HI  = 0x08c, Register32    # hwrev 2 only
    TLB_PA_LO   = 0x090, Register32
    TLB_PA_HI   = 0x094, Register32
    TLB_START_DVA_PAGE  = 0x098, Register32    # hwrev 2 only
    TLB_END_DVA_PAGE    = 0x0a0, Register32    # hwrev 2 only

    ERROR           = 0x100, R_ERROR
    ERROR_DISABLE   = 0x104, R_ERROR

    # Found via register bruteforcing
    STREAM_UNK_SET  = irange(0x120, 8, 4), Register32
    STREAM_UNK_CLR  = irange(0x140, 8, 4), Register32

    # these are all accessed by error interrupt handler
    REG_0x160   = 0x160, Register32
    REG_0x164   = 0x164, Register32
    ERROR_ADDR_LO   = 0x170, Register32
    ERROR_ADDR_HI   = 0x174, Register32
    REG_0x178   = 0x178, Register32     # hwrev 2 only
    REG_0x180   = irange(0x180, 4, 4), Register32
    REG_0x1a0   = irange(0x1a0, 8, 4), Register32
    ERR_SECONDARY   = irange(0x1c0, 8, 4), Register32

    # Write bits to _PROTECT to protect them.
    # They can be unprotected by writing to _UNPROTECT unless _LOCK is written.
    # If _LOCK is written, protection can be enabled but not disabled. 
    REG_PROTECT         = 0x200, R_PROTECT
    REG_UNPROTECT       = 0x204, R_PROTECT
    REG_PROTECT_LOCK    = 0x208, R_PROTECT

    # Tunables touch this, can set bits FF00001F, RW
    REG_0x20c       = 0x20c, Register32

    DIAG_LOCK   = 0x210, R_DIAG_LOCK

    # All unknown, related to transaction queueing???

    # can set bits 3FFFFFFC, RW
    REG_0x218   = 0x218, Register32
    # Tunables touch this, can set bits 000F0F0F, RW
    REG_0x220   = 0x220, Register32
    # Tunables touch this, can set bits 00FFFFFF, RW
    REG_0x224   = 0x224, Register32
    # can set bits 3F3F3F3F
    TLIMIT      = 0x228, Register32
    # can set bits 07070707
    TEQRESERVE  = 0x22c, Register32
    # RO, outstanding transaction count???
    TRANS       = irange(0x230, 4, 4), Register32

    # hwrev 2 only for all of these
    REG_0x300   = 0x300, Register32
    REG_0x308   = 0x308, Register32
    REG_0x310   = 0x310, Register32
    REG_0x318   = 0x318, Register32
    REG_0x320   = 0x320, Register32
    REG_0x328   = 0x328, Register32
    REG_0x330   = 0x330, Register32
    REG_0x338   = 0x338, Register32
    REG_0x340   = 0x340, Register32
    REG_0x348   = 0x348, Register32
    REG_0x350   = 0x350, Register32
    REG_0x358   = 0x358, Register32

    # Unknown
    REG_0x400   = 0x400, Register32     # can set 00000003
    REG_0x404   = 0x404, Register32     # can set 001FFFFF
    REG_0x408   = 0x408, Register32     # can set 00FFFFFC
    REG_0x410   = 0x410, Register32     # can set 3FFFFFFC

    # These registers exist even though it's "not supported"
    TZ_CONFIG           = 0x500, Register32     # 3 bits
    TZ_SELECT           = 0x504, Register32     # 1 bit
    TZ_REGION0_START    = 0x508, Register32
    TZ_REGION0_END      = 0x510, Register32
    TZ_REGION0_OFFSET   = 0x518, Register32
    TZ_REGION1_START    = 0x520, Register32
    TZ_REGION1_END      = 0x528, Register32
    TZ_REGION1_OFFSET   = 0x530, Register32
    TZ_REGION2_START    = 0x538, Register32
    TZ_REGION2_END      = 0x540, Register32
    TZ_REGION2_OFFSET   = 0x548, Register32

    # completely guessed, unverified, can set bits 0F077077
    PERF_INTR_ENABLE    = 0x700, Register32
    PERF_INTR_STATUS    = 0x704, Register32

    PERF_UNK1   = irange(0x720, 8, 4), Register32
    PERF_UNK2   = irange(0x740, 8, 4), Register32

    PERF_TLB_MISS       = 0x760, Register32
    PERF_TLB_FILL       = 0x764, Register32
    PERF_TLB_HIT        = 0x768, Register32
    PERF_ST_MISS        = 0x770, Register32
    PERF_ST_FILL        = 0x774, Register32
    PERF_ST_HIT         = 0x778, Register32
    # hwrev 1 doesn't have these
    PERF_CTC_MISS       = 0x780, Register32
    PERF_CTC_FILL       = 0x784, Register32
    PERF_CTC_HIT        = 0x788, Register32

    UNK_TUNABLES    = irange(0x800, 256, 4), Register32

    ENABLE_STREAMS  = irange(0xc00, 8, 4), Register32
    DISABLE_STREAMS = irange(0xc20, 8, 4), Register32

    TCR             = irange(0x1000, 256, 4), R_TCR
    TTBR            = irange(0x1400, 256, 4), R_TTBR


class DART8110(Reloadable):
    PAGE_BITS = 14
    PAGE_SIZE = 1 << PAGE_BITS

    L1_OFF = 25
    L2_OFF = 14

    IDX_BITS = 11
    Lx_SIZE = (1 << IDX_BITS)
    IDX_MASK = Lx_SIZE - 1

    def __init__(self, iface, regs, util=None, iova_range=(0x80000000, 0x90000000)):
        self.iface = iface
        self.regs = regs
        self.u = util
        self.pt_cache = {}

        enabled_streams = 0
        for i in range(8):
            enabled_streams |= regs.ENABLE_STREAMS[i].val << 32*i
        self.enabled_streams = enabled_streams
        self.iova_allocator = [Heap(iova_range[0], iova_range[1], self.PAGE_SIZE)
                               for i in range(16)]

    @classmethod
    def from_adt(cls, u, path, instance=0, **kwargs):
        dart_addr = u.adt[path].get_reg(instance)[0]
        regs = DART8110Regs(u, dart_addr)
        dart = cls(u.iface, regs, u, **kwargs)
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
            self.regs.ENABLE_STREAMS[stream // 32].val |= (1 << (stream % 32))

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

            ttbr = self.regs.TTBR[stream].reg
            if not ttbr.VALID:
                l1addr = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
                self.pt_cache[l1addr] = [0] * self.Lx_SIZE
                ttbr.VALID = 1
                ttbr.ADDR = l1addr >> self.PAGE_BITS
                self.regs.TTBR[stream].reg = ttbr

            cached, l1 = self.get_pt(ttbr.ADDR << self.PAGE_BITS)
            l1idx = (page >> self.L1_OFF) & self.IDX_MASK
            l1pte = PTE(l1[l1idx])
            if not l1pte.VALID:
                l2addr = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
                self.pt_cache[l2addr] = [0] * self.Lx_SIZE
                l1pte = PTE(
                    OFFSET=l2addr >> self.PAGE_BITS, VALID=1)
                l1[l1idx] = l1pte.value
                dirty.add(ttbr.ADDR << self.PAGE_BITS)
            else:
                l2addr = l1pte.OFFSET << self.PAGE_BITS

            dirty.add(l1pte.OFFSET << self.PAGE_BITS)
            cached, l2 = self.get_pt(l2addr)
            l2idx = (page >> self.L2_OFF) & self.IDX_MASK
            self.pt_cache[l2addr][l2idx] = PTE(
                SP_START=0, SP_END=0xfff,
                OFFSET=paddr >> self.PAGE_BITS, VALID=1).value

        for page in dirty:
            self.flush_pt(page)

    def iotranslate(self, stream, start, size):
        if size == 0:
            return []

        tcr = self.regs.TCR[stream].reg

        if tcr.BYPASS_DART and not tcr.TRANSLATE_ENABLE:
            # FIXME this may not be correct
            return [(start, size)]

        if tcr.BYPASS_DART or not tcr.TRANSLATE_ENABLE:
            raise Exception(f"Unknown DART mode {tcr}")

        start = start & 0xfffffffff

        start_page = align_down(start, self.PAGE_SIZE)
        start_off = start - start_page
        end = start + size
        end_page = align_up(end, self.PAGE_SIZE)
        end_size = end - (end_page - self.PAGE_SIZE)

        pages = []

        for page in range(start_page, end_page, self.PAGE_SIZE):
            ttbr = self.regs.TTBR[stream].reg
            if not ttbr.VALID:
                pages.append(None)
                continue

            cached, l1 = self.get_pt(ttbr.ADDR << self.PAGE_BITS)
            l1pte = PTE(l1[(page >> self.L1_OFF) & self.IDX_MASK])
            if not l1pte.VALID and cached:
                cached, l1 = self.get_pt(ttbr.ADDR << self.PAGE_BITS, uncached=True)
                l1pte = PTE(l1[(page >> self.L1_OFF) & self.IDX_MASK])
            if not l1pte.VALID:
                pages.append(None)
                continue

            cached, l2 = self.get_pt(l1pte.OFFSET << self.PAGE_BITS)
            l2pte = PTE(l2[(page >> self.L2_OFF) & self.IDX_MASK])
            if not l2pte.VALID and cached:
                cached, l2 = self.get_pt(l1pte.OFFSET << self.PAGE_BITS, uncached=True)
                l2pte = PTE(l2[(page >> self.L2_OFF) & self.IDX_MASK])
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
            self.regs.TTBR[i].reg = R_TTBR(VALID = 0)

        # self.regs.ERROR.val = 0xffffffff
        # self.regs.UNK1.val = 0
        self.regs.DISABLE_STREAMS[0].val = 0xffff
        self.enabled_streams = 0

        self.invalidate_streams()

    def show_error(self):
        if self.regs.ERROR.reg.FLAG:
            print(f"ERROR: {self.regs.ERROR.reg!s}")
            print(f"ADDR: {self.regs.ERROR_ADDR_HI.val:#x}:{self.regs.ERROR_ADDR_LO.val:#x}")
            self.regs.ERROR.val = 0x80000004

    def invalidate_streams(self, streams=0xffff):
        for sid in range(256):
            if streams & (1 << sid):
                self.regs.TLB_OP.val = R_TLB_OP(STREAM=sid, OP=1)
                while self.regs.TLB_OP.reg.BUSY:
                    pass

    def invalidate_cache(self):
        self.pt_cache = {}

    def dump_table2(self, base, l1_addr):

        def print_block(base, pte, start, last):
            pgcount = last - start
            pte.OFFSET -= pgcount
            print("    page (%4d): %09x ... %09x -> %016x [%d%d%d%d]" % (
                    start, base + start*0x4000, base + (start+1)*0x4000,
                    pte.OFFSET << self.PAGE_BITS,
                    pte.RDPROT, pte.WRPROT, pte.UNCACHABLE, pte.VALID))
            if start < last:
                print("     ==> (%4d):           ... %09x -> %016x size: %08x" % (
                    last, base + (last+1)*0x4000,
                    (pte.OFFSET + pgcount - 1) << self.PAGE_BITS, pgcount << self.PAGE_BITS))

        cached, tbl = self.get_pt(l1_addr)

        unmapped = False
        start = 0
        next_pte = PTE(VALID=0)

        for i, pte in enumerate(tbl):
            pte = PTE(pte)
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
            pte = PTE(pte)
            if not pte.VALID:
                if not unmapped:
                    print("  ...")
                    unmapped = True
                continue

            unmapped = False

            print("  table (%d): %09x ... %09x -> %016x [%d%d%d%d]" % (
                i, base + i*0x2000000, base + (i+1)*0x2000000,
                pte.OFFSET << self.PAGE_BITS,
                pte.RDPROT, pte.WRPROT, pte.UNCACHABLE, pte.VALID))
            self.dump_table2(base + i*0x2000000, pte.OFFSET << self.PAGE_BITS)

    def dump_ttbr(self, ttbr):
        if not ttbr.VALID:
            return

        l1_addr = (ttbr.ADDR) << self.PAGE_BITS
        print("  TTBR: %011x" % (l1_addr))

        self.dump_table(0, l1_addr)

    def dump_device(self, idx):
        tcr = self.regs.TCR[idx].reg
        ttbr = self.regs.TTBR[idx]
        print(f"dev {idx:02x}: TCR={tcr!s} TTBR = {ttbr!s}")

        if tcr.TRANSLATE_ENABLE and tcr.BYPASS_DART:
            print("  mode: INVALID")
        elif tcr.TRANSLATE_ENABLE:
            print("  mode: TRANSLATE")

            self.dump_ttbr(ttbr.reg)
        elif tcr.BYPASS_DART:
            print("  mode: BYPASS")
        else:
            print("  mode: UNKNOWN")

    def dump_all(self):
        for i in range(16):
            self.dump_device(i)

    def dump_params(self):
        print(self.regs.PARAMS_0.reg)
        print(self.regs.PARAMS_4.reg)
        print(self.regs.PARAMS_8.reg)
        print(self.regs.PARAMS_C.reg)
