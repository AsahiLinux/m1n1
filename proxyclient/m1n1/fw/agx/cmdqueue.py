# SPDX-License-Identifier: MIT
from m1n1.constructutils import *
from construct import *
from .microsequence import *
from ...utils import RegMap, Register32

__all__ = []

class WorkCommandBarrier(ConstructClass):
    """
        sent before WorkCommand3D on the Submit3d queue.
        Might be for initializing the tile buckets?

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x4, Int32ul),
        "stamp_addr" / Int64ul,
        "stamp" / ROPointer(this.stamp_addr, StampCounter),
        "wait_value" / Int32ul,
        "event" / Int32ul, # Event number that signals a stamp check
        "stamp_self" / Int32ul,
        "uuid" / Int32ul,
        "unk" / Default(Int32ul, 0),
        Ver("G >= G14X", "pad" / ZPadding(0x20)),
    )

class WorkCommandInitBM(ConstructClass):
    """
        occasionally sent before WorkCommandTA on the SubmitTA queue.

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x6, Hex(Int32ul)),
        "context_id" / Hex(Int32ul), # Might be context?
        "buffer_mgr_slot" / Hex(Int32ul), # 0
        "unk_c" / Hex(Int32ul), # 0
        "unk_10" / Hex(Int32ul), # 0x30
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "stamp_value" / Hex(Int32ul),  # 0x100
    )

class WorkCommandComputeUnk10(ConstructClass):
    """
        occassionally sent before WorkCommandCP on the SubmitCP queue.
    """
    subcon = Struct(
        "magic" / Const(0xa, Hex(Int32ul)),
        "unk" / Hex(Int32ul),
    )

class WorkCommandComputeUnk11(ConstructClass):
    """
        occassionally sent before WorkCommandCP on the SubmitCP queue.
    """
    subcon = Struct(
        "magic" / Const(0xb, Hex(Int32ul)),
        "unk" / Hex(Int32ul),
    )

class Flag(ConstructValueClass):
    subcon = Hex(Int32ul)

    def __init__(self):
        self.value = 0

class LinkedListHead(ConstructClass):
    subcon = Struct(
        "prev" / Int64ul,
        "next" / Int64ul,
    )

    def __init__(self):
        super().__init__()
        self.prev = 0
        self.next = 0

class EventControlUnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x8))

    def __init__(self):
        super().__init__()
        self.value = b"\xff" * 8

class EventControl(ConstructClass):
    subcon = Struct(
        "event_count_addr" / Int64ul,
        "event_count" / ROPointer(this.event_count_addr, Int32ul),
        "submission_id" / Int32ul,
        "cur_count" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int64ul,
        "unk_20" / Int32ul,
        "vm_slot" / Int32ul,
        "has_ta" / Int32ul,
        "pstamp_ta" / Array(4, Int64ul),
        "has_3d" / Int32ul,
        "pstamp_3d" / Array(4, Int64ul),
        "has_cp" / Int32ul,
        "pstamp_cp" / Array(4, Int64ul),
        "in_list" / Int32ul,
        Ver("G >= G14 && V < V13_0B4", "unk_98_g14_0" / HexDump(Bytes(0x14))),
        "list_head" / LinkedListHead,
        Ver("G >= G14 && V < V13_0B4", "unk_a8_g14_0" / ZPadding(4)),
        Ver("V >= V13_0B4", "unk_buf" / EventControlUnkBuf),
    )

    def __init__(self):
        super().__init__()
        self.unk_14 = 0
        self.unk_18 = 0
        self.unk_20 = 0
        self.vm_slot = 0
        self.has_ta = 0
        self.pstamp_ta = [0]*4
        self.has_3d = 0
        self.pstamp_3d = [0]*4
        self.has_cp = 0
        self.pstamp_cp = [0]*4
        self.in_list = 0
        self.unk_98_g14_0 = bytes(0x14)
        self.list_head = LinkedListHead()
        self.unk_buf = EventControlUnkBuf()

