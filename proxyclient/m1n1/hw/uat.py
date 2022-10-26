"""
    UAT is just regular ARMv8 pagetables, shared between the gfx-asc firmware
    and the actual AGX hardware.

    The OS doesn't have direct control over it, TTBR0 and TTBR1 entries are placed at
    gpu-region-base, one pair for each context. The firmware automatically loads TTBR0/TTBR1
    on boot and whenever the context changes.
"""


import struct
from ..fw.agx.handoff import GFXHandoff
from ..utils import *
from ..malloc import Heap
from enum import IntEnum
import traceback

__all__ = []

class MemoryAttr(IntEnum):
    # ff = Normal, Outer Writeback RW, Inner Writeback RW
    Normal = 0 # Only accessed by the gfx-asc coprocessor
    # 00 = Device nGnRnE
    Device = 1
    # f4 = Normal, Outer Writeback RW, Inner NC
    Shared = 2 # Probally Outer-shareable. Shared with either the main cpu or AGX hardware
    # 4f = Normal, Outer NC, Inner Writeback RW
    UNK3 = 3
    # 00 = Device nGnRnE
    UNK4 = 4
    # ff = Normal, Outer Writeback RW, Inner Writeback RW
    UNK5 = 5
    # 00 = Device nGnRnE
    UNK6 = 6
    # 00 = Device nGnRnE
    UNK7 = 7


class TTBR(Register64):
    ASID = 63, 48
    BADDR = 47, 1
    VALID = 0

    def valid(self):
        return self.VALID == 1

    def offset(self):
        return self.BADDR << 1

    def set_offset(self, offset):
        self.BADDR = offset >> 1

    def describe(self):
        return f"{self.offset():x} [ASID={self.ASID}, VALID={self.VALID}]"

class PTE(Register64):
    OFFSET = 47, 14
    UNK0   = 10 # probally an ownership flag, seems to be 1 for FW created PTEs and 0 for OS PTEs
    TYPE   = 1
    VALID  = 0

    def valid(self):
        return self.VALID == 1 and self.TYPE == 1

    def offset(self):
        return self.OFFSET << 14

    def set_offset(self, offset):
        self.OFFSET = offset >> 14

    def describe(self):
        if not self.valid():
            return f"<invalid> [{int(self)}:x]"
        return f"{self.offset():x}, UNK={self.UNK0}"

class Page_PTE(Register64):
    OS        = 55 # Owned by host os or firmware
    UXN       = 54
    PXN       = 53
    OFFSET    = 47, 14
    nG        = 11 # global or local TLB caching
    AF        = 10
    SH        = 9, 8
    AP        = 7, 6
    AttrIndex = 4, 2
    TYPE      = 1
    VALID     = 0

    def valid(self):
        return self.VALID == 1 and self.TYPE == 1

    def offset(self):
        return self.OFFSET << 14

    def set_offset(self, offset):
        self.OFFSET = offset >> 14

    def access_fw(self, gl=False):
        if not self.OS:
            return [[
                ["--", "--", "--", "--"],
                ["--", "RW", "--", "RW"],
                ["--", "RX", "--", "--"],
                ["RX", "R-", "--", "R-"],
            ], [
                ["--", "--", "--", "RW"],
                ["--", "--", "--", "RW"],
                ["RX", "--", "--", "R-"],
                ["RX", "RW", "--", "R-"],
            ]][gl][self.AP][(self.UXN << 1) | self.PXN]
        else:
            return [
                ["--", "R-", "-?", "RW"],
                ["R-", "--", "RW", "RW"],
                ["--", "--", "--", "--"],
                ["--", "--", "--", "--"],
            ][self.AP][(self.UXN << 1) | self.PXN]

    def access_gpu(self):
        if not self.OS:
            return "--"

        return [
            ["--", "R-", "-W", "RW"],
            ["--", "--", "--", "R-"],
            ["R-", "-W", "RW", "--"],
            ["--", "--", "--", "--"],
        ][self.AP][(self.UXN << 1) | self.PXN]

    def describe(self):
        if not self.valid():
            return f"<invalid> [{int(self)}:x]"

        return (
            f"{self.offset():x} [GPU={self.access_gpu()}, EL1={self.access_fw(0)}, GL1={self.access_fw(1)}, " +
            f"perm={self.OS}{self.AP:02b}{self.UXN}{self.PXN}, " +
            f"{MemoryAttr(self.AttrIndex).name}, {['Global', 'Local'][self.nG]}, " +
            f"Owner={['FW', 'OS'][self.OS]}, AF={self.AF}, SH={self.SH}] ({self.value:#x})"
        )

