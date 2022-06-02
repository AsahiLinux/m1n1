
import random

from m1n1.utils import *
from m1n1.constructutils import *
from construct import *
from .cmdqueue import *

__all__ = ["channelNames", "channelRings", "DeviceControlMsg", "EventMsg", "StatsMsg"]

class RunCmdQueueMsg(ConstructClass):
    subcon = Struct (
        "queue_type" / Default(Int32ul, 0),
        "cmdqueue_addr" / Default(Hex(Int64ul), 0),
        "cmdqueue" / Lazy(ROPointer(this.cmdqueue_addr, CommandQueueInfo)),
        "head" / Default(Int32ul, 0),
        "event_number" / Default(Int32ul, 0),
        "new_queue" / Default(Int32ul, 0),
        "data" / HexDump(Default(Bytes(0x18), bytes(0x18))),
    )

    TYPES = {
        0: "SubmitTA",
        1: "Submit3D",
        2: "SubmitCompute",
    }

    def __str__(self):
        s = super().__str__() + "\n"

        if self.cmdqueue_addr == 0:
            return s + "<Empty RunCmdQueueMsg>"

        r = random.randrange(2**64)
        s += f"{self.TYPES[self.queue_type]}(0x{self.cmdqueue_addr & 0xfff_ffffffff:x}, {self.head}, ev={self.event_number}, new={self.new_queue}) //{r:x}"
        return s

class DC_DestroyContext(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x17, Int32ul),
        "unk_4" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "unk_c" / Hex(Int32ul),
        "unk_10" / Hex(Int32ul),
        "unk_14" / Hex(Int32ul),
        "unk_18" / Hex(Int32ul),
        "context_addr" / Hex(Int64ul),
        "rest" / HexDump(Bytes(0xc))
    )

class DeviceControl_19(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x19, Int32ul),
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c)))
    )


class DeviceControl_1e(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x1e, Int32ul),
        "data" / HexDump(Bytes(0x2c)),
    ),

class DeviceControl_23(ConstructClass):
    subcon = Struct (
        "msg_type" / Const(0x23, Int32ul),
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c))),
    )

class UnknownMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Int32ul),
        "data" / HexDump(Bytes(0x2c)),
    )

DeviceControlMsg = FixedSized(0x30, Select(
    DC_DestroyContext,
    DeviceControl_19,
    DeviceControl_23,
    UnknownMsg,
))

# Tends to count up
class StatsMsg_00(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x00, Int32ul)),
        Padding(0x18), # ??? why the hole? never written...
        "offset" / Hex(Int64ul),
        Padding(0xc), # Confirmed padding
    )

class StatsMsg_02(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x02, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "data" / HexDump(Bytes(0x24)),
    )

# Related to 00, tends to "reset" the count
class StatsMsg_03(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x03, Int32ul)),
        "offset" / Hex(Int64ul),
        Padding(0x24), # Confirmed padding
    )

class StatsMsg_04(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x04, Int32ul)),
        "unk0" / Hex(Int32ul),
        "unk1" / Hex(Int32ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        "offset" / Hex(Int64ul),
        Padding(0x14), # Confirmed padding
    )

class StatsMsg_09(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x09, Int32ul)),
        "unk0" / Hex(Int32ul),
        "unk1" / Hex(Int32ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        "unk4" / Hex(Int32ul),
        "unk5" / Hex(Int32ul),
        Padding(0x14), # Confirmed padding
    )

class StatsMsg_0a(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0a, Int32ul)),
        Padding(8), # Not written
        "unk0" / Hex(Int32ul),
        "unk1" / Hex(Int32ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        Padding(0x14), # Confirmed padding
    )

class StatsMsg_0b(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0b, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "timestamp2" / Hex(Int64ul),
        "unk0" / Hex(Int32ul),
        "unk1" / Hex(Int32ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        "unk4" / Hex(Int32ul),
        "unk5" / Hex(Int32ul),
        Padding(4), # Confirmed padding
    )

class StatsMsg_0c(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0c, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "flag" / Int32ul,
        Padding(0x20), # Confirmed padding
    )

class StatsMsg_0d(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0d, Int32ul)),
        Padding(8), # Not written
        "unk0" / Hex(Int32ul),
        "unk1" / Hex(Int32ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        Padding(0x14), # Confirmed padding
    )

class StatsMsg_0e(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0e, Int32ul)),
        Padding(4), # Not written
        "unk0" / Hex(Int32ul),
        "unk1" / Hex(Int32ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        "unk4" / Hex(Int32ul),
        Padding(0x14), # Confirmed padding
    )

