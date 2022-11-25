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

mon = RegMonitor(u, ascii=True, bufsize=0x8000000)
agx.mon = mon

sgx = agx.sgx_dev

atexit.register(p.reboot)
agx.start()

mon.poll()
agx.poll_objects()

ctx = GPUContext(agx)
ctx.bind(63)

f = GPUFrame(ctx, sys.argv[1], track=False)

r = GPURenderer(ctx, 128, bm_slot=0x10, queue=1)

dep_stamp = agx.kobj.new(StampCounter, name="Dep stamp")
dep_stamp.value = 0x100
dep_stamp.push()

#r.submit(f.cmdbuf, (dep_stamp._addr, 0x200, 0x10))
r.submit(f.cmdbuf)
r.submit(f.cmdbuf)

def t(addr):
    paddr = agx.uat.iotranslate(0, addr, 4)[0][0]
    if paddr is None:
        raise Exception(f"Failed to iotranslate {addr:#x}")
    return paddr

regs = {
    "ta_cmds":  t(agx.initdata.regionB.stats_ta.addrof("total_cmds")),
    "ta_ts":    t(agx.initdata.regionB.stats_ta.stats.addrof("unk_timestamp")),
}

pend_base = agx.initdata.regionC.addrof("pending_stamps")
for i in range(5):
    regs[f"st{i}_info"] = t(pend_base + i*8)
    regs[f"st{i}_val"] = t(pend_base + i*8 + 4)

for i in range(4):
    regs[f"ta{i}_cq"] = t(agx.initdata.regionB.stats_ta.stats.queues[i].addrof("cur_cmdqueue"))

regs.update({
    #"pwr_status": t(agx.initdata.regionB.hwdata_a.addrof("pwr_status")),
    #"pstate": t(agx.initdata.regionB.hwdata_a.addrof("cur_pstate")),
    #"temp_c": t(agx.initdata.regionB.hwdata_a.addrof("temp_c")),
    #"pwr_mw": t(agx.initdata.regionB.hwdata_a.addrof("avg_power_mw")),
    #"pwr_ts": t(agx.initdata.regionB.hwdata_a.addrof("update_ts")),

    #"unk_10": t(agx.initdata.regionB.hwdata_a.addrof("unk_10")),
    #"unk_14": t(agx.initdata.regionB.hwdata_a.addrof("unk_14")),
    #"actual_pstate": t(agx.initdata.regionB.hwdata_a.addrof("actual_pstate")),
    #"tgt_pstate": t(agx.initdata.regionB.hwdata_a.addrof("tgt_pstate")),
    #"unk_40": t(agx.initdata.regionB.hwdata_a.addrof("unk_40")),
    #"unk_44": t(agx.initdata.regionB.hwdata_a.addrof("unk_44")),
    #"unk_48": t(agx.initdata.regionB.hwdata_a.addrof("unk_48")),
    #"freq_mhz": t(agx.initdata.regionB.hwdata_a.addrof("freq_mhz")),

    #"unk_748.0": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")),
    #"unk_748.1": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")+4),
    #"unk_748.2": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")+8),
    #"unk_748.3": t(agx.initdata.regionB.hwdata_a.addrof("unk_748")+12),
    #"use_percent": t(agx.initdata.regionB.hwdata_a.addrof("use_percent")),
    #"unk_83c": t(agx.initdata.regionB.hwdata_a.addrof("unk_83c")),
    #"freq_with_off": t(agx.initdata.regionB.hwdata_a.addrof("freq_with_off")),
    #"unk_ba0": t(agx.initdata.regionB.hwdata_a.addrof("unk_ba0")),
    #"unk_bb0": t(agx.initdata.regionB.hwdata_a.addrof("unk_bb0")),
    #"unk_c44": t(agx.initdata.regionB.hwdata_a.addrof("unk_c44")),
    #"unk_c58": t(agx.initdata.regionB.hwdata_a.addrof("unk_c58")),

    #"unk_3ca0": t(agx.initdata.regionB.hwdata_a.addrof("unk_3ca0")),
    #"unk_3ca8": t(agx.initdata.regionB.hwdata_a.addrof("unk_3ca8")),
    #"unk_3cb0": t(agx.initdata.regionB.hwdata_a.addrof("unk_3cb0")),
    #"ts_last_idle": t(agx.initdata.regionB.hwdata_a.addrof("ts_last_idle")),
    #"ts_last_poweron": t(agx.initdata.regionB.hwdata_a.addrof("ts_last_poweron")),
    #"ts_last_poweroff": t(agx.initdata.regionB.hwdata_a.addrof("ts_last_poweroff")),
    #"unk_3cd0": t(agx.initdata.regionB.hwdata_a.addrof("unk_3cd0")),

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
    #"3d_tvb_oflws_1":   t(agx.initdata.regionB.stats_3d.stats.addrof("tvb_overflows_1")),
    #"3d_tvb_oflws_2":   t(agx.initdata.regionB.stats_3d.stats.addrof("tvb_overflows_2")),
    "3d_cur_stamp_id":  t(agx.initdata.regionB.stats_3d.stats.addrof("cur_stamp_id")),
    "3d_ts":    t(agx.initdata.regionB.stats_3d.stats.addrof("unk_timestamp")),
    #"3d_cur_stamp_id":  t(agx.initdata.regionB.stats_3d.stats.addrof("cur_stamp_id")),
})

