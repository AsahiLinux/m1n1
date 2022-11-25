# SPDX-License-Identifier: MIT
import serial, os, struct, sys, time, json, os.path, gzip, functools
from contextlib import contextmanager
from construct import *

from .asm import ARMAsm
from .proxy import *
from .utils import Reloadable, chexdiff32
from .tgtypes import *
from .sysreg import *
from .malloc import Heap
from . import adt

__all__ = ["ProxyUtils", "RegMonitor", "GuardedHeap", "bootstrap_port"]

SIMD_B = Array(32, Array(16, Int8ul))
SIMD_H = Array(32, Array(8, Int16ul))
SIMD_S = Array(32, Array(4, Int32ul))
SIMD_D = Array(32, Array(2, Int64ul))
SIMD_Q = Array(32, BytesInteger(16, swapped=True))

# This isn't perfect, since multiple versions could have the same
# iBoot version, but it's good enough
VERSION_MAP = {
    "iBoot-7429.61.2": "V12_1",
    "iBoot-7459.101.2": "V12_3",
    "iBoot-7459.121.3": "V12_4",
    "iBoot-8419.0.151.0.1": "V13_0B4",
}

class ProxyUtils(Reloadable):
    CODE_BUFFER_SIZE = 0x10000
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

        if os.environ.get("M1N1HEAP", ""):
            self.heap_base = int(os.environ.get("M1N1HEAP", ""), 16)

        self.heap_base += 128 * 1024 * 1024 # We leave 128MB for m1n1 heap
        self.heap_top = self.heap_base + self.heap_size
        self.heap = Heap(self.heap_base, self.heap_top)
        self.proxy.heap = self.heap

        self.malloc = self.heap.malloc
        self.memalign = self.heap.memalign
        self.free = self.heap.free

        self.code_buffer = self.malloc(self.CODE_BUFFER_SIZE)

        self.adt_data = None
        self.adt = LazyADT(self)

        self.simd_buf = self.malloc(32 * 16)
        self.simd_type = None
        self.simd = None

        self.mmu_off = False

        self.inst_cache = {}

        self.exec_modes = {
            None: (self.proxy.call, REGION_RX_EL1),
            "el2": (self.proxy.call, REGION_RX_EL1),
            "el1": (self.proxy.el1_call, 0),
            "el0": (self.proxy.el0_call, REGION_RWX_EL0),
            "gl2": (self.proxy.gl2_call, REGION_RX_EL1),
            "gl1": (self.proxy.gl1_call, 0),
        }
        self._read = {
            8: lambda addr: self.proxy.read8(addr),
            16: lambda addr: self.proxy.read16(addr),
            32: lambda addr: self.proxy.read32(addr),
            64: lambda addr: self.uread64(addr),
            128: lambda addr: [self.uread64(addr),
                               self.uread64(addr + 8)],
            256: lambda addr: [self.uread64(addr),
                               self.uread64(addr + 8),
                               self.uread64(addr + 16),
                               self.uread64(addr + 24)],
            512: lambda addr: [self.uread64(addr + i) for i in range(0, 64, 8)],
        }
        self._write = {
            8: lambda addr, data: self.proxy.write8(addr, data),
            16: lambda addr, data: self.proxy.write16(addr, data),
            32: lambda addr, data: self.proxy.write32(addr, data),
            64: lambda addr, data: self.uwrite64(addr, data),
            128: lambda addr, data: (self.uwrite64(addr, data[0]),
                                     self.uwrite64(addr + 8, data[1])),
            256: lambda addr, data: (self.uwrite64(addr, data[0]),
                                     self.uwrite64(addr + 8, data[1]),
                                     self.uwrite64(addr + 16, data[2]),
                                     self.uwrite64(addr + 24, data[3])),
            512: lambda addr, data: [self.uwrite64(addr + 8 * i, data[i])
                                     for i in range(8)],
        }

    def uwrite64(self, addr, data):
        '''write 8 byte value to given address, supporting split 4-byte halves'''
        if addr & 3:
            raise AlignmentError()
        if addr & 4:
            self.proxy.write32(addr, data & 0xffffffff)
            self.proxy.write32(addr + 4, data >> 32)
        else:
            self.proxy.write64(addr, data)

    def uread64(self, addr):
        '''write 8 byte value to given address, supporting split 4-byte halves'''
        if addr & 3:
            raise AlignmentError()
        if addr & 4:
            return self.proxy.read32(addr) | (self.proxy.read32(addr + 4) << 32)
        else:
            return self.proxy.read64(addr)

    def read(self, addr, width):
        '''do a width read from addr and return it
        width can be 8, 16, 21, 64, 128 or 256'''
        val = self._read[width](addr)
        if self.proxy.get_exc_count():
            raise ProxyError("Exception occurred")
        return val

    def write(self, addr, data, width):
        '''do a width write of data to addr
        width can be 8, 16, 21, 64, 128 or 256'''
        self._write[width](addr, data)
        if self.proxy.get_exc_count():
            raise ProxyError("Exception occurred")

    def mrs(self, reg, *, silent=False, call=None):
        '''read system register reg'''
        op0, op1, CRn, CRm, op2 = sysreg_parse(reg)

        op =  ((op0 << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5200000)

        return self.exec(op, call=call, silent=silent)

    def msr(self, reg, val, *, silent=False, call=None):
        '''Write val to system register reg'''
        op0, op1, CRn, CRm, op2 = sysreg_parse(reg)

        op =  ((op0 << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5000000)

        self.exec(op, val, call=call, silent=silent)

    sys = msr
    sysl = mrs

    def exec(self, op, r0=0, r1=0, r2=0, r3=0, *, silent=False, call=None, ignore_exceptions=False):
        if callable(call):
            region = REGION_RX_EL1
        elif isinstance(call, tuple):
            call, region = call
        else:
            call, region = self.exec_modes[call]

        if isinstance(op, list):
            op = tuple(op)

        if op in self.inst_cache:
            func = self.inst_cache[op]
        elif isinstance(op, tuple) or isinstance(op, list):
            func = struct.pack(f"<{len(op)}II", *op, 0xd65f03c0) # ret
        elif isinstance(op, int):
            func = struct.pack("<II", op, 0xd65f03c0) # ret
        elif isinstance(op, str):
            c = ARMAsm(op + "; ret", self.code_buffer)
            func = c.data
        elif isinstance(op, bytes):
            func = op
        else:
            raise ValueError()

        if self.mmu_off:
            region = 0

        self.inst_cache[op] = func

        assert len(func) < self.CODE_BUFFER_SIZE
        self.iface.writemem(self.code_buffer, func)
        self.proxy.dc_cvau(self.code_buffer, len(func))
        self.proxy.ic_ivau(self.code_buffer, len(func))

        self.proxy.set_exc_guard(GUARD.SKIP | (GUARD.SILENT if silent else 0))
        ret = call(self.code_buffer | region, r0, r1, r2, r3)
        if not ignore_exceptions:
            cnt = self.proxy.get_exc_count()
            self.proxy.set_exc_guard(GUARD.OFF)
            if cnt:
                raise ProxyError("Exception occurred")
        else:
            self.proxy.set_exc_guard(GUARD.OFF)

        return ret

    inst = exec

    def compressed_writemem(self, dest, data, progress=None):
        if not len(data):
            return

        payload = gzip.compress(data, compresslevel=1)
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
        adt_base = (self.ba.devtree - self.ba.virt_base + self.ba.phys_base) & 0xffffffffffffffff
        adt_size = self.ba.devtree_size
        print(f"Fetching ADT ({adt_size} bytes)...")
        self.adt_data = self.iface.readmem(adt_base, self.ba.devtree_size)
        return self.adt_data

    def push_adt(self):
        self.adt_data = self.adt.build()
        adt_base = (self.ba.devtree - self.ba.virt_base + self.ba.phys_base) & 0xffffffffffffffff
        adt_size = len(self.adt_data)
        print(f"Pushing ADT ({adt_size} bytes)...")
        self.iface.writemem(adt_base, self.adt_data)

    def disassemble_at(self, start, size, pc=None, vstart=None, sym=None):
        '''disassemble len bytes of memory from start
         optional pc address will mark that line with a '*' '''
        code = struct.unpack(f"<{size // 4}I", self.iface.readmem(start, size))
        if vstart is None:
            vstart = start

        c = ARMAsm(".inst " + ",".join(str(i) for i in code), vstart)
        lines = list()
        for line in c.disassemble():
            sl = line.split()
            try:
                addr = int(sl[0].rstrip(":"), 16)
            except:
                addr = None
            if pc == addr:
                line = " *" + line
            else:
                line = "  " + line
            if sym:
                if s := sym(addr):
                    print()
                    print(f"{' '*len(sl[0])}   {s}:")
            print(line)

    def print_l2c_regs(self):
        print()
        print("  == L2C Registers ==")
        l2c_err_sts = self.mrs(L2C_ERR_STS_EL1)

        print(f"  L2C_ERR_STS: {l2c_err_sts:#x}")
        print(f"  L2C_ERR_ADR: {self.mrs(L2C_ERR_ADR_EL1):#x}");
        print(f"  L2C_ERR_INF: {self.mrs(L2C_ERR_INF_EL1):#x}");

        self.msr(L2C_ERR_STS_EL1, l2c_err_sts) # Clear the flag bits
        self.msr(DAIF, self.mrs(DAIF) | 0x100) # Re-enable SError exceptions

    def print_context(self, ctx, is_fault=True, addr=lambda a: f"0x{a:x}", sym=None, num_ctx=9):
        print(f"  == Exception taken from {ctx.spsr.M.name} ==")
        el = ctx.spsr.M >> 2
        print(f"  SPSR   = {ctx.spsr}")
        print(f"  ELR    = {addr(ctx.elr)}" + (f" (0x{ctx.elr_phys:x})" if ctx.elr_phys else ""))
        print(f"  SP_EL{el} = 0x{ctx.sp[el]:x}" + (f" (0x{ctx.sp_phys:x})" if ctx.sp_phys else ""))
        if is_fault:
            print(f"  ESR    = {ctx.esr}")
            print(f"  FAR    = {addr(ctx.far)}" + (f" (0x{ctx.far_phys:x})" if ctx.far_phys else ""))

        for i in range(0, 31, 4):
            j = min(30, i + 3)
            print(f"  {f'x{i}-x{j}':>7} = {' '.join(f'{r:016x}' for r in ctx.regs[i:j + 1])}")

        if ctx.elr_phys:
            print()
            print("  == Code context ==")

            off = -(num_ctx // 2)

            self.disassemble_at(ctx.elr_phys + 4 * off, num_ctx * 4, ctx.elr, ctx.elr + 4 * off, sym=sym)

        if is_fault:
            if ctx.esr.EC == ESR_EC.MSR or ctx.esr.EC == ESR_EC.IMPDEF and ctx.esr.ISS == 0x20:
                print()
                print("  == MRS/MSR fault decoding ==")
                if ctx.esr.EC == ESR_EC.MSR:
                    iss = ESR_ISS_MSR(ctx.esr.ISS)
                else:
                    iss = ESR_ISS_MSR(self.mrs(AFSR1_EL2))
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

                if iss.DFSC == DABORT_DFSC.ECC_ERROR:
                    self.print_l2c_regs()

            if ctx.esr.EC == ESR_EC.SERROR and ctx.esr.ISS == 0:
                self.print_l2c_regs()

        print()

    @contextmanager
    def mmu_disabled(self):
        flags = self.proxy.mmu_disable()
        try:
            yield
        finally:
            self.proxy.mmu_restore(flags)

    def push_simd(self):
        if self.simd is not None:
            data = self.simd_type.build(self.simd)
            self.iface.writemem(self.simd_buf, data)
            self.proxy.put_simd_state(self.simd_buf)
            self.simd = self.simd_type = None

    def get_simd(self, simd_type):
        if self.simd is not None and self.simd_type is not simd_type:
            data = self.simd_type.build(self.simd)
            self.simd = simd_type.parse(data)
            self.simd_type = simd_type
        elif self.simd is None:
            self.proxy.get_simd_state(self.simd_buf)
            data = self.iface.readmem(self.simd_buf, 32 * 16)
            self.simd = simd_type.parse(data)
            self.simd_type = simd_type

        return self.simd

    @property
    def b(self):
        return self.get_simd(SIMD_B)
    @property
    def h(self):
        return self.get_simd(SIMD_H)
    @property
    def s(self):
        return self.get_simd(SIMD_S)
    @property
    def d(self):
        return self.get_simd(SIMD_D)
    @property
    def q(self):
        return self.get_simd(SIMD_Q)

    def get_version(self, v):
        if isinstance(v, bytes):
            v = v.split(b"\0")[0].decode("ascii")
        return VERSION_MAP.get(v, None)

    @property
    def version(self):
        return self.get_version(self.adt["/chosen"].firmware_version)

    @property
    def sfr_version(self):
        return self.get_version(self.adt["/chosen"].system_firmware_version)

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
        return str(self._adt)
    def __iter__(self):
        return iter(self._adt)

class RegMonitor(Reloadable):
    def __init__(self, utils, bufsize=0x100000, ascii=False, log=None):
        self.utils = utils
        self.proxy = utils.proxy
        self.iface = self.proxy.iface
        self.ranges = []
        self.last = []
        self.bufsize = bufsize
        self.ascii = ascii
        self.log = log or print

        if bufsize:
            self.scratch = utils.malloc(bufsize)
        else:
            self.scratch = None

    def readmem(self, start, size, readfn):
        if readfn:
            return readfn(start, size)
        if self.scratch:
            assert size < self.bufsize
            self.proxy.memcpy32(self.scratch, start, size)
            start = self.scratch
        return self.proxy.iface.readmem(start, size)

    def add(self, start, size, name=None, offset=None, readfn=None):
        if offset is None:
            offset = start
        self.ranges.append((start, size, name, offset, readfn))
        self.last.append(None)

    def show_regions(self, log=print):
        for start, size, name, offset, readfn in sorted(self.ranges):
            end = start + size - 1
            log(f"{start:#x}..{end:#x} ({size:#x})\t{name}")

    def poll(self):
        if not self.ranges:
            return
        cur = []
        for (start, size, name, offset, readfn), last in zip(self.ranges, self.last):
            count = size // 4
            block = self.readmem(start, size, readfn)
            if block is None:
                if last is not None:
                    self.log(f"# Lost: {name} ({start:#x}..{start + size - 1:#x})")
                cur.append(None)
                continue

            words = struct.unpack("<%dI" % count, block)
            cur.append(block)
            if last == block:
                continue
            if name:
                header = f"# {name} ({start:#x}..{start + size - 1:#x})\n"
            else:
                header = f"# ({start:#x}..{start + size - 1:#x})\n"

            self.log(header + chexdiff32(last, block, offset=offset))
        self.last = cur

class GuardedHeap:
    def __init__(self, malloc, memalign=None, free=None):
        if isinstance(malloc, Heap):
            malloc, memalign, free = malloc.malloc, malloc.memalign, malloc.free

        self.ptrs = set()
        self._malloc = malloc
        self._memalign = memalign
        self._free = free

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.free_all()
        return False

    def malloc(self, sz):
        ptr = self._malloc(sz)
        self.ptrs.add(ptr)
        return ptr

    def memalign(self, align, sz):
        ptr = self._memalign(align, sz)
        self.ptrs.add(ptr)
        return ptr

    def free(self, ptr):
        self.ptrs.remove(ptr)
        self._free(ptr)

    def free_all(self):
        for ptr in self.ptrs:
            self._free(ptr)
        self.ptrs = set()

def bootstrap_port(iface, proxy):
    to = iface.dev.timeout
    iface.dev.timeout = 0.15
    try:
        do_baud = proxy.iodev_whoami() == IODEV.UART
    except ProxyCommandError:
        # Old m1n1 version -- assume non-USB serial link, force baudrate adjust
        do_baud = True
    except UartTimeout:
        # Assume the receiving end is already at 1500000
        iface.dev.baudrate = 1500000
        do_baud = False

    if do_baud:
        try:
            iface.nop()
            proxy.set_baud(1500000)
        except UartTimeout:
            # May fail even if the setting did get applied; checked by the .nop next
            iface.dev.baudrate = 1500000

    iface.nop()
    iface.dev.timeout = to