class UatAccessor(Reloadable):
    def __init__(self, uat, ctx=0):
        self.uat = uat
        self.ctx = ctx

    def translate(self, addr, width):
        paddr, _ = self.uat.iotranslate(self.ctx, addr, width)[0]
        if paddr is None:
            raise Exception(f"UAT Failed to translate {addr:#x}")
        return paddr

    def read(self, addr, width):
        return self.uat.u.read(self.translate(addr, width), width)
    def read8(self, addr):
        return self.uat.p.read8(self.translate(addr, 1))
    def read16(self, addr):
        return self.uat.p.read16(self.translate(addr, 2))
    def read32(self, addr):
        return self.uat.p.read32(self.translate(addr, 4))
    def read64(self, addr):
        return self.uat.p.read64(self.translate(addr, 8))

    def write(self, addr, data, width):
        self.uat.u.write(self.translate(addr, width), data, width)
    def write8(self, addr, data):
        self.uat.p.write8(self.translate(addr, 1), daat)
    def write16(self, addr, data):
        self.uat.p.write6(self.translate(addr, 2), data)
    def write32(self, addr, data):
        self.uat.p.write32(self.translate(addr, 4), data)
    def write64(self, addr, data):
        self.uat.p.write64(self.translate(addr, 8), data)

class UatStream(Reloadable):
    CACHE_SIZE = 0x1000

    def __init__(self, uat, ctx, addr, recurse=True):
        self.uat = uat
        self.ctx = ctx
        self.pos = addr
        self.cache = None
        self.meta_fn = None
        self.recurse = recurse

    def to_accessor(self):
        return UatAccessor(self.uat, self.ctx)

    def read(self, size):
        assert size >= 0

        data = b""
        if self.cache:
            data = self.cache[:size]
            cached = len(self.cache)
            self.pos += min(cached, size)
            if cached > size:
                self.cache = self.cache[size:]
                return data
            self.cache = None
            if cached == size:
                return data

            size -= cached

        # align any cache overreads to the next page boundary
        remaining_in_page = self.uat.PAGE_SIZE - (self.pos % self.uat.PAGE_SIZE)
        to_cache = min(remaining_in_page, self.CACHE_SIZE)

        try:
            self.cache = self.uat.ioread(self.ctx, self.pos, max(size, to_cache))
        except:
            traceback.print_exc()
            raise
        return data + self.read(size)

    def readable(self):
        return True

    def write(self, bytes):
        self.uat.iowrite(self.ctx, self.pos, bytes)
        self.pos += len(bytes)
        self.cache = None
        return len(bytes)

    def writable(self):
        return True

    def flush(self):
        self.cache = None

    def seek(self, n, wherenc=0):
        self.cache = None
        if wherenc == 0:
            self.pos = n
        elif wherenc == 2:
            self.pos += n

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def closed(self):
        return False


