# SPDX-License-Identifier: MIT
from m1n1.constructutils import *
from construct import *
from .controllist import *
from ...utils import RegMap, Register32

__all__ = []

class WorkCommandBarrier(ConstructClass):
    """
        sent before WorkCommand_1 on the Submit3d queue.
        Might be for initilzing the tile buckets?

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x4, Int32ul),
        "barrier_addr" / Int64ul,
        "barrier" / ROPointer(this.barrier_addr, Int32ul),
        "barrier_tag1" / Int32ul,
        "event" / Int32ul, # Event number that signals a barrier check
        "barrier_tag2" / Int32ul,
        "uuid" / Int32ul,
        "unk" / Default(Int32ul, 0),
    )

class WorkCommandInitBM(ConstructClass):
    """
        occationally sent before WorkCommand_0 on the SubmitTA queue.

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x6, Hex(Int32ul)),
        "context_id" / Hex(Int32ul), # Might be context?
        "unk_8" / Hex(Int32ul), # 0
        "unk_c" / Hex(Int32ul), # 0
        "unk_10" / Hex(Int32ul), # 0x30
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "barrier_tag" / Hex(Int32ul),  # 0x100
    )

class WorkCommandSubC(ConstructClass):
    subcon = Struct(
        "unkptr_0" / Hex(Int64ul),
        "unk_8" / Hex(Int32ul),
        "unk_c" / Hex(Int32ul),
        "unk_10" / Hex(Int64ul),
        "unk_18" / Hex(Int64ul),
        "unk_20" / Hex(Int32ul),
        "unk_24" / Hex(Int32ul),
        "unk_28" / HexDump(Bytes(0xa0 - 0x28)),
        "context_ptr" / Int64ul,
    )

class WorkCommand_3(ConstructClass):
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
        "unk_4" / Hex(Int32ul),
        "context_id" / Hex(Int32ul),
        "unkptr_c" / Hex(Int64ul),
        "unk_c" / ROPointer(this.unkptr_c, WorkCommandSubC),

        # This struct embeeds some data that the Control List has pointers back to, but doesn't
        # seem to be actually part of this struct
        Padding(0x1e8 - 0x14),

        # offset 000001e8
        "controllist_ptr" / Hex(Int64ul),
        "controllist_size" / Hex(Int32ul),
        "controllist" / ROPointer(this.controllist_ptr, ControlList),
    )

    def __str__(self) -> str:
        str = super().__str__(ignore=['magic'])
        str += f"   Control List - {self.controllist_size:#x} bytes @ {self.controllist_ptr:#x}:\n"
        str += textwrap.indent(repr(self.controllist), ' ' * 3)
        return str

class WorkCommand0_UnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x18))

    def __init__(self):
        self.value = bytes(0x18)

class WorkCommand1_UnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x118))

    def __init__(self):
        self.value = bytes(0x118)

class WorkCommand1_UnkBuf2(ConstructClass):
    subcon = Struct(
        "unk_0" / Int64ul,
        "unk_8" / Int64ul,
        "unk_10" / Int64ul,
    )

class WorkCommand_1(ConstructClass):
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
        "context_id" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "controllist_ptr" / Hex(Int64ul), # Command list
        "controllist_size" / Hex(Int32ul),
        "controllist" / ROPointer(this.controllist_ptr, ControlList),
        "unkptr_18" / Hex(Int64ul),
        "unk_18" / ROPointer(this.unkptr_18, WorkCommandSubC),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "unk_emptybuf_addr" / Hex(Int64ul),
        "tvb_addr" / Hex(Int64ul),
        "unk_40" / Hex(Int64ul),
        "unk_48" / Hex(Int32ul),
        "unk_4c" / Hex(Int32ul),
        "unk_50" / Hex(Int64ul),
        "unk_58" / Hex(Int64ul),
        "uuid1" / Hex(Int32ul), # same across repeated submits
        "uuid2" / Hex(Int32ul), # same across repeated submits
        "unk_68" / Hex(Int64ul),
        "unk_70" / Hex(Int64ul),

        # Embedded structures that are also pointed to by other stuff
        "struct_2" / Start3DStruct2,
        "struct_1" / Start3DStruct1,
        "unk_buf" / WorkCommand1_UnkBuf,
        "unk_word" / BarrierCounter,
        "struct_6" / Start3DStruct6,
        "struct_7" / Start3DStruct7,
        "unk_buf2" / WorkCommand1_UnkBuf2,
        "ts1" / Timestamp,
        "ts2" / Timestamp,
        "ts3" / Timestamp,
        "unk_914" / Int32ul,
        "unk_918" / Int64ul,
        "unk_920" / Int32ul,
        "unk_924" / Int32ul,
        "pad_928" / Default(HexDump(Bytes(0x18)), bytes(0x18)),
    )

    def __str__(self) -> str:
        str = super().__str__()
        # str += f"   Control List - {self.controllist_size:#x} bytes @ {self.controllist_ptr:#x}:\n"
        # str += textwrap.indent(repr(self.controllist), ' ' * 3)
        return str

class WorkCommand0_UnkBuf(ConstructValueClass):
    subcon = HexDump(Bytes(0x18))

    def __init__(self):
        self.value = bytes(0x18)