StatsMsg = FixedSized(0x30, Select(
    StatsMsg_00,
    #StatsMsg_02,
    StatsMsg_03,
    StatsMsg_04,
    StatsMsg_09,
    StatsMsg_0a,
    StatsMsg_0b,
    StatsMsg_0c,
    StatsMsg_0d,
    StatsMsg_0e,
    UnknownMsg,
))

class FWLogMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x03, Int32ul)),
        "seq_no" / Hex(Int32ul),
        "timestamp" / Hex(Int64ul),
        "msg" / PaddedString(0xc8, "ascii")
    )

class FlagMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(1, Int32ul)),
        "firing" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "unk_c" / Hex(Int32ul),
        "unk_10" / Hex(Int32ul),
        "unk_14" / Hex(Int16ul),
        "unkpad_16" / HexDump(Bytes(0x38 - 0x16)),
    )

class FaultMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(4, Int32ul)),
        "index" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "queue" / Hex(Int32ul),
        "unkpad_16" / HexDump(Bytes(0x38 - 0x10)),
    )

EventMsg = FixedSized(0x38, Select(
    FlagMsg,
    HexDump(Bytes(0x38)),
))

class KTraceMsg(ConstructClass):
    subcon = Struct (
        "unk" / HexDump(Bytes(0x70)),
    )

channelNames = [
    "TA_0", "3D_0", "CL_0",
    "TA_1", "3D_1", "CL_1",
    "TA_2", "3D_2", "CL_2",
    "TA_3", "3D_3", "CL_3",
    "DevCtrl",
    "Event", "FWLog", "KTrace", "Stats"
]

channelRings = (
    [[(RunCmdQueueMsg, 0x30, 0x100)]] * 12 + [
        [(DeviceControlMsg, 0x30, 0x100)],
        [(EventMsg, 0x38, 0x100)],
        [
            (FWLogMsg, 0xd8, 0x100),                # unk 0
            (FWLogMsg, 0xd8, 0x100),                # init log
            (FWLogMsg, 0xd8, 0x100),                # unk 2
            (FWLogMsg, 0xd8, 0x100),                # warnings?
            (FWLogMsg, 0xd8, 0x100),                # unk 4
            (FWLogMsg, 0xd8, 0x100),                # unk 5
        ],
        [(KTraceMsg, 0x70, 0x100)],
        [(StatsMsg, 0x30, 0x100)]
    ]
)

class ChannelStateFields(RegMap):
    READ_PTR = 0x00, Register32
    WRITE_PTR = 0x20, Register32

class Channel(Reloadable):
    def __init__(self, u, uat, info, ring_defs, base=None):
        self.uat = uat
        self.u = u
        self.p = u.proxy
        self.iface = u.iface

        self.ring_defs = ring_defs
        self.info = info

        self.st_maps = uat.iotranslate(0, info.state_addr, 0x30 * len(ring_defs))
        assert len(self.st_maps) == 1
        self.state_phys = self.st_maps[0][0]
        self.state = []
        self.rb_base = []
        self.rb_maps = []

        if base is None:
            p = info.ringbuffer_addr
        else:
            p = base
        for i, (msg, size, count) in enumerate(ring_defs):
            assert msg.sizeof() == size

            self.state.append(ChannelStateFields(self.u, self.state_phys + 0x30 * i))
            m = uat.iotranslate(0, p, size * count)
            self.rb_base.append(p)
            self.rb_maps.append(m)
            p += size * count

    def get_message(self, ring, index, meta_fn=None):
        msgcls, size, count = self.ring_defs[ring]

        assert index < count
        addr = self.rb_base[ring] + index * size
        stream = self.uat.iostream(0, addr)
        stream.meta_fn = meta_fn
        return msgcls.parse_stream(stream)

    def clear_message(self, ring, index):
        msgcls, size, count = self.ring_defs[ring]

        self.put_message(ring, index, b"\xef\xbe\xad\xde" * (size // 4))

    def put_message(self, ring, index, obj):
        msgcls, size, count = self.ring_defs[ring]

        assert index < count
        if isinstance(obj, bytes):
            data = obj
        else:
            data = obj.build()
        self.uat.iowrite(0, self.rb_base[ring] + index * size, data)

class ChannelInfo(ConstructClass):
    subcon = Struct(
        "state_addr" / Hex(Int64ul),
        "ringbuffer_addr" / Hex(Int64ul),
    )

class ChannelInfoSet(ConstructClass):
    CHAN_COUNT = len(channelNames)

    subcon = Struct(*[ name / ChannelInfo for name in channelNames])

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