for i in range(4):
    regs[f"3d{i}_cq"] = t(agx.initdata.regionB.stats_3d.stats.queues[i].addrof("cur_cmdqueue"))


i = 0
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
    f"r{i}_ta_stamp1": t(r.stamp_ta1._addr),
    f"r{i}_ta_stamp2":t(r.stamp_ta2._addr),
    f"r{i}_3d_stamp1": t(r.stamp_3d1._addr),
    f"r{i}_3d_stamp2":t(r.stamp_3d2._addr),

    f"r{i}_ev_cnt":t(r.event_control.event_count._addr),
    f"r{i}_ev_cur":t(r.event_control.addrof("cur_count")),
    f"r{i}_ev_10":t(r.event_control.addrof("unk_10")),
})

div=4
ticks = 24000000 // div * 25

la = GPIOLogicAnalyzer(u, regs=regs, cpu=analyzer_cpu, div=div)

print("Queues:")
print(f"  TA: {r.wq_ta.info._addr:#x} (stamp {r.work[0].ev_ta.id})")
#print(r.wq_ta.info)
print(f"  3D: {r.wq_3d.info._addr:#x} (stamp {r.work[0].ev_3d.id})")
#print(r.wq_3d.info)

print("==========================================")
print("## Run")
print("==========================================")

la.start(ticks, bufsize=0x8000000)

t = time.time()

buf = agx.kobj.new_buf(0x1000, "foo")
buf.val = b"A" * 0x1000
buf.push()
agx.uat.flush_dirty()

try:
    r.run()

    #for a in range(8):
        #for b in range(8):
            #agx.ch.devctrl.dc_1e(a, b)

    #agx.uat.flush_dirty()
    #agx.ch.devctrl.write32(dep_stamp._addr, 0x200)

    #data = struct.pack("<QQQQQI", 0xaaaa, buf._addr, 0xbbbb, 0, 0, 0)


    #agx.poll_objects()
    #mon.poll()
    #agx.ch.devctrl.send_foo(9, data)
    #agx.ch.devctrl.dc_09(0xaaaa, buf._addr, 0xbbbb)

    #for i in range(0x28, 0xff):
        #print(hex(i))
        #data = struct.pack("<QQQQQI", dep_stamp._addr, 0x10_00000200, buf._addr, 0x12_00000010, 0x13_00000010, 0x10)
        #agx.ch.devctrl.send_foo(i, data)
        #agx.asc.work()
        #time.sleep(0.1)
        #agx.poll_objects()
        #mon.poll()

    #time.sleep(0.1)
    #agx.asc.work()

    #chexdump(buf.pull().val)

    agx.kick_firmware()

    while not r.ev_3d.fired:
        agx.asc.work()
        agx.poll_channels()
        print("==========================================")
        #agx.poll_objects()
        #mon.poll()
        agx.kick_firmware()
        if time.time() > t + 2:
            raise Exception("Timeout")
    r.wait()

finally:

    dep_stamp.pull()
    print(f"Stamp value: {dep_stamp.value:#x}")

    #agx.poll_objects()
    #mon.poll()

    la.complete()
    la.show()

time.sleep(2)

