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

from m1n1.gpiola import GPIOLogicAnalyzer

analyzer_cpu = 1

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")
p.smp_start_secondaries()
p.mmu_init_secondary(analyzer_cpu)
iface.dev.timeout = 10

agx = AGX(u)

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
ctx.bind(1)

renderer = GPURenderer(ctx, 8, bm_slot=0, queue=0)
renderer2 = GPURenderer(ctx, 8, bm_slot=1, queue=1)

for q in (renderer2.wq_3d, renderer2.wq_ta):
    q.info.set_prio(0)
    q.info.push()

for q in (renderer.wq_3d, renderer.wq_ta):
    q.info.set_prio(2)
    q.info.push()

f = GPUFrame(ctx, sys.argv[1], track=False)

print("==========================================")
print("## Pre submit")
print("==========================================")

mon.poll()
agx.poll_objects()

print("==========================================")
print("## Submitting")
print("==========================================")

work = renderer.submit(f.cmdbuf)
work2 = renderer2.submit(f.cmdbuf)
workb = renderer.submit(f.cmdbuf)
work2b = renderer2.submit(f.cmdbuf)

print(work.wc_3d)
print(work.wc_ta)
print(work2.wc_3d)
print(work2.wc_ta)

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
    "ta0_busy": t(agx.initdata.regionB.stats_ta.stats.queues[0].addrof("busy")),
    "ta0_unk4": t(agx.initdata.regionB.stats_ta.stats.queues[0].addrof("unk_4")),
    "ta0_cnt":  t(agx.initdata.regionB.stats_ta.stats.queues[0].addrof("cur_count")),
    "ta1_busy": t(agx.initdata.regionB.stats_ta.stats.queues[1].addrof("busy")),
    "ta1_unk4": t(agx.initdata.regionB.stats_ta.stats.queues[1].addrof("unk_4")),
    "ta1_cnt":  t(agx.initdata.regionB.stats_ta.stats.queues[1].addrof("cur_count")),
    "ta_ts":    t(agx.initdata.regionB.stats_ta.stats.addrof("unk_timestamp")),
    "3d_cmds":  t(agx.initdata.regionB.stats_3d.addrof("total_cmds")),
    "3d_tvb_oflws_1":   t(agx.initdata.regionB.stats_3d.stats.addrof("tvb_overflows_1")),
    "3d_tvb_oflws_2":   t(agx.initdata.regionB.stats_3d.stats.addrof("tvb_overflows_2")),
    "3d_cur_stamp_id":  t(agx.initdata.regionB.stats_3d.stats.addrof("cur_stamp_id")),
    "3d_ts":    t(agx.initdata.regionB.stats_3d.stats.addrof("unk_timestamp")),

    "bmctl_0":  t(agx.initdata.regionB.buffer_mgr_ctl._addr + 0),
    "bmctl_8":  t(agx.initdata.regionB.buffer_mgr_ctl._addr + 8),
    "2_bmctl_0":  t(agx.initdata.regionB.buffer_mgr_ctl._addr + 16),
    "2_bmctl_8":  t(agx.initdata.regionB.buffer_mgr_ctl._addr + 24),

    "bmi_gpuc":  t(renderer.buffer_mgr.info.addrof("gpu_counter")),
    "bmi_18":    t(renderer.buffer_mgr.info.addrof("unk_18")),
    "bmi_gpuc2": t(renderer.buffer_mgr.info.addrof("gpu_counter2")),

    "2_bmi_gpuc":  t(renderer2.buffer_mgr.info.addrof("gpu_counter")),
    "2_bmi_18":    t(renderer2.buffer_mgr.info.addrof("unk_18")),
    "2_bmi_gpuc2": t(renderer2.buffer_mgr.info.addrof("gpu_counter2")),

    "ctxdat_0": t(renderer.scheduler_context._addr + 0),
    "ctxdat_4": t(renderer.scheduler_context._addr + 4),
    "ctxdat_6": t(renderer.scheduler_context._addr + 6),
    "ctxdat_a": t(renderer.scheduler_context._addr + 0xa),
    "ctxdat_e": t(renderer.scheduler_context._addr + 0xe),
    "ctxdat_12": t(renderer.scheduler_context._addr + 0x12),
    "ctxdat_16": t(renderer.scheduler_context._addr + 0x16),
    "ctxdat_1a": t(renderer.scheduler_context._addr + 0x1a),
    "ctxdat_24": t(renderer.scheduler_context._addr + 0x24),
    "ctxdat_28": t(renderer.scheduler_context._addr + 0x28),
    "ctxdat_2c": t(renderer.scheduler_context._addr + 0x2c),

    "2_ctxdat_0": t(renderer2.scheduler_context._addr + 0),
    "2_ctxdat_4": t(renderer2.scheduler_context._addr + 4),
    "2_ctxdat_6": t(renderer2.scheduler_context._addr + 6),
    "2_ctxdat_a": t(renderer2.scheduler_context._addr + 0xa),
    "2_ctxdat_e": t(renderer2.scheduler_context._addr + 0xe),
    "2_ctxdat_12": t(renderer2.scheduler_context._addr + 0x12),
    "2_ctxdat_16": t(renderer2.scheduler_context._addr + 0x16),
    "2_ctxdat_1a": t(renderer2.scheduler_context._addr + 0x1a),
    "2_ctxdat_24": t(renderer2.scheduler_context._addr + 0x24),
    "2_ctxdat_28": t(renderer2.scheduler_context._addr + 0x28),
    "2_ctxdat_2c": t(renderer2.scheduler_context._addr + 0x2c),

    "evctl_ta":      t(renderer.event_control.addrof("has_ta")),
    "evctl_pta":     t(renderer.event_control.addrof("pstamp_ta")),
    "evctl_3d":      t(renderer.event_control.addrof("has_3d")),
    "evctl_p3d":     t(renderer.event_control.addrof("pstamp_3d")),
    "evctl_in_list": t(renderer.event_control.addrof("in_list")),
    "evctl_prev":    t(renderer.event_control.list_head.addrof("prev")),
    "evctl_next":    t(renderer.event_control.list_head.addrof("next")),

    "2_evctl_ta":    t(renderer2.event_control.addrof("has_ta")),
    "2_evctl_pta":   t(renderer2.event_control.addrof("pstamp_ta")),
    "2_evctl_3d":    t(renderer2.event_control.addrof("has_3d")),
    "2_evctl_p3d":   t(renderer2.event_control.addrof("pstamp_3d")),
    "2_evctl_in_list":t(renderer2.event_control.addrof("in_list")),
    "2_evctl_prev":  t(renderer2.event_control.list_head.addrof("prev")),
    "2_evctl_next":  t(renderer2.event_control.list_head.addrof("next")),

    "jl_first": t(renderer.job_list.addrof("first_job")),
    "jl_last":  t(renderer.job_list.addrof("last_head")),
    "jl_10":    t(renderer.job_list.addrof("unkptr_10")),

    "2_jl_first": t(renderer2.job_list.addrof("first_job")),
    "2_jl_last":  t(renderer2.job_list.addrof("last_head")),
    "2_jl_10":    t(renderer2.job_list.addrof("unkptr_10")),

    "3d_done":  t(renderer.wq_3d.info.pointers.addrof("gpu_doneptr")),
    "3d_rptr":  t(renderer.wq_3d.info.pointers.addrof("gpu_rptr")),
    "3d_rptr1": t(renderer.wq_3d.info.addrof("gpu_rptr1")),
    "3d_rptr2": t(renderer.wq_3d.info.addrof("gpu_rptr2")),
    "3d_rptr3": t(renderer.wq_3d.info.addrof("gpu_rptr3")),
    "3d_busy":  t(renderer.wq_3d.info.addrof("busy")),
    "3d_54":    t(renderer.wq_3d.info.addrof("unk_54")),
    "3d_58":    t(renderer.wq_3d.info.addrof("unk_58")),

    "2_3d_done":  t(renderer2.wq_3d.info.pointers.addrof("gpu_doneptr")),
    "2_3d_rptr":  t(renderer2.wq_3d.info.pointers.addrof("gpu_rptr")),
    "2_3d_busy":  t(renderer2.wq_3d.info.addrof("busy")),
    "2_3d_54":    t(renderer2.wq_3d.info.addrof("unk_54")),

    "ta_done":  t(renderer.wq_ta.info.pointers.addrof("gpu_doneptr")),
    "ta_rptr":  t(renderer.wq_ta.info.pointers.addrof("gpu_rptr")),
    "ta_rptr1": t(renderer.wq_ta.info.addrof("gpu_rptr1")),
    "ta_rptr2": t(renderer.wq_ta.info.addrof("gpu_rptr2")),
    "ta_rptr3": t(renderer.wq_ta.info.addrof("gpu_rptr3")),
    "ta_busy":  t(renderer.wq_ta.info.addrof("busy")),
    "ta_54":   t(renderer.wq_ta.info.addrof("unk_54")),
    "ta_58":   t(renderer.wq_ta.info.addrof("unk_58")),

    "2_ta_done":  t(renderer2.wq_ta.info.pointers.addrof("gpu_doneptr")),
    "2_ta_rptr":  t(renderer2.wq_ta.info.pointers.addrof("gpu_rptr")),
    "2_ta_busy":  t(renderer2.wq_ta.info.addrof("busy")),
    "2_ta_54":    t(renderer2.wq_ta.info.addrof("unk_54")),

    "ta_ts": t(work.wc_ta.ts1._addr),
    "ta_tsb": t(workb.wc_ta.ts1._addr),
    "3d_ts": t(work.wc_3d.ts1._addr),
    "3d_tsb": t(workb.wc_3d.ts1._addr),
    "2_ta_ts": t(work2.wc_ta.ts1._addr),
    "2_ta_tsb": t(work2b.wc_ta.ts1._addr),
    "2_3d_ts": t(work2.wc_3d.ts1._addr),
    "2_3d_tsb": t(work2b.wc_3d.ts1._addr),

    "ta_unkts": t(work.wc_ta.unk_ts._addr),
    "ta_unktsb": t(workb.wc_ta.unk_ts._addr),
    "3d_unkts": t(work.wc_3d.unk_ts._addr),
    "3d_unktsb": t(workb.wc_3d.unk_ts._addr),
    "2_ta_unkts": t(work2.wc_ta.unk_ts._addr),
    "2_ta_unktsb": t(work2b.wc_ta.unk_ts._addr),
    "2_3d_unkts": t(work2.wc_3d.unk_ts._addr),
    "2_3d_unktsb": t(work2b.wc_3d.unk_ts._addr),

    "ta_unkts2": t(work.wc_ta.unk_ts2._addr),
    "ta_unkts2b": t(workb.wc_ta.unk_ts2._addr),
    "3d_unkts2": t(work.wc_3d.unk_ts2._addr),
    "3d_unkts2b": t(workb.wc_3d.unk_ts2._addr),
    "2_ta_unkts2": t(work2.wc_ta.unk_ts2._addr),
    "2_ta_unkts2b": t(work2b.wc_ta.unk_ts2._addr),
    "2_3d_unkts2": t(work2.wc_3d.unk_ts2._addr),
    "2_3d_unkts2b": t(work2b.wc_3d.unk_ts2._addr),

    "ta_start": t(work.tsta_start._addr),
    "ta_end": t(work.tsta_end._addr),
    "3d_start": t(work.ts3d_start._addr),
    "3d_end": t(work.ts3d_end._addr),
    "ta2_sart": t(workb.tsta_start._addr),
    "ta2_end": t(workb.tsta_end._addr),
    "3d2_start": t(workb.ts3d_start._addr),
    "3d2_end": t(workb.ts3d_end._addr),
    "2_ta_start": t(work2.tsta_start._addr),
    "2_ta_end": t(work2.tsta_end._addr),
    "2_3d_start": t(work2.ts3d_start._addr),
    "2_3d_end": t(work2.ts3d_end._addr),
    "2_ta2_sart": t(work2b.tsta_start._addr),
    "2_ta2_end": t(work2b.tsta_end._addr),
    "2_3d2_start": t(work2b.ts3d_start._addr),
    "2_3d2_end": t(work2b.ts3d_end._addr),

    "ns_ta_start": t(work.nsta_start._addr),
    "ns_ta_end": t(work.nsta_end._addr),
    "ns_3d_start": t(work.ns3d_start._addr),
    "ns_3d_end": t(work.ns3d_end._addr),
    "ns_ta2_sart": t(workb.nsta_start._addr),
    "ns_ta2_end": t(workb.nsta_end._addr),
    "ns_3d2_start": t(workb.ns3d_start._addr),
    "ns_3d2_end": t(workb.ns3d_end._addr),
    "2_ns_ta_start": t(work2.nsta_start._addr),
    "2_ns_ta_end": t(work2.nsta_end._addr),
    "2_ns_3d_start": t(work2.ns3d_start._addr),
    "2_ns_3d_end": t(work2.ns3d_end._addr),
    "2_ns_ta2_sart": t(work2b.nsta_start._addr),
    "2_ns_ta2_end": t(work2b.nsta_end._addr),
    "2_ns_3d2_start": t(work2b.ns3d_start._addr),
    "2_ns_3d2_end": t(work2b.ns3d_end._addr),

    "ta_stamp1":    t(renderer.stamp_ta1._addr),
    "ta_stamp2":    t(renderer.stamp_ta2._addr),
    "3d_stamp1":    t(renderer.stamp_3d1._addr),
    "3d_stamp2":    t(renderer.stamp_3d2._addr),

    "2_ta_stamp1":    t(renderer2.stamp_ta1._addr),
    "2_ta_stamp2":    t(renderer2.stamp_ta2._addr),
    "2_3d_stamp1":    t(renderer2.stamp_3d1._addr),
    "2_3d_stamp2":    t(renderer2.stamp_3d2._addr),
}

