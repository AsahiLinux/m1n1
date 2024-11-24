"""
I think these are executed by a simple state machine on the firmware's arm core,
and the typical result is a commandlist submitting to one of the gpu's hardware
command processors.

It seems like a common pattern is:
  1. Start (3D or Compute)
  2. Timestamp
  3. Wait For Interrupts
  4. Timestamp again
  5. Finish (3D or Compute)
  6. End

Error messages call these as SKU commands

"""
from m1n1.constructutils import *

from construct import *
from construct.core import Int64ul, Int32ul, Int32sl
import textwrap

__all__ = []

class TimeStamp(ConstructValueClass):
    subcon = Int64ul

    def __init__(self, value=0):
        self.value = value

class TimeStampPointers(ConstructClass):
    subcon = Struct(
        "start_addr" / Int64ul,
        "end_addr" / Int64ul,
    )

    def __init__(self, start_addr=0, end_addr=0):
        super().__init__()
        self.start_addr = start_addr
        self.end_addr = end_addr

class TsFlag(ConstructValueClass):
    subcon = Int8ul

    def __init__(self, value=0):
        self.value = value

class WrappedPointer(ConstructValueClass):
    subcon = Int64ul

    def __init__(self, value=0):
        self.value = value

class StampCounter(ConstructValueClass):
    subcon = Hex(Int32ul)

    def __init__(self):
        self.value = 0

class BufferManagerBlockControl(ConstructClass):
    subcon = Struct(
        "total" / Int32ul,
        "wptr" / Int32ul,
        "unk" / Int32ul,
        "pad" / ZPadding(0x34)
    )

class BufferManagerCounter(ConstructClass):
    subcon = Struct(
        "count" / Int32ul,
        "pad" / ZPadding(0x3c)
    )

class BufferManagerMisc(ConstructClass):
    subcon = Struct(
        "gpu_0" / Default(Int32ul, 0),
        "gpu_4" / Default(Int32ul, 0),
        "gpu_8" / Default(Int32ul, 0),
        "gpu_c" / Default(Int32ul, 0),
        "pad_10" / ZPadding(0x10),
        "cpu_flag" / Int32ul,
        "pad_24" / ZPadding(0x1c),
    )

class BufferManagerInfo(ConstructClass):
    subcon = Struct(
        "gpu_counter" / Int32ul,
        "unk_4" / Int32ul,
        "last_id" / Int32ul,
        "cur_id" / Int32ul,
        "unk_10" / Int32ul,
        "gpu_counter2" / Int32ul,
        "unk_18" / Int32ul,
        Ver("V < V13_0B4 || G >= G14X", "unk_1c" / Int32ul),
        "page_list_addr" / Int64ul,
        "page_list_size" / Int32ul,
        "page_count" / Int32ul,
        "unk_30" / Int32ul,
        "block_count" / Int32ul,
        "unk_38" / Int32ul,
        "block_list_addr" / Int64ul,
        "block_ctl_addr" / Int64ul, # points to two u32s
        "block_ctl" / ROPointer(this.block_ctl_addr, BufferManagerBlockControl),
        "last_page" / Int32ul,
        "gpu_page_ptr1" / Int32ul,
        "gpu_page_ptr2" / Int32ul,
        "unk_58" / Int32ul,
        "block_size" / Int32ul,
        "unk_60" / Int64ul,
        "counter_addr" / Int64ul,
        "counter" / ROPointer(this.counter_addr, BufferManagerCounter),
        "unk_70" / Int32ul,
        "unk_74" / Int32ul,
        "unk_78" / Int32ul,
        "unk_7c" / Int32ul,
        "unk_80" / Int32ul,
        "unk_84" / Int32ul,
        "unk_88" / Int32ul,
        "unk_8c" / Int32ul,
        "unk_90" / HexDump(Bytes(0x30)),

    )

    def __init__(self):
        super().__init__()
        self.gpu_counter = 0x0
        self.unk_4 = 0
        self.last_id = 0x0
        self.cur_id = 0xffffffff
        self.unk_10 = 0x0
        self.gpu_counter2 = 0x0
        self.unk_18 = 0x0
        self.unk_1c = 0x0
        self.unk_30 = 0xd1a
        self.unk_38 = 0x0
        self.gpu_page_ptr1 = 0x0
        self.gpu_page_ptr2 = 0x0
        self.unk_58 = 0x0
        self.unk_60 = 0x0
        self.unk_70 = 0x0
        self.unk_74 = 0x0
        self.unk_78 = 0x0
        self.unk_7c = 0x0
        self.unk_80 = 0x1
        self.unk_84 = 0x66cc
        self.unk_88 = 0x2244
        self.unk_8c = 0x0
        self.unk_90 = bytes(0x30)

class RegisterDefinition(ConstructClass):
    subcon = Struct(
        "number" / Int32ul,
        "data" / Int64ul,
    )

    def __init__(self, number, data):
        super().__init__()
        self.number = number
        self.data = data

class Start3DClearPipelineBinding(ConstructClass):
    subcon = Struct(
        "pipeline_bind" / Int64ul,
        "address" / Int64ul,
    )

    def __init__(self, pipeline_bind=None, address=None):
        super().__init__()
        self.pipeline_bind = pipeline_bind
        self.address = address