class UAT(Reloadable):
    NUM_CONTEXTS = 64

    PAGE_BITS = 14
    PAGE_SIZE = 1 << PAGE_BITS

    L0_SIZE = 2
    L0_OFF = 39
    L1_SIZE = 8
    L1_OFF = 36
    L2_OFF = 25
    L3_OFF = 14

    IDX_BITS = 11
    Lx_SIZE = (1 << IDX_BITS)

    LEVELS = [
        (L0_OFF, L0_SIZE, TTBR),
        (L1_OFF, L1_SIZE, PTE),
        (L2_OFF, Lx_SIZE, PTE),
        (L3_OFF, Lx_SIZE, Page_PTE),
    ]

    def __init__(self, iface, util=None, hv=None):
        self.iface = iface
        self.u = util
        self.p = util.proxy
        self.hv = hv
        self.pt_cache = {}
        self.dirty = set()
        self.dirty_ranges = {}
        self.allocator = None
        self.ttbr = None
        self.initialized = False
        self.sgx_dev = self.u.adt["/arm-io/sgx"]
        self.shared_region = self.sgx_dev.gfx_shared_region_base
        self.gpu_region = self.sgx_dev.gpu_region_base
        self.ttbr0_base = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
        self.ttbr1_base = self.sgx_dev.gfx_shared_region_base
        self.handoff = GFXHandoff(self.u)

        self.VA_MASK = 0
        for (off, size, _) in self.LEVELS:
            self.VA_MASK |= (size - 1) << off
        self.VA_MASK |= self.PAGE_SIZE - 1


    def set_l0(self, ctx, off, base, asid=0):
        ttbr = TTBR(BADDR = base >> 1, ASID = asid, VALID=(base != 0))
        print(f"[UAT] Set L0 ctx={ctx} off={off:#x} base={base:#x} asid={asid} ({ttbr})")
        self.write_pte(self.gpu_region + ctx * 16, off, 2, ttbr)

    def ioread(self, ctx, base, size):
        if size == 0:
            return b""

        ranges = self.iotranslate(ctx, base, size)

        iova = base
        data = []
        for addr, size in ranges:
            if addr is None:
                raise Exception(f"Unmapped page at iova {ctx}:{iova:#x}")
            data.append(self.iface.readmem(addr, size))
            iova += size

        return b"".join(data)

    def iowrite(self, ctx, base, data):
        if len(data) == 0:
            return

        ranges = self.iotranslate(ctx, base, len(data))

        iova = base
        p = 0
        for addr, size in ranges:
            if addr is None:
                raise Exception(f"Unmapped page at iova {ctx}:{iova:#x}")
            self.iface.writemem(addr, data[p:p + size])
            p += size
            iova += size

    # A stream interface that can be used for random access by Construct
    def iostream(self, ctx, base, recurse=True):
        return UatStream(self, ctx, base, recurse)

    # A read/write register interface like proxy/utils objects that can be used by RegMap
    def ioaccessor(self, ctx, base):
        return UatAccessor(self, ctx)

    def iomap(self, ctx, addr, size, **flags):
        iova = self.allocator.malloc(size)

        self.iomap_at(ctx, iova, addr, size, **flags)
        self.flush_dirty()
        return iova

    def iomap_at(self, ctx, iova, addr, size, **flags):
        if size == 0:
            return

        if addr & (self.PAGE_SIZE - 1):
            raise Exception(f"Unaligned PA {addr:#x}")

        if iova & (self.PAGE_SIZE - 1):
            raise Exception(f"Unaligned IOVA {iova:#x}")

        self.init()

        map_flags = {'OS': 1, 'AttrIndex': MemoryAttr.Normal, 'VALID': 1, 'TYPE': 1, 'AP': 1, 'AF': 1, 'UXN': 1}
        map_flags.update(flags)

        start_page = align_down(iova, self.PAGE_SIZE)
        end = iova + size
        end_page = align_up(end, self.PAGE_SIZE)

        for page in range(start_page, end_page, self.PAGE_SIZE):
            table_addr = self.gpu_region + ctx * 16
            for (offset, size, ptecls) in self.LEVELS:
                if ptecls is Page_PTE:
                    pte = Page_PTE(**map_flags)
                    pte.set_offset(addr)
                    self.write_pte(table_addr, page >> offset, size, pte)
                    addr += self.PAGE_SIZE
                else:
                    pte = self.fetch_pte(table_addr, page >> offset, size, ptecls)
                    if not pte.valid():
                        table = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
                        self.p.memset32(table, 0, self.PAGE_SIZE)
                        pte.set_offset(table)
                        if ptecls is not TTBR:
                            pte.VALID = 1
                            pte.TYPE = 1
                            #pte.UNK0 = 1
                        self.write_pte(table_addr, page >> offset, size, pte)
                    table_addr = pte.offset()

        self.dirty_ranges.setdefault(ctx, []).append((start_page, end_page - start_page))
        #self.flush_dirty()


    def fetch_pte(self, offset, idx, size, ptecls):
        idx = idx & (size - 1)

        cached, table = self.get_pt(offset, size=size)
        pte = ptecls(table[idx])
        if not pte.valid() and cached:
            self.flush_dirty()
            cached, table = self.get_pt(offset, size=size, uncached=True)
            pte = ptecls(table[idx])

        return pte

    def write_pte(self, offset, idx, size, pte):
        idx = idx & (size - 1)

        cached, table = self.get_pt(offset, size=size)

        table[idx] = pte.value
        self.dirty.add(offset)

    def iotranslate(self, ctx, start, size):
        if size == 0:
            return []

        start = start & self.VA_MASK

        start_page = align_down(start, self.PAGE_SIZE)
        start_off = start - start_page
        end = start + size
        end_page = align_up(end, self.PAGE_SIZE)
        end_size = end - (end_page - self.PAGE_SIZE)

        pages = []

        for page in range(start_page, end_page, self.PAGE_SIZE):
            table_addr = self.gpu_region + ctx * 16
            for (offset, size, ptecls) in self.LEVELS:
                pte = self.fetch_pte(table_addr, page >> offset, size, ptecls)
                if not pte.valid():
                    break
                table_addr = pte.offset()

            if pte.valid():
                pages.append(pte.offset())
            else:
                pages.append(None)

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

    def get_pt(self, addr, size=None, uncached=False):
        if size is None:
            size = self.Lx_SIZE
        cached = True
        if addr not in self.pt_cache or uncached:
            cached = False
            self.pt_cache[addr] = list(
                struct.unpack(f"<{size}Q", self.iface.readmem(addr, size * 8)))

        return cached, self.pt_cache[addr]

    def flush_pt(self, addr):
        assert addr in self.pt_cache
        table = self.pt_cache[addr]
        self.iface.writemem(addr, struct.pack(f"<{len(table)}Q", *table))
        #self.p.dc_civac(addr, 0x4000)

    def flush_dirty(self):
        inval = False

        for page in self.dirty:
            self.flush_pt(page)
            inval = True

        self.dirty.clear()

        for ctx, ranges in self.dirty_ranges.items():
            asid = ctx << 48
            self.u.inst("tlbi aside1os, x0", asid)

    def invalidate_cache(self):
        self.pt_cache = {}

    def recurse_level(self, level, base, table, page_fn=None, table_fn=None):
        def extend(addr):
            if addr >= 0x80_00000000:
                addr |= 0xf00_00000000
            return addr

        offset, size, ptecls = self.LEVELS[level]

        cached, tbl = self.get_pt(table, size)
        sparse = False
        for i, pte in enumerate(tbl):
            pte = ptecls(pte)
            if not pte.valid():
                sparse = True
                continue

            range_size = 1 << offset
            start = extend(base + i * range_size)
            end = start + range_size - 1

            if level + 1 == len(self.LEVELS):
                if page_fn:
                    page_fn(start, end, i, pte, level, sparse=sparse)
            else:
                if table_fn:
                    table_fn(start, end, i, pte, level, sparse=sparse)
                self.recurse_level(level + 1, start, pte.offset(), page_fn, table_fn)

            sparse = False

    def foreach_page(self, ctx, page_fn):
        self.recurse_level(0, 0, self.gpu_region + ctx * 16, page_fn)

    def foreach_table(self, ctx, table_fn):
        self.recurse_level(0, 0, self.gpu_region + ctx * 16, table_fn=table_fn)

    def init(self):
        if self.initialized:
            return

        print("[UAT] Initializing...")

        # Clear out any stale kernel page tables
        self.p.memset64(self.ttbr1_base + 0x10, 0, 0x3ff0)
        self.u.inst("tlbi vmalle1os")

        self.handoff.initialize()

        with self.handoff.lock():
            print(f"[UAT] TTBR0[0] = {self.ttbr0_base:#x}")
            print(f"[UAT] TTBR1[0] = {self.ttbr1_base:#x}")
            self.set_l0(0, 0, self.ttbr0_base)
            self.set_l0(0, 1, self.ttbr1_base)
            self.flush_dirty()
            self.invalidate_cache()

        print("[UAT] Init complete")

        self.initialized = True

    def bind_context(self, ctx, ttbr0_base):
        assert ctx != 0

        with self.handoff.lock():
            self.set_l0(ctx, 0, ttbr0_base, ctx)
            self.set_l0(ctx, 1, self.ttbr1_base, ctx)
            self.flush_dirty()
            self.invalidate_cache()

    def dump(self, ctx, log=print):
        def print_fn(start, end, i, pte, level, sparse):
            type = "page" if level+1 == len(self.LEVELS) else "table"
            if sparse:
                log(f"{'  ' * level}...")
            log(f"{'  ' * level}{type}({i:03}): {start:011x} ... {end:011x}"
                       f" -> {pte.describe()}")

        self.recurse_level(0, 0, self.gpu_region + ctx * 16, print_fn, print_fn)

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
