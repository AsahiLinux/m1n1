#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, json, zipfile

json.c_make_encoder = None

from m1n1.proxy import *
from .context import *
from .event import GPUEventManager
from .uapi import *
from m1n1.constructutils import ConstructClass, Ver

def unswizzle(agx, addr, w, h, psize, dump=None, grid=False):
    iface = agx.u.iface

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
        open(dump, "wb").write(data[:w*h*psize])
    #iface.writemem(addr, data)

class GPUFrame:
    def __init__(self, context, filename=None, track=False):
        self.ctx = context
        self.agx = context.agx
        self.objects = []
        self.cmdbuf = None
        self.track = track
        if filename is not None:
            self.load(filename)

    def add_object(self, obj):
        self.objects.append(obj)

    def save(self, filename):
        cmdbuf = self.cmdbuf
        with zipfile.ZipFile(filename, "w") as zf:
            cmdbuf_data = json.dumps(cmdbuf, indent=4).encode("utf-8")
            zf.writestr("cmdbuf.json", cmdbuf_data)

            obj_info = []
            for obj in self.objects:
                if obj._data == bytes(obj._size):
                    filename = None
                else:
                    filename = f"obj_{obj._addr:x}.bin"
                    zf.writestr(filename, obj._data)
                obj_info.append({
                    "file": filename,
                    "name": obj._name,
                    "addr": obj._addr,
                    "size": obj._size,
                    "map_flags": obj._map_flags,
                })

            obj_info_data = json.dumps(obj_info, indent=4).encode("utf-8")
            zf.writestr("objects.json", obj_info_data)

    def load(self, filename):
        with zipfile.ZipFile(filename, "r") as zf:
            with zf.open("cmdbuf.json", "r") as fd:
                self.cmdbuf = drm_asahi_cmdbuf_t.from_json(fd)
            with zf.open("objects.json", "r") as fd:
                obj_info = json.load(fd)

            self.objects = []
            for i in obj_info:
                filename = i["file"]
                obj = self.ctx.new_at(i["addr"], Bytes(i["size"]), name=i["name"], track=self.track,
                                          **i["map_flags"])
                if filename is not None:
                    with zf.open(i["file"], "r") as fd:
                        data = fd.read()
                        obj.val = data
                        obj.push()
                else:
                    obj.val = bytes(i["size"])
                    obj.push()
                self.objects.append(obj)

class GPUWork:
    def __init__(self, renderer):
        self.objects = []
        self.renderer = renderer

    def add(self, obj):
        self.objects.append(obj)

    def free(self):
        for obj in self.objects:
            obj.free()
        self.objects = []

