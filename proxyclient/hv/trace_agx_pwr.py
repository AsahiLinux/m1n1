# SPDX-License-Identifier: MIT
import datetime

from m1n1.constructutils import show_struct_trace, Ver
from m1n1.utils import *

Ver.set_version(hv.u)

trace_device("/arm-io/sgx", True)
#trace_device("/arm-io/pmp", True)
#trace_device("/arm-io/gfx-asc", False)

from m1n1.trace.agx import AGXTracer
AGXTracer = AGXTracer._reloadcls(True)

agx_tracer = AGXTracer(hv, "/arm-io/gfx-asc", verbose=1)
agx_tracer.trace_kernmap = False
agx_tracer.trace_kernva = False
agx_tracer.trace_usermap = False

sgx = hv.adt["/arm-io/sgx"]

freqs =    []
voltages = []

for j in range(8):
    for i, v in enumerate(voltages):
        if j != 0:
            v = 1
        sgx.perf_states[i+j*len(voltages)].freq = freqs[i] * 1000000
        sgx.perf_states[i+j*len(voltages)].volt = v
        sgx.perf_states_sram[i+j*len(voltages)].freq = freqs[i] * 1000000
        sgx.perf_states_sram[i+j*len(voltages)].volt = 1
        if j >= 1:
            getattr(sgx, f"perf_states{j}")[i].freq = freqs[i] * 1000000
            getattr(sgx, f"perf_states{j}")[i].volt = v
            getattr(sgx, f"perf_states_sram{j}")[i].freq = freqs[i] * 1000000
            getattr(sgx, f"perf_states_sram{j}")[i].volt = 1

def after_init():
    plat = hv.adt.compatible[0].lower()
    fname = f"initdata/{datetime.datetime.now().isoformat()}-{plat}.log"
    idlog = open(fname, "w")
    print(f"Platform: {plat}", file=idlog)
    fw = hv.adt["/chosen"].firmware_version.split(b"\0")[0].decode("ascii")
    print(f"Firmware: {fw}", file=idlog)
    sfw = hv.adt["/chosen"].system_firmware_version
    print(f"System firmware: {sfw}", file=idlog)
    print(file=idlog)

    print("ADT SGX:", file=idlog)
    print(sgx, file=idlog)
    open("adt_hv.txt","w").write(str(hv.adt))

    print("InitData:", file=idlog)
    print(agx_tracer.state.initdata, file=idlog)

    power = [int(i) for i in agx_tracer.state.initdata.regionB.hwdata_b.rel_max_powers]
    volt = [int(i[0]) for i in agx_tracer.state.initdata.regionB.hwdata_b.voltages]
    freq = [int(i) for i in agx_tracer.state.initdata.regionB.hwdata_b.frequencies]

    print("p/v", [p/max(1, v) for p,v in zip(power,volt)])
    print("p/f", [p/max(1, f) for p,f in zip(power,freq)])
    print("p/v2", [p/max(1, (v*v)) for p,v in zip(power,volt)])
    hv.reboot()

agx_tracer.after_init_hook = after_init

#agx_tracer.encoder_id_filter = lambda i: (i >> 16) == 0xc0de
agx_tracer.start()

def resume_tracing(ctx):
    fname = f"{datetime.datetime.now().isoformat()}.log"
    hv.set_logfile(open(f"gfxlogs/{fname}", "a"))
    agx_tracer.resume()
    return True

def pause_tracing(ctx):
    agx_tracer.pause()
    hv.set_logfile(None)
    return True

hv.add_hvcall(100, resume_tracing)
hv.add_hvcall(101, pause_tracing)

mode = TraceMode.SYNC
trace_range(irange(agx_tracer.gpu_region, agx_tracer.gpu_region_size), mode=mode, name="gpu_region")
trace_range(irange(agx_tracer.gfx_shared_region, agx_tracer.gfx_shared_region_size), mode=mode, name="gfx_shared_region")

## Trace the entire mmio range around the GPU
node = hv.adt["/arm-io/sgx"]
addr, size = node.get_reg(0)
hv.trace_range(irange(addr, 0x1000000), TraceMode.SYNC, name="sgx")
#hv.trace_range(irange(addr, 0x1000000), TraceMode.OFF, name="sgx")
hv.trace_range(irange(0x204017030, 8), TraceMode.SYNC, name="faultcode")