div=4
ticks = 24000000 // div * 3

la = GPIOLogicAnalyzer(u, regs=regs, cpu=analyzer_cpu, div=div)


print("==========================================")
print("## Poll prior to job start")
print("==========================================")

mon.poll()
agx.poll_objects()

print("==========================================")
print("## Run")
print("==========================================")

la.start(ticks, bufsize=0x400000)
renderer.run()

print("==========================================")
print("## After r1 start")
print("==========================================")
#agx.poll_objects()

#time.sleep(0.1)
#mon.poll()
#time.sleep(0.15)
#mon.poll()
renderer2.run()

print("==========================================")
print("## After r2 start")
print("==========================================")
agx.poll_objects()

#mon.poll()
print("==========================================")
print("## Waiting")
print("==========================================")

try:

    #while not work.ev_3d.fired:
        #agx.asc.work()
        ##mon.poll()
        #agx.poll_objects()
        #agx.poll_channels()
        #print("==========================================")
        ##time.sleep(0.1)

    #print("==========================================")
    #print("## Ev1 Fired")
    #print("==========================================")

    while not work2b.ev_3d.fired:
        agx.asc.work()
        #mon.poll()
        agx.poll_objects()
        agx.poll_channels()
        print("==========================================")
        #time.sleep(0.1)

    print("==========================================")
    print("## Ev2 Fired")
    print("==========================================")

    renderer.wait()
    renderer2.wait()

    agx.poll_objects()
    #mon.poll()

finally:
    la.complete()
    la.show()

time.sleep(2)

