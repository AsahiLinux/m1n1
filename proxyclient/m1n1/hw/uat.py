"""
    UAT is just regular ARMv8 pagetables, shared between the gfx-asc firmware
    and the actual AGX hardware.

    The OS doesn't have direct control over it, TTBR0 and TTBR1 entries are placed at
    gpu-region-base, one pair for each context. The firmware automatically loads TTBR0/TTBR1
    on boot and whenever the context changes.
"""


import struct
from ..utils import *
from ..malloc import Heap
from enum import IntEnum
import traceback

class MemoryAttr(IntEnum):
    Normal = 0 # Only accessed by the gfx-asc coprocessor
    Device = 1
    Shared = 2 # Probally Outer-shareable. Shared with either the main cpu or AGX hardware


class TTBR(Register64):
    ASID = 63, 48
    BADDR = 47, 1
    CnP = 0

    def valid(self):
        return self.BADDR != 0

    def offset(self):
        return self.BADDR << 1

    def set_offset(self, offset):
        self.BADDR = offset >> 1

    def describe(self):
        return f"{self.offset():x} [ASID={self.ASID}, CnP={self.CnP}]"

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

    def access(self, el):
        if el == 0:
            return [["Xo", "RW", "Xo", "RX"],
                    ["None", "RW", "None", "Ro"]][self.UXN][self.AP]

        return [["RW", "RW", "RX", "RX"],
                ["RW", "RW", "Ro", "Ro"]][self.PXN][self.AP]

    def describe(self):
        if not self.valid():
            return f"<invalid> [{int(self)}:x]"

        return f"{self.offset():x} [EL1={self.access(1)}, EL0={self.access(0)}, " \
               f"{MemoryAttr(self.AttrIndex).name}, {['Global', 'Local'][self.nG]}, " \
               f"Owner={['FW', 'OS'][self.OS]}, AF={self.AF}]"


class UatStream(Reloadable):
    CACHE_SIZE = 0x1000

    def __init__(self, uat, ctx, addr):
        self.uat = uat
        self.ctx = ctx
        self.pos = addr
        self.cache = None
        self.meta_fn = None

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
        self.hv = hv
        self.pt_cache = {}
        self.dirty = set()
        self.allocator = None
        self.ttbr = None

        self.VA_MASK = 0
        for (off, size, _) in self.LEVELS:
            self.VA_MASK |= (size - 1) << off
        self.VA_MASK |= self.PAGE_SIZE - 1


    def set_l0(self, ctx, off, base, asid=0):
        self.write_pte(self.ttbr + ctx * 16, off, 2,
                       TTBR(BADDR = base >> 1, ASID = asid))

    def set_ttbr(self, addr):
        self.ttbr = addr

    def ioread(self, ctx, base, size):
        if size == 0:
            return b""

        ranges = self.iotranslate(ctx, base, size)

        iova = base
        data = []
        for addr, size in ranges:
            if addr is None:
                raise Exception(f"Unmapped page at iova {iova:#x}")
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
                raise Exception(f"Unmapped page at iova {iova:#x}")
            self.iface.writemem(addr, data[p:p + size])
            p += size
            iova += size

    # A stream interface that can be used for random access by Construct
    def iostream(self, ctx, base):
        return UatStream(self, ctx, base)

    def iomap(self, ctx, addr, size, **flags):
        iova = self.allocator.malloc(size)

        self.iomap_at(ctx, iova, addr, size, **flags)
        return iova

    def iomap_at(self, ctx, iova, addr, size, **flags):
        if size == 0:
            return

        if addr & (self.PAGE_SIZE - 1):
            raise Exception(f"Unaligned PA {addr:#x}")

        if iova & (self.PAGE_SIZE - 1):
            raise Exception(f"Unaligned IOVA {iova:#x}")

        map_flags = {'OS': 1, 'AttrIndex': MemoryAttr.Normal, 'VALID': 1, 'TYPE': 1, 'AP': 1, 'AF': 1, 'UXN': 1}
        map_flags.update(flags)

        start_page = align_down(iova, self.PAGE_SIZE)
        end = iova + size
        end_page = align_up(end, self.PAGE_SIZE)

        for page in range(start_page, end_page, self.PAGE_SIZE):
            table_addr = self.ttbr + ctx * 16
            for (offset, size, ptecls) in self.LEVELS:
                if ptecls is Page_PTE:
                    pte = Page_PTE(**map_flags)
                    pte.set_offset(addr)
                    self.write_pte(table_addr, page >> offset, size, pte)
                    addr += self.PAGE_SIZE
                else:
                    pte = self.fetch_pte(table_addr, page >> offset, size, ptecls)
                    if not pte.valid():
                        pte.set_offset(self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE))
                        if ptecls is not TTBR:
                            pte.VALID = 1
                            pte.TYPE = 1
                            #pte.UNK0 = 1
                        self.write_pte(table_addr, page >> offset, size, pte)
                    table_addr = pte.offset()

        self.flush_dirty()


    def fetch_pte(self, offset, idx, size, ptecls):
        idx = idx & (size - 1)

        cached, table = self.get_pt(offset, size=size)
        pte = ptecls(table[idx])
        if not pte.valid() and cached:
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
            table_addr = self.ttbr + ctx * 16
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

    def flush_dirty(self):
        for page in self.dirty:
            self.flush_pt(page)

        self.dirty.clear()

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
        self.recurse_level(0, 0, self.ttbr + ctx * 16, page_fn)

    def foreach_table(self, ctx, table_fn):
        self.recurse_level(0, 0, self.ttbr + ctx * 16, table_fn=table_fn)

    def dump(self, ctx, log=print):
        if not self.ttbr:
            log("No translation table")
            return

        def print_fn(start, end, i, pte, level, sparse):
            type = "page" if level+1 == len(self.LEVELS) else "table"
            if sparse:
                log(f"{'  ' * level}...")
            log(f"{'  ' * level}{type}({i:03}): {start:011x} ... {end:011x}"
                       f" -> {pte.describe()}")

        self.recurse_level(0, 0, self.ttbr + ctx * 16, print_fn, print_fn)