class Start3DStorePipelineBinding(ConstructClass):
    subcon = Struct(
        "unk_0" / Int64ul,
        "unk_8" / Int32ul,
        "pipeline_bind" / Int32ul,
        "unk_10" / Int32ul,
        "address" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c_padding" / Int32ul,
    )

    def __init__(self, pipeline_bind=None, address=None):
        super().__init__()
        self.unk_0 = 0
        self.unk_8 = 0
        self.pipeline_bind = pipeline_bind
        self.unk_10 = 0
        self.address = address
        self.unk_18 = 0
        self.unk_1c_padding = 0

class Start3DArrayAddr(ConstructClass):
    subcon = Struct(
        "ptr" / Int64ul,
        "unk_padding" / Int64ul,
    )

    def __init__(self, ptr=None):
        super().__init__()
        self.ptr = ptr
        self.unk_padding = 0

class AuxFBInfo(ConstructClass):
    subcon = Struct(
        "unk1" / Int32ul,
        "unk2" / Int32ul,
        "width" / Dec(Int32ul),
        "height" / Dec(Int32ul),
        Ver("V >= V13_0B4", "unk3" / Int64ul),
    )

    def __init__(self, unk1, unk2, width, height):
        super().__init__()
        self.unk1 = unk1
        self.unk2 = unk2
        self.width = width
        self.height = height
        self.unk3 = 0x100000

class Start3DStruct1(ConstructClass):
    subcon = Struct(
        "store_pipeline_bind" / Int32ul, # 0x12, 0x34 seen
        "store_pipeline_addr" / Int32ul,
        "unk_8" / Int32ul,
        "unk_c" / Int32ul,
        "merge_upper_x" / Float32l,
        "merge_upper_y" / Float32l,
        "unk_18" / Int64ul,
        "tile_blocks_y" / Int16ul, # * 4
        "tile_blocks_x" / Int16ul, # * 4
        "unk_24" / Int32ul,
        "tile_counts" / Int32ul,
        "unk_2c" / Int32ul,
        "depth_clear_val1" / Float32l,
        "stencil_clear_val1" / Int8ul,
        "unk_35" / Int8ul,
        "unk_36" / Int16ul,
        "unk_38" / Int32ul,
        "unk_3c" / Int32ul,
        "helper_cfg" / Int32ul,
        "unk_44_padding" / HexDump(Bytes(0x9c)),
    )

class Start3DStruct2(ConstructClass):
    subcon = Struct(
        "unk_0" / Int64ul,
        "clear_pipeline" / Start3DClearPipelineBinding,
        "unk_18" / Int64ul,
        "scissor_array" / Int64ul,
        "depth_bias_array" / Int64ul,
        "aux_fb" / AuxFBInfo,
        "depth_dimensions" / Int64ul,
        "visibility_result_buffer" / Int64ul,
        "depth_flags" / Int64ul, # 0x40000 - has stencil 0x80000 - has depth
        Ver("G >= G14", "unk_58_g14_0" / Int64ul),
        Ver("G >= G14", "unk_58_g14_8" / Int64ul),
        "depth_buffer_ptr1" / Int64ul,
        "depth_buffer_ptr2" / Int64ul,
        "stencil_buffer_ptr1" / Int64ul,
        "stencil_buffer_ptr2" / Int64ul,
        Ver("G >= G14", "unk_68_g14_0" / HexDump(Bytes(0x20))),
        "unk_78" / Array(4, Int64ul),
        "depth_aux_buffer_ptr1" / Int64ul,
        "unk_a0" / Int64ul,
        "depth_aux_buffer_ptr2" / Int64ul,
        "unk_b0" / Int64ul,
        "stencil_aux_buffer_ptr1" / Int64ul,
        "unk_c0" / Int64ul,
        "stencil_aux_buffer_ptr2" / Int64ul,
        "unk_d0" / Int64ul,
        "tvb_tilemap" / Int64ul,
        "tvb_heapmeta_addr" / Int64ul,
        "unk_e8" / Int64ul,
        "tvb_heapmeta_addr2" / Int64ul,
        "unk_f8" / Int64ul,
        "aux_fb_ptr" / Int64ul,
        "unk_108" / Array(6, Int64ul),
        "pipeline_base" / Int64ul,
        "unk_140" / Int64ul,
        "helper_program" / Int32ul, # bit 0: enable
        "unk_14c" / Int32ul, # 0
        "helper_arg" / Int64ul, # stack layout
        "unk_158" / Int64ul,
        "unk_160" / Int64ul,
        Ver("G < G14", "unk_168_padding" / HexDump(Bytes(0x1d8))),
        Ver("G >= G14", "unk_198_padding" / HexDump(Bytes(0x1a8))),
        Ver("V < V13_0B4", ZPadding(8)),
    )

