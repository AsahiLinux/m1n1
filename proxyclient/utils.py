import serial, os, struct, sys, time, json, os.path
from proxy import *
from tgtypes import *
import malloc

def load_registers():
    data = json.load(open(os.path.join(os.path.dirname(__file__), "regs.json")))
    for reg in data:
        yield reg["name"], reg["enc"]

globals().update(dict(load_registers()))

class ProxyUtils(object):
    def __init__(self, p):
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
        self.heap_size = 128 * 1024 * 1024
        try:
            self.heap_base = p.heapblock_alloc(0)
        except ProxyRemoteError:
            # Compat with versions that don't have heapblock yet
            self.heap_base = (self.base + ((self.ba.top_of_kernel_data + 0xffff) & ~0xffff) -
                              self.ba.phys_base)
        self.heap_base += 128 * 1024 * 1024 # We leave 128MB for m1n1 heap
        self.heap = malloc.Heap(self.heap_base, self.heap_base + self.heap_size)

        self.malloc = self.heap.malloc
        self.memalign = self.heap.memalign
        self.free = self.heap.free

        self.code_buffer = self.malloc(0x10000)

    def mrs(self, reg):
        op0, op1, CRn, CRm, op2 = reg

        op =  (((op0 & 1) << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5300000)

        func = struct.pack("<II", op, 0xd65f03c0)

        self.iface.writemem(self.code_buffer, func)
        self.proxy.dc_cvau(self.code_buffer, 8)
        self.proxy.ic_ivau(self.code_buffer, 8)

        self.proxy.set_exc_guard(self.proxy.GUARD_MARK)
        retval = self.proxy.call(self.code_buffer)
        cnt = self.proxy.get_exc_count()
        self.proxy.set_exc_guard(self.proxy.GUARD_OFF)
        if cnt:
            raise ProxyError("Exception occurred")
        return retval

    def msr(self, reg, val):
        op0, op1, CRn, CRm, op2 = reg

        op =  (((op0 & 1) << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5100000)

        func = struct.pack("<II", op, 0xd65f03c0)

        self.iface.writemem(self.code_buffer, func)
        self.proxy.dc_cvau(self.code_buffer, 8)
        self.proxy.ic_ivau(self.code_buffer, 8)

        self.proxy.set_exc_guard(self.proxy.GUARD_SKIP)
        self.proxy.call(self.code_buffer, val)
        cnt = self.proxy.get_exc_count()
        self.proxy.set_exc_guard(self.proxy.GUARD_OFF)
        if cnt:
            raise ProxyError("Exception occurred")

    def inst(self, op):
        func = struct.pack("<II", op, 0xd65f03c0)

        self.iface.writemem(self.code_buffer, func)
        self.proxy.dc_cvau(self.code_buffer, 8)
        self.proxy.ic_ivau(self.code_buffer, 8)

        self.proxy.set_exc_guard(self.proxy.GUARD_SKIP)
        self.proxy.call(self.code_buffer)
        cnt = self.proxy.get_exc_count()
        self.proxy.set_exc_guard(self.proxy.GUARD_OFF)
        if cnt:
            raise ProxyError("Exception occurred")

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
