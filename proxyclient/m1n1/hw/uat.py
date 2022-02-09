import struct
from ..utils import *

class PTE(Register64):
    FLAG   = 59, 56 # Values seen: 3, 4, 7, 6
    CTX    = 55, 48 # Only ever set in L0, matches the context id (might just be software tracking)
    OFFSET = 47, 14
    UNK11  = 11 # set for gfx pages, 0 for asc pages
    UNK9   = 9
    UNK8   = 8
    READONLY = 7
    UNK6   = 6
    UNK3   = 3 # 1 for gfx pages, 0 for asc pages
    UNCACHED = 2 # maybe? set for IO ranges
    UNK1   = 1 # Useally unset on L0
    VALID  = 0

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
        (L0_OFF, L0_SIZE),
        (L1_OFF, L1_SIZE),
        (L2_OFF, Lx_SIZE),
        (L3_OFF, Lx_SIZE),
    ]

    def __init__(self, iface, util=None, iova_range=(0x80000000, 0x90000000)):
        self.iface = iface
        self.u = util
        self.pt_cache = {}
        #self.iova_allocator = [Heap(iova_range[0], iova_range[1], self.PAGE_SIZE)
        #                       for i in range(16)]
        self.ptecls = PTE
        self.ttbr = None

        self.VA_MASK = 0
        for (off, size) in self.LEVELS:
            self.VA_MASK |= (size - 1) << off

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

    # TODO: fix this
    # def iomap(self, stream, addr, size):
    #     iova = self.iova_allocator[stream].malloc(size)

    #     self.iomap_at(stream, iova, addr, size)
    #     return iova

    # def iomap_at(self, stream, iova, addr, size):
    #     if size == 0:
    #         return

    #     if not (self.enabled_streams & (1 << stream)):
    #         self.enabled_streams |= (1 << stream)
    #         self.regs.ENABLED_STREAMS.val |= self.enabled_streams

    #     tcr = self.regs.TCR[stream].reg

    #     if addr & (self.PAGE_SIZE - 1):
    #         raise Exception(f"Unaligned PA {addr:#x}")

    #     if iova & (self.PAGE_SIZE - 1):
    #         raise Exception(f"Unaligned IOVA {iova:#x}")

    #     start_page = align_down(iova, self.PAGE_SIZE)
    #     end = iova + size
    #     end_page = align_up(end, self.PAGE_SIZE)

    #     dirty = set()

    #     for page in range(start_page, end_page, self.PAGE_SIZE):
    #         paddr = addr + page - start_page

    #         l0 = page >> self.L0_OFF
    #         assert l0 < self.L0_SIZE
    #         ttbr = self.regs.TTBR[stream, l0].reg
    #         if not ttbr.VALID:
    #             l1addr = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
    #             self.pt_cache[l1addr] = [0] * self.Lx_SIZE
    #             ttbr.VALID = 1
    #             ttbr.ADDR = l1addr >> 12
    #             self.regs.TTBR[stream, l0].reg = ttbr

    #         cached, l1 = self.get_pt(ttbr.ADDR << 12)
    #         l1idx = (page >> self.L1_OFF) & self.IDX_MASK
    #         l1pte = self.ptecls(l1[l1idx])
    #         if not l1pte.VALID:
    #             l2addr = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
    #             self.pt_cache[l2addr] = [0] * self.Lx_SIZE
    #             l1pte = self.ptecls(
    #                 OFFSET=l2addr >> self.PAGE_BITS, VALID=1, SP_PROT_DIS=1)
    #             l1[l1idx] = l1pte.value
    #             dirty.add(ttbr.ADDR << 12)
    #         else:
    #             l2addr = l1pte.OFFSET << self.PAGE_BITS

    #         dirty.add(l1pte.OFFSET << self.PAGE_BITS)
    #         cached, l2 = self.get_pt(l2addr)
    #         l2idx = (page >> self.L2_OFF) & self.IDX_MASK
    #         self.pt_cache[l2addr][l2idx] = self.ptecls(
    #             SP_START=0, SP_END=0xfff,
    #             OFFSET=paddr >> self.PAGE_BITS, VALID=1, SP_PROT_DIS=1).value

    #     for page in dirty:
    #         self.flush_pt(page)

    def fetch_pte(self, offset, idx, size):
        idx = idx & (size - 1)

        cached, level = self.get_pt(offset, size=size)
        pte = self.ptecls(level[idx])
        if not pte.VALID and cached:
            cached, level = self.get_pt(offset, size=size, uncached=True)
            pte = self.ptecls(level[idx])
        #print(f"fetch_pte {size} {offset:#x} {idx:#x} {int(pte):#x}")

        return pte


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
            for (offset, size) in self.LEVELS:
                pte = self.fetch_pte(table_addr, page >> offset, size)
                if not pte.VALID:
                    break
                table_addr = pte.OFFSET << self.PAGE_BITS

            if pte.VALID:
                pages.append(pte.OFFSET << self.PAGE_BITS)
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
        self.iface.writemem(addr, struct.pack(f"<{self.Lx_SIZE}Q", *self.pt_cache[addr]))

    def invalidate_cache(self):
        self.pt_cache = {}

    def dump_level(self, level, base, table):
        def extend(addr):
            if addr >= 0x80_00000000:
                addr |= 0xf00_00000000
            return addr

        offset, size = self.LEVELS[level]

        cached, tbl = self.get_pt(table, size)
        unmapped = False
        for i, pte in enumerate(tbl):
            pte = self.ptecls(pte)
            if not pte.VALID:
                if not unmapped:
                    print("  ...")
                    unmapped = True
                continue
            unmapped = False

            range_size = 1 << offset
            start = extend(base + i * range_size)
            end = start + range_size - 1
            addr = pte.OFFSET << self.PAGE_BITS
            type = " page" if level + 1 == len(self.LEVELS) else "table"
            print(f"{'  ' * level}{type} ({i}): {start:011x} ... {end:011x}"
                       f" -> {addr:016x} [{int(pte):x}]")

            if level + 1 != len(self.LEVELS):
                self.dump_level(level + 1, start, addr)

    def dump(self, ctx):
        if not self.ttbr:
            print("No translation table")
            return

        self.dump_level(0, 0, self.ttbr + ctx * 16)