class Start3DStruct3(ConstructClass):
    subcon = Struct(
        "registers_addr" / Int64ul,
        "register_count" / Int16ul,
        "registers_length" / Int16ul,
        "unk_d8" / Int32ul,
        "depth_bias_array" / Start3DArrayAddr,
        "scissor_array" / Start3DArrayAddr,
        "visibility_result_buffer" / Int64ul,
        "unk_118" / Int64ul,
        "unk_120" / Array(37, Int64ul),
        "unk_reload_pipeline" / Start3DClearPipelineBinding,
        "unk_258" / Int64ul,
        "unk_260" / Int64ul,
        "unk_268" / Int64ul,
        "unk_270" / Int64ul,
        "reload_pipeline" / Start3DClearPipelineBinding,
        "depth_flags" / Int64ul, # 0x40000 - has stencil 0x80000 - has depth
        "unk_290" / Int64ul,
        "depth_buffer_ptr1" / Int64ul,
        "unk_2a0" / Int64ul,
        "unk_2a8" / Int64ul,
        "depth_buffer_ptr2" / Int64ul,
        "depth_buffer_ptr3" / Int64ul,
        "depth_aux_buffer_ptr" / Int64ul,
        "stencil_buffer_ptr1" / Int64ul,
        "unk_2d0" / Int64ul,
        "unk_2d8" / Int64ul,
        "stencil_buffer_ptr2" / Int64ul,
        "stencil_buffer_ptr3" / Int64ul,
        "stencil_aux_buffer_ptr" / Int64ul,
        "unk_2f8" / Array(2, Int64ul),
        "aux_fb_unk0" / Int32ul,
        "unk_30c" / Int32ul,
        "aux_fb" / AuxFBInfo,
        "s2_unk_f8" / Int32ul,
        "unk_324_padding" / HexDump(Bytes(0xc)),
        "unk_partial_store_pipeline" / Start3DStorePipelineBinding,
        "partial_store_pipeline" / Start3DStorePipelineBinding,
        "depth_clear_val2" / Float32l,
        "stencil_clear_val2" / Int8ul,
        "unk_375" / Int8ul,
        "unk_376" / Int16ul,
        "unk_378" / Int32ul,
        "unk_37c" / Int32ul,
        "unk_380" / Int64ul,
        "unk_388" / Int64ul,
        Ver("V >= V13_0B4", "unk_390_0" / Int64ul),
        "depth_dimensions" / Int64ul,
    )

class BufferThing(ConstructClass):
    subcon = Struct(
        Ver("G >= G14X", "unk0_addr" / Int64ul),
        Ver("G >= G14X", "unk0_addr2" / Int64ul),
        # Ver("G >= G14X", "unk0" / ROPointer(this.unk0_addr, Array(8, Int32ul))),
        "unk_0" / Int64ul,
        "unk_8" / Int64ul,
        "unk_10" / Int64ul,
        "unkptr_18" / Int64ul,
        "unk_20" / Int32ul,
        Ver("V >= V13_3", "unk_28" / Int64ul),
        "bm_misc_addr" / Int64ul,
        "bm_misc" / ROPointer(this.bm_misc_addr, BufferManagerMisc),
        "unk_2c" / Int32ul,
        Ver("G < G14X", "unk_30" / Int64ul),
        Ver("G < G14X", "unk_38" / Int64ul),
    )

class Start3DStruct6(ConstructClass):
    subcon = Struct(
        "tvb_overflow_count" / Int64ul,
        "unk_8" / Int32ul,
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "encoder_id" / Int64ul,
        "unk_1c" / Int32ul,
        "sampler_array" / Int64ul,
        "sampler_count" / Int32ul,
        "sampler_max" / Int32ul,
        "unk_30" / Int32ul,
        "unk_34" / Int32ul,
        "unk_38" / Int32ul,
    )