class WorkCommandCP(ConstructClass):
    """
    For compute

    Example:
    00000000  00000003 00000000 00000004 0c3d80c0 ffffffa0 00000000 00000000 00000000
    00000020  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000040  *
    00000060  00000000 00000000 00088000 00000015 00078000 00000015 000a6300 00000015
    00000080  000a6308 00000015 000a6310 00000015 000a6318 00000015 00000000 00000011
    000000a0  00008c60 00000000 00000041 00000000 000e8000 00000015 00000040 00000000
    000000c0  00000001 00000000 0000001c 00000000 00000000 00000000 00000000 00000000
    000000e0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000100  *
    000001e0  00000000 00000000 0c311cc0 ffffffa0 00000240 00000000 00000000 00000000
    00000200  00000000 00000000 00000000 00000000 00000000 00000000 00088000 00000015
    00000220  00078024 00000015 00000000 00000000 00000000 00000000 00000000 00000000
    00000240  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000260  110022b3 00000000 ffffffff 00000500 00000015 00000000 00000000 00000000
    00000280  000c8014 ffffffa0 0c378014 ffffffa0 00003b00 00000005 00000000 00000000
    000002a0  120022b8 00000000 00000000 00000000 00029030 ffffffa0 00029038 ffffffa0
    000002c0  00000000 00000000 00000000 00000000 00000015 00000000 00000000 00000000
    000002e0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """

    subcon = Struct(
        "addr" / Tell,
        "magic" / Const(0x3, Hex(Int32ul)),
        Ver("V >= V13_0B4", "counter" / Int64ul),
        "unk_4" / Hex(Int32ul),
        "context_id" / Hex(Int32ul),
        "event_control_addr" / Hex(Int64ul),
        "event_control" / ROPointer(this.event_control_addr, EventControl),
        "unk_2c" / Int32ul,
        Ver("G >= G14X", "registers" / Array(128, RegisterDefinition)),
        Ver("G >= G14X", "unk_g14x" / Default(Array(64, Int32ul), [0]*64)),
        Ver("G < G14X", "unk_buf" / HexDump(Bytes(0x50))),
        Ver("G < G14X", "compute_info" / ComputeInfo),
        "registers_addr" / Int64ul,
        "register_count" / Int16ul,
        "registers_length" / Int16ul,
        "unk_pad" / HexDump(Bytes(0x24)),
        "microsequence_ptr" / Hex(Int64ul),
        "microsequence_size" / Hex(Int32ul),
        "microsequence" / ROPointer(this.microsequence_ptr, MicroSequence),
        "compute_info2" / ComputeInfo2,
        "encoder_params" / EncoderParams,
        "job_meta" / JobMeta,
        "ts1" / TimeStamp,
        "ts_pointers" / TimeStampPointers,
        "user_ts_pointers" / TimeStampPointers, # This is a guess, but it makes sense
        "client_sequence" / Int8ul,
        Ver("V >= V13_0B4", "unk_ts2" / TimeStamp),
        Ver("V >= V13_0B4", "unk_ts" / TimeStamp),
        Ver("V >= V13_0B4", "unk_2e1" / Default(HexDump(Bytes(0x1c)), bytes(0x1c))),
        Ver("V >= V13_0B4", "unk_flag" / Flag),
        Ver("V >= V13_0B4", "unk_pad" / Default(HexDump(Bytes(0x10)), bytes(0x10))),
        "pad_2d9" / Default(HexDump(Bytes(0x7)), bytes(0x7)),
    )

class WorkCommand0_UnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x18))

    def __init__(self):
        self.value = bytes(0x18)

class WorkCommand1_UnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x110))

    def __init__(self):
        self.value = bytes(0x110)

class WorkCommand1_UnkBuf2(ConstructClass):
    subcon = Struct(
        "unk_0" / Int64ul,
        "unk_8" / Int64ul,
        "unk_10" / Int64ul,
    )

