
import random

from m1n1.utils import *
from m1n1.constructutils import *
from construct import *
from .cmdqueue import *

__all__ = ["channelNames", "channelRings", "DeviceControlMsg", "EventMsg", "StatsMsg", "StatsSize"]

if Ver.check("G >= G14 && V >= V13_2 && G < G14X"):
    RunCmdQueueSize = 0x40
else:
    RunCmdQueueSize = 0x30

class RunCmdQueueMsg(ConstructClass):
    subcon = Struct (
        "queue_type" / Default(Int32ul, 0),
        "cmdqueue_addr" / Default(Hex(Int64ul), 0),
        "cmdqueue" / Lazy(ROPointer(this.cmdqueue_addr, CommandQueueInfo)),
        "head" / Default(Int32ul, 0),
        "event_number" / Default(Int32ul, 0),
        "new_queue" / Default(Int32ul, 0),
        "timestamp" / Default(Int64ul, 0),
        "data" / HexDump(Default(Bytes(0x10), bytes(0x10))),
        Ver("G >= G14 && V >= V13_2 && G < G14X", ZPadding(0x10)),
    )

    TYPES = {
        0: "SubmitTA",
        1: "Submit3D",
        2: "SubmitCompute",
    }

    def __str__(self, *args, **kwargs):
        s = super().__str__(*args, **kwargs) + "\n"

        if self.cmdqueue_addr == 0:
            return s + "<Empty RunCmdQueueMsg>"

        r = random.randrange(2**64)
        s += f"{self.TYPES[self.queue_type]}(0x{self.cmdqueue_addr & 0xfff_ffffffff:x}, {self.head}, ev={self.event_number}, new={self.new_queue}) //{r:x}"
        return s