class Start3DStruct7(ConstructClass):
    subcon = Struct(
        Ver("V >= V13_3", "unk_0_0" / Int32ul),
        "unk_0" / Int64ul,
        "stamp1_addr" / WrappedPointer, # same contents as below
        "stamp1" / ROPointer(this.stamp1_addr.value, StampCounter),
        "stamp2_addr" / WrappedPointer, # same as FinalizeComputeCmd.stamp - some kind of fence/token
        "stamp2" / ROPointer(this.stamp2_addr.value, StampCounter),
        "stamp_value" / Int32ul,
        "ev_3d" / Int32ul,
        "evctl_index" / Int32ul,
        "unk_24" / Int32ul,
        "uuid" / Int32ul,
        "queue_cmd_count" / Int32ul,
        "unk_30" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.stamp1_addr = StampCounter()
        self.stamp2_addr = StampCounter()

class Attachment(ConstructClass):
    subcon = Struct(
        "address" / Int64ul,
        "size" / Int32ul,
        "unk_c" / Int16ul,
        "unk_e" / Int16ul,
    )

    def __init__(self, addr, size, unk_c, unk_e):
        self.address = addr
        self.size = size
        self.unk_c = unk_c
        self.unk_e = unk_e

class Start3DCmd(ConstructClass):
    subcon = Struct( # 0x194 bytes''''
        "magic" / Const(0x24, Int32ul),
        "struct1_addr" / Int64ul, # empty before run. Output? WorkCommand3D + 0x3c0
        "struct2_addr" / Int64ul, # ??  WorkCommand3D + 0x78
        Ver("G >= G14X", "registers_addr" / Int64ul),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "stats_ptr" / Int64ul,
        "busy_flag_ptr" / Int64ul, # 4 bytes
        "struct6_addr" / Int64ul, # 0x3c bytes
        "struct6" / ROPointer(this.struct6_addr, Start3DStruct6),
        "struct7_addr" / Int64ul, # 0x34 bytes
        "struct7" / ROPointer(this.struct7_addr, Start3DStruct7),
        "cmdqueue_ptr" / Int64ul, # points back to the CommandQueueInfo that this command came from
        "workitem_ptr" / Int64ul, # points back at the WorkItem that this command came from
        "context_id" / Int32ul,
        "unk_50" / Int32ul,
        "submission_id" / Int32ul,
        "buffer_mgr_slot" / Int32ul,
        "unk_5c" / Int32ul,
        "queue_cmd_count" / Int64ul, # 0
        "unk_68" / Int32ul, # 0
        "unk_buf_ptr" / Int64ul,
        "unk_buf2_ptr" / Int64ul, # 0x18 bytes
        Ver("V >= V13_3", "unk_7c_0" / Int64ul),
        "unk_7c" / Int32ul,
        "unk_80" / Int32ul,
        "unk_84" / Int32ul,
        "uuid" / Int32ul, # uuid for tracking
        "attachments" / Array(16, Attachment),
        "num_attachments" / Int32ul,
        "unk_190" / Int32ul,
        Ver("V >= V13_0B4", "counter" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_19c" / Int64ul),
    )


class Finalize3DCmd(ConstructClass):
    subcon = Struct( # 0x9c bytes
        "magic" / Const(0x25, Int32ul),
        "uuid" / Int32ul, # uuid for tracking
        "unk_8" / Int32ul, # 0
        "stamp_addr" / Int64ul,
        "stamp" / ROPointer(this.stamp_addr, StampCounter),
        "stamp_value" / Int32ul,
        "unk_18" / Int32ul,
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "unk_2c" / Int64ul, # 1
        "stats_ptr" / Int64ul,
        "struct7_addr" / Int64ul,
        "struct7" / ROPointer(this.struct7_addr, Start3DStruct7),
        "busy_flag_ptr" / Int64ul,
        "cmdqueue_ptr" / Int64ul,
        "workitem_ptr" / Int64ul,
        "unk_5c" / Int64ul,
        "unk_buf_ptr" / Int64ul, # Same as Start3DCmd.unkptr_6c
        Ver("V >= V13_3", "unk_6c_0" / Int64ul),
        "unk_6c" / Int64ul, # 0
        "unk_74" / Int64ul, # 0
        "unk_7c" / Int64ul, # 0
        "unk_84" / Int64ul, # 0
        "unk_8c" / Int64ul, # 0
        Ver("G == G14 && V < V13_0B4", "unk_8c_g14" / Int64ul),
        "restart_branch_offset" / Int32sl,
        "unk_98" / Int32ul, # 1
        Ver("V >= V13_0B4", "unk_9c" / HexDump(Bytes(0x10))),
    )

class TilingParameters(ConstructClass):
    subcon = Struct(
        "size1" / Int32ul,
        "unk_4" / Int32ul,
        "unk_8" / Int32ul,
        "x_max" / Dec(Int16ul),
        "y_max" / Dec(Int16ul),
        "tile_count" / Int32ul,
        "x_blocks" / Int32ul,
        "y_blocks" / Int32ul,
        "size2" / Int32ul,
        "size3" / Int32ul,
        "unk_24" / Int32ul,
        "unk_28" / Int32ul,
        "helper_cfg" / Int32ul,
    )

class StartTACmdStruct2(ConstructClass):
    subcon = Struct(
        "unk_0" / Hex(Int64ul),
        "unk_8" / Hex(Int32ul),
        "unk_c" / Hex(Int32ul),
        "tvb_tilemap" / Hex(Int64ul),
        Ver("G < G14", "tvb_cluster_tilemaps" / Hex(Int64ul)),
        "tpc" / Hex(Int64ul),
        "tvb_heapmeta_addr" / Hex(Int64ul), # like Start3DStruct2.tvb_end_addr with bit 63 set?
        "iogpu_unk_54" / Int32ul,
        "iogpu_unk_55" / Int32ul,
        "iogpu_unk_56" / Int64ul,
        Ver("G < G14", "tvb_cluster_meta1" / Int64ul),
        "unk_48" / Int64ul,
        "unk_50" / Int64ul,
        "tvb_heapmeta_addr2" / Int64ul,
        Ver("G < G14", "unk_60" / Int64ul),
        Ver("G < G14", "core_mask" / Int64ul),
        "iogpu_deflake_1" / Int64ul,
        "iogpu_deflake_2" / Int64ul,
        "unk_80" / Int64ul,
        "iogpu_deflake_3" / Int64ul, # bit 50 set
        "encoder_addr" / Int64ul,
        Ver("G < G14", "tvb_cluster_meta2" / Int64ul),
        Ver("G < G14", "tvb_cluster_meta3" / Int64ul),
        Ver("G < G14", "tiling_control" / Int64ul),
        "unk_b0" / Array(6, Hex(Int64ul)),
        "pipeline_base" / Int64ul,
        Ver("G < G14", "tvb_cluster_meta4" / Int64ul),
        Ver("G < G14", "unk_f0" / Int64ul),
        "unk_f8" / Int64ul,
        "helper_program" / Int32ul, # bit 0: enable
        "unk_104" / Int32ul, # 0
        "helper_arg" / Int64ul, # stack layout
        "unk_110" / Hex(Int64ul),
        "unk_118" / Int32ul,
        Ver("G >= G14", ZPadding(8 * 9)),
    )

class StartTACmdStruct3(ConstructClass):
    subcon = Struct(
        "unk_480" / Array(6, Int32ul),
        "unk_498" / Int64ul,
        "unk_4a0" / Int32ul,
        "iogpu_deflake_1" / Int64ul,
        "unk_4ac" / Int32ul,
        "unk_4b0" / Int64ul,
        "unk_4b8" / Int32ul,
        "unk_4bc" / Int64ul,
        "unk_4c4_padding" / HexDump(Bytes(0x48)),
        "unk_50c" / Int32ul,
        "unk_510" / Int64ul,
        "unk_518" / Int64ul,
        "unk_520" / Int64ul,
        "unk_528" / Int32ul,
        "unk_52c" / Int32ul,
        "unk_530" / Int32ul,
        "encoder_id" / Int32ul,
        "unk_538" / Int32ul,
        "unk_53c" / Int32ul,
        "sampler_array" / Int64ul,
        "sampler_count" / Int32ul,
        "sampler_max" / Int32ul,
        "unk_550" / Array(6, Int32ul),
        "stamp1_addr" / WrappedPointer, # same contents as below
        "stamp1" / ROPointer(this.stamp1_addr.value, StampCounter),
        "stamp2_addr" / WrappedPointer, # same as FinalizeComputeCmd.stamp - some kind of fence/token
        "stamp2" / ROPointer(this.stamp2_addr.value, StampCounter),
        "stamp_value" / Int32ul,
        "ev_ta" / Int32ul,
        "evctl_index" / Int32ul, # 0-3
        "unk_584" / Int32ul,
        "uuid2" / Int32ul,
        "queue_cmd_count" / Int32ul,
        "unk_590" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.stamp1_addr = StampCounter()
        self.stamp2_addr = StampCounter()

class StartTACmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x22, Int32ul),
        "tiling_params_addr" / Int64ul,
        "struct2_addr" / Int64ul,
        Ver("G >= G14X", "registers_addr" / Int64ul),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "stats_ptr" / Int64ul,
        "cmdqueue_ptr" / Int64ul,
        "context_id" / Int32ul,
        "unk_38" / Int32ul,
        "submission_id" / Int32ul,
        "buffer_mgr_slot" / Int64ul,
        "unk_48" / Int64ul,
        "unk_50" / Int32ul,
        "struct3_addr" / Int64ul,
        "unkptr_5c" / Int64ul,
        "unk_5c" / ROPointer(this.unkptr_5c, HexDump(Bytes(0x18))),
        "unk_64" / Int32ul,
        "unk_68" / Int32ul,
        "uuid" / Int32ul,
        "unk_70" / Int32ul,
        "unk_74" / Array(29, Int64ul),
        "unk_15c" / Int32ul,
        "unk_160" / Int64ul,
        "unk_168" / Int32ul,
        "unk_16c" / Int32ul,
        "unk_170" / Int64ul,
        Ver("V >= V13_0B4", "counter" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_180" / Int64ul),
        "unk_178" / Int32ul,
    )

class FinalizeTACmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x23, Int32ul),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "stats_ptr" / Int64ul,
        "cmdqueue_ptr" / Int64ul, #
        "context_id" / Int32ul,
        "unk_28" / Int32ul,
        "struct3_addr" / Int64ul,
        "unk_34" / Int32ul,
        "uuid" / Int32ul,
        "stamp_addr" / Int64ul,
        "stamp" / ROPointer(this.stamp_addr, StampCounter),
        "stamp_value" / Int32ul,
        "unk_48" / Int64ul,
        "unk_50" / Int32ul,
        "unk_54" / Int32ul,
        "unk_58" / Int64ul,
        "unk_60" / Int32ul,
        "unk_64" / Int32ul,
        "unk_68" / Int32ul,
        Ver("G == G14 && V < V13_0B4", "unk_6c_g14" / Int64ul),
        "restart_branch_offset" / Int32sl,
        "unk_70" / Int32ul,
        Ver("V >= V13_0B4", "unk_74" / HexDump(Bytes(0x10))),
    )