trace_device("/arm-io/sgx", True)
trace_device("/arm-io/gfx-asc", False)

def trace_all_gfx_io():
    # These are all the IO ranges that get mapped into the UAT iommu pagetable
    # Trace them so we can see if any of them are being written by the CPU

    # page (8): fa010020000 ... fa010023fff -> 000000020e100000 [8000020e100447]
    hv.trace_range(irange(0x20e100000, 0x4000), mode=TraceMode.SYNC)

    # page (10): fa010028000 ... fa01002bfff -> 000000028e104000 [c000028e104447]
    hv.trace_range(irange(0x20e100000, 0x4000), mode=TraceMode.SYNC)

    # page (22): fa010058000 ... fa01005bfff -> 000000028e494000 [8000028e494447]
    hv.trace_range(irange(0x28e494000, 0x4000), mode=TraceMode.SYNC)

    # page (28): fa010070000 ... fa010073fff -> 0000000204d60000 [c0000204d60447]
    hv.trace_range(irange(0x204d60000, 0x4000), mode=TraceMode.SYNC)

    # page (30): fa010078000 ... fa01007bfff -> 0000000200000000 [c0000200000447]
    #    to
    # page (83): fa01014c000 ... fa01014ffff -> 00000002000d4000 [c00002000d4447]
    hv.trace_range(irange(0x200000000, 0xd5000), mode=TraceMode.SYNC)

    # page (84): fa010150000 ... fa010153fff -> 0000000201000000 [c0000201000447]
    #page (137): fa010224000 ... fa010227fff -> 00000002010d4000 [c00002010d4447]
    hv.trace_range(irange(0x201000000, 0xd5000), mode=TraceMode.SYNC)

    # page (138): fa010228000 ... fa01022bfff -> 0000000202000000 [c0000202000447]
    # page (191): fa0102fc000 ... fa0102fffff -> 00000002020d4000 [c00002020d4447]
    hv.trace_range(irange(0x202000000, 0xd5000), mode=TraceMode.SYNC)

    # page (192): fa010300000 ... fa010303fff -> 0000000203000000 [c0000203000447]
    hv.trace_range(irange(0x203000000, 0xd5000), mode=TraceMode.SYNC)
    hv.trace_range(irange(0x204000000, 0xd5000), mode=TraceMode.SYNC)
    hv.trace_range(irange(0x205000000, 0xd5000), mode=TraceMode.SYNC)
    hv.trace_range(irange(0x206000000, 0xd5000), mode=TraceMode.SYNC)
    hv.trace_range(irange(0x207000000, 0xd5000), mode=TraceMode.SYNC)

    # page (464): fa010740000 ... fa010743fff -> 00000002643c4000 [c00002643c4447]
    hv.trace_range(irange(0x2643c4000, 0x4000), mode=TraceMode.SYNC)
    # page (466): fa010748000 ... fa01074bfff -> 000000028e3d0000 [c000028e3d0447]
    hv.trace_range(irange(0x28e3d0000, 0x4000), mode=TraceMode.SYNC)
    # page (468): fa010750000 ... fa010753fff -> 000000028e3c0000 [8000028e3c0447]
    hv.trace_range(irange(0x28e3c0000, 0x4000), mode=TraceMode.SYNC)

    # page (8): f9100020000 ... f9100023fff -> 0000000406000000 [60000406000447]
    # page (263): f910041c000 ... f910041ffff -> 00000004063fc000 [600004063fc447]
    hv.trace_range(irange(0x2643c4000, 0x63fc000), mode=TraceMode.SYNC)

def trace_gpu_irqs():
    # Trace sgx interrupts
    node = hv.adt["/arm-io/sgx"]
    for irq in getattr(node, "interrupts"):
        hv.trace_irq(f"{node.name} {irq}", irq, 1, hv.IRQTRACE_IRQ)

    ## Trace gfx-asc interrupts
    #node = hv.adt["/arm-io/gfx-asc"]
    #for irq in getattr(node, "interrupts"):
        #hv.trace_irq(f"{node.name} {irq}", irq, 1, hv.IRQTRACE_IRQ)

trace_gpu_irqs()