class DC_DestroyContext(ConstructClass):
    subcon =  Struct (
        Ver("V < V13_3", "msg_type" / Const(0x17, Int32ul)),
        Ver("V >= V13_3", "msg_type" / Const(0x18, Int32ul)),
        "unk_4" / Hex(Int32ul),
        "unk_8" / Hex(Int32ul),
        "unk_c" / Hex(Int32ul),
        "unk_10" / Hex(Int32ul),
        "unk_14" / Hex(Int32ul),
        "unk_18" / Hex(Int32ul),
        "context_addr" / Hex(Int64ul),
        "rest" / HexDump(Default(Bytes(0xc), bytes(0xc))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_Write32(ConstructClass):
    subcon =  Struct (
        Ver("V < V13_3", "msg_type" / Const(0x18, Int32ul)),
        Ver("V >= V13_3", "msg_type" / Const(0x19, Int32ul)),
        "addr" / Hex(Int64ul),
        "data" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c" / Int32ul,
        "rest" / HexDump(Default(Bytes(0x10), bytes(0x10))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_Write32B(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x13, Int32ul),
        "addr" / Hex(Int64ul),
        "data" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c" / Int32ul,
        "rest" / HexDump(Default(Bytes(0x10), bytes(0x10))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_Init(ConstructClass):
    subcon =  Struct (
        Ver("V < V13_3", "msg_type" / Const(0x19, Int32ul)),
        Ver("V >= V13_3", "msg_type" / Const(0x1a, Int32ul)),
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_09(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x9, Int32ul),
        "unk_4" / Int64ul,
        "unkptr_c" / Int64ul,
        "unk_14" / Int64ul,
        "data" /  HexDump(Default(Bytes(0x14), bytes(0x14))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_ConfigurePerfCounters(ConstructClass):
    subcon = Struct (
        "msg_type" / Const(0xb, Int32ul),
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_DisablePerfCounters(ConstructClass):
    subcon = Struct (
        "msg_type" / Const(0xc, Int32ul),
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_GrowTVBAck(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0xd, Int32ul),
        "unk_4" / Int32ul,
        "bm_id" / Int32ul,
        "vm_id" / Int32ul,
        "counter" / Int32ul,
        "rest" / HexDump(Default(Bytes(0x1c), bytes(0x1c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_Any(ConstructClass):
    subcon =  Struct (
        "msg_type" / Int32ul,
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_1e(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x1e, Int32ul),
        "unk_4" / Int64ul,
        "unk_c" / Int64ul,
        "data" /  HexDump(Default(Bytes(0x1c), bytes(0x1c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class DC_UpdateIdleTS(ConstructClass):
    subcon = Struct (
        "msg_type" / Const(0x23, Int32ul),
        "data" / HexDump(Default(Bytes(0x2c), bytes(0x2c))),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

class UnknownMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Int32ul),
        "data" / HexDump(Bytes(0x2c)),
        Ver("G == G14 && V >= V13_2", ZPadding(0x10)),
    )

if Ver.check("G == G14 && V >= V13_2"):
    DeviceControlSize = 0x40
else:
    DeviceControlSize = 0x30

DeviceControlMsg = FixedSized(DeviceControlSize, Select(
    DC_DestroyContext,
    DC_Init,
    DC_UpdateIdleTS,
    DC_1e,
    DC_Write32,
    DC_ConfigurePerfCounters,
    DC_DisablePerfCounters,
    DC_GrowTVBAck,
    UnknownMsg,
))

class StatsMsg_Power(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x00, Int32ul)),
        ZPadding(0x18), # ??? why the hole? never written...
        "power" / Hex(Int64ul),
        ZPadding(0xc), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )

    def __str__(self):
        return f"Power: {self.power / 8192.0:.3f} mW"

class StatsMsg_PowerOn(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x02, Int32ul)),
        "power_off_ticks" / Dec(Int64ul),
        ZPadding(0x24), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )
    def __str__(self):
        t = self.power_off_ticks / 24000000
        return f"Power ON: spent {t:.04}s powered off ({self.power_off_ticks} ticks)"

class StatsMsg_PowerOff(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x03, Int32ul)),
        "power_on_ticks" / Dec(Int64ul),
        ZPadding(0x24), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )
    def __str__(self):
        t = self.power_on_ticks / 24000000
        return f"Power OFF: spent {t:.04}s powered on ({self.power_on_ticks} ticks)"

class StatsMsg_Util(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x04, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "util1" / Dec(Int32ul),
        "util2" / Dec(Int32ul),
        "util3" / Dec(Int32ul),
        "util4" / Dec(Int32ul),
        ZPadding(0x14), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )
    def __str__(self):
        return f"Utilization: {self.util1:>3d}% {self.util2:>3d}% {self.util3:>3d}% {self.util4:>3d}%"

class StatsMsg_AvgPower(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x09, Int32ul)),
        "active_cs" / Dec(Int64ul),
        "unk2" / Hex(Int32ul),
        "unk3" / Hex(Int32ul),
        "unk4" / Hex(Int32ul),
        "avg_power" / Dec(Int32ul),
        ZPadding(0x14), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )

    def __str__(self):
        return f"Activity: Active {self.active_cs * 10:6d} ms Avg Pwr {self.avg_power:4d} mW ({self.unk2:d} {self.unk3:d} {self.unk4:d})"

class StatsMsg_Temp(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0a, Int32ul)),
        ZPadding(8), # Not written
        "raw_value" / Hex(Int32ul),
        "scale" / Hex(Int32ul),
        "tmin" / Hex(Int32ul),
        "tmax" / Hex(Int32ul),
        ZPadding(0x14), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )

    def __str__(self):
        temp = self.raw_value / float(self.scale) / 64.0
        return f"Temp: {temp:.2f}°C s={self.scale:d} tmin={self.tmin:d} tmax={self.tmax:d}"

class StatsMsg_PowerState(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0b, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "last_busy_ts" / Hex(Int64ul),
        "active" / Hex(Int32ul),
        "poweroff" / Dec(Int32ul),
        "unk2" / Dec(Int32ul),
        "pstate" / Dec(Int32ul),
        "unk4" / Dec(Int32ul),
        "unk5" / Dec(Int32ul),
        ZPadding(4), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )

    def __str__(self):
        act = "ACT" if self.active else "   "
        off = "OFF" if self.poweroff else "   "

        return f"PowerState: {act} {off} ps={int(self.pstate)} {self.unk4} {self.unk2} {self.unk5}"

class StatsMsg_FWBusy(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0c, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "flag" / Int32ul,
        ZPadding(0x20), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )

    def __str__(self):
        return f"FW active: {bool(self.flag)}"

class StatsMsg_PState(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0d, Int32ul)),
        ZPadding(8), # Not written
        "ps_min" / Dec(Int32ul),
        "unk1" / Dec(Int32ul),
        "ps_max" / Dec(Int32ul),
        "unk3" / Dec(Int32ul),
        ZPadding(0x14), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )
    def __str__(self):
        return f"PState: {self.ps_min:d}..{self.ps_max:d} ({self.unk1:d}/{self.unk3:d})"

class StatsMsg_TempSensor(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x0e, Int32ul)),
        ZPadding(4), # Not written
        "sensor_id" / Hex(Int32ul),
        "raw_value" / Hex(Int32ul),
        "scale" / Dec(Int32ul),
        "tmin" / Dec(Int32ul),
        "tmax" / Dec(Int32ul),
        ZPadding(0x14), # Confirmed padding
        Ver("V >= V13_0B4", ZPadding(0x10)),
    )
    def __str__(self):
        temp = self.raw_value / float(self.scale) / 64.0
        return f"TempSensor: #{self.sensor_id:d} {temp:.2f}°C s={self.scale:d} tmin={self.tmin:d} tmax={self.tmax:d}"

if Ver.check("V < V13_0B4"):
    StatsSize = 0x30
else:
    StatsSize = 0x40

StatsMsg = FixedSized(StatsSize, Select(
    StatsMsg_Power,
    StatsMsg_PowerOn,
    StatsMsg_PowerOff,
    StatsMsg_Util,
    StatsMsg_AvgPower,
    StatsMsg_Temp,
    StatsMsg_PowerState,
    StatsMsg_FWBusy,
    StatsMsg_PState,
    StatsMsg_TempSensor,
    UnknownMsg,
))

class FWLogMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0x03, Int32ul)),
        "seq_no" / Hex(Int32ul),
        "timestamp" / Hex(Int64ul),
        "msg" / PaddedString(0xc8, "ascii")
    )

class FaultMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(0, Int32ul)),
        "unk_4" / HexDump(Bytes(0x34)),
    )

class FlagMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(1, Int32ul)),
        "firing" / Array(2, Hex(Int64ul)),
        "unk_14" / Hex(Int16ul),
        "tail" / Bytes(0x38 - 0x18),
    )

class TimeoutMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(4, Int32ul)),
        "counter" / Hex(Int64ul),
        "stamp_index" / Hex(Int32sl),
        "unkpad_16" / HexDump(Bytes(0x38 - 0x10)),
    )

class GrowTVBMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(7, Int32ul)),
        "vm_id" / Hex(Int32ul),
        "bm_id" / Hex(Int32ul),
        "counter" / Hex(Int32ul),
        "tail" / HexDump(Bytes(0x38 - 0x10)),
    )

class ChannelError(ConstructClass):
    subcon = Struct (
        "msg_type" / Hex(Const(8, Int32ul)),
        "tail" / HexDump(Bytes(0x38 - 0x4)),
    )

EventMsg = FixedSized(0x38, Select(
    FaultMsg,
    FlagMsg,
    TimeoutMsg,
    GrowTVBMsg,
    ChannelError,
    HexDump(Bytes(0x38)),
))

TRACE_MSGS = {
    (0x00, 0x00, 0): ("StartTA", "uuid", None, "unk", "cmdqueue"),
    (0x00, 0x01, 0): ("FinishTA", "uuid", None, "unk", "cmdqueue"),
    (0x00, 0x04, 0): ("Start3D", "uuid", "partial_render", "unk", "cmdqueue"),
    (0x00, 0x05, 0): ("Finish3D_unk", "uuid", "unk", "flag", "buf_related"),
    (0x00, 0x06, 0): ("Finish3D", "uuid", None, "unk", "cmdqueue"),
    (0x00, 0x07, 0): ("StartCP", "uuid", None, "unk", "cmdqueue"),
    (0x00, 0x08, 0): ("FinishCP", "uuid", None, "unk", "cmdqueue"),
    (0x00, 0x0a, 0): ("StampUpdateTA", "value", "ev_id", "addr", "uuid"),
    (0x00, 0x0c, 0): ("StampUpdate3D", "value", "ev_id", "addr", "uuid"),
    (0x00, 0x0e, 0): ("StampUpdateCL", "value", "ev_id", "addr", "uuid"),
    (0x00, 0x10, 1): ("TAPreproc1", "unk"),
    (0x00, 0x10, 2): ("TAPreproc2", "unk1", "unk2"),
    (0x00, 0x17, 0): ("Finish3D2", "uuid", None, "unk", "cmdqueue"),
    (0x00, 0x28, 0): ("EvtNotify", "firing0", "firing1", "firing2", "firing3"),
    (0x00, 0x2f, 0): ("Finish3D_unk2", "uuid", "unk"),
    (0x00, 0x1e, 0): ("CleanupPB", "uuid", "unk2", "slot"),
    (0x01, 0x0a, 0): ("Postproc", "cmdid", "event_ctl", "stamp_val", "uuid"),
    (0x01, 0x0b, 0): ("EvtComplete", None, "event_ctl"),
    (0x01, 0x0d, 0): ("EvtDequeued", "next", "event_ctl"),
    (0x01, 0x16, 0): ("InitAttachment", "idx", "flags", "addr", "size"),
    (0x01, 0x18, 0): ("ReInitAttachment", "idx", "flags", "addr", "size"),
}