class ComputeArgs(ConstructClass):
    subcon = Struct(
        unk = Bytes(0x7fa0),
        arg_buffers = Array(8, Int64ul),
        threadgroups_per_grid_addr = Int64ul,
        threads_per_threadgroup_addr = Int64ul,
    )

class JobMeta(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "stamp_addr" / WrappedPointer, # same contents as below
        "stamp" / ROPointer(this.stamp_addr.value, StampCounter),
        "fw_stamp_addr" / WrappedPointer, # same as FinalizeComputeCmd.stamp - some kind of fence/token
        "stamp" / ROPointer(this.fw_stamp_addr.value, StampCounter),
        "stamp_value" / Int32ul,
        "stamp_slot" / Int32ul,
        "evctl_index" / Int32ul,
        "unk_20" / Int32ul,
        "uuid" / Int32ul,
        "queue_cmd_count" / Int32ul,
    )

class EncoderParams(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "unk_4" / Int32ul,
        "unk_8" / Int32ul,
        "encoder_id" / Int32ul,
        "unk_10" / Int32ul,
        "iogpu_compute_unk44" / Int32ul,
        "seq_buffer" / Int64ul,
        "unk_1c" / Int64ul,
    )

class SubBufferList(ConstructClass):
    subcon = Struct(
        # Least significant byte encoding
        # 7654 3210
        # ==== ====
        # 0000 0000 - invalid
        # aaaa aa01 - Block size 0x400 or continuation
        # aaaa 0011 - Block size 0x1000
        # aa00 0111 - Block size 0x4000
        # 0000 1111 - Block size 0x10000
        # 0001 1111 - Block size 0x40000
        # 0011 1111 - Block size 0x100000? (not seen)
        # 0111 1111 - Block size 0x400000
        "buffers" / Array(256 + 12, Array(4, Int32ul))
    )

