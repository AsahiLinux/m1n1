#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.constructutils import Ver
from m1n1.utils import *

Ver.set_version(u)

from m1n1.shell import run_shell

from m1n1.agx import AGX
from m1n1.agx.context import *

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")
#p.pmgr_adt_clocks_enable("/arm-io/pmp")

# [cpu0] [0xfffffe00124bf5c0] MMIO: R.4   0x204d14000 (sgx, offset 0xd14000) = 0x0
p.read32(0x204000000 + 0xd14000)
# [cpu0] [0xfffffe00124bf9a8] MMIO: W.4   0x204d14000 (sgx, offset 0xd14000) = 0x70001
p.write32(0x204000000 + 0xd14000, 0x70001)

#p.read32(0x204010258)

agx = AGX(u)

mon = RegMonitor(u, ascii=True, bufsize=0x8000000)
agx.mon = mon

sgx = agx.sgx_dev
mon.add(sgx.gpu_region_base, sgx.gpu_region_size, "contexts")
mon.add(sgx.gfx_shared_region_base, sgx.gfx_shared_region_size, "gfx-shared")
mon.add(sgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

#addr, size = sgx.get_reg(0)
#mon.add(addr + 0x600000, size - 0x600000, "sgx")

addr, size = u.adt["/arm-io/aic"].get_reg(0)
mon.add(addr, size, "aic")

def unswizzle(addr, w, h, psize, dump=None, grid=False):
    tw = 64
    th = 64
    ntx = (w + tw - 1) // 64
    nty = (h + th - 1) // 64
    data = iface.readmem(addr, ntx * nty * psize * tw * th)
    new_data = []
    for y in range(h):
        ty = y // th
        for x in range(w):
            tx = x // tw
            toff = tw * th * psize * (ty * ntx + tx)
            j = x & (tw - 1)
            i = y & (th - 1)
            off = (
                ((j & 1) << 0) | ((i & 1) << 1) |
                ((j & 2) << 1) | ((i & 2) << 2) |
                ((j & 4) << 2) | ((i & 4) << 3) |
                ((j & 8) << 3) | ((i & 8) << 4) |
                ((j & 16) << 4) | ((i & 16) << 5) |
                ((j & 32) << 5) | ((i & 32) << 6))
            r,g,b,a = data[toff + psize*off: toff + psize*(off+1)]
            if grid:
                if x % 64 == 0 or y % 64 == 0:
                    r,g,b,a = 255,255,255,255
                elif x % 32 == 0 or y % 32 == 0:
                    r,g,b,a = 128,128,128,255
            new_data.append(bytes([b, g, r, a]))
    data = b"".join(new_data)
    if dump:
        open(dump, "wb").write(data)
    iface.writemem(addr, data)

try:
    agx.start()

    ctx_id = 3
    buffer_mgr_slot = 2

    #agx.initdata.regionA.add_to_mon(mon)
    #agx.initdata.regionB.add_to_mon(mon)
    #agx.initdata.regionC.add_to_mon(mon)

    #agx.initdata.regionB.unk_170.add_to_mon(mon)
    #agx.initdata.regionB.unk_178.add_to_mon(mon)
    #agx.initdata.regionB.unk_180.add_to_mon(mon)
    #agx.initdata.regionB.unk_190.add_to_mon(mon)
    #agx.initdata.regionB.unk_198.add_to_mon(mon)
    ##agx.initdata.regionB.fwlog_ring2.add_to_mon(mon)
    #agx.initdata.regionB.hwdata_a.add_to_mon(mon)
    #agx.initdata.regionB.hwdata_b.add_to_mon(mon)
    mon.poll()

    #agx.asc.work_for(0.3)

    #p.write32(agx.initdata.regionC._paddr + 0x8900, 0xffffffff)
    #p.write32(agx.initdata.regionC._paddr + 0x8904, 0xffffffff)
    #mon.poll()

    agx.kick_firmware()
    #agx.asc.work_for(0.3)

    #mon.poll()

    ##### Initialize context and load data

    ctx = GPUContext(agx)
    ctx.bind(ctx_id)

    #p.read32(0x204000000 + 0xd14000)
    #p.write32(0x204000000 + 0xd14000, 0x70001)

    #base = "gpudata/1tri/"
    #base = "gpudata/mesa-flag/"
    base = "gpudata/bunny/"
    ctx.load_blob(0x1100000000, True, base + "mem_0_0.bin")
    ctx.load_blob(0x1100008000, True, base + "mem_8000_0.bin")
    ctx.load_blob(0x1100010000, True, base + "mem_10000_0.bin")
    ctx.load_blob(0x1100058000, True, base + "mem_58000_0.bin")
    ctx.load_blob(0x1100060000, True, base + "mem_60000_0.bin")
    #ctx.load_blob(0x1100068000, True, base + "mem_68000_0.bin")
    ctx.load_blob(0x1500000000, False, base + "mem_1500000000_0.bin")
    ctx.load_blob(0x1500048000, False, base + "mem_1500048000_0.bin")
    ctx.load_blob(0x15000d0000, False, base + "mem_15000d0000_0.bin")
    ctx.load_blob(0x1500158000, False, base + "mem_1500158000_0.bin")
    ctx.load_blob(0x15001e0000, False, base + "mem_15001e0000_0.bin")
    ctx.load_blob(0x15001e8000, False, base + "mem_15001e8000_0.bin")
    ctx.load_blob(0x15001f0000, False, base + "mem_15001f0000_0.bin")
    ctx.load_blob(0x15001f8000, False, base + "mem_15001f8000_0.bin")
    #ctx.load_blob(0x1500490000, False, base + "mem_1500490000_0.bin")
    #ctx.load_blob(0x1500518000, False, base + "mem_1500518000_0.bin")
    #color = ctx.buf_at(0x1500200000, False, 1310720, "Color", track=False)
    #depth = ctx.buf_at(0x1500348000, False, 1310720, "Depth", track=False)
    color = ctx.buf_at(0x1500200000, False, 2129920, "Color", track=False)
    depth = ctx.buf_at(0x1500410000, False, 2129920, "Depth", track=False)
    ctx.load_blob(0x1500620000, False, base + "mem_1500620000_0.bin", track=False)
    ctx.load_blob(0x1500890000, False, base + "mem_1500890000_0.bin", track=False)

    mon.poll()

    p.memset32(color._paddr, 0xdeadbeef, color._size)
    p.memset32(depth._paddr, 0xdeadbeef, depth._size)

    stencil = ctx.buf_at(0x1510410000, False, 2129920, "Stencil", track=False)

    width = 800
    height = 600

    width_a = align_up(width, 64)
    height_a = align_up(height, 64)

    depth_addr = depth._addr

    ##### Initialize buffer manager

    #buffer_mgr = GPUBufferManager(agx, ctx, 26)
    buffer_mgr = GPUBufferManager(agx, ctx, 8)

    ##### Initialize work queues

    wq_3d = GPU3DWorkQueue(agx, ctx)
    wq_ta = GPUTAWorkQueue(agx, ctx)

    ##### TA stamps

    #Message 1: DAG: Non Sequential Stamp Updates seen entryIdx 0x41 roots.dag 0x1 stampIdx 0x7 stampValue 0x4100 channel 0xffffffa000163f58 channelRingCommandIndex 0x1

    prev_stamp_value = 0x4000
    stamp_value = 0x4100

    # start?
    stamp_ta1 = agx.kshared.new(BarrierCounter, name="TA stamp 1")
    stamp_ta1.value = prev_stamp_value
    stamp_ta1.push()

    # complete?
    stamp_ta2 = agx.kobj.new(BarrierCounter, name="TA stamp 2")
    stamp_ta2.value = prev_stamp_value
    stamp_ta2.push()

    ##### 3D stamps

    # start?
    stamp_3d1 = agx.kshared.new(BarrierCounter, name="3D stamp 1")
    stamp_3d1.value = prev_stamp_value
    stamp_3d1.push()

    # complete?
    stamp_3d2 = agx.kobj.new(BarrierCounter, name="3D stamp 2")
    stamp_3d2.value = prev_stamp_value
    stamp_3d2.push()

    ##### Some kind of feedback/status buffer, GPU managed?

    event_control = agx.kobj.new(EventControl)
    event_control.event_count = agx.kobj.new(Int32ul, "Event Count")
    event_control.base_stamp = 0x15 #0
    event_control.unk_c = 0
    event_control.unk_10 = 0x50
    event_control.push()

    ##### TVB allocations / Tiler config

    tile_width = 32
    tile_height = 32
    tiles_x = ((width + tile_width - 1) // tile_width)
    tiles_y = ((height + tile_height - 1) // tile_height)
    tiles = tiles_x * tiles_y

    tile_blocks_x = (tiles_x + 15) // 16
    tile_blocks_y = (tiles_y + 15) // 16
    tile_blocks = tile_blocks_x * tile_blocks_y

    tiling_params = TilingParameters()
    tiling_params.size1 = 0x14 * tile_blocks
    tiling_params.unk_4 = 0x88
    tiling_params.unk_8 = 0x202
    tiling_params.x_max = width - 1
    tiling_params.y_max = height - 1
    tiling_params.tile_count = ((tiles_y-1) << 12) | (tiles_x-1)
    tiling_params.x_blocks = (12 * tile_blocks_x) | (tile_blocks_x << 12) | (tile_blocks_x << 20)
    tiling_params.y_blocks = (12 * tile_blocks_y) | (tile_blocks_y << 12) | (tile_blocks_y << 20)
    tiling_params.size2 = 0x10 * tile_blocks
    tiling_params.size3 = 0x20 * tile_blocks
    tiling_params.unk_24 = 0x100
    tiling_params.unk_28 = 0x8000

    tvb_something_size = 0x800 * tile_blocks
    tvb_something = ctx.uobj.new_buf(tvb_something_size, "TVB Something")

    tvb_tilemap_size = 0x800 * tile_blocks
    tvb_tilemap = ctx.uobj.new_buf(tvb_tilemap_size, "TVB Tilemap")

    tvb_heapmeta_size = 0x4000
    tvb_heapmeta = ctx.uobj.new_buf(tvb_heapmeta_size, "TVB Heap Meta")

    ##### Buffer stuff?

    # buffer related?
    buf_desc = agx.kobj.new(BufferThing)
    buf_desc.unk_0 = 0x0
    buf_desc.unk_8 = 0x0
    buf_desc.unk_10 = 0x0
    buf_desc.unkptr_18 = ctx.uobj.buf(0x80, "BufferThing.unkptr_18")
    buf_desc.unk_20 = 0x0
    buf_desc.bm_misc_addr = buffer_mgr.misc_obj._addr
    buf_desc.unk_2c = 0x0
    buf_desc.unk_30 = 0x0
    buf_desc.unk_38 = 0x0
    buf_desc.push()

    uuid_3d = 0x4000a14
    uuid_ta = 0x4000a15
    encoder_id = 0x30009fb

    ##### 3D barrier command

    ev_ta = 6
    ev_3d = 7

    barrier_cmd = agx.kobj.new(WorkCommandBarrier)
    barrier_cmd.stamp = stamp_ta2
    barrier_cmd.stamp_value1 = 0x4100
    barrier_cmd.stamp_value2 = 0x4100
    barrier_cmd.event = ev_ta
    barrier_cmd.uuid = uuid_3d


    #stamp.add_to_mon(mon)
    #stamp2.add_to_mon(mon)

    print(barrier_cmd)

    wq_3d.submit(barrier_cmd.push())

    ##### 3D execution

    wc_3d = agx.kobj.new(WorkCommand3D)
    wc_3d.context_id = ctx_id
    wc_3d.unk_8 = 0
    wc_3d.event_control = event_control
    wc_3d.buffer_mgr = buffer_mgr.info
    wc_3d.buf_thing = buf_desc
    wc_3d.unk_emptybuf_addr = agx.kobj.buf(0x100, "unk_emptybuf")
    wc_3d.tvb_tilemap = tvb_tilemap._addr
    wc_3d.unk_40 = 0x88
    wc_3d.unk_48 = 0x1
    wc_3d.tile_blocks_y = tile_blocks_y * 4
    wc_3d.tile_blocks_x = tile_blocks_x * 4
    wc_3d.unk_50 = 0x0
    wc_3d.unk_58 = 0x0
    wc_3d.uuid1 = 0x3b315cae
    wc_3d.uuid2 = 0x3b6c7b92
    wc_3d.unk_68 = 0x0
    wc_3d.tile_count = tiles

    wc_3d.unk_buf = WorkCommand1_UnkBuf()
    wc_3d.unk_word = BarrierCounter()
    wc_3d.unk_buf2 = WorkCommand1_UnkBuf2()
    wc_3d.unk_buf2.unk_0 = 0
    wc_3d.unk_buf2.unk_8 = 0
    wc_3d.unk_buf2.unk_10 = 1
    wc_3d.ts1 = Timestamp()
    wc_3d.ts2 = Timestamp()
    wc_3d.ts3 = Timestamp()
    wc_3d.unk_914 = 0
    wc_3d.unk_918 = 0
    wc_3d.unk_920 = 0
    wc_3d.unk_924 = 1

    # Structures embedded in WorkCommand3D
    if True:
        wc_3d.struct_1 = Start3DStruct1()
        wc_3d.struct_1.store_pipeline_addr = 0x14004 # CHECKED
        wc_3d.struct_1.unk_8 = 0x0
        wc_3d.struct_1.unk_c = 0x0
        wc_3d.struct_1.uuid1 = wc_3d.uuid1
        wc_3d.struct_1.uuid2 = wc_3d.uuid2
        wc_3d.struct_1.unk_18 = 0x0
        wc_3d.struct_1.tile_blocks_y = tile_blocks_y * 4
        wc_3d.struct_1.tile_blocks_x = tile_blocks_x * 4
        wc_3d.struct_1.unk_24 = 0x0
        wc_3d.struct_1.tile_counts = ((tiles_y-1) << 12) | (tiles_x-1)
        wc_3d.struct_1.unk_2c = 0x8
        wc_3d.struct_1.depth_clear_val1 = 1.0 # works
        wc_3d.struct_1.stencil_clear_val1 = 0x0
        wc_3d.struct_1.unk_38 = 0x0
        wc_3d.struct_1.unk_3c = 0x1
        wc_3d.struct_1.unk_40_padding = bytes(0xb0)
        wc_3d.struct_1.depth_bias_array = Start3DArrayAddr(0x1500158000)
        wc_3d.struct_1.scissor_array = Start3DArrayAddr(0x15000d0000)
        wc_3d.struct_1.unk_110 = 0x0
        wc_3d.struct_1.unk_118 = 0x0
        wc_3d.struct_1.unk_120 = [0] * 37
        wc_3d.struct_1.unk_reload_pipeline = Start3DStorePipelineBinding(0xffff8212, 0xfffffff4)
        wc_3d.struct_1.unk_258 = 0
        wc_3d.struct_1.unk_260 = 0
        wc_3d.struct_1.unk_268 = 0
        wc_3d.struct_1.unk_270 = 0
        wc_3d.struct_1.reload_pipeline = Start3DClearPipelineBinding(0xffff8212, 0x13004) # CHECKED
        wc_3d.struct_1.depth_flags = 0x00000
        wc_3d.struct_1.unk_290 = 0x0
        wc_3d.struct_1.depth_buffer_ptr1 = depth_addr
        wc_3d.struct_1.unk_2a0 = 0x0
        wc_3d.struct_1.unk_2a8 = 0x0
        wc_3d.struct_1.depth_buffer_ptr2 = depth_addr
        wc_3d.struct_1.depth_buffer_ptr3 = depth_addr
        wc_3d.struct_1.unk_2c0 = 0x0
        wc_3d.struct_1.stencil_buffer_ptr1 = stencil._addr
        wc_3d.struct_1.unk_2d0 = 0x0
        wc_3d.struct_1.unk_2d8 = 0x0
        wc_3d.struct_1.stencil_buffer_ptr2 = stencil._addr
        wc_3d.struct_1.stencil_buffer_ptr3 = stencil._addr
        wc_3d.struct_1.unk_2f0 = [0x0, 0x0, 0x0]
        wc_3d.struct_1.aux_fb_unk0 = 0x4
        wc_3d.struct_1.unk_30c = 0x0
        wc_3d.struct_1.aux_fb = AuxFBInfo(0xc000, 0, width, height)
        wc_3d.struct_1.unk_320_padding = bytes(0x10)
        wc_3d.struct_1.unk_partial_store_pipeline = Start3DStorePipelineBinding(0xffff8212, 0xfffffff4)
        wc_3d.struct_1.partial_store_pipeline = Start3DStorePipelineBinding(0x12, 0x14004) # CHECKED
        wc_3d.struct_1.depth_clear_val2 = 1.0
        wc_3d.struct_1.stencil_clear_val2 = 0x0
        wc_3d.struct_1.context_id = ctx_id
        wc_3d.struct_1.unk_376 = 0x0
        wc_3d.struct_1.unk_378 = 0x8
        wc_3d.struct_1.unk_37c = 0x0
        wc_3d.struct_1.unk_380 = 0x0
        wc_3d.struct_1.unk_388 = 0x0
        wc_3d.struct_1.depth_dimensions = 0x12b831f #0xef827f

    if True:
        wc_3d.struct_2 = Start3DStruct2()
        wc_3d.struct_2.unk_0 = 0xa000
        wc_3d.struct_2.clear_pipeline = Start3DClearPipelineBinding(0xffff8002, 0x12004)
        wc_3d.struct_2.unk_18 = 0x88
        wc_3d.struct_2.scissor_array = 0x15000d0000
        wc_3d.struct_2.depth_bias_array = 0x1500158000
        wc_3d.struct_2.aux_fb =  wc_3d.struct_1.aux_fb
        wc_3d.struct_2.depth_dimensions = wc_3d.struct_1.depth_dimensions
        wc_3d.struct_2.unk_48 = 0x0
        wc_3d.struct_2.depth_flags = wc_3d.struct_1.depth_flags
        wc_3d.struct_2.depth_buffer_ptr1 = depth_addr
        wc_3d.struct_2.depth_buffer_ptr2 = depth_addr
        wc_3d.struct_2.stencil_buffer_ptr1 = stencil._addr
        wc_3d.struct_2.stencil_buffer_ptr2 = stencil._addr
        wc_3d.struct_2.unk_68 = [0] * 12
        wc_3d.struct_2.tvb_tilemap = tvb_tilemap._addr
        wc_3d.struct_2.tvb_heapmeta_addr = tvb_heapmeta._addr
        wc_3d.struct_2.unk_e8 = 0x50000000 * tile_blocks
        wc_3d.struct_2.tvb_heapmeta_addr2 = tvb_heapmeta._addr
        wc_3d.struct_2.unk_f8 = 0x10280 # TODO: varies 0, 0x280, 0x10000, 0x10280
        wc_3d.struct_2.aux_fb_ptr = 0x1500006000
        wc_3d.struct_2.unk_108 = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0]
        wc_3d.struct_2.pipeline_base = 0x1100000000
        wc_3d.struct_2.unk_140 = 0x8c60
        wc_3d.struct_2.unk_148 = 0x0
        wc_3d.struct_2.unk_150 = 0x0
        wc_3d.struct_2.unk_158 = 0x1c
        wc_3d.struct_2.unk_160_padding = bytes(0x1e8)

    if True:
        wc_3d.struct_6 = Start3DStruct6()
        wc_3d.struct_6.unk_0 = 0x0
        wc_3d.struct_6.unk_8 = 0x0
        wc_3d.struct_6.unk_10 = 0x0
        wc_3d.struct_6.encoder_id = encoder_id
        wc_3d.struct_6.unk_1c = 0xffffffff
        wc_3d.struct_6.unknown_buffer = 0x150000e000
        wc_3d.struct_6.unk_28 = 0x0
        wc_3d.struct_6.unk_30 = 0x1
        wc_3d.struct_6.unk_34 = 0x1

    if True:
        wc_3d.struct_7 = Start3DStruct7()
        wc_3d.struct_7.unk_0 = 0x0
        wc_3d.struct_7.stamp1 = stamp_3d1
        wc_3d.struct_7.stamp2 = stamp_3d2
        wc_3d.struct_7.stamp_value = stamp_value
        wc_3d.struct_7.ev_3d = ev_3d
        wc_3d.struct_7.unk_20 = 0x0
        wc_3d.struct_7.unk_24 = 0x0 # check
        wc_3d.struct_7.uuid = uuid_3d
        wc_3d.struct_7.prev_stamp_value = 0x0
        wc_3d.struct_7.unk_30 = 0x0

    wc_3d.set_addr() # Update inner structure addresses
    print("WC3D", hex(wc_3d._addr))
    print(" s1", hex(wc_3d.struct_1._addr))
    print(" s2", hex(wc_3d.struct_2._addr))
    print(" s6", hex(wc_3d.struct_6._addr))
    print(" s7", hex(wc_3d.struct_7._addr))

    ms = GPUMicroSequence(agx)

    start_3d = Start3DCmd()
    start_3d.struct1 = wc_3d.struct_1
    start_3d.struct2 = wc_3d.struct_2
    start_3d.buf_thing = buf_desc
    start_3d.unkptr_1c = agx.initdata.regionB.unkptr_178 + 8
    start_3d.unkptr_24 = wc_3d.unk_word._addr
    start_3d.struct6 = wc_3d.struct_6
    start_3d.struct7 = wc_3d.struct_7
    start_3d.cmdqueue_ptr = wq_3d.info._addr
    start_3d.workitem_ptr = wc_3d._addr
    start_3d.context_id = ctx_id
    start_3d.unk_50 = 0x1
    start_3d.unk_54 = 0x0
    start_3d.unk_58 = 0x2
    start_3d.unk_5c = 0x0
    start_3d.prev_stamp_value = 0x0
    start_3d.unk_68 = 0x0
    start_3d.unk_buf_ptr = wc_3d.unk_buf._addr
    start_3d.unk_buf2_ptr = wc_3d.unk_buf2._addr
    start_3d.unk_7c = 0x0
    start_3d.unk_80 = 0x0
    start_3d.unk_84 = 0x0
    start_3d.uuid = uuid_3d
    start_3d.attachments = [
        Attachment(color._addr, 0x2800, 0x10017),
        Attachment(depth._addr, 0x4100, 0x10017),
    ] + [Attachment(0, 0, 0)] * 14
    start_3d.num_attachments = 2
    start_3d.unk_190 = 0x0

    ms.append(start_3d)

    ts1 = TimestampCmd()
    ts1.unk_1 = 0x0
    ts1.unk_2 = 0x0
    ts1.unk_3 = 0x80
    ts1.ts0_addr = wc_3d.ts1._addr
    ts1.ts1_addr = wc_3d.ts2._addr
    ts1.ts2_addr = wc_3d.ts2._addr
    ts1.cmdqueue_ptr = wq_3d.info._addr
    ts1.unk_24 = 0x0
    ts1.uuid = uuid_3d
    ts1.unk_30_padding = 0x0
    ms.append(ts1)

    ms.append(WaitForInterruptCmd(0, 1, 0))

    ts2 = TimestampCmd()
    ts2.unk_1 = 0x0
    ts2.unk_2 = 0x0
    ts2.unk_3 = 0x0
    ts2.ts0_addr = wc_3d.ts1._addr
    ts2.ts1_addr = wc_3d.ts2._addr
    ts2.ts2_addr = wc_3d.ts3._addr
    ts2.cmdqueue_ptr = wq_3d.info._addr
    ts2.unk_24 = 0x0
    ts2.uuid = uuid_3d
    ts2.unk_30_padding = 0x0
    ms.append(ts2)

    finish_3d = Finalize3DCmd()
    finish_3d.uuid = uuid_3d
    finish_3d.unk_8 = 0
    finish_3d.stamp = stamp_3d2
    finish_3d.stamp_value = stamp_value
    finish_3d.unk_18 = 0
    finish_3d.buf_thing = buf_desc
    finish_3d.buffer_mgr = buffer_mgr.info
    finish_3d.unk_2c = 1
    finish_3d.unkptr_34 = agx.initdata.regionB.unkptr_178 + 8
    finish_3d.struct7 = wc_3d.struct_7
    finish_3d.unkptr_44 = wc_3d.unk_word._addr
    finish_3d.cmdqueue_ptr = wq_3d.info._addr
    finish_3d.workitem_ptr = wc_3d._addr
    finish_3d.unk_5c = ctx_id
    finish_3d.unk_buf_ptr = wc_3d.unk_buf._addr
    finish_3d.unk_6c = 0
    finish_3d.unk_74 = 0
    finish_3d.unk_7c = 0
    finish_3d.unk_84 = 0
    finish_3d.unk_8c = 0
    finish_3d.startcmd_offset = -0x200
    finish_3d.unk_98 = 1
    ms.append(finish_3d)
    ms.finalize()

    wc_3d.microsequence_ptr = ms.obj._addr
    wc_3d.microsequence_size = ms.size

    print(wc_3d)

    wc_3d.push()
    ms.dump()
    print(wc_3d)
    wq_3d.submit(wc_3d)

    ##### TA init

    #print(ctx_info)

    wc_initbm = agx.kobj.new(WorkCommandInitBM)
    wc_initbm.context_id = ctx_id
    wc_initbm.unk_8 = buffer_mgr_slot
    wc_initbm.unk_c = 0
    wc_initbm.unk_10 = buffer_mgr.info.block_count
    wc_initbm.buffer_mgr = buffer_mgr.info
    wc_initbm.stamp_value = stamp_value
    wc_initbm.push()

    print(wc_initbm)
    wq_ta.submit(wc_initbm)

    ##### TA execution

    wc_ta = agx.kobj.new(WorkCommandTA)
    wc_ta.context_id = ctx_id
    wc_ta.unk_8 = 0
    wc_ta.event_control = event_control
    wc_ta.unk_14 = buffer_mgr_slot
    wc_ta.buffer_mgr = buffer_mgr.info
    wc_ta.buf_thing = buf_desc
    wc_ta.unk_emptybuf_addr = wc_3d.unk_emptybuf_addr
    wc_ta.unk_34 = 0x0

    wc_ta.unk_154 = bytes(0x268)
    wc_ta.unk_3e8 = bytes(0x74)
    wc_ta.unk_594 = WorkCommand0_UnkBuf()

    wc_ta.ts1 = Timestamp()
    wc_ta.ts2 = Timestamp()
    wc_ta.ts3 = Timestamp()
    wc_ta.unk_5c4 = 0
    wc_ta.unk_5c8 = 0
    wc_ta.unk_5cc = 0
    wc_ta.unk_5d0 = 0
    wc_ta.unk_5d4 = 0x27 #1

    # Structures embedded in WorkCommandTA
    if True:

        wc_ta.tiling_params = tiling_params
        #wc_ta.tiling_params.unk_0 = 0x28
        #wc_ta.tiling_params.unk_4 = 0x88
        #wc_ta.tiling_params.unk_8 = 0x202
        #wc_ta.tiling_params.x_max = 639
        #wc_ta.tiling_params.y_max = 479
        #wc_ta.tiling_params.unk_10 = 0xe013
        #wc_ta.tiling_params.unk_14 = 0x20_20_18
        #wc_ta.tiling_params.unk_18 = 0x10_10_0c
        #wc_ta.tiling_params.unk_1c = 0x20
        #wc_ta.tiling_params.unk_20 = 0x40
        #wc_ta.tiling_params.unk_24 = 0x100
        #wc_ta.tiling_params.unk_28 = 0x8000

    if True:
        wc_ta.struct_2 = StartTACmdStruct2()
        wc_ta.struct_2.unk_0 = 0x200
        wc_ta.struct_2.unk_8 = 0x1e3ce508 # fixed
        wc_ta.struct_2.unk_c = 0x1e3ce508 # fixed
        wc_ta.struct_2.tvb_tilemap = tvb_tilemap._addr
        wc_ta.struct_2.unkptr_18 = 0x0
        wc_ta.struct_2.unkptr_20 = tvb_something._addr
        wc_ta.struct_2.tvb_heapmeta_addr = tvb_heapmeta._addr | 0x8000000000000000
        wc_ta.struct_2.iogpu_unk_54 = 0x6b0003 # fixed
        wc_ta.struct_2.iogpu_unk_55 = 0x3a0012 # fixed
        wc_ta.struct_2.iogpu_unk_56 = 0x1 # fixed
        wc_ta.struct_2.unk_40 = 0x0 # fixed
        wc_ta.struct_2.unk_48 = 0xa000 # fixed
        wc_ta.struct_2.unk_50 = 0x88 # fixed
        wc_ta.struct_2.tvb_heapmeta_addr2 = tvb_heapmeta._addr
        wc_ta.struct_2.unk_60 = 0x0 # fixed
        wc_ta.struct_2.unk_68 = 0x0 # fixed
        wc_ta.struct_2.iogpu_deflake_1 = 0x15000052a0
        wc_ta.struct_2.iogpu_deflake_2 = 0x1500005020
        wc_ta.struct_2.unk_80 = 0x1 # fixed
        wc_ta.struct_2.iogpu_deflake_3 = 0x1500005000
        wc_ta.struct_2.encoder_addr = 0x1500048000
        wc_ta.struct_2.unk_98 = [0x0, 0x0] # fixed
        wc_ta.struct_2.unk_a8 = 0xa041 # fixed
        wc_ta.struct_2.unk_b0 = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0] # fixed
        wc_ta.struct_2.pipeline_base = 0x1100000000
        wc_ta.struct_2.unk_e8 = 0x0 # fixed
        wc_ta.struct_2.unk_f0 = 0x1c # fixed
        wc_ta.struct_2.unk_f8 = 0x8c60 # fixed
        wc_ta.struct_2.unk_100 = [0x0, 0x0, 0x0] # fixed
        wc_ta.struct_2.unk_118 = 0x1c # fixed

    if True:
        wc_ta.struct_3 = StartTACmdStruct3()
        wc_ta.struct_3.unk_480 = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0] # fixed
        wc_ta.struct_3.unk_498 = 0x0 # fixed
        wc_ta.struct_3.unk_4a0 = 0x0 # fixed
        wc_ta.struct_3.iogpu_deflake_1 = 0x15000052a0
        wc_ta.struct_3.unk_4ac = 0x0 # fixed
        wc_ta.struct_3.unk_4b0 = 0x0 # fixed
        wc_ta.struct_3.unk_4b8 = 0x0 # fixed
        wc_ta.struct_3.unk_4bc = 0x0 # fixed
        wc_ta.struct_3.unk_4c4_padding = bytes(0x48)
        wc_ta.struct_3.unk_50c = 0x0 # fixed
        wc_ta.struct_3.unk_510 = 0x0 # fixed
        wc_ta.struct_3.unk_518 = 0x0 # fixed
        wc_ta.struct_3.unk_520 = 0x0 # fixed
        wc_ta.struct_3.unk_528 = 0x0 # fixed
        wc_ta.struct_3.unk_52c = 0x0 # fixed
        wc_ta.struct_3.unk_530 = 0x0 # fixed
        wc_ta.struct_3.encoder_id = encoder_id
        wc_ta.struct_3.unk_538 = 0x0 # fixed
        wc_ta.struct_3.unk_53c = 0xffffffff
        wc_ta.struct_3.unknown_buffer = wc_3d.struct_6.unknown_buffer
        wc_ta.struct_3.unk_548 = 0x0 # fixed
        wc_ta.struct_3.unk_550 = [
            0x0, 0x0, # fixed
            0x0, # 1 for boot stuff?
            0x0, 0x0, 0x0] # fixed
        wc_ta.struct_3.stamp1 = stamp_ta1
        wc_ta.struct_3.stamp2 = stamp_ta2
        wc_ta.struct_3.stamp_value = stamp_value
        wc_ta.struct_3.ev_ta = ev_ta
        wc_ta.struct_3.unk_580 = 0x0 # fixed
        wc_ta.struct_3.unk_584 = 0x0 # 1 for boot stuff?
        wc_ta.struct_3.uuid2 = uuid_ta
        #wc_ta.struct_3.unk_58c = [0x0, 0x0]
        wc_ta.struct_3.unk_58c = [0x1, 0x0]

    wc_ta.set_addr() # Update inner structure addresses
    #print("wc_ta", wc_ta)

    ms = GPUMicroSequence(agx)

    start_ta = StartTACmd()
    start_ta.tiling_params = wc_ta.tiling_params
    start_ta.struct2 = wc_ta.struct_2
    start_ta.buffer_mgr = buffer_mgr.info
    start_ta.buf_thing = buf_desc
    start_ta.unkptr_24 = agx.initdata.regionB.unkptr_170 + 4
    start_ta.cmdqueue_ptr = wq_ta.info._addr
    start_ta.context_id = ctx_id
    start_ta.unk_38 = 1
    start_ta.unk_3c = 1 #0
    start_ta.unk_40 = buffer_mgr_slot
    start_ta.unk_48 = 1 #0
    start_ta.unk_50 = 0
    start_ta.struct3 = wc_ta.struct_3

    start_ta.unkptr_5c = wc_ta.unk_594._addr
    start_ta.unk_64 = 0x0 # fixed
    start_ta.uuid = uuid_ta
    start_ta.unk_70 = 0x0 # fixed
    start_ta.unk_74 = [ # fixed
        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
    ]
    start_ta.unk_15c = 0x0 # fixed
    start_ta.unk_160 = 0x0 # fixed
    start_ta.unk_168 = 0x0 # fixed
    start_ta.unk_16c = 0x0 # fixed
    start_ta.unk_170 = 0x0 # fixed
    start_ta.unk_178 = 0x0 # fixed
    ms.append(start_ta)

    ts1 = TimestampCmd()
    ts1.unk_1 = 0x0
    ts1.unk_2 = 0x0
    ts1.unk_3 = 0x80
    ts1.ts0_addr = wc_ta.ts1._addr
    ts1.ts1_addr = wc_ta.ts2._addr
    ts1.ts2_addr = wc_ta.ts2._addr
    ts1.cmdqueue_ptr = wq_ta.info._addr
    ts1.unk_24 = 0x0
    ts1.uuid = uuid_ta
    ts1.unk_30_padding = 0x0
    ms.append(ts1)

    ms.append(WaitForInterruptCmd(1, 0, 0))

    ts2 = TimestampCmd()
    ts2.unk_1 = 0x0
    ts2.unk_2 = 0x0
    ts2.unk_3 = 0x0
    ts2.ts0_addr = wc_ta.ts1._addr
    ts2.ts1_addr = wc_ta.ts2._addr
    ts2.ts2_addr = wc_ta.ts3._addr
    ts2.cmdqueue_ptr = wq_ta.info._addr
    ts2.unk_24 = 0x0
    ts2.uuid = uuid_ta
    ts2.unk_30_padding = 0x0
    ms.append(ts2)

    finish_ta = FinalizeTACmd()
    finish_ta.buf_thing = buf_desc
    finish_ta.buffer_mgr = buffer_mgr.info
    finish_ta.unkptr_14 = agx.initdata.regionB.unkptr_170 + 4
    finish_ta.cmdqueue_ptr = wq_ta.info._addr
    finish_ta.context_id = ctx_id
    finish_ta.unk_28 = 0x0 # fixed
    finish_ta.struct3 = wc_ta.struct_3
    finish_ta.unk_34 = 0x0 # fixed
    finish_ta.uuid = uuid_ta
    finish_ta.stamp = stamp_ta2
    finish_ta.stamp_value = stamp_value
    finish_ta.unk_48 = 0x0 # fixed
    finish_ta.unk_50 = 0x0 # fixed
    finish_ta.unk_54 = 0x0 # fixed
    finish_ta.unk_58 = 0x0 # fixed
    finish_ta.unk_60 = 0x0 # fixed
    finish_ta.unk_64 = 0x0 # fixed
    finish_ta.unk_68 = 0x0 # fixed
    finish_ta.startcmd_offset = -0x1e8 # fixed
    finish_ta.unk_70 = 0x0 # fixed
    ms.append(finish_ta)

    ms.finalize()

    wc_ta.unkptr_45c = tvb_something._addr
    wc_ta.tvb_size = tvb_something_size
    wc_ta.microsequence_ptr = ms.obj._addr
    wc_ta.microsequence_size = ms.size
    wc_ta.ev_3d = ev_3d
    wc_ta.stamp_value = stamp_value

    wc_ta.push()
    ms.dump()

    mon.poll()

    print(wc_ta)
    wq_ta.submit(wc_ta)

    ##### Run queues
    agx.ch.queue[2].q_3D.run(wq_3d, ev_3d)
    agx.ch.queue[2].q_TA.run(wq_ta, ev_ta)

    ##### Wait for work
    agx.asc.work_for(0.3)
    print("3D:")
    print(wq_3d.info.pull())
    print("TA:")
    print(wq_ta.info.pull())
    print("Barriers:")
    print(stamp_ta1.pull())
    print(stamp_ta2.pull())
    print(stamp_3d1.pull())
    print(stamp_3d2.pull())

    event_control.pull()
    print(event_control)

    print("==")
    mon.poll()
    print("==")
    #agx.kick_firmware()
    agx.asc.work_for(0.3)
    p.read32(0x204000000 + 0xd14000)
    # [cpu0] [0xfffffe00124bf9a8] MMIO: W.4   0x204d14000 (sgx, offset 0xd14000) = 0x70001
    p.write32(0x204000000 + 0xd14000, 0x70001)

    #agx.uat.dump(ctx_id)

    fault_code = p.read64(0x204017030)
    fault_addr = fault_code >> 24
    if fault_addr & 0x8000000000:
        fault_addr |= 0xffffff8000000000
    print(f"FAULT CODE: {fault_code:#x}")
    base, obj = agx.find_object(fault_addr)
    if obj is not None:
        print(f"Faulted at : {fault_addr:#x}: {obj!s} + {fault_addr - base:#x}")
    #agx.kick_firmware()
    mon.poll()

    #print(buffer_mgr.info.pull())
    #print(buffer_mgr.counter_obj.pull())
    #print(buffer_mgr.misc_obj.pull())
    #print(buffer_mgr.block_ctl_obj.pull())

    width = 800
    height = 600

    unswizzle(color._paddr, width, height, 4, "fb.bin", grid=True)
    unswizzle(depth._paddr, width, height, 4, "depth.bin", grid=True)

    p.fb_blit(0, 0, width, height, color._paddr, width)

    print("TVB something:")
    chexdump(iface.readmem(tvb_something._paddr, tvb_something._size), stride=16, abbreviate=False)

    print("TVB list:")
    chexdump(iface.readmem(tvb_tilemap._paddr, tvb_tilemap._size), stride=5, abbreviate=False)

    print("Tile params:")
    print(f"X: {tiles_x} ({tile_blocks_x})")
    print(f"Y: {tiles_y} ({tile_blocks_y})")
    print(f"Total: {tiles} ({tile_blocks})")

    agx.stop()
except:
    #agx.uat.dump(ctx_id)
    p.reboot()
    raise
    #agx.stop()

#time.sleep(10)
#p.reboot()
