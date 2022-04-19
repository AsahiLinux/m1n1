# SPDX-License-Identifier: MIT
from m1n1.constructutils import *
from construct import *
from .controllist import *

class WorkCommand_4(ConstructClass):
    """
        sent before WorkCommand_1 on the Submit3d queue.
        Might be for initilzing the tile buckets?

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x4, Hex(Int32ul)),
        "ptr" / Hex(Int64ul), # These appare to be shared over multiple contexes
        "unk_c" / Hex(Int32ul), # Counts up by 0x100 each frame, gets written to ptr? (on completion?)
        "flag" / Hex(Int32ul), # 2, 4 or 6
        "unk_14" / Hex(Int32ul),  # Counts up by 0x100 each frame? starts at diffrent point?
        "uuid" / Hex(Int32ul),
    )

class WorkCommand_6(ConstructClass):
    """
        occationally sent before WorkCommand_0 on the SubmitTA queue.

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x6, Hex(Int32ul)),
        "unk_4" / Hex(Int32ul), # Might be context?
        "unk_8" / Hex(Int32ul), # 0
        "unk_c" / Hex(Int32ul), # 0
        "unk_10" / Hex(Int32ul), # 0x30
        "unkptr_14" / Hex(Int64ul), # same as unkptr_20 of the previous worckcommand_1, has some userspace VAs
        "size" / Hex(Int32ul),  # 0x100
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
        "magic" / Const(0x3, Hex(Int32ul)),
        "unk_4" / Hex(Int32ul),
        "context_id" / Hex(Int32ul),
        "unkptr_c" / Hex(Int64ul),

        # This struct embeeds some data that the Control List has pointers back to, but doesn't
        # seem to be actually part of this struct
        Padding(0x1e8 - 0x14),

        # offset 000001e8
        "controllist_ptr" / Hex(Int64ul),
        "controllist_size" / Hex(Int32ul),
        "controllist" / Pointer(this.controllist_ptr, ControlList),
    )

    def __str__(self) -> str:
        str = super().__str__(ignore=['magic', 'controllist_ptr', 'controllist_size'])
        # str += f"   Control List - {self.controllist_size:#x} bytes @ {self.controllist_ptr:#x}:\n"
        # str += textwrap.indent(repr(self.controllist), ' ' * 3)
        return str


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
        "magic" / Const(0x1, Hex(Int32ul)),
        "context_id" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "controllist_ptr" / Hex(Int64ul), # Command list
        "controllist_size" / Hex(Int32ul),
        "controllist" / Pointer(this.controllist_ptr, ControlList),
        "unkptr_18" / Hex(Int64ul),
        "unkptr_20" / Hex(Int64ul), # Size: 0x100
        "unkptr_28" / Hex(Int64ul), # Size: 0x8c0
        "unkptr_30" / Hex(Int64ul),
        "unkptr_38" / Hex(Int64ul),
        "unk_40" / Hex(Int64ul),
        "unk_48" / Hex(Int32ul),
        "unk_4c" / Hex(Int32ul),
        "unk_50" / Hex(Int64ul),
        "unk_58" / Hex(Int64ul),
        "uuid1" / Hex(Int32ul), # same across repeated submits
        "uuid2" / Hex(Int32ul), # same across repeated submits
        "unk_68" / Hex(Int64ul),
        "unk_70" / Hex(Int64ul),
    )

    def __str__(self) -> str:
        str = super().__str__(ignore=['magic', 'controllist_ptr', 'controllist_size'])
        # str += f"   Control List - {self.controllist_size:#x} bytes @ {self.controllist_ptr:#x}:\n"
        # str += textwrap.indent(repr(self.controllist), ' ' * 3)
        return str


class WorkCommand_0(ConstructClass):
    """
    For TA

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
        "magic" / Const(0x0, Hex(Int32ul)),
        "context_id" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "unkptr_c" / Hex(Int64ul),
        "unk_14" / Hex(Int64ul),
        "unkptr_1c" / Hex(Int64ul),
        "unkptr_24" / Hex(Int64ul),
        "unkptr_2c" / Hex(Int64ul),
        "unk_34" / Hex(Int64ul),
        "unk_3c" / Hex(Int32ul),
        "uuid1" / Hex(Int32ul),
        "uuid2" / Hex(Int32ul),
        "unkptr_48" / Hex(Int64ul),
        "unkptr_50" / Hex(Int64ul),
        "unkptr_58" / Hex(Int64ul),
        "unkptr_60" / Hex(Int64ul),

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
    subcon = Select(
        WorkCommand_0,
        WorkCommand_1,
        WorkCommand_3,
        WorkCommand_4,
        WorkCommand_6,

        UnknownWorkCommand
    )

class CommandQueueInfo(ConstructClass):
    """ Structure type shared by Submit3D, SubmitTA and SubmitCompute
        Applications have multiple of these, one of each submit type
        TODO: Can applications have more than one of each type? One per encoder?

    """
    subcon = Struct(
        "unkptr_0" / Hex(Int64ul), # data at this pointer seems to match the current offests below
        "RingBuffer_addr" / Hex(Int64ul), # 0x4ff pointers
        "Ringbuffer_count" / Computed(0x4ff),
        "ContextInfo" / Hex(Int64ul), # ffffffa000000000, size 0x18 (shared by 3D and TA)
        "unkptr_18" / Hex(Int64ul), # eventually leads to userspace VAs
        "cpu_tail" / Hex(Int32ul), # controled by cpu, tail
        "gpu_tail" / Hex(Int32ul), # controled by gpu
        "offset3" / Hex(Int32ul), # controled by gpu
        "unk_2c" / Int32sl, # touched by both cpu and gpu, cpu likes -1, gpu likes 3. Might be a return value?
        "unk_30" / Hex(Int64ul), # zero
        "unk_38" / Hex(Int64ul), # 0xffffffffffff0000, page mask?
        "unk_40" / Hex(Int32ul), # 1
        "unk_44" / Hex(Int32ul), # 0
        "unk_48" / Hex(Int32ul), # 1, 2
        "unk_4c" / Int32sl, # -1
        "unk_50" / Hex(Int32ul), # Counts up for each new process or command queue
        "unk_54" / Hex(Int32ul), # always 0x04
        "unk_58" / Hex(Int64ul), # 0
        "unk_60" / Hex(Int32ul), # Set to 1 by gpu after work complete. Reset to zero by cpu
        Padding(0x20),
        "unk_84" / Hex(Int32ul), # Set to 1 by gpu after work complete. Reset to zero by cpu
        Padding(0x18),
        "unkptr_a0" / Hex(Int64ul), # Size 0x40 ; Also seen in DeviceControl_17

        # End of struct
    )

    def getTail(self):
        return self.cpu_tail
        try:
            return CommandQueueRingbufferTail[self._addr]
        except KeyError:
            return self.cpu_tail

    def setTail(self, new_tail):
        CommandQueueRingbufferTail[self._addr] = new_tail

    def getSubmittedWork(self, head):
        Work = []
        orig_tail = tail = self.getTail()
        count = 0

        while tail != head:
            count += 1
            stream = self._stream
            stream.seek(self.RingBuffer_addr + tail * 8, 0)
            pointer = Hex(Int64ul).parse_stream(stream)
            stream.seek(pointer, 0)

            Work.append(CmdBufWork.parse_stream(stream))

            tail = (tail + 1) % self.Ringbuffer_count

        #print(f"Parsed {count} items from {orig_tail} to {head}")

        #self.setTail(tail)
        return Work

CommandQueueInfo = CommandQueueInfo._reloadcls()
