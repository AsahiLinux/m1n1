import serial, os, struct, sys, time, json, os.path, gzip, functools
from asm import ARMAsm
from proxy import *
from tgtypes import *
from sysreg import *
import malloc, adt
from contextlib import contextmanager

class ProxyUtils(object):
    def __init__(self, p, heap_size=1024 * 1024 * 1024):
        self.iface = p.iface
        self.proxy = p
        self.base = p.get_base()
        self.ba_addr = p.get_bootargs()

        self.ba = self.iface.readstruct(self.ba_addr, BootArgs)

        # We allocate a 128MB heap, 128MB after the m1n1 heap, without telling it about it.
        # This frees up from having to coordinate memory management or free stuff after a Python
        # script runs, at the expense that if m1n1 ever uses more than 128MB of heap it will
        # clash with Python (m1n1 will normally not use *any* heap when running proxy ops though,
        # except when running very high-level operations like booting a kernel, so this should be
        # OK).
        self.heap_size = heap_size
        try:
            self.heap_base = p.heapblock_alloc(0)
        except ProxyRemoteError:
            # Compat with versions that don't have heapblock yet
            self.heap_base = (self.base + ((self.ba.top_of_kernel_data + 0xffff) & ~0xffff) -
                              self.ba.phys_base)
        self.heap_base += 128 * 1024 * 1024 # We leave 128MB for m1n1 heap
        self.heap_top = self.heap_base + self.heap_size
        self.heap = malloc.Heap(self.heap_base, self.heap_top)
        self.proxy.heap = self.heap

        self.malloc = self.heap.malloc
        self.memalign = self.heap.memalign
        self.free = self.heap.free

        self.code_buffer = self.malloc(0x10000)

        self.adt_data = None
        self.adt = LazyADT(self)

    def mrs(self, reg, silent=False, call=None):
        op0, op1, CRn, CRm, op2 = reg

        op =  (((op0 & 1) << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5300000)

        return self.exec(op, call=call)

    def msr(self, reg, val, silent=False, el0=False, call=None):
        op0, op1, CRn, CRm, op2 = reg

        op =  (((op0 & 1) << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5100000)

        self.exec(op, val, call=call)

    def exec(self, op, r0=0, r1=0, r2=0, r3=0, silent=False, call=None):
        if call is None:
            call = self.proxy.call
        if isinstance(op, int):
            func = struct.pack("<I", op)
        elif isinstance(op, str):
            c = ARMAsm(op, self.code_buffer)
            func = c.data
        else:
            raise ValueError()

        func += struct.pack("<I", 0xd65f03c0) # ret

        self.iface.writemem(self.code_buffer, func)
        self.proxy.dc_cvau(self.code_buffer, 8)
        self.proxy.ic_ivau(self.code_buffer, 8)

        self.proxy.set_exc_guard(GUARD.SKIP | (GUARD.SILENT if silent else 0))
        ret = call(self.code_buffer, r0, r1, r2, r3)
        cnt = self.proxy.get_exc_count()
        self.proxy.set_exc_guard(GUARD.OFF)
        if cnt:
            raise ProxyError("Exception occurred")
        return ret
    inst = exec

    def compressed_writemem(self, dest, data, progress):
        if not len(data):
            return

        payload = gzip.compress(data)
        compressed_size = len(payload)

        with self.heap.guarded_malloc(compressed_size) as compressed_addr:
            self.iface.writemem(compressed_addr, payload, progress)
            timeout = self.iface.dev.timeout
            self.iface.dev.timeout = None
            try:
                decompressed_size = self.proxy.gzdec(compressed_addr, compressed_size, dest, len(data))
            finally:
                self.iface.dev.timeout = timeout

            assert decompressed_size == len(data)

    def get_adt(self):
        if self.adt_data is not None:
            return self.adt_data
        adt_base = self.ba.devtree - self.ba.virt_base + self.ba.phys_base
        adt_size = self.ba.devtree_size
        print(f"Fetching ADT ({adt_size} bytes)...")
        self.adt_data = self.iface.readmem(adt_base, self.ba.devtree_size)
        return self.adt_data

    def push_adt(self):
        self.adt_data = self.adt.build()
        adt_base = self.ba.devtree - self.ba.virt_base + self.ba.phys_base
        adt_size = len(self.adt_data)
        print(f"Pushing ADT ({adt_size} bytes)...")
        self.iface.writemem(adt_base, self.adt_data)

    def disassemble_at(self, start, size, pc=None):
        code = struct.unpack(f"<{size // 4}I", self.iface.readmem(start, size))

        c = ARMAsm(".inst " + ",".join(str(i) for i in code), start)
        lines = list(c.disassemble())
        if pc is not None:
            idx = (pc - start) // 4
            lines[idx] = " *" + lines[idx][2:]
        for i in lines:
            print(" " + i)

    def print_exception(self, code, ctx):
        print(f"  == Exception taken from {ctx.spsr.M.name} ==")
        el = ctx.spsr.M >> 2
        print(f"  SPSR   = {ctx.spsr}")
        print(f"  ELR    = 0x{ctx.elr:x}" + (f" (0x{ctx.elr_phys:x})" if ctx.elr_phys else ""))
        print(f"  ESR    = {ctx.esr}")
        print(f"  FAR    = 0x{ctx.far:x}" + (f" (0x{ctx.far_phys:x})" if ctx.far_phys else ""))
        print(f"  SP_EL{el} = 0x{ctx.sp[el]:x}" + (f" (0x{ctx.sp_phys:x})" if ctx.sp_phys else ""))

        for i in range(0, 31, 4):
            j = min(30, i + 3)
            print(f"  {f'x{i}-x{j}':>7} = {' '.join(f'{r:016x}' for r in ctx.regs[i:j + 1])}")

        if ctx.elr_phys:
            print()
            print("  == Faulting code ==")

            self.disassemble_at(ctx.elr_phys - 4 * 4, 9 * 4, ctx.elr_phys)

        if code == EXC.SYNC:
            if ctx.esr.EC == ESR_EC.MSR:
                print()
                print("  == MRS/MSR fault decoding ==")
                iss = ESR_ISS_MSR(ctx.esr.ISS)
                enc = iss.Op0, iss.Op1, iss.CRn, iss.CRm, iss.Op2
                if enc in sysreg_rev:
                    name = sysreg_rev[enc]
                else:
                    name = f"s{iss.Op0}_{iss.Op1}_c{iss.CRn}_c{iss.CRm}_{iss.Op2}"
                if iss.DIR == MSR_DIR.READ:
                    print(f"  Instruction:   mrs x{iss.Rt}, {name}")
                else:
                    print(f"  Instruction:   msr {name}, x{iss.Rt}")

            if ctx.esr.EC in (ESR_EC.DABORT, ESR_EC.DABORT_LOWER):
                print()
                print("  == Data abort decoding ==")
                iss = ESR_ISS_DABORT(ctx.esr.ISS)
                if iss.ISV:
                    print(f"  ISS: {iss!s}")
                else:
                    print("  No instruction syndrome available")

        print()

    @contextmanager
    def mmu_disabled(self):
        flags = self.proxy.mmu_disable()
        try:
            yield
        finally:
            self.proxy.mmu_restore(flags)

class LazyADT:
    def __init__(self, utils):
        self.__dict__["_utils"] = utils

    @functools.cached_property
    def _adt(self):
        return adt.load_adt(self._utils.get_adt())
    def __getitem__(self, item):
        return self._adt[item]
    def __setitem__(self, item, value):
         self._adt[item] = value
    def __delitem__(self, item):
         del self._adt[item]
    def __getattr__(self, attr):
        return getattr(self._adt, attr)
    def __setattr__(self, attr, value):
        return setattr(self._adt, attr, value)
    def __delattr__(self, attr):
        return delattr(self._adt, attr)
    def __str__(self, t=""):
        return gstr(self._adt)
    def __iter__(self):
        return iter(self._adt)

class RegMonitor(object):
    def __init__(self, utils):
        self.utils = utils
        self.proxy = utils.proxy
        self.iface = self.proxy.iface
        self.ranges = []
        self.last = None

        base = utils.base
        self.scratch = utils.malloc(0x100000)

    def add(self, start, size):
        self.ranges.append((start, size))
        self.last = [None] * len(self.ranges)

    def poll(self):
        if not self.ranges:
            return
        cur = []
        for (start, size), last in zip(self.ranges, self.last):
            self.proxy.memcpy32(self.scratch, start, size)
            block = self.proxy.iface.readmem(self.scratch, size)
            count = size // 4

            words = struct.unpack("<%dI" % count, block)
            cur.append(words)
            if last == words:
                continue
            row = 8
            for i in range(0, count, row):
                if not last:
                    print("%016x" % (start + i * 4), end=" ")
                    for new in words[i:i+row]:
                        print("%08x" % new, end=" ")
                    print()
                elif last[i:i+row] != words[i:i+row]:
                    print("%016x" % (start + i * 4), end=" ")
                    for old, new in zip(last[i:i+row], words[i:i+row]):
                        so = "%08x" % old
                        sn = s = "%08x" % new
                        if old != new:
                            s = "\x1b[32m"
                            ld = False
                            for a,b in zip(so, sn):
                                d = a != b
                                if ld != d:
                                    s += "\x1b[31;1;4m" if d else "\x1b[32m"
                                    ld = d
                                s += b
                            s += "\x1b[m"
                        print(s, end=" ")
                    print()
        self.last = cur

class GuardedHeap:
    def __init__(self, malloc, memalign, free):
        self.ptrs = set()
        self.malloc = malloc
        self.memalign = memalign
        self.free = free

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.free_all()
        return False

    def malloc(self, sz):
        ptr = self.malloc(sz)
        self.ptrs.add(ptr)
        return ptr

    def memalign(self, align, sz):
        ptr = self.memalign(align, sz)
        self.ptrs.add(ptr)
        return ptr

    def free(self, ptr):
        self.ptrs.remove(ptr)
        self.free(ptr)

    def free_all(self):
        for ptr in self.ptrs:
            self.free(ptr)
        self.ptrs = set()

def bootstrap_port(iface, proxy):
    try:
        iface.dev.timeout = 0.15
        iface.nop()
        proxy.set_baud(1500000)
    except UartTimeout:
        iface.dev.baudrate = 1500000

    iface.nop()
    iface.dev.timeout = 3