class WorkCommand3D(ConstructClass):
    """
    For 3D

    Example: 0xfa00c095640
    00000000  00000001 00000004 00000000 0c2d5f00 ffffffa0 000002c0 0c3d80c0 ffffffa0
    00000020  0c3e0000 ffffffa0 0c3e0100 ffffffa0 0c3e09c0 ffffffa0 01cb0000 00000015
    00000040  00000088 00000000 00000001 0010000c 00000000 00000000 00000000 00000000
    00000060  3a8de3be 3abd2fa8 00000000 00000000 0000076c 00000000 0000a000 00000000
    00000080  ffff8002 00000000 00028044 00000000 00000088 00000000 005d0000 00000015
    000000a0  00758000 00000015 0000c000 00000000 00000640 000004b0 0257863f 00000000
    000000c0  00000000 00000000 00000154 00000000 011d0000 00000015 011d0000 00000015
    000000e0  0195c000 00000015 0195c000 00000015 00000000 00000000 00000000 00000000
    00000100  00000000 00000000 00000000 00000000 0193c000 00000015 00000000 00000000
    00000120  0193c000 00000015 00000000 00000000 01b64000 00000015 00000000 00000000
    00000140  01b64000 00000015 00000000 00000000 01cb0000 00000015 01cb4000 00000015
    00000160  c0000000 00000003 01cb4000 00000015 00010280 00000000 00a38000 00000015
    00000180  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    000001a0  00000000 00000000 00000000 00000000 00000000 00000011 00008c60 00000000
    000001c0  00000000 00000000 00000000 00000000 0000001c 00000000 00000000 00000000
    000001e0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000200  *
    000003c0  00000012 00028084 00000000 00000000 3a8de3be 3abd2fa8 00000000 00000000
    000003e0  0010000c 00000000 00025031 00000004 3f800000 00000700 00000000 00000001
    """

    subcon = Struct(
        "addr" / Tell,
        "magic" / Const(0x1, Hex(Int32ul)),
        Ver("V >= V13_0B4", "counter" / Int64ul),
        "context_id" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "microsequence_ptr" / Hex(Int64ul), # Command list
        "microsequence_size" / Hex(Int32ul),
        "microsequence" / ROPointer(this.microsequence_ptr, MicroSequence),
        "event_control_addr" / Hex(Int64ul),
        "event_control" / ROPointer(this.event_control_addr, EventControl),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "unk_emptybuf_addr" / Hex(Int64ul),
        "tvb_tilemap" / Hex(Int64ul),
        "unk_40" / Hex(Int64ul),
        "unk_48" / Hex(Int32ul),
        "tile_blocks_y" / Hex(Int16ul), # * 4
        "tile_blocks_x" / Hex(Int16ul), # * 4
        "unk_50" / Hex(Int64ul),
        "unk_58" / Hex(Int64ul),
        "merge_upper_x" / Hex(Float32l),
        "merge_upper_y" / Hex(Float32l),
        "unk_68" / Hex(Int64ul),
        "tile_count" / Hex(Int64ul),
        # Embedded structures that are also pointed to by other stuff
        Ver("G < G14X", "struct_2" / Start3DStruct2),
        Ver("G < G14X", "struct_1" / Start3DStruct1),
        Ver("G >= G14X", "registers" / Array(128, RegisterDefinition)),
        Ver("G >= G14X", "unk_g14x" / Default(Array(64, Int32ul), [0]*64)),
        "struct_3" / Start3DStruct3,
        "unk_758" / Flag,
        "unk_75c" / Flag,
        "unk_buf" / WorkCommand1_UnkBuf,
        "busy_flag" / Flag,
        "struct_6" / Start3DStruct6,
        "struct_7" / Start3DStruct7,
        "unk_buf2" / WorkCommand1_UnkBuf2,
        "ts1" / TimeStamp,
        "ts_pointers" / TimeStampPointers,
        "user_ts_pointers" / TimeStampPointers, # This is a guess, but it makes sense
        "client_sequence" / Int8ul,
        Ver("V >= V13_0B4", "unk_ts2" / TimeStamp),
        Ver("V >= V13_0B4", "unk_ts" / TimeStamp),
        Ver("V >= V13_0B4", "unk_pad3" / Default(HexDump(Bytes(0x20)), bytes(0x20))),
        "pad_925" / Default(HexDump(Bytes(0x3)), bytes(0x3)),
        Ver("V == V13_3", "unk_pad2" / Default(HexDump(Bytes(0x3c)), bytes(0x3c))),
    )

class WorkCommand0_UnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x18))

    def __init__(self):
        super().__init__()
        self.value = bytes(0x18)

