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


class Start3DCmd(ConstructClass):
    subcon = Struct( # 0x194 bytes''''
        "magic" / Const(0x24, Int32ul),
        "unkptr_4" / Int64ul, # empty before run. Output? WorkCommand_1 + 0x3c0
        "unkptr_c" / Int64ul, # ??  WorkCommand_1 + 0x78
        "unkptr_14" / Int64ul, #  same as workcommand_1.unkptr_28.
        "unkptr_1c" / Int64ul, # constant 0xffffffa00c33ec88, AKA initdata->unkptr_178+8
        "unkptr_24" / Int64ul, # 4 bytes
        "unkptr_2c" / Int64ul, # 0x3c bytes
        "unkptr_34" / Int64ul, # 0x34 bytes
        "cmdqueue_ptr" / Int64ul, # points back to the CommandQueueInfo that this command came from
        "workitem_ptr" / Int64ul, # points back at the WorkItem that this command came from
        "context_id" / Int32ul, # 4
        "unk_50" / Int32ul, # 1
        "unk_54" / Int32ul, # 1
        "unk_58" / Int32ul, # 2
        "unk_5c" / Int32ul, # 0
        "unk_60" / Int32ul, # 0
        "unk_64" / Int32ul, # 0
        "unk_68" / Int32ul, # 0
        "unkptr_6c" / Int64ul,
        "unkprt_74" / Int64ul, # 0x18 bytes
        "unk_7c" / Int32ul,
        "unk_80" / Int32ul,
        "unk_84" / Int32ul,
        "uuid" / Int32ul, # uuid for tracking
        "unkptr_8c" / Int64ul, # Userspace VA
        "unk_94" / Int64ul, # 0x000100170000ed80
        Padding(0x194 - 0x9c),
    )

    def __str__(self):
        return super().__str__(ignore=["cmdqueue_ptr", "workitem_ptr"])


class Finalize3DCmd(ConstructClass):
    subcon = Struct( # 0x9c bytes
        "magic" / Const(0x25, Int32ul),
        "uuid" / Int32ul, # uuid for tracking
        "unk_8" / Int32ul, # 0
        "unkptr_c" / Int64ul,
        "unk_14" / Int64ul, # multiple of 0x100, gets written to unkptr_c
        "unkptr_1c" / Int64ul, # Same as Start3DCmd.unkptr_14
        "unkptr_24" / Int64ul,
        "unk_2c" / Int64ul, # 1
        "unkptr_34" / Int64ul, # Same as Start3DCmd.unkptr_1c
        "unkptr_3c" / Int64ul, # Same as Start3DCmd.unkptr_34
        "unkptr_44" / Int64ul, # Same as Start3DCmd.unkptr_24
        "cmdqueue_ptr" / Int64ul,
        "workitem_ptr" / Int64ul,
        "unk_5c" / Int64ul,
        "unkptr_64" / Int64ul, # Same as Start3DCmd.unkptr_6c
        "unk_6c" / Int64ul, # 0
        "unk_74" / Int64ul, # 0
        "unk_7c" / Int64ul, # 0
        "unk_84" / Int64ul, # 0
        "unk_8c" / Int64ul, # 0
        "startcmd_offset" / Int32sl, # realative offset from start of Finalize to StartComputeCmd
        "unk_98" / Int32ul, # 1
    )

    def __str__(self):
        return super().__str__(ignore=["cmdqueue_ptr", "workitem_ptr", "startcmd_offset"])


class ComputeInfo(ConstructClass):
    # Only the cmdlist and pipelinebase and cmdlist fields are strictly needed to launch a basic
    # compute shader.
    subcon = Struct( # 0x1c bytes
        "unkptr_0" / Int64ul, # always 0 in my tests. Might be unforms?
        "cmdlist" / Int64ul, # CommandList from userspace
        "unkptr_10" / Int64ul, # size 8, null
        "unkptr_18" / Int64ul, # size 8, null
        "unkptr_20" / Int64ul, # size 8, null
        "unkptr_28" / Int64ul, #
        "pipeline_base" / Int64ul, # 0x11_00000000: Used for certain "short" pointers like pipelines (and shaders?)
        "unkptr_38" / Int64ul, # always 0x8c60.
        "unk_40" / Int32ul, # 0x41
        "unk_44" / Int32ul, # 0
        "unkptr_48" / Int64ul, #
        "unk_50" / Int32ul, # 0x40 - Size?
        "unk_54" / Int32ul, # 0
        "unk_58" / Int32ul, # 1
        "unk_5c" / Int32ul, # 0
        "unk_60" / Int32ul, # 0x1c
    )