class GPURenderer:
    def __init__(self, ctx, buffers=16, bm_slot=0, queue=0):
        self.agx = agx = ctx.agx
        self.queue = queue
        self.scheduler_context = agx.kobj.new(GPUContextData).push()

        # 0..63
        self.ctx = ctx
        self.ctx_id = ctx.ctx

        # 0..255
        self.buffers = buffers
        self.buffer_mgr_slot = bm_slot

        ## These MUST go together
        self.buffer_mgr = GPUBufferManager(agx, ctx, buffers)
        self.buffer_mgr_initialized = False
        self.unk_emptybuf = agx.kobj.new_buf(0x40, "unk_emptybuf")
        self.tpc_size = 0

        ##### Job group

        self.job_list = agx.kshared.new(JobList)
        self.job_list.first_job = 0
        self.job_list.last_head = self.job_list._addr # Empty list has self as last_head
        self.job_list.unkptr_10 = 0
        self.job_list.push()

        ##### Work Queues

        self.wq_3d = GPU3DWorkQueue(agx, self.scheduler_context, self.job_list)
        self.wq_ta = GPUTAWorkQueue(agx, self.scheduler_context, self.job_list)

        self.wq_3d.info.uuid = 0x3D0000 | bm_slot
        self.wq_3d.info.push()
        self.wq_ta.info.uuid = 0x7A0000 | bm_slot
        self.wq_ta.info.push()

        self.stamp_value_3d = 0x3D000000 | (bm_slot << 16)
        self.stamp_value_ta = 0x7A000000 | (bm_slot << 16)

        ##### TA stamps

        # start?
        self.stamp_ta1 = agx.kshared.new(StampCounter, name="TA stamp 1")
        self.stamp_ta1.value = self.stamp_value_ta
        self.stamp_ta1.push()

        # complete?
        self.stamp_ta2 = agx.kobj.new(StampCounter, name="TA stamp 2")
        self.stamp_ta2.value = self.stamp_value_ta
        self.stamp_ta2.push()

        ##### 3D stamps

        # start?
        self.stamp_3d1 = agx.kshared.new(StampCounter, name="3D stamp 1")
        self.stamp_3d1.value = self.stamp_value_3d
        self.stamp_3d1.push()

        # complete?
        self.stamp_3d2 = agx.kobj.new(StampCounter, name="3D stamp 2")
        self.stamp_3d2.value = self.stamp_value_3d
        self.stamp_3d2.push()


        ##### Things userspace deals with for macOS

        #self.aux_fb = ctx.uobj.new_buf(0x8000, "Aux FB thing")
        ##self.deflake_1 = ctx.uobj.new_buf(0x20, "Deflake 1")
        ##self.deflake_2 = ctx.uobj.new_buf(0x280, "Deflake 2")
        ##self.deflake_3 = ctx.uobj.new_buf(0x540, "Deflake 3")
        #self.deflake = ctx.uobj.new_buf(0x7e0, "Deflake")
        #self.unk_buf = ctx.uobj.new(Array(0x800, Int64ul), "Unknown Buffer")
        #self.unk_buf.val = [0, *range(1, 0x400), *(0x400 * [0])]
        #self.unk_buf.push()

        ##### Some kind of feedback/status buffer, GPU managed?

        self.event_control = agx.kobj.new(EventControl)
        self.event_control.event_count = agx.kobj.new(Int32ul, "event_count")
        self.event_control.event_count.val = 0
        self.event_control.event_count.push()

        self.event_control.submission_id = 0
        self.event_control.cur_count = 0
        self.event_control.unk_10 = 0x50
        self.event_control.push()

        self.frames = 0

        self.ev_ta = ev_ta = self.agx.event_mgr.allocate_event()
        self.ev_3d = ev_3d = self.agx.event_mgr.allocate_event()

        self.work = []

        self.ev_idx = 0

        self.mshook_ta = None
        self.mshook_3d = None

    def submit(self, cmdbuf, wait_for=None):
        clustering = True
        nclusters = 8

        work = GPUWork(self)
        self.work.append(work)

        def mktimestamp(alloc, name):
            ts = alloc.new(Int64ul, name=name)
            ts.val = 0
            ts.push()
            work.add(ts)
            return ts

        work.ts3d_start = mktimestamp(self.agx.kshared, "3D timestamp start")
        work.ts3d_end = mktimestamp(self.agx.kshared, "3D timestamp end")
        work.tsta_start = mktimestamp(self.agx.kshared, "TA timestamp start")
        work.tsta_end = mktimestamp(self.agx.kshared, "TA timestamp end")

        work.ns3d_start = mktimestamp(self.agx.ktimestamp, "3D user timestamp start")
        work.ns3d_end = mktimestamp(self.agx.ktimestamp, "3D user timestamp end")
        work.nsta_start = mktimestamp(self.agx.ktimestamp, "TA timestamp start")
        work.nsta_end = mktimestamp(self.agx.ktimestamp, "TA timestamp end")

        self.buffer_mgr.increment()

        aux_fb = self.ctx.uobj.new_buf(0x20000, "Aux FB thing", track=False)
        work.add(aux_fb)

        # t8103
        deflake_1_size = 0x540
        deflake_2_size = 0x280
        deflake_3_size = 0x20

        # 4 * 0x40 on M2 Max?
        if Ver.check("G >= G14X"):
            deflake_3_size = 0x40

        # t6002 - 9 times larger instead of 8? works with 8...
        deflake_1_size *= nclusters
        deflake_2_size *= nclusters
        deflake_3_size *= nclusters

        deflake_1 = self.ctx.uobj.new_buf(deflake_1_size, "Deflake 1", track=False)
        deflake_2 = self.ctx.uobj.new_buf(deflake_2_size, "Deflake 2", track=False)
        deflake_3 = self.ctx.uobj.new_buf(deflake_3_size, "Deflake 3", track=False)
        work.add(deflake_1)
        work.add(deflake_2)
        work.add(deflake_3)

        unk_buf = self.ctx.uobj.new(Array(0x800, Int64ul), "Unknown Buffer", track=False)
        work.add(unk_buf)

        unk_buf.val = [0, *range(2, 0x401), *(0x400 * [0])]
        unk_buf.push()

        work.cmdbuf = cmdbuf

        self.frames += 1

        work.ev_ta = ev_ta = self.ev_ta
        work.ev_3d = ev_3d = self.ev_3d

        self.ev_ta.rearm()
        self.ev_3d.rearm()

        self.agx.log(f"ev_ta: {ev_ta.id}")
        self.agx.log(f"ev_3d: {ev_3d.id}")

        #self.event_control.base_stamp = self.stamp_value >> 8
        #self.event_control.push()

        self.prev_stamp_value_3d = self.stamp_value_3d
        self.prev_stamp_value_ta = self.stamp_value_ta
        self.stamp_value_3d += 0x100
        self.stamp_value_ta += 0x100
        self.event_control.event_count.val += 2
        self.event_control.event_count.push()

        work.stamp_value_3d = self.stamp_value_3d
        work.stamp_value_ta = self.stamp_value_ta

        agx = self.agx
        ctx = self.ctx

        work.width = width = cmdbuf.fb_width
        work.height = height = cmdbuf.fb_height

        ##### TVB allocations / Tiler config

        tile_width = 32
        tile_height = 32
        tiles_x = ((width + tile_width - 1) // tile_width)
        tiles_y = ((height + tile_height - 1) // tile_height)
        tiles = tiles_x * tiles_y

        mtiles_x = 4
        mtiles_y = 4

        mtile_x1 = align(((tiles_x + mtiles_x - 1) // mtiles_x), 4)
        mtile_x2 = 2 * mtile_x1
        mtile_x3 = 3 * mtile_x1
        mtile_y1 = align(((tiles_y + mtiles_y - 1) // mtiles_y), 4)
        mtile_y2 = 2 * mtile_y1
        mtile_y3 = 3 * mtile_y1

        mtile_stride = mtile_x1 * mtile_y1

        ## TODO: *samples
        tiles_per_mtile_x = mtile_x1
        tiles_per_mtile_y = mtile_y1

        tile_blocks_x = (tiles_x + 15) // 16
        tile_blocks_y = (tiles_y + 15) // 16
        tile_blocks = tile_blocks_x * tile_blocks_y

        tiling_params = TilingParameters()
        # rgn_header_size
        rgn_entry_size = 5
        tiling_params.size1 = (rgn_entry_size * tiles_per_mtile_x * tiles_per_mtile_y + 3) // 4
        # PPP_MULTISAMPLECTL
        tiling_params.unk_4 = 0x88
        # PPP_CTRL
        tiling_params.unk_8 = 0x203 # bit 0: GL clip mode
        # PPP_SCREEN
        tiling_params.x_max = width - 1
        tiling_params.y_max = height - 1
        # TE_SCREEN
        tiling_params.tile_count = ((tiles_y-1) << 12) | (tiles_x-1)
        # TE_MTILE1
        tiling_params.x_blocks = mtile_x3 | (mtile_x2 << 9) | (mtile_x1 << 18)
        # TE_MTILE2
        tiling_params.y_blocks = mtile_y3 | (mtile_y2 << 9) | (mtile_y1 << 18)
        tiling_params.size2 = mtile_stride
        tiling_params.size3 = 2 * mtile_stride
        tiling_params.unk_24 = 0x100
        tiling_params.unk_28 = 0x8000

        tilemap_size = (4 * tiling_params.size1 * mtiles_x * mtiles_y)

        tmtiles_x = tiles_per_mtile_x * mtiles_x
        tmtiles_y = tiles_per_mtile_y * mtiles_y

        tpc_entry_size = 8
        tpc_size = tpc_entry_size * tmtiles_x * tmtiles_y * nclusters

        if self.tpc_size < tpc_size:
            self.tpc = ctx.uobj.new_buf(tpc_size, "TPC", track=False).push()
            self.tpc_size = tpc_size

        depth_aux_buffer_addr = 0
        if cmdbuf.depth_buffer:
            size = align_pot(max(width, tile_width)) * align_pot(max(height, tile_width)) // 32
            depth_aux_buffer = self.ctx.uobj.new_buf(size, "Depth Aux", track=False)
            work.add(depth_aux_buffer)
            depth_aux_buffer_addr = depth_aux_buffer._addr

        stencil_aux_buffer_addr = 0
        if cmdbuf.stencil_buffer:
            size = align_pot(max(width, tile_width)) * align_pot(max(height, tile_width)) // 32
            stencil_aux_buffer = self.ctx.uobj.new_buf(size, "Stencil Aux", track=False)
            work.add(stencil_aux_buffer)
            stencil_aux_buffer_addr = stencil_aux_buffer._addr

        #tvb_tilemap_size = 0x80 * mtile_stride
        tvb_tilemap_size = tilemap_size
        tvb_tilemap = ctx.uobj.new_buf(tvb_tilemap_size, "TVB Tilemap", track=False).push()
        work.tvb_tilemap_size = tvb_tilemap_size
        work.tvb_tilemap = tvb_tilemap
        work.add(tvb_tilemap)

        # rogue: 0x180 * 4?
        tvb_heapmeta_size = 0x200
        #tvb_heapmeta_size = 0x600
        tvb_heapmeta = ctx.uobj.new_buf(tvb_heapmeta_size, "TVB Heap Meta", track=False).push()
        work.add(tvb_heapmeta)

        unk_tile_buf1 = self.ctx.uobj.new_buf(tvb_tilemap_size * nclusters, "Unk tile buf 1", track=False)
        print("tvb_tilemap_size", hex(tvb_tilemap_size))
        unk_tile_buf2 = self.ctx.uobj.new_buf(0x4 * nclusters, "Unk tile buf 2", track=False)
        #size = 0xc0 * nclusters
        size = 0xc80
        unk_tile_buf3 = self.ctx.uobj.new_buf(size, "Unk tile buf 3", track=False)
        f4 = 0x280
        #f4 = 0x400 # t602x?
        unk_tile_buf4 = self.ctx.uobj.new_buf(f4 * nclusters, "Unk tile buf 4", track=False)
        f5 = 0x30
        #f5 = 0x980
        unk_tile_buf5 = self.ctx.uobj.new_buf(f5 * nclusters, "Unk tile buf 5", track=False)
        work.add(unk_tile_buf1)
        work.add(unk_tile_buf2)
        work.add(unk_tile_buf3)
        work.add(unk_tile_buf4)
        work.add(unk_tile_buf5)

        ##### Buffer stuff?

        # buffer related?
        bufferthing_buf = ctx.uobj.new_buf(0x80, "BufferThing.unkptr_18", track=False)
        work.add(bufferthing_buf)

        work.buf_desc = buf_desc = agx.kobj.new(BufferThing, track=False)
        work.add(buf_desc)
        buf_desc.unk0_addr = self.buffer_mgr.get_scene()
        buf_desc.unk0_addr2 = buf_desc.unk0_addr
        buf_desc.unk_0 = 0x0
        buf_desc.unk_8 = 0x0
        buf_desc.unk_10 = 0x0
        buf_desc.unkptr_18 = bufferthing_buf._addr
        buf_desc.unk_20 = 0x0
        buf_desc.unk_28 = 0x0
        buf_desc.bm_misc_addr = self.buffer_mgr.misc_obj._addr
        buf_desc.unk_2c = 0x0
        buf_desc.unk_30 = 0x0
        buf_desc.unk_38 = 0x0
        buf_desc.push()

        uuid_3d = cmdbuf.cmd_3d_id
        uuid_ta = cmdbuf.cmd_ta_id
        encoder_id = cmdbuf.encoder_id

        #print(barrier_cmd)

        #self.wq_ta.submit(ta_barrier_cmd)

        ##### 3D barrier command

        barrier_cmd = agx.kobj.new(WorkCommandBarrier, track=False, align=0x20)
        work.add(barrier_cmd)
        barrier_cmd.stamp = self.stamp_ta2
        barrier_cmd.wait_value = self.stamp_value_ta
        barrier_cmd.stamp_self = self.stamp_value_3d
        barrier_cmd.event = ev_ta.id
        barrier_cmd.uuid = uuid_3d

        #print(barrier_cmd)

        self.wq_3d.submit(barrier_cmd)

        process_empty_tiles = True
        no_clear_pipeline_textures = True
        msaa_zs = False

        unk1 = False

        samples = 1
        layers = 1
        tile_config = 0x10000
        if not unk1:
            tile_config |= 0x280
        if layers > 1:
            tile_config |= 1
        if process_empty_tiles:
            tile_config |= 0x10000

        utile_config = 0xa000 | {1:0, 2:1, 4:2}[samples]
        ppp_multisamplectl = 0x88

        iogpu_unk_214 = 0xc000

        tib_blocks = 8
        large_tib = tib_blocks > 8
        set_when_reloading_z_or_s = False

        TAN_60 = 1.732051

        ##### 3D execution

        work.wc_3d = wc_3d = agx.cmdbuf.new(WorkCommand3D, track=False, align=0x20)
        work.add(work.wc_3d)
        wc_3d.counter = 0
        wc_3d.context_id = self.ctx_id
        wc_3d.unk_8 = 0
        wc_3d.event_control = self.event_control
        wc_3d.buffer_mgr = self.buffer_mgr.info
        wc_3d.buf_thing = buf_desc
        wc_3d.unk_emptybuf_addr = self.unk_emptybuf._addr
        wc_3d.tvb_tilemap = tvb_tilemap._addr
        wc_3d.unk_40 = ppp_multisamplectl
        wc_3d.unk_48 = samples
        wc_3d.tile_blocks_y = mtile_y1
        wc_3d.tile_blocks_x = mtile_x1
        wc_3d.unk_50 = 0x0
        wc_3d.unk_58 = 0x0

        wc_3d.merge_upper_x = TAN_60 / width
        wc_3d.merge_upper_y = TAN_60 / height
        wc_3d.unk_68 = 0x0
        wc_3d.tile_count = tiles

        wc_3d.unk_758 = Flag()
        wc_3d.unk_75c = Flag()
        wc_3d.unk_buf = WorkCommand1_UnkBuf()
        wc_3d.busy_flag = Flag()
        wc_3d.unk_buf2 = WorkCommand1_UnkBuf2()
        wc_3d.unk_buf2.unk_0 = 0
        wc_3d.unk_buf2.unk_8 = 0
        wc_3d.unk_buf2.unk_10 = 1
        wc_3d.ts1 = TimeStamp(0)
        wc_3d.ts_pointers = TimeStampPointers(work.ts3d_start._addr, work.ts3d_end._addr)
        wc_3d.user_ts_pointers = TimeStampPointers(work.ns3d_start._addr, work.ns3d_end._addr)
        wc_3d.client_sequence = 1
        # Ventura
        wc_3d.unk_ts = TimeStamp()
        wc_3d.unk_ts2 = TimeStamp()

        use_registers = Ver.check("G >= G14X")

        # Structures embedded in WorkCommand3D
        if not use_registers:
            wc_3d.struct_1 = Start3DStruct1()
            wc_3d.struct_1.store_pipeline_bind = cmdbuf.store_pipeline_bind
            wc_3d.struct_1.store_pipeline_addr = cmdbuf.store_pipeline | 4
            wc_3d.struct_1.unk_8 = 0x0
            wc_3d.struct_1.unk_c = 0x0

            wc_3d.struct_1.merge_upper_x = TAN_60 / width
            wc_3d.struct_1.merge_upper_y = TAN_60 / height

            wc_3d.struct_1.unk_18 = 0x0
            # ISP_MTILE_SIZE
            wc_3d.struct_1.tile_blocks_y = mtile_y1
            wc_3d.struct_1.tile_blocks_x = mtile_x1
            wc_3d.struct_1.unk_24 = 0x0
            wc_3d.struct_1.tile_counts = ((tiles_y-1) << 12) | (tiles_x-1)
            wc_3d.struct_1.unk_2c = tib_blocks
            wc_3d.struct_1.depth_clear_val1 = cmdbuf.depth_clear_value
            wc_3d.struct_1.stencil_clear_val1 = cmdbuf.stencil_clear_value
            wc_3d.struct_1.unk_35 = 0x7 # clear flags? 2 = depth 4 = stencil?
            wc_3d.struct_1.unk_36 = 0x0
            wc_3d.struct_1.unk_38 = 0x0
            wc_3d.struct_1.unk_3c = 0x1
            wc_3d.struct_1.unk_40 = 0
            wc_3d.struct_1.unk_44_padding = bytes(0x9c)

        if not use_registers:
            wc_3d.struct_2 = Start3DStruct2()
            wc_3d.struct_2.unk_0 = utile_config
            wc_3d.struct_2.clear_pipeline = Start3DClearPipelineBinding(
                cmdbuf.load_pipeline_bind, cmdbuf.load_pipeline | 4)
            wc_3d.struct_2.unk_18 = ppp_multisamplectl
            wc_3d.struct_2.scissor_array = cmdbuf.scissor_array
            wc_3d.struct_2.depth_bias_array = cmdbuf.depth_bias_array
            wc_3d.struct_2.aux_fb = AuxFBInfo(iogpu_unk_214, 0, width, height)
            # ISP_ZLS_PIXELS
            wc_3d.struct_2.depth_dimensions = (width - 1) | ((height - 1) << 15)
            wc_3d.struct_2.visibility_result_buffer = 0x0
            # ISP_ZLSCTL
            wc_3d.struct_2.depth_flags = cmdbuf.ds_flags
            wc_3d.struct_2.unk_58_g14_0 = 0x4040404
            wc_3d.struct_2.unk_58_g14_8 = 0
            wc_3d.struct_2.depth_buffer_ptr1 = cmdbuf.depth_buffer
            wc_3d.struct_2.depth_buffer_ptr2 = cmdbuf.depth_buffer
            wc_3d.struct_2.unk_68_g14_0 = 0
            wc_3d.struct_2.stencil_buffer_ptr1 = cmdbuf.stencil_buffer
            wc_3d.struct_2.stencil_buffer_ptr2 = cmdbuf.stencil_buffer
            wc_3d.struct_2.unk_78 = [0] * 4
            wc_3d.struct_2.depth_aux_buffer_ptr1 = depth_aux_buffer_addr
            wc_3d.struct_2.unk_a0 = 0
            wc_3d.struct_2.depth_aux_buffer_ptr2 = depth_aux_buffer_addr
            wc_3d.struct_2.unk_b0 = 0
            wc_3d.struct_2.stencil_aux_buffer_ptr1 = stencil_aux_buffer_addr
            wc_3d.struct_2.unk_c0 = 0
            wc_3d.struct_2.stencil_aux_buffer_ptr2 = stencil_aux_buffer_addr
            wc_3d.struct_2.unk_d0 = 0
            wc_3d.struct_2.tvb_tilemap = tvb_tilemap._addr
            wc_3d.struct_2.tvb_heapmeta_addr = tvb_heapmeta._addr
            wc_3d.struct_2.unk_e8 = tiling_params.size1 << 24
            wc_3d.struct_2.tvb_heapmeta_addr2 = tvb_heapmeta._addr
            # 0x10000 - clear empty tiles
            # ISP_CTL (but bits seem to have moved)
            wc_3d.struct_2.unk_f8 = tile_config
            wc_3d.struct_2.aux_fb_ptr = aux_fb._addr
            wc_3d.struct_2.unk_108 = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0]
            wc_3d.struct_2.pipeline_base = self.ctx.pipeline_base
            wc_3d.struct_2.unk_140 = 0x8c60
            wc_3d.struct_2.helper_program = 0
            wc_3d.struct_2.unk_14c = 0
            wc_3d.struct_2.helper_arg = 0
            wc_3d.struct_2.unk_158 = 0x1c
            wc_3d.struct_2.unk_160 = 0
            wc_3d.struct_2.unk_168_padding = bytes(0x1d8)
            wc_3d.struct_2.unk_198_padding = bytes(0x1a8)

        def fui(v):
            return struct.unpack("<I", struct.pack("<f", v))[0]

        if use_registers:
            regs = {
                0x1739:     1,
                0x10009:    utile_config,                       # s2.unk_0 utile_config
                0x15379:    cmdbuf.store_pipeline_bind,         # s1.store_pipeline_bind
                0x15381:    cmdbuf.store_pipeline | 4,          # s1.store_pipeline_addr
                0x15369:    cmdbuf.load_pipeline_bind,          # s2.clear_pipeline.bind
                0x15371:    cmdbuf.load_pipeline | 4,           # s2.clear_pipeline.addr
                0x15131:    fui(TAN_60 / width),                # ISP_MERGE_UPPER_X
                0x15139:    fui(TAN_60 / height),               # ISP_MERGE_UPPER_Y
                0x100a1:    0x0,
                0x15069:    0,
                0x15071:    0,                                  # pointer
                0x16058:    0,
                0x10019:    ppp_multisamplectl,                 # PPP_MULTISAMPLECTL
                0x100b1:    mtile_y1 | (mtile_x1 << 16),        # ISP_MTILE_SIZE
                0x16030:    mtile_y1 | (mtile_x1 << 16),        # ISP_MTILE_SIZE
                0x100d9:    ((tiles_y-1) << 12) | (tiles_x-1),  # TE_SCREEN
                0x16098:    tvb_heapmeta._addr,                 # tvb_heapmeta_addr?
                0x15109:    cmdbuf.scissor_array,               # ISP_SCISSOR_BASE
                0x15101:    cmdbuf.depth_bias_array,            # ISP_DBIAS_BASE
                0x15021:    0,                                  # s2.aux_fb.unk_1
                0x15211:    (height << 32) | width,             # s2.aux_fb.{width, height}
                0x15049:    0,                                  # s2.aux_fb.unk3
                0x10051:    tib_blocks,                         # s1.unk_2c
                0x15321:    (width - 1) | ((height - 1) << 15), # ISP_ZLS_PIXELS
                0x15301:    fui(cmdbuf.depth_clear_value),      # ISP_BGOBJDEPTH
                0x15309:    cmdbuf.stencil_clear_value | 0x300, # ISP_BGOBJVALS
                0x15311:    0,                                  # ISP_OCLQRY_BASE
                0x15319:    cmdbuf.ds_flags,                    # ISP_ZLSCTL
                0x15349:    0x4040404,                          # s2.unk_58_g14_0
                0x15351:    0,                                  # s2.unk_58_g14_8
                0x15329:    cmdbuf.depth_buffer,                # ISP_ZLOAD_BASE
                0x15331:    cmdbuf.depth_buffer,                # ISP_ZSTORE_BASE
                0x15339:    cmdbuf.stencil_buffer,              # ISP_STENCIL_LOAD_BASE
                0x15341:    cmdbuf.stencil_buffer,              # ISP_STENCIL_STORE_BASE
                0x15231:    0,
                0x15221:    0,
                0x15239:    0,
                0x15229:    0,
                0x15401:    0,
                0x15421:    0,
                0x15409:    0,
                0x15429:    0,
                0x153c1:    depth_aux_buffer_addr,
                0x15411:    0,
                0x153c9:    depth_aux_buffer_addr,
                0x15431:    0,
                0x153d1:    stencil_aux_buffer_addr,
                0x15419:    0,
                0x153d9:    stencil_aux_buffer_addr,
                0x15439:    0,
                0x16429:    tvb_tilemap._addr,                  # tvb_tilemap
                0x16060:    tvb_heapmeta._addr,                 # tvb_heapmeta_addr
                0x16431:    (4 * tiling_params.size1) << 24,    # s2.unk_e8
                0x10039:    tile_config,                        # tile_config ISP_CTL?
                0x16451:    0x0,                                # tile offset Y/X
                0x11821:    0x0,                                # some shader?
                0x11829:    0,
                0x11f79:    0,
                0x15359:    0,
                0x10069:    self.ctx.pipeline_base,             # USC_EXEC_BASE_ISP
                0x16020:    0,
                0x16461:    aux_fb._addr,                       # aux_fb_ptr?
                0x16090:    aux_fb._addr,                       # aux_fb_ptr?
                0x120a1:    0x1c,                               # s2.unk_158
                0x160a8:    0,
                0x16068:    (
                                0x0000000_00036011 |
                                ((tiles_x-1) << 44) |
                                ((tiles_y-1) << 53) |
                                (0 if unk1 else 0x20_00000000) |
                                ((utile_config & 0xf000) << 28)
                            ),
                0x160b8:    0x0,
            }

            if False:
                # These are actually appended by the firmware?
                regs[0x10211] = 0x134
                regs[0x10420] = 0x134
                regs[0x1c838] = 0x1
                regs[0x1ca28] = 0x1502961540 # buf_desc.unkptr_18
                regs[0x1731] = 0x1

            wc_3d.registers = [RegisterDefinition(k, v) for k, v in regs.items()]
            reg_count = len(wc_3d.registers)
            wc_3d.registers += [RegisterDefinition(0, 0) for i in range(len(regs), 128)]

        wc_3d.set_addr() # Update inner structure addresses

        if True:
            wc_3d.struct_3 = Start3DStruct3()
            if use_registers:
                wc_3d.struct_3.registers_addr = wc_3d.registers[0]._addr
                wc_3d.struct_3.register_count = reg_count
                wc_3d.struct_3.registers_length = reg_count * 12
            else:
                wc_3d.struct_3.registers_addr = 0
                wc_3d.struct_3.register_count = 0
                wc_3d.struct_3.registers_length = 0
            wc_3d.struct_3.unk_d8 = 0
            wc_3d.struct_3.depth_bias_array = Start3DArrayAddr(cmdbuf.depth_bias_array)
            wc_3d.struct_3.scissor_array = Start3DArrayAddr(cmdbuf.scissor_array)
            wc_3d.struct_3.visibility_result_buffer = 0x0
            wc_3d.struct_3.unk_118 = 0x0
            wc_3d.struct_3.unk_120 = [0] * 37
            wc_3d.struct_3.unk_reload_pipeline = Start3DClearPipelineBinding(
                cmdbuf.partial_reload_pipeline_bind, cmdbuf.partial_reload_pipeline | 4)
            wc_3d.struct_3.unk_258 = 0
            wc_3d.struct_3.unk_260 = 0
            wc_3d.struct_3.unk_268 = 0
            wc_3d.struct_3.unk_270 = 0
            wc_3d.struct_3.reload_pipeline = Start3DClearPipelineBinding(
                cmdbuf.partial_reload_pipeline_bind, cmdbuf.partial_reload_pipeline | 4)
            wc_3d.struct_3.depth_flags = cmdbuf.ds_flags | 0x44
            wc_3d.struct_3.unk_290 = 0x4040404
            wc_3d.struct_3.depth_buffer_ptr1 = cmdbuf.depth_buffer
            wc_3d.struct_3.unk_2a0 = 0x0
            wc_3d.struct_3.unk_2a8 = 0x0
            wc_3d.struct_3.depth_buffer_ptr2 = cmdbuf.depth_buffer
            wc_3d.struct_3.depth_buffer_ptr3 = cmdbuf.depth_buffer
            wc_3d.struct_3.depth_aux_buffer_ptr = depth_aux_buffer_addr
            wc_3d.struct_3.stencil_buffer_ptr1 = cmdbuf.stencil_buffer
            wc_3d.struct_3.unk_2d0 = 0x0
            wc_3d.struct_3.unk_2d8 = 0x0
            wc_3d.struct_3.stencil_buffer_ptr2 = cmdbuf.stencil_buffer
            wc_3d.struct_3.stencil_buffer_ptr3 = cmdbuf.stencil_buffer
            wc_3d.struct_3.stencil_aux_buffer_ptr = stencil_aux_buffer_addr
            wc_3d.struct_3.unk_2f8 = [0x0, 0x0]
            wc_3d.struct_3.aux_fb_unk0 = tib_blocks
            wc_3d.struct_3.unk_30c = 0x0
            wc_3d.struct_3.aux_fb = AuxFBInfo(iogpu_unk_214, 0, width, height)
            if use_registers:
                wc_3d.struct_3.s2_unk_f8 = tile_config
            else:
                wc_3d.struct_3.s2_unk_f8 = 0
            wc_3d.struct_3.unk_324_padding = bytes(0xc)
            wc_3d.struct_3.unk_partial_store_pipeline = Start3DStorePipelineBinding(
                cmdbuf.partial_store_pipeline_bind, cmdbuf.partial_store_pipeline | 4)
            wc_3d.struct_3.partial_store_pipeline = Start3DStorePipelineBinding(
                cmdbuf.partial_store_pipeline_bind, cmdbuf.partial_store_pipeline | 4)
            wc_3d.struct_3.depth_clear_val2 = cmdbuf.depth_clear_value
            wc_3d.struct_3.stencil_clear_val2 = cmdbuf.stencil_clear_value
            wc_3d.struct_3.unk_375 = 3
            wc_3d.struct_3.unk_376 = 0x0
            wc_3d.struct_3.unk_378 = 0x10
            wc_3d.struct_3.unk_37c = 0x0
            wc_3d.struct_3.unk_380 = 0x0
            wc_3d.struct_3.unk_388 = 0x0
            wc_3d.struct_3.unk_390_0 = 0x0 # Ventura
            wc_3d.struct_3.depth_dimensions = (width - 1) | ((height - 1) << 15)

        if True:
            wc_3d.struct_6 = Start3DStruct6()
            wc_3d.struct_6.tvb_overflow_count = 0x0
            wc_3d.struct_6.unk_8 = int(set_when_reloading_z_or_s)
            wc_3d.struct_6.unk_c = int(large_tib)
            wc_3d.struct_6.unk_10 = 0x0
            wc_3d.struct_6.encoder_id = cmdbuf.encoder_id
            wc_3d.struct_6.unk_1c = 0xffffffff
            wc_3d.struct_6.sampler_array = unk_buf._addr
            wc_3d.struct_6.sampler_count = 0x0
            wc_3d.struct_6.sampler_max = 0x0
            wc_3d.struct_6.unk_30 = int(process_empty_tiles)
            wc_3d.struct_6.unk_34 = int(no_clear_pipeline_textures)
            wc_3d.struct_6.unk_38 = int(msaa_zs)

        if True:
            wc_3d.struct_7 = Start3DStruct7()
            wc_3d.struct_7.unk_0_0 = 0x0
            wc_3d.struct_7.unk_0 = 0x0
            wc_3d.struct_7.stamp1 = self.stamp_3d1
            wc_3d.struct_7.stamp2 = self.stamp_3d2
            wc_3d.struct_7.stamp_value = self.stamp_value_3d
            wc_3d.struct_7.ev_3d = ev_3d.id
            wc_3d.struct_7.evctl_index = self.ev_idx
            wc_3d.struct_7.unk_24 = 1
            wc_3d.struct_7.uuid = uuid_3d
            wc_3d.struct_7.queue_cmd_count = 0
            wc_3d.struct_7.unk_30 = int(unk1)

        wc_3d.set_addr() # Update inner structure addresses
        #print("WC3D", hex(wc_3d._addr))
        #print(" s1", hex(wc_3d.struct_1._addr))
        #print(" s2", hex(wc_3d.struct_2._addr))
        #print(" s6", hex(wc_3d.struct_6._addr))
        #print(" s7", hex(wc_3d.struct_7._addr))

        ms = GPUMicroSequence(agx)
        if self.mshook_3d:
            self.mshook_3d(self, work, ms)

        start_3d = Start3DCmd()
        if not use_registers:
            start_3d.struct1_addr = wc_3d.struct_1._addr # 0x44 bytes!
            start_3d.struct2_addr = wc_3d.struct_2._addr # 0x168 bytes!
            start_3d.registers_addr = 0
        else:
            start_3d.struct1_addr = 0
            start_3d.struct2_addr = 0
            start_3d.registers_addr = wc_3d.registers[0]._addr
        start_3d.buf_thing = buf_desc
        start_3d.stats_ptr = agx.initdata.regionB.stats_3d.stats._addr
        start_3d.busy_flag_ptr = wc_3d.busy_flag._addr
        start_3d.struct6 = wc_3d.struct_6 # 4 bytes!
        start_3d.struct7 = wc_3d.struct_7 # 4 bytes!
        start_3d.cmdqueue_ptr = self.wq_3d.info._addr
        start_3d.workitem_ptr = wc_3d._addr
        start_3d.context_id = self.ctx_id
        start_3d.unk_50 = 0x1
        start_3d.submission_id = self.event_control.submission_id
        start_3d.buffer_mgr_slot = self.buffer_mgr_slot
        start_3d.unk_5c = int(large_tib)
        start_3d.queue_cmd_count = self.prev_stamp_value_3d >> 8
        start_3d.unk_68 = 0x0
        start_3d.unk_buf_ptr = wc_3d.unk_758._addr
        start_3d.unk_buf2_ptr = wc_3d.unk_buf2._addr
        start_3d.unk_7c_0 = 0x0
        start_3d.unk_7c = 0x0
        start_3d.unk_80 = 0x0
        start_3d.unk_84 = int(unk1)
        start_3d.uuid = uuid_3d
        start_3d.attachments = []
        start_3d.counter = wc_3d.counter
        start_3d.unkptr_19c = self.event_control.unk_buf._addr

        work.fb = None
        work.depth = None

        for i in cmdbuf.attachments[:cmdbuf.attachment_count]:
            cache_lines = align_up(i.size, 128) // 128
            order = 1 # FIXME
            start_3d.attachments.append(Attachment(i.pointer, cache_lines, 0x17, order)) # FIXME check
            if work.fb is None and i.type == ASAHI_ATTACHMENT_C:
                work.fb = i.pointer
            if work.depth is None and i.type == ASAHI_ATTACHMENT_Z:
                work.depth = i.pointer
        start_3d.attachments += [Attachment(0, 0, 0, 0)] * (16 - len(start_3d.attachments))
        start_3d.num_attachments = cmdbuf.attachment_count
        start_3d.unk_190 = 0x0

        start_3d_offset = ms.append(start_3d)

        ts1 = TimestampCmd()
        ts1.unk_1 = 0x0
        ts1.unk_2 = 0x0
        ts1.unk_3 = 0x80
        ts1.ts0_addr = wc_3d.ts1._addr
        ts1.ts_pointers_addr = wc_3d.ts_pointers._addr
        ts1.unk_addr = 0xdeadbeef
        ts1.cmdqueue_ptr = self.wq_3d.info._addr
        ts1.user_ts_pointers_addr = wc_3d.user_ts_pointers._addr
        if Ver.check("V >= V13_0B4"):
            ts1.unk_ts_addr = wc_3d.unk_ts._addr
        ts1.uuid = uuid_3d
        ts1.unk_30 = 0x0
        ms.append(ts1)

        if Ver.check("G >= G14X"):
            ms.append(Wait2Cmd())
        else:
            ms.append(WaitForInterruptCmd(0, 1, 0))

        ts2 = TimestampCmd()
        ts2.unk_1 = 0x0
        ts2.unk_2 = 0x0
        ts2.unk_3 = 0x0
        ts2.ts0_addr = wc_3d.ts1._addr
        ts2.ts_pointers_addr = wc_3d.ts_pointers._addr
        ts2.unk_addr = 0xdeadbeef
        ts2.cmdqueue_ptr = self.wq_3d.info._addr
        ts2.user_ts_pointers_addr = wc_3d.user_ts_pointers._addr
        if Ver.check("V >= V13_0B4"):
            ts2.unk_ts_addr = wc_3d.unk_ts._addr
        ts2.uuid = uuid_3d
        ts2.unk_30 = 0x0
        ms.append(ts2)

        finish_3d = Finalize3DCmd()
        finish_3d.uuid = uuid_3d
        finish_3d.unk_8 = 0
        finish_3d.stamp = self.stamp_3d2
        finish_3d.stamp_value = self.stamp_value_3d
        finish_3d.unk_18 = 0
        finish_3d.buf_thing = buf_desc
        finish_3d.buffer_mgr = self.buffer_mgr.info
        finish_3d.unk_2c = 1
        finish_3d.stats_ptr = agx.initdata.regionB.stats_3d.stats._addr
        finish_3d.struct7 = wc_3d.struct_7
        finish_3d.busy_flag_ptr = wc_3d.busy_flag._addr
        finish_3d.cmdqueue_ptr = self.wq_3d.info._addr
        finish_3d.workitem_ptr = wc_3d._addr
        finish_3d.unk_5c = self.ctx_id
        finish_3d.unk_buf_ptr = wc_3d.unk_758._addr
        finish_3d.unk_6c_0 = 0
        finish_3d.unk_6c = 0
        finish_3d.unk_74 = 0
        finish_3d.unk_7c = 0
        finish_3d.unk_84 = 0
        finish_3d.unk_8c = 0
        finish_3d.unk_8c_g14 = 0
        finish_3d.restart_branch_offset = start_3d_offset - ms.off
        finish_3d.unk_98 = 0
        finish_3d.unk_9c = bytes(0x10)
        ms.append(finish_3d)
        ms.finalize()

        work.add(ms.obj)

        wc_3d.microsequence_ptr = ms.obj._addr
        wc_3d.microsequence_size = ms.size

        print(wc_3d)
        self.wq_3d.submit(wc_3d)

        ##### TA init

        #print(ctx_info)
        if wait_for is not None:
            barrier_cmd = agx.kobj.new(WorkCommandBarrier, track=False, align=0x20)
            work.add(barrier_cmd)
            if not isinstance(wait_for, tuple):
                barrier_cmd.stamp = wait_for.renderer.stamp_3d2
                barrier_cmd.wait_value = wait_for.stamp_value_3d
                barrier_cmd.event = wait_for.ev_3d.id
            else:
                barrier_cmd.stamp_addr = wait_for[0]
                barrier_cmd.wait_value = wait_for[1]
                barrier_cmd.event = wait_for[2]

            barrier_cmd.stamp_self = self.stamp_value_ta
            barrier_cmd.uuid = uuid_ta

            self.wq_ta.submit(barrier_cmd)

        if not self.buffer_mgr_initialized:
            wc_initbm = agx.kobj.new(WorkCommandInitBM, track=False, align=0x20)
            work.add(wc_initbm)
            wc_initbm.context_id = self.ctx_id
            wc_initbm.buffer_mgr_slot = self.buffer_mgr_slot
            wc_initbm.unk_c = 0
            wc_initbm.unk_10 = self.buffer_mgr.info.block_count
            wc_initbm.buffer_mgr = self.buffer_mgr.info
            wc_initbm.stamp_value = self.stamp_value_ta

            self.wq_ta.submit(wc_initbm)

            self.buffer_mgr_initialized = True

        ##### TA execution

        work.wc_ta = wc_ta = agx.cmdbuf.new(WorkCommandTA, track=False, align=0x20)
        work.add(work.wc_ta)
        wc_ta.context_id = self.ctx_id
        wc_ta.counter = 1
        wc_ta.unk_8 = 0
        wc_ta.event_control = self.event_control
        wc_ta.buffer_mgr_slot = self.buffer_mgr_slot
        wc_ta.buffer_mgr = self.buffer_mgr.info
        wc_ta.buf_thing = buf_desc
        wc_ta.unk_emptybuf_addr = wc_3d.unk_emptybuf_addr
        wc_ta.unk_34 = 0x0

        wc_ta.unk_3e8 = bytes(0x64)
        wc_ta.unk_594 = WorkCommand0_UnkBuf()

        wc_ta.ts1 = TimeStamp(0)
        wc_ta.ts_pointers = TimeStampPointers(work.tsta_start._addr, work.tsta_end._addr)
        wc_ta.user_ts_pointers = TimeStampPointers(work.nsta_start._addr, work.nsta_end._addr)
        wc_ta.client_sequence = 1
        # Ventura
        wc_ta.unk_ts = TimeStamp()
        wc_ta.unk_ts2 = TimeStamp()

        # Structures embedded in WorkCommandTA
        if not use_registers:
            wc_ta.tiling_params = tiling_params

        import random

        tiling_control = agx.chip_info.tiling_control
        if not clustering:
            tiling_control |= 1

        if not use_registers:
            wc_ta.struct_2 = StartTACmdStruct2()
            wc_ta.struct_2.unk_0 = 0 if unk1 else 0x200
            wc_ta.struct_2.unk_8 = 0x1e3ce508 # fixed
            wc_ta.struct_2.unk_c = 0x1e3ce508 # fixed
            wc_ta.struct_2.tvb_tilemap = tvb_tilemap._addr
            wc_ta.struct_2.tvb_cluster_tilemaps = unk_tile_buf1._addr
            wc_ta.struct_2.tpc = self.tpc._addr
            wc_ta.struct_2.tvb_heapmeta_addr = tvb_heapmeta._addr | 0x8000_0000_0000_0000
            wc_ta.struct_2.iogpu_unk_54 = 0x6b0003 # fixed
            wc_ta.struct_2.iogpu_unk_55 = 0x3a0012 # fixed
            wc_ta.struct_2.iogpu_unk_56 = 0x1 # fixed
            wc_ta.struct_2.tvb_cluster_meta1 = unk_tile_buf2._addr | 0x4_0000_0000_0000
            wc_ta.struct_2.unk_48 = utile_config
            wc_ta.struct_2.unk_50 = 0x88 # fixed
            wc_ta.struct_2.tvb_heapmeta_addr2 = tvb_heapmeta._addr
            wc_ta.struct_2.unk_60 = 0x0 # fixed
            wc_ta.struct_2.core_mask = 0xffffffffffffffff
            #wc_ta.struct_2.unk_68 = 0xff << (8 * (self.buffer_mgr_slot % 8))
            wc_ta.struct_2.iogpu_deflake_1 = deflake_1._addr
            wc_ta.struct_2.iogpu_deflake_2 = deflake_2._addr
            wc_ta.struct_2.unk_80 = 0x1 # fixed
            wc_ta.struct_2.iogpu_deflake_3 = deflake_3._addr | 0x4_0000_0000_0000 # check
            wc_ta.struct_2.encoder_addr = cmdbuf.encoder_ptr
            wc_ta.struct_2.tvb_cluster_meta2 = unk_tile_buf3._addr
            wc_ta.struct_2.tvb_cluster_meta3 = unk_tile_buf4._addr
            wc_ta.struct_2.tiling_control = tiling_control
            wc_ta.struct_2.unk_b0 = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0] # fixed
            wc_ta.struct_2.pipeline_base = self.ctx.pipeline_base
            wc_ta.struct_2.tvb_cluster_meta4 = unk_tile_buf5._addr | 0x3000_0000_0000_0000
            wc_ta.struct_2.unk_f0 = 0x20 # fixed
            wc_ta.struct_2.unk_f8 = 0x8c60 # fixed
            wc_ta.struct_2.helper_program = 0
            wc_ta.struct_2.unk_104 = 0
            wc_ta.struct_2.helper_arg = 0
            wc_ta.struct_2.unk_110 = 0
            wc_ta.struct_2.unk_118 = 0x1c # fixed

            wc_ta.registers_addr = 0
            wc_ta.register_count = 0
            wc_ta.registers_length = 0
        else:
            regs = {
                0x10141:    (0 if unk1 else 0x200),               # s2.unk_0
                0x1c039:    tvb_tilemap._addr,
                0x1c9c8:    tvb_tilemap._addr,
                0x1c041:    unk_tile_buf1._addr,                # s2.tvb_cluster_tilemaps
                0x1c9d0:    unk_tile_buf1._addr,
                0x1c0a1:    self.tpc._addr,                     # TE_TPC_ADDR
                0x1c031:    tvb_heapmeta._addr | 0x8000_0000_0000_0000,
                0x1c9c0:    tvb_heapmeta._addr | 0x8000_0000_0000_0000,
                0x1c051:    0x3a0012006b0003,                   # iogpu_unk_54/55
                0x1c061:    1,                                  # iogpu_unk_56
                0x10149:    utile_config,                       # s2.unk_48 utile_config
                0x10139:    ppp_multisamplectl,                 # PPP_MULTISAMPLECTL
                0x10111:    deflake_1._addr,
                0x1c9b0:    deflake_1._addr,
                0x10119:    deflake_2._addr,
                0x1c9b8:    deflake_2._addr,
                0x1c958:    1,                                  # s2.unk_80
                0x1c950:    deflake_3._addr | 0x4_0000_0000_0000,
                0x1c930:    0,                                  # VCE related addr, lsb to enable
                0x1c880:    cmdbuf.encoder_ptr,                 # VDM_CTRL_STREAM_BASE
                0x1c898:    0x0,                                # if lsb set, faults in UL1C0, possibly missing addr.
                0x1c948:    unk_tile_buf3._addr,                # tvb_cluster_meta2
                0x1c888:    unk_tile_buf4._addr,                # tvb_cluster_meta3
                0x1c890:    tiling_control,                     # tvb_tiling_control
                0x1c918:    0x4,
                0x1c079:    tvb_heapmeta._addr,
                0x1c9d8:    tvb_heapmeta._addr,
                0x1c089:    0,
                0x1c9e0:    0,
                0x16c41:    unk_tile_buf5._addr,                # tvb_cluster_meta4
                0x1ca40:    unk_tile_buf5._addr,                # tvb_cluster_meta4
                0x1c9a8:    0x1c, # + meta1_blocks?             # min_free_tvb_pages?
                0x1c920:    unk_tile_buf2._addr,                # ??? | meta1_blocks?
                0x10151:    0,
                0x1c199:    0,
                0x1c1a1:    0,
                0x1c1a9:    0,                                  # 0x10151 bit 1 enables
                0x1c1b1:    0,
                0x1c1b9:    0,
                0x10061:    self.ctx.pipeline_base,             # USC_EXEC_BASE_TA
                0x11801:    0,                                  # some shader?
                0x11809:    0,                                  # maybe arg?
                0x11f71:    0,
                0x1c0b1:    tiling_params.size1,                # TE_PSG
                0x1c850:    tiling_params.size1,
                0x10131:    tiling_params.unk_4,
                0x10121:    tiling_params.unk_8,                # PPP_CTRL
                0x10129:    tiling_params.x_max | (tiling_params.y_max << 16),  # PPP_SCREEN
                0x101b9:    tiling_params.tile_count,           # TE_SCREEN
                0x1c069:    tiling_params.x_blocks,             # TE_MTILE1
                0x1c071:    tiling_params.y_blocks,             # TE_MTILE2
                0x1c081:    tiling_params.size2,                # TE_MTILE
                0x1c0a9:    tiling_params.size3,                # TE_TPC
                0x10171:    tiling_params.unk_24,
                0x10169:    tiling_params.unk_28,               # TA_RENDER_TARGET_MAX
                0x12099:    0,
                0x1c9e8:    0,
            }

            if False:
                # These are actually appended by the firmware?
                regs[0x10209] = 0x133
                regs[0x1c9f0] = 0x133
                regs[0x1c830] = 0x1
                regs[0x1c9f0] = 0x1502960fa0
                regs[0x16c39] = 0x1502960fa0 # buf_desc.unkptr_18
                regs[0x1c910] = 0xa0000b0125
                regs[0x1c8e0] = 0xff # core_mask_0
                regs[0x1c8e8] = 0x00 # core_mask_1

            wc_ta.registers = [RegisterDefinition(k, v) for k, v in regs.items()]
            ta_reg_count = len(wc_ta.registers)
            wc_ta.registers += [RegisterDefinition(0, 0) for i in range(len(regs), 128)]

            wc_ta.set_addr() # Update inner structure addresses

            wc_ta.registers_addr = wc_ta.registers[0]._addr
            wc_ta.register_count = ta_reg_count
            wc_ta.registers_length = ta_reg_count * 12

        wc_ta.unk_pad = 0

        if True:
            wc_ta.struct_3 = StartTACmdStruct3()
            wc_ta.struct_3.unk_480 = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0] # fixed
            wc_ta.struct_3.unk_498 = 0x0 # fixed
            wc_ta.struct_3.unk_4a0 = 0x0 # fixed
            wc_ta.struct_3.iogpu_deflake_1 = deflake_1._addr
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
            wc_ta.struct_3.encoder_id = cmdbuf.encoder_id
            wc_ta.struct_3.unk_538 = 0x0 # fixed
            wc_ta.struct_3.unk_53c = 0xffffffff
            wc_ta.struct_3.sampler_array = wc_3d.struct_6.sampler_array
            wc_ta.struct_3.sampler_count = 0x0
            wc_ta.struct_3.sampler_max = 0x0
            wc_ta.struct_3.unk_550 = [
                0x0, 0x0, # fixed
                0x0, # memoryless_rts_used
                0x0, 0x0, 0x0] # fixed
            wc_ta.struct_3.stamp1 = self.stamp_ta1
            wc_ta.struct_3.stamp2 = self.stamp_ta2
            wc_ta.struct_3.stamp_value = self.stamp_value_ta
            wc_ta.struct_3.ev_ta = ev_ta.id
            wc_ta.struct_3.evctl_index = self.ev_idx
            wc_ta.struct_3.unk_584 = 0x0 # flush_stamps
            wc_ta.struct_3.uuid2 = uuid_ta
            wc_ta.struct_3.queue_cmd_count = 0
            wc_ta.struct_3.unk_590 = int(unk1)

        wc_ta.set_addr() # Update inner structure addresses
        #print("wc_ta", wc_ta)

        ms = GPUMicroSequence(agx)
        if self.mshook_ta:
            self.mshook_ta(self, work, ms)

        start_ta = StartTACmd()
        if not use_registers:
            start_ta.tiling_params_addr = wc_ta.tiling_params._addr
            start_ta.struct2_addr = wc_ta.struct_2._addr # len 0x120
            start_ta.registers_addr = 0
        else:
            start_ta.tiling_params_addr = 0
            start_ta.struct2_addr = 0
            start_ta.registers_addr = wc_ta.registers[0]._addr
        start_ta.buffer_mgr = self.buffer_mgr.info
        start_ta.buf_thing = buf_desc
        start_ta.stats_ptr = agx.initdata.regionB.stats_ta.stats._addr
        start_ta.cmdqueue_ptr = self.wq_ta.info._addr
        start_ta.context_id = self.ctx_id
        start_ta.unk_38 = 1
        start_ta.submission_id = self.event_control.submission_id
        start_ta.buffer_mgr_slot = self.buffer_mgr_slot
        start_ta.unk_48 = 0#1 #0
        start_ta.unk_50 = 0
        start_ta.struct3_addr = wc_ta.struct_3._addr

        start_ta.unkptr_5c = wc_ta.unk_594._addr
        start_ta.unk_64 = 0x0 # fixed
        start_ta.unk_68 = int(unk1) # sometimes 1?
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
        start_ta.unk_178 = 0 if clustering else 1
        start_ta.counter = wc_ta.counter
        start_ta.unkptr_180 = self.event_control.unk_buf._addr

        start_ta_offset = ms.append(start_ta)

        ts1 = TimestampCmd()
        ts1.unk_1 = 0x0
        ts1.unk_2 = 0x0
        ts1.unk_3 = 0x80
        ts1.ts0_addr = wc_ta.ts1._addr
        ts1.ts_pointers_addr = wc_ta.ts_pointers._addr
        ts1.unk_addr = 0xdeadbeef
        ts1.cmdqueue_ptr = self.wq_ta.info._addr
        ts1.user_ts_pointers_addr = wc_ta.user_ts_pointers._addr
        if Ver.check("V >= V13_0B4"):
            ts1.unk_ts_addr = wc_ta.unk_ts._addr
        ts1.uuid = uuid_ta
        ts1.unk_30 = 0x0
        ms.append(ts1)

        if Ver.check("G >= G14X"):
            ms.append(Wait2Cmd())
        else:
            ms.append(WaitForInterruptCmd(1, 0, 0))

        ts2 = TimestampCmd()
        ts2.unk_1 = 0x0
        ts2.unk_2 = 0x0
        ts2.unk_3 = 0x0
        ts2.ts0_addr = wc_ta.ts1._addr
        ts2.ts_pointers_addr = wc_ta.ts_pointers._addr
        ts2.unk_addr = 0xdeadbeef
        ts2.cmdqueue_ptr = self.wq_ta.info._addr
        ts2.user_ts_pointers_addr = wc_ta.user_ts_pointers._addr
        if Ver.check("V >= V13_0B4"):
            ts2.unk_ts_addr = wc_ta.unk_ts._addr
        ts2.uuid = uuid_ta
        ts2.unk_30 = 0x0
        ms.append(ts2)

        finish_ta = FinalizeTACmd()
        finish_ta.buf_thing = buf_desc
        finish_ta.buffer_mgr = self.buffer_mgr.info
        finish_ta.stats_ptr = agx.initdata.regionB.stats_ta.stats._addr
        finish_ta.cmdqueue_ptr = self.wq_ta.info._addr
        finish_ta.context_id = self.ctx_id
        finish_ta.unk_28 = 0x0 # fixed
        finish_ta.struct3_addr = wc_ta.struct_3._addr
        finish_ta.unk_34 = 0x0 # fixed
        finish_ta.uuid = uuid_ta
        finish_ta.stamp = self.stamp_ta2
        finish_ta.stamp_value = self.stamp_value_ta
        finish_ta.unk_48 = 0x0 # fixed
        finish_ta.unk_50 = 0x0 # fixed
        finish_ta.unk_54 = 0x0 # fixed
        finish_ta.unk_58 = 0x0 # fixed
        finish_ta.unk_60 = 0x0 # fixed
        finish_ta.unk_64 = 0x0 # fixed
        finish_ta.unk_68 = 0x0 # fixed
        finish_ta.unk_6c_g14 = 0 # fixed
        finish_ta.restart_branch_offset = start_ta_offset - ms.off
        finish_ta.unk_70 = 0x0 # fixed
        finish_ta.unk_74 = bytes(0x10) # Ventura
        ms.append(finish_ta)

        ms.finalize()

        print(wc_ta)
        print(hex(wc_ta.struct_3._addr))
        print(hex(finish_ta.struct3_addr))
        print(hex(wc_ta._addr))
        ms.dump()

        work.add(ms.obj)

        wc_ta.unkptr_45c = self.tpc._addr
        wc_ta.tvb_size = tpc_size
        wc_ta.microsequence_ptr = ms.obj._addr
        wc_ta.microsequence_size = ms.size
        wc_ta.ev_3d = ev_3d.id
        wc_ta.stamp_value = self.stamp_value_ta

        print(wc_ta)
        self.wq_ta.submit(wc_ta)

        self.agx.log("Submit done")

        #self.ev_idx = (self.ev_idx + 1) % 4

        return work

    def run(self):
        ##### Run queues
        self.agx.log("Run queues")
        self.agx.ch.queue[self.queue].q_3D.run(self.wq_3d, self.ev_3d.id)
        self.agx.ch.queue[self.queue].q_TA.run(self.wq_ta, self.ev_ta.id)
        self.agx.log("Run done")

    def wait(self):
        self.agx.log("Waiting...")
        work = self.work[-1]

        ##### Wait for work completion
        while True:
            self.stamp_3d1.pull()
            self.stamp_ta1.pull()
            if (self.stamp_3d1.value >= self.stamp_value_3d and
                self.stamp_ta1.value >= self.stamp_value_ta):
                break
            self.agx.wait_for_events(timeout=2.0)

        if not self.ev_3d.fired:
            self.agx.log("3D event didn't fire")

        self.agx.log(f"Event {self.ev_3d.id} fired")
        #print("Stamps:")
        #print(self.stamp_ta1.pull())
        #print(self.stamp_ta2.pull())
        #print(self.stamp_3d1.pull())
        #print(self.stamp_3d2.pull())

        #print("WCs:")
        #print(work.wc_3d.pull())
        #print(work.wc_ta.pull())

        #if work.fb is not None and work.width and work.height:
        if work.fb is not None and work.width and work.height and work.width == 1920:
            agx = self.agx
            self.agx.log(f"Render {work.width}x{work.height} @ {work.fb:#x}")
            base, obj = self.agx.find_object(work.fb, self.ctx_id)

            #unswizzle(agx, obj._paddr, work.width, work.height, 4, "fb.bin", grid=False)
            #open("fb.bin", "wb").write(self.agx.u.iface.readmem(obj._paddr, work.width*work.height*4))
            #os.system(f"convert -size {work.width}x{work.height} -depth 8 rgba:fb.bin -alpha off frame{self.frames}.png")
            self.agx.p.fb_blit(0, 0, work.width, work.height, obj._paddr, work.width, PIX_FMT.XBGR)

        if False: #work.depth is not None:
            base, obj = self.agx.find_object(work.depth, self.ctx_id)

            width = align_up(work.width, 64)
            height = align_up(work.height, 64)

            obj.pull()
            chexdump(obj.val)

            unswizzle(self.agx, obj._paddr, work.width, work.height, 4, "depth.bin", grid=False)
            os.system(f"convert -size {work.width}x{work.height} -depth 8 rgba:depth.bin -alpha off depth.png")

        for i in self.work:
            i.free()

        self.work = []
