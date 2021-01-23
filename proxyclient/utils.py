import serial, os, struct, sys, time
from proxy import *
from tgtypes import *
import malloc

CurrentEL = 3,0,4,2,2
DAIF = 3,3,4,2,1

DAIFSet = 0,3,4,2,6
DAIFClr = 0,3,4,2,7

TPIDR_EL0 = 3,3,13,0,2

CNTFRQ_EL0 = 3,3,14,0,0
CNTPCT_EL0 = 3,3,14,0,1
CNTP_TVAL_EL0 = 3,3,14,2,0
CNTP_CTL_EL0 = 3,3,14,2,1
CNTP_CVAL_EL0 = 3,3,14,2,2

SCTLR_EL1 = 3,0,1,0,0
TTBR0_EL1 = 3,0,2,0,0
TTBR0_EL2 = 3,4,2,0,0
TCR_EL1 = 3,0,2,0,2
TCR_EL2 = 3,4,2,0,2
HCR_EL2 = 3,4,1,1,0

MIDR_EL1 = 3,0,0,0,0
MPIDR_EL1 = 3,0,0,0,5
AA64MMFR0_EL1 = 3,0,0,7,0

OSLAR_EL1 = 2,0,1,0,4

ACTLR_EL1 = 3,0,1,0,1

class ProxyUtils(object):
    def __init__(self, p):
        self.iface = p.iface
        self.proxy = p
        self.base = p.get_base()
        self.ba_addr = p.get_bootargs()

        self.ba = self.iface.readstruct(self.ba_addr, BootArgs)
        self._scratch = self.base + ((self.ba.top_of_kernel_data + 0xffff) & ~0xffff) - self.ba.phys_base

        self.heap = malloc.Heap(self._scratch, self._scratch + 0x1000000)

        self.malloc = self.heap.malloc
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

        return self.proxy.call(self.code_buffer)

    def msr(self, reg, val):
        op0, op1, CRn, CRm, op2 = reg

        op =  (((op0 & 1) << 19) | (op1 << 16) | (CRn << 12) |
               (CRm << 8) | (op2 << 5) | 0xd5100000)

        func = struct.pack("<II", op, 0xd65f03c0)

        self.iface.writemem(self.code_buffer, func)
        self.proxy.dc_cvau(self.code_buffer, 8)
        self.proxy.ic_ivau(self.code_buffer, 8)

        self.proxy.call(self.code_buffer, val)

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