class StartComputeCmd(ConstructClass):
    subcon = Struct( # 0x154 bytes''''
        "magic" / Const(0x29, Int32ul),
        "unkptr_4" / Int64ul, # empty: WorkCommand_3 + 0x14, size: 0x54
        "computeinfo_addr" / Int64ul, # List of userspace VAs: WorkCommand_3 + 0x68
        "computeinfo" / Pointer(this.computeinfo_addr, ComputeInfo),
        "unkptr_14" / Int64ul, # In gpu-asc's heap? Did this pointer come from the gfx firmware?
        "cmdqueue_ptr" / Int64ul, # points back to the submitinfo that this command came from
        "context_id" / Int32ul, # 4
        "unk_28" / Int32ul, # 1
        "unk_2c" / Int32ul, # 0
        "unk_30" / Int32ul,
        "unk_34" / Int32ul,
        "unk_38" / Int32ul,
        "unkprt_3c" / Int64ul, # WorkCommand_3 + 0x1f4
        "unk_44" / Int32ul,
        "uuid" / Int32ul, # uuid for tracking?
        "padding" / Bytes(0x154 - 0x4c),
    )

    def parsed(self, ctx):
        try:
            if self.padding != b"\x00" * (0x154 - 0x4c):
                raise ExplicitError("padding is not zero")
            del self.padding
            self._keys = [x for x in self._keys if x != "padding"]
        except AttributeError:
            pass

    def __str__(self):
        return super().__str__(ignore=["cmdqueue_ptr", "workitem_ptr"])


class FinalizeComputeCmd(ConstructClass):
    subcon = Struct( # 0x64 bytes''''
        "magic" / Const(0x2a, Int32ul),
        "unkptr_4" / Int64ul, # same as ComputeStartCmd.unkptr_14
        "cmdqueue_ptr" / Int64ul, # points back to the submitinfo
        "unk_14" / Int32ul, # Context ID?
        "unk_18" / Int32ul,
        "unkptr_1c" / Int64ul, # same as ComputeStartCmd.unkptr_3c
        "unk_24" / Int32ul,
        "uuid" / Int32ul,  # uuid for tracking?
        "unkptr_2c" / Int64ul,
        "unk_34" / Int32ul, # Gets written to unkptr_2c (after completion?)
        "unk_38" / Int32ul,
        "unk_3c" / Int32ul,
        "unk_40" / Int32ul,
        "unk_44" / Int32ul,
        "unk_48" / Int32ul,
        "unk_4c" / Int32ul,
        "unk_50" / Int32ul,
        "unk_54" / Int32ul,
        "unk_58" / Int32ul,
        "startcmd_offset" / Int32sl, # realative offset from start of Finalize to StartComputeCmd
        "unk_60" / Int32ul,
    )

    def __str__(self):
        return super().__str__(ignore=["cmdqueue_ptr", "workitem_ptr", "startcmd_offset"])

class EndCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x18, Byte),
        "unk_1" / Byte,
        "unk_2" / Byte,
        "unk_3" / Byte,
    )

    def __str__(self) -> str:
        return f"End({self.unk_1}, {self.unk_2}, {self.unk_3})"

class TimestampCmd(ConstructClass):
    subcon = Struct( # 0x34 bytes
        "magic" / Const(0x19, Byte),
        "unk_1" / Byte,
        "unk_2" / Byte,
        "unk_3" / Byte, # Sometimes 0x80
        # all these pointers point to 0xfa0... addresses. Might be where the timestamp should be writen?
        "unkptr_4" / Int64ul, # Size: 8 bytes, points to 0
        "unkptr_c" / Int64ul, # Size: 8 bytes, points to single pointer
        "unkptr_14" / Int64ul, # Size: 8 bytes, sometimes a repeate of unkptr_c, points to single pointer
        "cmdqueue_ptr" / Int64ul,
        "unk_24" / Int32ul,
        "unk_28" / Int32ul,
        "uuid" / Int32ul,
        "unk_30" / Int32ul,
    )

class WaitForInterruptCmd(ConstructClass):
    subcon = Struct(
        "magic" / Const(0x01, Byte),
        "unk_1" / Byte,
        "unk_2" / Byte,
        "unk_3" / Byte,
    )

    def __str__(self) -> str:
        return f"WaitForInterrupt({self.unk_1}, {self.unk_2}, {self.unk_3})"

class NopCmd(ConstructClass):
    # This doesn't exist
    subcon = Struct(
        "magic" / Const(0x00, Int32ul),
    )

    def __str__(self) -> str:
        return "Nop"


class ControlList(ConstructValueClass):
    subcon = GreedyRange(
        Select(
            #NopCmd,
            WaitForInterruptCmd,

            EndCmd,
            TimestampCmd,

            Start3DCmd,
            Finalize3DCmd,
            StartComputeCmd,
            FinalizeComputeCmd,
        )
    )

    def __str__(self):
        s = ""
        for cmd in self.value:
            s += str(cmd) + '\n'
            if isinstance(cmd, EndCmd):
                break
        return s

