# SPDX-License-Identifier: MIT

from m1n1 import asm
from m1n1.trace import Tracer
from m1n1.utils import *
from m1n1.proxy import *
from m1n1.sysreg import *
from m1n1.proxyutils import RegMonitor
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, msg, msg_log, DIR
from m1n1.fw.pmp import *

#trace_device("/arm-io/pmgr", False)
#trace_device("/arm-io/jpeg0")
#trace_device("/arm-io/jpeg1")

#for reg in (0, 1, 2, 3, 4, 23):
    #addr, size = hv.adt["/arm-io/pmgr"].get_reg(reg)
    #hv.trace_range(irange(addr, 0x20000))

#hv.trace_range(irange(0x210e00000, 0x80000), read=False)
#hv.trace_range(irange(0x211e00000, 0x80000), read=False)

#hv.trace_range(irange(0x23b040000, 0x1000))
#hv.trace_range(irange(0x23b044000, 0x14000))

Tracer = Tracer._reloadcls()
ASCTracer = ASCTracer._reloadcls()

iomon = RegMonitor(hv.u, ascii=True)

def readmem_iova(addr, size):
    try:
        return dart_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova

class PMPEpTracer(EP):
    BASE_MESSAGE = PMPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.shmem_iova = None
        self.state.verbose = 1

    def start(self):
        self.add_mon()

    def add_mon(self):
        if self.state.shmem_iova:
            iomon.add(self.state.shmem_iova, 0x10000,
                      name=f"{self.name}.shmem@{self.state.shmem_iova:08x}", offset=0)

    @msg(1, DIR.TX, PMP_Configure)
    def Configure(self, msg):
        self.state.shmem_iova = msg.DVA
        self.add_mon()

class PMPTracer(ASCTracer):
    ENDPOINTS = {
        0x20: PMPEpTracer
    }

    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)
        iomon.poll()

    def start(self, dart=None):
        super().start()
        # noisy doorbell
        self.trace(0x23bc34000, 4, TraceMode.OFF)

#dart_tracer = DARTTracer(hv, "/arm-io/dart-pmp", verbose=2)
#dart_tracer.start()

#pmp_tracer = PMPTracer(hv, "/arm-io/pmp", verbose=1)
#pmp_tracer.start(dart_tracer.dart)

class PMGRTracer(Tracer):
    IGNORED = set(["SPI1", "I2C2"])
    def __init__(self, hv):
        super().__init__(hv)
        self.dev = hv.adt["/arm-io/pmgr"]
        self.ignored_ranges = [
            (0x23b738004, 4), # ecpu state report
            (0x23b738008, 4), # pcpu state report
            (0x23d2b9000, 0x30),
            (0x23d2dc100, 4),
        ]
        self.build_table(hv)
        self.reg_cache = {}

    def hook_w(self, addr, val, width, **kwargs):
        self.hv.log(f"PMGR: W {addr:#x} <- {val:#x}")
        #print("-> ignored")
        super().hook_w(addr, val, width, **kwargs)

    def hook_r(self, addr, width, **kwargs):
        val = super().hook_r(addr, width, **kwargs)
        self.hv.log(f"PMGR: R {addr:#x} = {val:#x}")
        return val

    def evt_rw(self, evt):
        if not evt.flags.WRITE:
            self.reg_cache[evt.addr] = evt.data
        cb = self.ranges.lookup(evt.addr)
        cb[0](evt, *cb[1:])
        self.reg_cache[evt.addr] = evt.data

    def event_default(self, evt, start, name):
        t = "W" if evt.flags.WRITE else "R"
        m = "+" if evt.flags.MULTI else " "
        data = f"{evt.data:#x}"
        if evt.flags.WRITE:
            data = f"{evt.data:#x}"
            old = self.reg_cache.get(evt.addr, None)
            if old is not None:
                data = f"{old:#x} -> {evt.data:#x}"
        self.hv.log(f"[cpu{evt.flags.CPU}][0x{evt.pc:016x}] PMGR: {t}.{1<<evt.flags.WIDTH:<2}{m} " +
                    f"0x{evt.addr:x} ({name} + {evt.addr - start:#04x}) = {data}", show_cpu=False)

    def build_table(self, hv):
        self.ranges = ScalarRangeMap()
        self.state_regs = {}

        starts = {}
        for reg in (0, 1):
            addr, size = self.dev.get_reg(reg)
            self.ranges[addr:addr + size] = self.event_default, addr, f"reg[{reg}]"

        for i, ps in enumerate(self.dev.ps_regs):
            addr = self.dev.get_reg(ps.reg)[0] + ps.offset
            for idx in range(32):
                ps_addr = addr + idx * 8
                self.ranges[ps_addr:ps_addr + 8] = self.event_default, ps_addr, f"ps[{i}][{idx}]"

        for i, dev in enumerate(self.dev.devices):
            ps = self.dev.ps_regs[dev.psreg]
            if dev.psidx or dev.psreg:
                addr = self.dev.get_reg(ps.reg)[0] + ps.offset + dev.psidx * 8
                self.state_regs[addr] = dev.name
                if dev.name in self.IGNORED:
                    self.ignored_ranges.append((addr, 8))
                self.ranges[addr:addr + 8] = self.event_default, addr, f"{dev.name}.pstate"

    def start(self):
        self.hv.clear_tracers(self.ident)

        for reg in (0, 1):
            addr, size = self.dev.get_reg(reg)
            self.trace(addr, size, TraceMode.WSYNC, read=False)

        for ps in self.dev.ps_regs:
            addr = self.dev.get_reg(ps.reg)[0] + ps.offset
            self.trace(addr, 0x100, TraceMode.WSYNC)

        for lane in range(8):
            addr = 0x200200000 + 0x40000 * lane
            self.trace(addr, 0x40000, TraceMode.HOOK)
        #for reg in (23,):
            #addr, size = self.dev.get_reg(reg)
            #self.trace(addr, 0x20000, TraceMode.SYNC)
        for addr, size in self.ignored_ranges:
            self.trace(addr, size, TraceMode.OFF)

pmgr_tracer = PMGRTracer(hv)
pmgr_tracer.start()