class WorkCommand_0(ConstructClass):
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
        "context_id" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "unkptr_c" / Hex(Int64ul),
        "unk_c" / ROPointer(this.unkptr_c, WorkCommandSubC),
        "unk_14" / Hex(Int64ul),
        "buffer_mgr_addr" / Int64ul,
        "buffer_mgr" / ROPointer(this.buffer_mgr_addr, BufferManagerInfo),
        "buf_thing_addr" / Int64ul,
        "buf_thing" / ROPointer(this.buf_thing_addr, BufferThing),
        "unk_emptybuf_addr" / Hex(Int64ul),
        "unk_34" / Hex(Int32ul),

        # Embedded structures that are also pointed to by other stuff
        "struct_2" / StartTACmdStruct2, # 0x11c bytes
        "unk_154" / HexDump(Bytes(0x268)), # unknown
        "tiling_params" / TilingParameters, # 0x2c bytes
        "unk_3e8" / HexDump(Bytes(0x74)), # unknown

        "unkptr_45c" / Int64ul,
        "tvb_size" / Int64ul,
        "controllist_ptr" / Hex(Int64ul),
        "controllist_size" / Hex(Int32ul),
        "controllist" / ROPointer(this.controllist_ptr, ControlList),
        "unk_478" / Int32ul,
        "barrier_tag" / Int32ul,

        "struct_3" / StartTACmdStruct3, # 0x114 bytes

        "unk_594" / WorkCommand0_UnkBuf,

        "ts1" / Timestamp,
        "ts2" / Timestamp,
        "ts3" / Timestamp,

        "unk_5c4" / Int32ul,
        "unk_5c8" / Int32ul,
        "unk_5cc" / Int32ul,
        "unk_5d0" / Int32ul,
        "unk_5d4" / Int8ul,
        "pad_5d5" / Default(HexDump(Bytes(0xb)), bytes(0xb)),
    )

    def __str__(self) -> str:
        str = super().__str__(ignore=['magic'])
        #str += f"   Control List - {self.controllist_size:#x} bytes @ {self.controllist_ptr:#x}:\n"
        #str += textwrap.indent(repr(self.controllist), ' ' * 3)
        return str

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
            0: WorkCommand_0,
            1: WorkCommand_1,
            3: WorkCommand_3,
            4: WorkCommandBarrier,
            6: WorkCommandInitBM,
        })
    )

class ContextInfo(ConstructClass):
    subcon = Struct(
        "fb_ptr" / Default(Int64ul, 0),
        "self" / Int64ul,
        "unkptr_10" / Default(Int64ul, 0),
    )

class GPUContextData(ConstructClass):
    subcon = Struct(
        "unk_0" / Int16ul,
        Padding(3),
        "unk_5" / Int8ul,
        Padding(0x1e - 6),
        "unk_1e" / Int8ul,
        "unk_1f" / Int8ul,
        Padding(3),
        "unk_23" / Int8ul,
        Padding(0x1c),
    )

    def __init__(self):
        self.unk_0 = 0xffff
        self.unk_5 = 1
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
        Padding(12),
        "unk_10" / Int32ul,
        Padding(12),
        "unk_20" / Int32ul,
        Padding(12),
        "gpu_rptr" / Int32ul,
        Padding(12),
        "cpu_wptr" / Int32ul,
        Padding(12),
        "rb_size" / Int32ul,
        Padding(12),
        "unk" / Default(Bytes(0x2800), bytes(0x2800)),
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
        Mostly managed by GPU, only intialize by CPU

    """
    subcon = Struct(
        "pointers_addr" / Hex(Int64ul),
        "pointers" / ROPointer(this.pointers_addr, CommandQueuePointers),
        "rb_addr" / Hex(Int64ul), # 0x4ff pointers
        "context_info_addr" / Hex(Int64ul), # ffffffa000000000, size 0x18 (shared by 3D and TA)
        "context_info" / ROPointer(this.context_info_addr, ContextInfo),
        "gpu_buf_addr" / Hex(Int64ul), # GPU space for this queue, 0x2c18 bytes?
        "gpu_buf" / ROPointer(this.gpu_buf_addr, HexDump(Bytes(0x2c18))),
        "gpu_rptr1" / Hex(Int32ul),
        "gpu_rptr2" / Hex(Int32ul),
        "gpu_rptr3" / Hex(Int32ul),
        "unk_2c" / Int32ul, # busy flags?
        "unk_30" / Hex(Int32ul), # read by CPU
        "unk_34" / Hex(Int32ul),
        "unk_38" / Hex(Int64ul), # 0xffffffffffff0000, page mask?
        "unk_40" / Hex(Int32ul), # 1
        "unk_44" / Hex(Int32ul), # 0
        "unk_48" / Hex(Int32ul), # 1, 2
        "unk_4c" / Int32sl, # -1
        "unk_50" / Hex(Int32ul), # Counts up for each new process or command queue
        "unk_54" / Hex(Int32ul), # always 0x04
        "unk_58" / Hex(Int64ul), # 0
        "busy" / Hex(Int32ul), # 1 = gpu busy
        Padding(0x20),
        "blocked_on_barrier" / Hex(Int32ul),
        Padding(0x18),
        "gpu_context_addr" / Hex(Int64ul), # GPU managed context, shared between 3D and TA. Passed to DC_DestroyContext
        "gpu_context" / ROPointer(this.gpu_context_addr, GPUContextData),

        # End of struct
    )

    def __init__(self):
        super().__init__()
        self.gpu_rptr1 = 0
        self.gpu_rptr2 = 0
        self.gpu_rptr3 = 0
        self.unk_2c = 0xffffffff
        self.unk_30 = 0x0
        self.unk_34 = 0x0
        self.unk_38 = 0xffffffffffff0000
        self.unk_40 = 0x1
        self.unk_44 = 0x0
        self.unk_48 = 0x1
        self.unk_4c = -0x1
        self.unk_50 = 0x96
        self.unk_54 = 0xffffffff
        self.unk_58 = 0x0
        self.busy = 0x0
        self.blocked_on_barrier = 0x0

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