class WorkCommandTA(ConstructClass):
    """
    For TA

    Example:
    00000000  00000000 00000004 00000000 0c3d80c0 ffffffa0 00000002 00000000 0c3e0000
    00000020  ffffffa0 0c3e0100 ffffffa0 0c3e09c0 ffffffa0 00000000 00000200 00000000
    00000040  1e3ce508 1e3ce508 01cb0000 00000015 00000000 00000000 00970000 00000015
    00000060  01cb4000 80000015 006b0003 003a0012 00000001 00000000 00000000 00000000
    00000080  0000a000 00000000 00000088 00000000 01cb4000 00000015 00000000 00000000
    000000a0  0000ff00 00000000 007297a0 00000015 00728120 00000015 00000001 00000000
    000000c0  00728000 00040015 009f8000 00000015 00000000 00000000 00000000 00000000
    000000e0  0000a441 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000100  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000011
    00000120  00000000 00000000 0000001c 00000000 00008c60 00000000 00000000 00000000
    00000140  00000000 00000000 00000000 00000000 0000001c 00000000 00000000 00000000
    00000160  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000180  *
    000003a0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 000000f0
    000003c0  00000088 00000202 04af063f 00025031 00404030 00303024 000000c0 00000180
    000003e0  00000100 00008000 00000000 00000000 00000000 00000000 00000000 00000000
    """

    subcon = Struct(
        "addr" / Tell,
        "magic" / Const(0x0, Hex(Int32ul)),
        Ver("V >= V13_0B4", "counter" / Int64ul),
        "context_id" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "event_control_addr" / Hex(Int64ul),
        "event_control" / ROPointer(this.event_control_addr, EventControl),
        "buffer_mgr_slot" / Hex(Int64ul),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "unk_emptybuf_addr" / Hex(Int64ul),
        "unk_34" / Hex(Int32ul),

        # Embedded structures that are also pointed to by other stuff
        Ver("G >= G14X", "registers" / Array(128, RegisterDefinition)),
        Ver("G >= G14X", "unk_154" / Default(HexDump(Bytes(0x100)), bytes(0x100))), # unknown
        Ver("G < G14X", "struct_2" / StartTACmdStruct2), # 0x11c bytes
        Ver("G < G14X", "unk_154" / Default(HexDump(Bytes(0x268)), bytes(0x268))), # unknown
        Ver("G < G14X", "tiling_params" / TilingParameters), # unknown
        Ver("G < G14X", "unk_3e8" / HexDump(Bytes(0x60))), # unknown
        "registers_addr" / Int64ul,
        "register_count" / Int16ul,
        "registers_length" / Int16ul,
        "unk_pad" / Int32ul,
        "unkptr_45c" / Int64ul,
        "tvb_size" / Int64ul,
        "microsequence_ptr" / Hex(Int64ul),
        "microsequence_size" / Hex(Int32ul),
        "microsequence" / ROPointer(this.microsequence_ptr, MicroSequence),
        "ev_3d" / Int32ul,
        "stamp_value" / Int32ul,

        "struct_3" / StartTACmdStruct3, # 0x114 bytes

        "unk_594" / WorkCommand0_UnkBuf,

        "ts1" / TimeStamp,
        "ts_pointers" / TimeStampPointers,
        "user_ts_pointers" / TimeStampPointers, # This is a guess, but it makes sense

        "client_sequence" / Int8ul,
        Ver("V >= V13_0B4", "unk_ts2" / TimeStamp),
        Ver("V >= V13_0B4", "unk_ts" / TimeStamp),
        Ver("V >= V13_0B4", "unk_5d8_15" / Default(HexDump(Bytes(0x18)), bytes(0x18))),
        "pad_5d5" / Default(HexDump(Bytes(0x3)), bytes(0x3)),
        "pad_5d8" / Default(HexDump(Bytes(0x8)), bytes(0x8)),
        Ver("V >= V13_3", "unk_pad2" / Default(HexDump(Bytes(0xc)), bytes(0xc))),
    )

