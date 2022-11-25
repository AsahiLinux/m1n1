#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import atexit, sys

from m1n1.setup import *
from m1n1.constructutils import Ver
from m1n1.utils import *

Ver.set_version(u)

from m1n1.agx import AGX
from m1n1.agx.render import *

from m1n1 import asm

from m1n1.gpiola import GPIOLogicAnalyzer

analyzer_cpu = 1

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")
p.smp_start_secondaries()
p.mmu_init_secondary(analyzer_cpu)
iface.dev.timeout = 42

agx = AGX(u)

def initdata_hook(agx):
    agx.initdata.regionC.idle_to_off_timeout_ms = 20000
    agx.initdata.regionC.push()

agx.initdata_hook = initdata_hook

mon = RegMonitor(u, ascii=True, bufsize=0x8000000)
agx.mon = mon

sgx = agx.sgx_dev
#mon.add(sgx.gpu_region_base, sgx.gpu_region_size, "contexts")
#mon.add(sgx.gfx_shared_region_base, sgx.gfx_shared_region_size, "gfx-shared")
#mon.add(sgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

#mon.add(agx.initdasgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

atexit.register(p.reboot)
agx.start()

print("==========================================")
print("## After init")
print("==========================================")
mon.poll()
agx.poll_objects()

ctx = GPUContext(agx)
ctx.bind(3)

f = GPUFrame(ctx, sys.argv[1], track=False)

RENDERERS = 1
FRAMES = 1

renderers = []

for i in range(RENDERERS):
    r = GPURenderer(ctx, 4, bm_slot=0x10 + i, queue=1)
    renderers.append(r)

    for q in (r.wq_3d, r.wq_ta):
        q.info.set_prio(2)
        q.info.push()

print("==========================================")
print("## Submitting")
print("==========================================")

for i, r in enumerate(renderers):
    for j in range(FRAMES):
        r.submit(f.cmdbuf)

print("==========================================")
print("## Submitted")
print("==========================================")

def t(addr):
    paddr = agx.uat.iotranslate(0, addr, 4)[0][0]
    if paddr is None:
        raise Exception(f"Failed to iotranslate {addr:#x}")
    return paddr

regs = {
    "ta_cmds":  t(agx.initdata.regionB.stats_ta.addrof("total_cmds")),
    "ta_ts":    t(agx.initdata.regionB.stats_ta.stats.addrof("unk_timestamp")),
}

#pend_base = agx.initdata.regionC.addrof("pending_stamps")
#for i in range(5):
    #regs[f"st{i}_info"] = t(pend_base + i*8)
    #regs[f"st{i}_val"] = t(pend_base + i*8 + 4)

#for i in range(4):
    #regs[f"ta{i}_cq"] = t(agx.initdata.regionB.stats_ta.stats.queues[i].addrof("cur_cmdqueue"))