class HelperArg(ConstructClass):
    subcon = Struct(
        "core_stride" / Int32ul,
        "alloc_size_map" / Array(16, Int16ul),
        "max_subgroups" / Array(16, Int16ul),
        "core_list" / Array(128, Int16ul),
    )

class ComputeInfo(ConstructClass):
    # Only the cmdlist and pipelinebase and cmdlist fields are strictly needed to launch a basic
    # compute shader.
    subcon = Struct( # 0x1c bytes
        "iogpu_deflake_1" / Int64ul, # ComputeArgs
        "encoder" / Int64ul, # CommandList from userspace
        "iogpu_deflake_2" / Int64ul, # size 8, null
        "iogpu_deflake_3" / Int64ul, # size 8, null
        "iogpu_deflake_4" / Int64ul, # size 8, null
        "iogpu_deflake_5" / Int64ul, # size 8, null
        "pipeline_base" / Int64ul, # 0x11_00000000: Used for certain "short" pointers like pipelines (and shaders?)
        "unk_38" / Int64ul, # always 0x8c60
        "helper_program" / Int32ul, # 0x98000; bit 0: enable
        "unk_44" / Int32ul, # 0
        "helper_arg" / Int64ul, # work layout
        "helper_cfg" / Int32ul, # 0x40 - Size? only if work layout is provided
        "unk_54" / Int32ul, # 0
        "unk_58" / Int32ul, # 1
        "unk_5c" / Int32ul, # 0
        "iogpu_unk_40" / Int32ul, # 0x1c
        "unk_pad" / ZPadding(0xec),
    )

# Related to "IOGPU Misc"
class ComputeInfo2(ConstructClass):
    subcon = Struct(
        Ver("V >= V13_0B4", "unk_0_0" / ZPadding(4)),
        "unk_0" / HexDump(Bytes(0x24)),
        "iogpu_deflake_1" / Int64ul,
        "encoder_end" / Int64ul,
        "unk_34" / HexDump(Bytes(0x20)),
        "unk_g14x" / Int32ul,
        "unk_58" / Int32ul,
        Ver("V < V13_0B4", "unk_5c" / ZPadding(4)),
    )

class StartComputeCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x29, Int32ul),
        "unk_buf_addr" / Int64ul, # Pointer to WorkCommandCP.unk_buf
        "computeinfo_addr" / Int64ul,
        Ver("G >= G14X", "registers_addr" / Int64ul),
        "stats_ptr" / Int64ul,
        "cmdqueue_ptr" / Int64ul,
        "context_id" / Int32ul, # 4
        "unk_28" / Int32ul, # 1
        "counter1" / Int32ul,
        "counter2" / Int32ul,
        "unk_34" / Int32ul,
        "unk_38" / Int32ul,
        "computeinfo2_addr" / Int64ul,
        "computeinfo2" / ROPointer(this.computeinfo2_addr, ComputeInfo2),
        "unk_44" / Int32ul,
        "uuid" / Int32ul,
        "attachments" / Array(16, Attachment),
        "num_attachments" / Int32ul,
        "padding" / Bytes(4),
        Ver("V >= V13_0B4", "unk_flag_addr" / Int64ul),
        Ver("V >= V13_0B4", "counter" / Int64ul),
        Ver("V >= V13_0B4", "event_ctrl_buf_addr" / Int64ul),
    )

class FinalizeComputeCmd(ConstructClass):
    subcon = Struct( # 0x64 bytes''''
        "magic" / Const(0x2a, Int32ul),
        "unkptr_4" / Int64ul, # same as ComputeStartCmd.unkptr_14
        "cmdqueue_ptr" / Int64ul, # points back to the submitinfo
        "context_id" / Int32ul,
        Ver("V < V13_0B4", "unk_18" / Int32ul),
        "computeinfo2_addr" / Int64ul, # same as ComputeStartCmd.unkptr_3c
        "unk_24" / Int32ul,
        "uuid" / Int32ul,  # uuid for tracking?
        "stamp" / Int64ul,
        "stamp_value" / Int32ul, # Gets written to unkptr_2c (after stamp?)
        "unk_38" / Int32ul,
        "unk_3c" / Int32ul,
        "unk_40" / Int32ul,
        "unk_44" / Int32ul,
        "unk_48" / Int32ul,
        "unk_4c" / Int32ul,
        "unk_50" / Int32ul,
        "unk_54" / Int32ul,
        "unk_58" / Int32ul,
        Ver("G == G14 && V < V13_0B4", "unk_5c_g14" / Int64ul),
        "restart_branch_offset" / Int32sl, # relative offset from start of Finalize to StartComputeCmd
        "unk_60" / Int32ul,
        Ver("V >= V13_0B4", "unk_64" / HexDump(Bytes(0xd))),
        Ver("V >= V13_0B4", "unkptr_71" / Int64ul),
        Ver("V >= V13_0B4", "pad_79" / ZPadding(7)),
    )