class WorkCommandBlit(ConstructClass):
    subcon = Struct(
        "addr" / Tell,
        "magic" / Const(0x2, Int32ul),
        Ver("V >= V13_0B4", "counter" / Int64ul),
        "context_id" / Int32ul,
        "event_control_addr" / Hex(Int64ul),
        "event_control" / ROPointer(this.event_control_addr, EventControl),
        "unk_10" / Hex(Int32ul),
        "unk_14" / Int32ul,
        Ver("G < G14X", "blit_info" / BlitInfo),
        Ver("G >= G14X", "registers" / Array(128, RegisterDefinition)),
        Ver("G >= G14X", "unk_g14x" / Default(Array(64, Int32ul), [0]*64)),
        "registers_addr" / Int64ul,
        "register_count" / Int16ul,
        "registers_length" / Int16ul,
        "blit_info2" / BlitInfo2,
        "microsequence_ptr" / Hex(Int64ul),
        "microsequence_size" / Hex(Int32ul),
        "microsequence" / ROPointer(this.microsequence_ptr, MicroSequence),
        "unkptr_49c" / HexDump(Bytes(0x114)),
        "job_meta" / JobMeta,
        "unk_5d8" / Int32ul,
        "unk_stamp_ptr" / Int64ul,
        "unk_stamp_val" / Int32ul,
        "unk_5ec" / Int32ul,
        "encoder_params" / EncoderParams,
        "unk_618" / Int32ul,
        "ts1" / TimeStamp,
        "ts_pointers" / TimeStampPointers,
        "user_ts_pointers" / TimeStampPointers,
        "client_sequence" / Int8ul,
        "pad_645" / Default(HexDump(Bytes(0x3)), bytes(0x3)),
        "unk_648" / Int32ul,
        "unk_64c" / Int8ul,
        "pad_64d" / Default(HexDump(Bytes(0x7)), bytes(0x7)),
    )

class UnknownWorkCommand(ConstructClass):
    subcon = Struct(
        "magic" / Hex(Int32ul),
        "unk_4" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "unk_c" / Hex(Int32ul),
        "unk_10" / Hex(Int32ul),
        "unk_14" / Hex(Int32ul),
        "unk_18" / Hex(Int32ul),
        "unk_1c" / Hex(Int32ul),
    )

class CmdBufWork(ConstructClass):
    subcon = Struct(
        "cmdid" / Peek(Int32ul),
        "cmd" / Switch(this.cmdid, {
            0: WorkCommandTA,
            1: WorkCommand3D,
            2: WorkCommandBlit,
            3: WorkCommandCP,
            4: WorkCommandBarrier,
            6: WorkCommandInitBM,
            10: WorkCommandComputeUnk10,
            11: WorkCommandComputeUnk11,
        })
    )

class JobList(ConstructClass):
    subcon = Struct(
        "first_job" / Default(Int64ul, 0),
        "last_head" / Int64ul,
        "unkptr_10" / Default(Int64ul, 0),
    )

class GPUContextData(ConstructClass):
    subcon = Struct(
        "queue_table_index" / Int8ul,
        "pid_table_index" / Int8ul,
        "unk_2" / Default(Bytes(3), bytes(3)),
        "unk_5" / Int8ul,
        "unk_6" / Int32ul,
        "unk_a" / Int32ul,
        "unk_e" / Int32ul,
        "unk_12" / Int32ul,
        "unk_16" / Int32ul,
        "unk_1a" / Int32ul,
        "unk_1e" / Int8ul,
        "unk_1f" / Int8ul,
        "unk_20" / Default(Bytes(3), bytes(3)),
        "unk_23" / Int8ul,
        "unk_24" / Default(Bytes(0x1c), bytes(0x1c)),
    )

    def __init__(self):
        self.queue_table_index = 0xff
        self.pid_table_index = 0xff
        self.unk_5 = 1
        self.unk_6 = 0
        self.unk_a = 0
        self.unk_e = 0
        self.unk_12 = 0
        self.unk_16 = 0
        self.unk_1a = 0
        self.unk_1e = 0xff
        self.unk_1f = 0
        self.unk_23 = 2

class CommandQueuePointerMap(RegMap):
    GPU_DONEPTR = 0x00, Register32
    GPU_RPTR = 0x30, Register32
    CPU_WPTR = 0x40, Register32

class CommandQueuePointers(ConstructClass):
    subcon = Struct(
        "gpu_doneptr" / Int32ul,
        ZPadding(12),
        "unk_10" / Int32ul,
        ZPadding(12),
        "unk_20" / Int32ul,
        ZPadding(12),
        "gpu_rptr" / Int32ul,
        ZPadding(12),
        "cpu_wptr" / Int32ul,
        ZPadding(12),
        "rb_size" / Int32ul,
        ZPadding(12),
    )

    def __init__(self):
        super().__init__()
        self.gpu_doneptr = 0
        self.unk_10 = 0
        self.unk_20 = 0
        self.gpu_rptr = 0
        self.cpu_wptr = 0
        self.rb_size = 0x500