regs.update({
    "pwr_status": t(agx.initdata.regionB.hwdata_a.addrof("pwr_status")),
    "pstate": t(agx.initdata.regionB.hwdata_a.addrof("cur_pstate")),
    "temp_c": t(agx.initdata.regionB.hwdata_a.addrof("temp_c")),
    "pwr_mw": t(agx.initdata.regionB.hwdata_a.addrof("avg_power_mw")),
    "pwr_ts": t(agx.initdata.regionB.hwdata_a.addrof("update_ts")),

    "unk_10": t(agx.initdata.regionB.hwdata_a.addrof("unk_10")),
    "unk_14": t(agx.initdata.regionB.hwdata_a.addrof("unk_14")),
    "actual_pstate": t(agx.initdata.regionB.hwdata_a.addrof("actual_pstate")),
    "tgt_pstate": t(agx.initdata.regionB.hwdata_a.addrof("tgt_pstate")),
    "unk_40": t(agx.initdata.regionB.hwdata_a.addrof("unk_40")),
    "unk_44": t(agx.initdata.regionB.hwdata_a.addrof("unk_44")),
    "unk_48": t(agx.initdata.regionB.hwdata_a.addrof("unk_48")),
    "freq_mhz": t(agx.initdata.regionB.hwdata_a.addrof("freq_mhz")),

    "unk_748.0": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")),
    "unk_748.1": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")+4),
    "unk_748.2": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")+8),
    "unk_748.3": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")+12),
    "use_percent": t(agx.initdata.regionB.hwdata_a.addrof("use_percent")),
    "unk_83c": t(agx.initdata.regionB.hwdata_a.addrof("unk_83c")),
    "freq_with_off": t(agx.initdata.regionB.hwdata_a.addrof("freq_with_off")),
    "unk_ba0": t(agx.initdata.regionB.hwdata_a.addrof("unk_ba0")),
    "unk_bb0": t(agx.initdata.regionB.hwdata_a.addrof("unk_bb0")),
    "unk_c44": t(agx.initdata.regionB.hwdata_a.addrof("unk_c44")),
    "unk_c58": t(agx.initdata.regionB.hwdata_a.addrof("unk_c58")),

    "unk_3ca0": t(agx.initdata.regionB.hwdata_a.addrof("unk_3ca0")),
    "unk_3ca8": t(agx.initdata.regionB.hwdata_a.addrof("unk_3ca8")),
    "unk_3cb0": t(agx.initdata.regionB.hwdata_a.addrof("unk_3cb0")),
    "ts_last_idle": t(agx.initdata.regionB.hwdata_a.addrof("ts_last_idle")),
    "ts_last_poweron": t(agx.initdata.regionB.hwdata_a.addrof("ts_last_poweron")),
    "ts_last_poweroff": t(agx.initdata.regionB.hwdata_a.addrof("ts_last_poweroff")),
    "unk_3cd0": t(agx.initdata.regionB.hwdata_a.addrof("unk_3cd0")),

    "halt_count":  t(agx.initdata.fw_status.addrof("halt_count")),
    "halted":  t(agx.initdata.fw_status.addrof("halted")),
    "resume":  t(agx.initdata.fw_status.addrof("resume")),
    "unk_40":  t(agx.initdata.fw_status.addrof("unk_40")),
    "unk_ctr":  t(agx.initdata.fw_status.addrof("unk_ctr")),
    "unk_60":  t(agx.initdata.fw_status.addrof("unk_60")),
    "unk_70":  t(agx.initdata.fw_status.addrof("unk_70")),
    "c_118c0":  t(agx.initdata.regionC._addr + 0x118c0),
    "c_118c4":  t(agx.initdata.regionC._addr + 0x118c4),
    "c_118c8":  t(agx.initdata.regionC._addr + 0x118c8),
    "c_118cc":  t(agx.initdata.regionC._addr + 0x118cc),
    "c_118d0":  t(agx.initdata.regionC._addr + 0x118d0),
    "c_118d4":  t(agx.initdata.regionC._addr + 0x118d4),
    "c_118d8":  t(agx.initdata.regionC._addr + 0x118d8),
    "c_118dc":  t(agx.initdata.regionC._addr + 0x118dc),
    "3d_cmds":  t(agx.initdata.regionB.stats_3d.addrof("total_cmds")),
    #"3d_cq":    t(agx.initdata.regionB.stats_3d.stats.addrof("cur_cmdqueue")),
    #"3d_tvb_oflws_1":   t(agx.initdata.regionB.stats_3d.stats.addrof("tvb_overflows_1")),
    #"3d_tvb_oflws_2":   t(agx.initdata.regionB.stats_3d.stats.addrof("tvb_overflows_2")),
    #"3d_cur_stamp_id":  t(agx.initdata.regionB.stats_3d.stats.addrof("cur_stamp_id")),
    "3d_ts":    t(agx.initdata.regionB.stats_3d.stats.addrof("unk_timestamp")),
    "hoff_lock": agx.uat.handoff.reg.LOCK_AP.addr,
    "hoff_ctx": agx.uat.handoff.reg.CUR_CTX.addr,
    "hoff_unk2": agx.uat.handoff.reg.UNK2.addr,
    "hoff_unk3_lo": agx.uat.handoff.reg.UNK3.addr,
    "hoff_unk3_hi": agx.uat.handoff.reg.UNK3.addr + 4,
})