class BlitInfo(ConstructClass):
    subcon = Struct(
        "unk_18" / Int64ul,
        "unk_20" / Int64ul,
        "unk_28" / Int64ul,
        "unk_30" / Int64ul,
        "unk_38" / Int64ul,
        "unk_40" / Int64ul,
        "unk_48" / HexDump(Bytes(0xa0)),
        "unkptr_e8" / Int64ul,
        "unk_f0" / Int64ul,
        "unkptr_f8" / Int64ul,
        "pipeline_base" / Int64ul,
        "unk_108" / Int64ul,
        "unk_110" / HexDump(Bytes(0x248)),
        "unk_358" / Int32ul,
        "unk_35c" / Int32ul,
        "unk_360" / Int32ul,
        "unk_364" / Int32ul,
        "unk_368" / Float32l,
        "unk_36c" / Float32l,
        "unk_370" / Int64ul,
        "unk_378" / Int64ul,
        "unk_380" / Int64ul,
        "unk_388" / Int64ul,
        "unk_390" / HexDump(Bytes(0xa8)),
    )

class BlitInfo2(ConstructClass):
    subcon = Struct(
        "unk_0" / HexDump(Bytes(0x24)),
        "unk_24" / Int64ul,
        "unk_470" / Int64ul,
        "unk_478" / Int32ul,
        "unk_47c" / Int32ul,
        "unk_480" / Int64ul,
        "unk_488" / Int64ul,
    )

class StartBlitCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x26, Int32ul),
        "unkptr_4" / Int64ul,
        "unkptr_c" / Int64ul,
        "registers_addr" / Int64ul,
        Ver("G >= G14X", "unk_1c_0" / Int32ul),
        "unkptr_1c" / Int64ul,
        "unkptr_24" / Int64ul,
        "context_id" / Int32ul,
        "unk_30" / Int32ul,
        "submission_id" / Int32ul,
        "unk_38" / Int32ul,
        "unk_3c" / Int32ul,
        "unk_40" / Int32ul,
        "unkptr_44" / Int64ul,
        "unkptr_4c" / Int64ul,
        "uuid" / Int32ul,
        Ver("G < G14X", "unk_2c" / Int32ul),
        "attachments" / Array(16, Attachment),
        "num_attachments" / Int32ul,
        "unk_160" / Int32ul,
        Ver("V >= V13_0B4", "counter" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_19c" / Int64ul),
    )

class FinalizeBlitCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x27, Int32ul),
        "unkptr_4" / Int64ul,
        "unkptr_c" / Int64ul,
        "context_id" / Int32ul,
        "unk_18" / Int32ul,
        "unkptr_1c" / Int64ul,
        "uuid" / Int32ul,
        Ver("V < V13_3", "unk_28" / Int32ul),
        "stamp_addr" / Int64ul,
        "stamp" / ROPointer(this.stamp_addr, StampCounter),
        "stamp_value" / Int32ul,
        "unk_38" / HexDump(Bytes(0x24)),
        "restart_branch_offset" / Int32sl, # relative
        "unk_60" / Int32ul,
        Ver("V >= V13_0B4", "unk_5d8_0" / Int32ul),
        Ver("V >= V13_0B4", "unk_5d8_4" / Int8ul),
        Ver("V >= V13_0B4", "evctl_buf_addr" / Int64ul),
        Ver("V >= V13_0B4", "unk_5d8_4" / Array(3, Int8ul)),
        Ver("V >= V13_0B4", "unk_0" / Int32ul),
        Ver("V >= V13_0B4", "unkptr_1" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_2" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_3" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_4" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_5" / Int64ul),
        Ver("V >= V13_0B4", "unk_9c" / Int64ul),
        Ver("V >= V13_0B4", "unkptr_6" / Int64ul),
        Ver("V >= V13_0B4", "unk_ac" / HexDump(Bytes(0x30))),
        Ver("V >= V13_0B4", "unk_dc" / Int32ul),
        Ver("V >= V13_0B4", "unk_e0" / HexDump(Bytes(0x14))),
    )

class EndCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x18, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "flags" / Int8ul,
    )

    def __init__(self):
        super().__init__()
        self.unk_1 = 0
        self.unk_2 = 0
        self.flags = 0x40

class TimestampCmd(ConstructClass):
    subcon = Struct( # 0x34 bytes
        "magic" / Const(0x19, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul, # Sometimes 0x80
        # all these pointers point to 0xfa0... addresses. Might be where the timestamp should be writen?
        "ts0_addr" / Int64ul,
        "ts0" / ROPointer(this.ts0_addr, TimeStamp),
        "ts_pointers_addr" / Int64ul,
        "ts_pointers" / ROPointer(this.ts_pointers_addr, TimeStampPointers),
        "unk_addr" / Int64ul,
        "cmdqueue_ptr" / Int64ul,
        "user_ts_pointers_addr" / Int64ul,
        "ts_pointers" / ROPointer(this.user_ts_pointers_addr, TimeStampPointers),
        Ver("V >= V13_0B4", "unk_ts_addr" / Int64ul),
        "uuid" / Int32ul,
        "unk_30" / Int32ul,
    )

class WaitForInterruptCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x01, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
    )

    def __init__(self, unk_1, unk_2, unk_3):
        super().__init__()
        self.unk_1 = unk_1
        self.unk_2 = unk_2
        self.unk_3 = unk_3

class Wait2Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x02, Int32ul),
    )

class NopCmd(ConstructClass):
    # This doesn't exist
    subcon = Struct(
        "magic" / Const(0x00, Int32ul),
    )

    def __str__(self) -> str:
        return "Nop"


class Write32Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x0e, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
        "addr" / Int64ul,
        "val" / Int32ul,
    )

    def __init__(self, addr, val):
        super().__init__()
        self.unk_1 = self.unk_2 = 0
        self.unk_3 = 0x20
        self.addr = addr
        self.val = val