class KTraceMsg(ConstructClass):
    THREADS = [
        "irq",
        "bg",
        "smpl",
        "pwr",
        "rec",
        "kern",
    ]
    subcon = Struct (
        "msg_type" / Hex(Const(5, Int32ul)),
        "timestamp" / Hex(Int64ul),
        "args" / Array(4, Int64ul),
        "code" / Int8ul,
        "channel" / Int8ul,
        "pad" / Const(0, Int8ul),
        "thread" / Int8ul,
        "unk_flag" / Int64ul,
    )
    def __str__(self):
        ts = self.timestamp / 24000000
        code = (self.channel, self.code, self.unk_flag)
        if code in TRACE_MSGS:
            info = TRACE_MSGS[code]
            args = info[0] + ": " + " ".join(f"{k}={v:#x}" for k, v in zip(info[1:], self.args) if k is not None)
        else:
            args = "UNK: " + ", ".join(hex(i) for i in self.args)
        return f"TRACE: [{ts:10.06f}][{self.THREADS[self.thread]:4s}] {self.channel:2x}:{self.code:2x} ({self.unk_flag}) {args}"

class FWCtlMsg(ConstructClass):
    subcon = Struct (
        "addr" / Int64ul,
        "unk_8" / Int32ul,
        "context_id" / Int32ul,
        "unk_10" / Int16ul,
        "unk_12" / Int16ul,
    )

channelNames = [
    "TA_0", "3D_0", "CL_0",
    "TA_1", "3D_1", "CL_1",
    "TA_2", "3D_2", "CL_2",
    "TA_3", "3D_3", "CL_3",
    "DevCtrl",
    "Event", "FWLog", "KTrace", "Stats",

    ## Not really in normal order
    "FWCtl"
]

# Exclude FWCtl
CHANNEL_COUNT = len(channelNames) - 1

channelRings = (
    [[(RunCmdQueueMsg, RunCmdQueueSize, 0x100)]] * 12 + [
        [(DeviceControlMsg, DeviceControlSize, 0x100)],
        [(EventMsg, 0x38, 0x100)],
        [
            (FWLogMsg, 0xd8, 0x100),                # unk 0
            (FWLogMsg, 0xd8, 0x100),                # init log
            (FWLogMsg, 0xd8, 0x100),                # unk 2
            (FWLogMsg, 0xd8, 0x100),                # warnings?
            (FWLogMsg, 0xd8, 0x100),                # unk 4
            (FWLogMsg, 0xd8, 0x100),                # unk 5
        ],
        [(KTraceMsg, 0x38, 0x200)],
        [(StatsMsg, StatsSize, 0x100)],
        [(FWCtlMsg, 0x14, 0x100)],
    ]
)

class ChannelStateFields(RegMap):
    _SIZE = 0x30

    READ_PTR = 0x00, Register32
    WRITE_PTR = 0x20, Register32

class FWControlStateFields(RegMap):
    _SIZE = 0x20

    READ_PTR = 0x00, Register32
    WRITE_PTR = 0x10, Register32

class Channel(Reloadable):
    def __init__(self, u, uat, info, ring_defs, base=None, state_fields=ChannelStateFields):
        self.uat = uat
        self.u = u
        self.p = u.proxy
        self.iface = u.iface

        self.ring_defs = ring_defs
        self.info = info

        self.accessor = uat.ioaccessor(0)
        self.state_addr = info.state_addr
        self.state = []
        self.rb_base = []
        self.rb_maps = []

        if base is None:
            p = info.ringbuffer_addr
        else:
            p = base
        for i, (msg, size, count) in enumerate(ring_defs):
            assert msg.sizeof() == size

            self.state.append(state_fields(self.accessor, self.state_addr + 0x30 * i))
            m = uat.iotranslate(0, p, size * count)
            self.rb_base.append(p)
            self.rb_maps.append(m)
            p += size * count

    def get_message(self, ring, index, meta_fn=None):
        msgcls, size, count = self.ring_defs[ring]

        assert index < count
        addr = self.rb_base[ring] + index * size
        stream = self.uat.iostream(0, addr)
        if meta_fn is not None:
            stream.meta_fn = lambda a, b: meta_fn(0, a, b)
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
    CHAN_COUNT = CHANNEL_COUNT

    subcon = Struct(*[ name / ChannelInfo for name in channelNames[:CHAN_COUNT]])

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