for i, r in enumerate(renderers):
    regs.update({
        f"r{i}_3d_done":  t(r.wq_3d.info.pointers.addrof("gpu_doneptr")),
        #f"r{i}_3d_rptr":  t(r.wq_3d.info.pointers.addrof("gpu_rptr")),
        f"r{i}_3d_busy":  t(r.wq_3d.info.addrof("busy")),
        #f"r{i}_3d_blk":   t(r.wq_3d.info.addrof("blocked_on_barrier")),
        #f"r{i}_3d_2c":    t(r.wq_3d.info.addrof("unk_2c")),
        #f"r{i}_3d_54":    t(r.wq_3d.info.addrof("unk_54")),

        f"r{i}_ta_done":  t(r.wq_ta.info.pointers.addrof("gpu_doneptr")),
        #f"r{i}_ta_rptr":  t(r.wq_ta.info.pointers.addrof("gpu_rptr")),
        f"r{i}_ta_busy":  t(r.wq_ta.info.addrof("busy")),
        #f"r{i}_ta_blk":   t(r.wq_ta.info.addrof("blocked_on_barrier")),
        #f"r{i}_ta_2c":    t(r.wq_ta.info.addrof("unk_2c")),
        #f"r{i}_ta_54":    t(r.wq_ta.info.addrof("unk_54")),
        f"r{i}_f{j}_ta_stamp1": t(r.stamp_ta1._addr),
        f"r{i}_ta_stamp2":t(r.stamp_ta2._addr),
        f"r{i}_f{j}_3d_stamp1": t(r.stamp_3d1._addr),
        f"r{i}_3d_stamp2":t(r.stamp_3d2._addr),
    })

    #for j in range(FRAMES):
        #work = r.work[j]
        #regs.update({
            #f"r{i}_f{j}_3d_ts": t(work.wc_3d.ts1._addr),
            #f"r{i}_f{j}_ta_ts": t(work.wc_ta.ts1._addr),
        #})

div=4
ticks = 24000000 // div * 25

la = GPIOLogicAnalyzer(u, regs=regs, cpu=analyzer_cpu, div=div)

print("==========================================")
print("## Run")
print("==========================================")

la.start(ticks, bufsize=0x8000000)

depth_len = align_up(1920*1080*4, 0x4000)
#agx.uat.iomap_at(ctx.ctx, f.cmdbuf.depth_buffer, 0, depth_len, VALID=0)
#agx.uat.flush_dirty()

fb = r.work[0].fb

#agx.uat.iomap_at(ctx.ctx, fb, 0, depth_len, VALID=0)
#agx.uat.flush_dirty()

agx.kick_firmware()

agx.show_stats = False
count_pa = renderers[0].event_control.event_count._paddr

print(f"count: {p.read32(count_pa)}")

agx.uat.invalidate_cache()
agx.uat.dump(ctx.ctx)

mon.add(0x9fff74000, 0x4000)

try:
    for r in renderers:
        r.run()

    for r in renderers:
        while not r.ev_ta.fired:
            agx.asc.work()
            agx.poll_channels()

    print("TA fired")
    print(f"count: {p.read32(count_pa)}")

    for r in renderers:
        while not r.ev_3d.fired:
            agx.asc.work()
            agx.poll_channels()
            #print("==========================================")

        r.wait()

    print("3D fired")
    print("Timestamps:")
    print(f"  3D 1: {r.ts3d_1.pull().val}")
    print(f"  3D 2: {r.ts3d_2.pull().val}")
    print(f"  TA 1: {r.tsta_1.pull().val}")
    print(f"  TA 2: {r.tsta_2.pull().val}")
    print("CPU flag:", r.buffer_mgr.misc_obj.pull().cpu_flag)

    mon.poll()

    #agx.uat.iomap_at(ctx.ctx, fb, 0, depth_len, VALID=0)
    #agx.uat.flush_dirty()

    print(f"fb: {fb:#x}")

    for i, r in enumerate(renderers):
        for j in range(FRAMES):
            r.submit(f.cmdbuf)

        r.run()

    for r in renderers:
        while not r.ev_3d.fired:
            agx.asc.work()
        r.wait()

    print("3D fired again")
    print("Timestamps:")
    print(f"  3D 1: {r.ts3d_1.pull().val}")
    print(f"  3D 2: {r.ts3d_2.pull().val}")
    print(f"  TA 1: {r.tsta_1.pull().val}")
    print(f"  TA 2: {r.tsta_2.pull().val}")
    print("CPU flag:", r.buffer_mgr.misc_obj.pull().cpu_flag)

    time.sleep(0.5)

finally:
    agx.poll_channels()
    #agx.poll_objects()
    #mon.poll()

    la.complete()
    la.show()

time.sleep(2)