class Store32Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x0e, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
        "addr" / Int64ul,
    )

    def __init__(self, addr):
        super().__init__()
        self.unk_1 = self.unk_2 = self.unk_3 = 0
        self.addr = addr

class Store64Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x0f, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
        "addr" / Int64ul,
    )

    def __init__(self, addr):
        super().__init__()
        self.unk_1 = self.unk_2 = self.unk_3 = 0
        self.addr = addr

class Write64Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x0f, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
        "addr" / Int64ul,
        "val" / Int64ul,
    )

    def __init__(self, addr, val):
        super().__init__()
        self.unk_1 = self.unk_2 = 0
        self.unk_3 = 0x20
        self.addr = addr
        self.val = val

class Read32Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x10, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
        "addr" / Int64ul,
    )

    def __init__(self, addr):
        super().__init__()
        self.unk_1 = self.unk_2 = self.unk_3 = 0
        self.addr = addr

class Read64Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x11, Int8ul),
        "unk_1" / Int8ul,
        "unk_2" / Int8ul,
        "unk_3" / Int8ul,
        "addr" / Int64ul,
    )

    def __init__(self, addr):
        super().__init__()
        self.unk_1 = self.unk_2 = self.unk_3 = 0
        self.addr = addr

class ALUCmd(ConstructClass):
    AND = 0
    OR = 1
    XOR = 2
    LSR = 3
    LSL = 4

    subcon = Struct(
        "magic" / Const(0x16, Int8ul),
        "v1" / Int8ul,
        "op" / Int16ul,
        "arg" / Int64ul,
    )

    def __init__(self, op, arg):
        super().__init__()
        self.v1 = 0
        self.op = (op << 3) | (2 << 11)
        self.arg = arg

class Add16Cmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x17, Int8ul),
        "arg1" / Int16ul,
        "arg2" / Int8ul,
    )

    def __init__(self, arg):
        super().__init__()
        self.arg1 = (arg << 3) & 0xffff
        self.arg2 = arg >> 13

class CompleteCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x2b, Int8ul),
        ZPadding(3),
        "unk" / Int64ul,
        "stamp_addr" / Int64ul,
        "stamp_val" / Int32ul,
        "pad" / ZPadding(0x14),
    )

    def __init__(self):
        super().__init__()
        self.unk = 0

class AbortCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x2c, Int8ul),
        ZPadding(3),
        "bits" / Int32ul,
        "unk1" / Int32ul,
        "unk2" / Int64ul,
        "unk3" / Int64ul,
        "stamp_addr" / Int64ul,
        "stamp_val" / Int32ul,
        "pad" / ZPadding(0x14),
    )

    def __init__(self):
        super().__init__()
        self.bits = 0
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0

class DoorbellCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x03, Int8ul),
        "pad" / Int8ul,
        "arg" / Int16ul,
    )

    def __init__(self, flags):
        super().__init__()
        self.pad = 0
        self.arg = flags << 10

class ProfileCaptureCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x1f, Int8ul),
        "arg0" / Int8ul,
        "arg1" / Int8ul,
        "arg2" / Int8ul,
        "encoder_id" / Int32ul,
        "uuid" / Int32ul,
        "workitem_ptr" / Int64ul,
    )

    def __init__(self, flags):
        super().__init__()

class MicroSequence(ConstructValueClass):
    subcon = RepeatUntil(lambda obj, lst, ctx: lst[-1].op & 0x3f in (0x18, 0x2b, 0x2c),
                         Struct(
            "op" / Peek(Int32ul),
            #Probe(lookahead=32),
            "cmd" / Switch(this.op & 0x3f, {
                0x01: WaitForInterruptCmd,
                0x02: Wait2Cmd,
                0x03: DoorbellCmd,
                #0x04: write sgx u8
                #0x05: write sgx u32
                #0x06: write sgx u64
                #0x07: AGFSKUCommandTypeRegWriteStream not supported
                #0x08: read sgx u8
                #0x09: read sgx u32
                #0x0a: read sgx u64
                #0x0b: wait sgx reg u32
                #0x0c: wait sgx reg u64
                #0x0d: AGFSKUCommandTypeJump not supported
                0x0e:  Switch(this.op >> 28, {
                    0: Store32Cmd,
                    2: Write32Cmd,
                }),
                0x0f:  Switch(this.op >> 28, {
                    0: Store64Cmd,
                    2: Write64Cmd,
                }),
                0x10: Read32Cmd,
                0x11: Read64Cmd,
                0x16: ALUCmd,
                0x17: Add16Cmd,
                0x18: EndCmd,
                0x19: TimestampCmd,
                0x1f: ProfileCaptureCmd,
                #0x1a: KTraceCmd,
                0x22: StartTACmd,
                0x23: FinalizeTACmd,
                0x24: Start3DCmd,
                0x25: Finalize3DCmd,
                0x26: StartBlitCmd,
                0x27: FinalizeBlitCmd,
                0x29: StartComputeCmd,
                0x2a: FinalizeComputeCmd,
                0x2b: CompleteCmd,
                0x2c: AbortCmd,
            }, default=Error)
        )
    )

    def __str__(self):
        s = "{\n"
        for cmd in self.value:
            s += str(cmd.cmd) + '\n'
            if isinstance(cmd.cmd, (EndCmd, CompleteCmd)):
                s += "}\n"
                break
        else:
            s += "?\n"
        return s

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