class CommandQueueInfo(ConstructClass):
    """ Structure type shared by Submit3D, SubmitTA and SubmitCompute
        Applications have multiple of these, one of each submit type
        TODO: Can applications have more than one of each type? One per encoder?
        Mostly managed by GPU, only initialize by CPU

    """
    subcon = Struct(
        "pointers_addr" / Hex(Int64ul),
        "pointers" / ROPointer(this.pointers_addr, CommandQueuePointers),
        "rb_addr" / Hex(Int64ul), # 0x4ff pointers
        "job_list_addr" / Hex(Int64ul), # ffffffa000000000, size 0x18 (shared by 3D and TA)
        "job_list" / ROPointer(this.job_list_addr, JobList),
        "gpu_buf_addr" / Hex(Int64ul), # GPU space for this queue, 0x2c18 bytes?
        #"gpu_buf" / ROPointer(this.gpu_buf_addr, HexDump(Bytes(0x2c18))),
        "gpu_rptr1" / Hex(Int32ul),
        "gpu_rptr2" / Hex(Int32ul),
        "gpu_rptr3" / Hex(Int32ul),
        "event_id" / Int32sl,
        "priority" / Hex(Int32ul), # read by CPU
        "unk_34" / Hex(Int32ul),
        "unk_38" / Hex(Int64ul),
        "unk_40" / Hex(Int32ul), # 1
        "unk_44" / Hex(Int32ul), # 0
        "prio5" / Hex(Int32ul), # 1, 2
        "unk_4c" / Int32sl, # -1
        "uuid" / Hex(Int32ul), # Counts up for each new process or command queue
        "unk_54" / Int32sl,
        "unk_58" / Hex(Int64ul), # 0
        "busy" / Hex(Int32ul), # 1 = gpu busy
        "pad1" / ZPadding(0x1c),
        "unk_80" / Hex(Int32ul),
        "has_commands" / Hex(Int32ul),
        "unk_88" / Int32ul,
        "unk_8c" / Int32ul,
        "unk_90" / Int32ul,
        "unk_94" / Int32ul,
        "inflight_commands" / Int32ul,
        "unk_9c" / Int32ul,
        Ver("V >= V13_2 && G < G14X", "unk_a0_0" / Int32ul),
        "gpu_context_addr" / Hex(Int64ul), # GPU managed context, shared between 3D and TA. Passed to DC_DestroyContext
        "gpu_context" / ROPointer(this.gpu_context_addr, GPUContextData),
        "unk_a8" / Int64ul,
        Ver("V >= V13_2 && G < G14X", "unk_b0" / Int32ul),
        # End of struct
    )

    def __init__(self):
        super().__init__()
        self.gpu_rptr1 = 0
        self.gpu_rptr2 = 0
        self.gpu_rptr3 = 0
        self.event_id = -1
        self.unk_4c = -1
        self.uuid = 0xdeadbeef # some kind of ID
        self.unk_54 = -1
        self.unk_58 = 0x0
        self.busy = 0x0
        self.unk_80 = 0
        self.has_commands = 0
        self.unk_88 = 0
        self.unk_8c = 0
        self.unk_90 = 0
        self.unk_94 = 0
        self.inflight_commands = 0
        self.unk_9c = 0
        self.unk_a0_0 = 0
        self.set_prio(0)
        self.unk_a8 = 0
        self.unk_b0 = 0

    def set_prio(self, p):
        if p == 0:
            self.priority = 0
            self.unk_34 = 0 # 0-3?
            self.unk_38 = 0xffff_ffff_ffff_0000
            self.unk_40 = 1
            self.unk_44 = 0
            self.prio5 = 1
        elif p == 1:
            self.priority = 1
            self.unk_34 = 1
            self.unk_38 = 0xffff_ffff_0000_0000
            self.unk_40 = 0
            self.unk_44 = 0
            self.prio5 = 0
        elif p == 2:
            self.priority = 2
            self.unk_34 = 2
            self.unk_38 = 0xffff_0000_0000_0000
            self.unk_40 = 0
            self.unk_44 = 0
            self.prio5 = 2
        else:
            self.priority = 3
            self.unk_34 = 3
            self.unk_38 = 0x0000_0000_0000_0000
            self.unk_40 = 0
            self.unk_44 = 0
            self.prio5 = 3

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
