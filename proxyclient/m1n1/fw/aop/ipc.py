from enum import IntEnum
from construct import *
from io import BytesIO

from m1n1.utils import FourCC, chexdump
from m1n1.constructutils import ZPadding
from m1n1.fw.afk.epic import EPICCmd, EPICCategory


EPICSubHeaderVer2 = Struct(
    "length" / Int32ul,
    "version" / Default(Int8ul, 2),
    "category" / EPICCategory,
    "type" / Hex(Int16ul),
    "timestamp" / Default(Int64ul, 0),
    "unk1" / Default(Hex(Int32ul), 0),
    "unk2" / Default(Hex(Int32ul), 0),
)

class AOPAudioPropKey(IntEnum):
    IS_READY = 0x01

    UNK_11 = 0x11
    PLACEMENT = 0x1e
    UNK_21 = 0x21
    ORIENTATION = 0x2e
    LOCATION_ID = 0x30
    SERIAL_NO = 0x3e
    VENDOR_ID = 0x5a
    PRODUCT_ID = 0x5b

    SERVICE_CONTROLLER = 0x64
    DEVICE_COUNT = 0x65

    VERSION = 0x67

class EPICCall:
    @classmethod
    def matches(cls, hdr, sub):
        return int(sub.type) == cls.TYPE

    def _args_fixup(self):
        pass

    def __init__(self, *args, **kwargs):
        if args:
            self.args = args[0]
        else:
            self.args = Container(**kwargs)
            self._args_fixup()
        self.rets = None

    @classmethod
    def from_stream(cls, f):
        return cls(cls.ARGS.parse_stream(f))

    def dump(self, logger=None):
        if logger is None:
            logger = print
        args_fmt = [f"{k}={v}" for (k, v) in self.args.items() if k != "_io"]
        rets_fmt = [f"{k}={v}" for (k, v) in self.rets.items() if k != "_io"]
        logger(f"{type(self).__name__}({', '.join(args_fmt)}) -> ({', '.join(rets_fmt)})")

    def read_resp(self, f):
        self.rets = self.RETS.parse_stream(f)

CALLTYPES = []
def reg_calltype(calltype):
    CALLTYPES.append(calltype)
    return calltype

@reg_calltype
class GetHIDDescriptor(EPICCall):
    TYPE = 0x1
    ARGS = Struct(
        "blank" / Const(0x0, Int32ul),
    )
    RETS = Struct(
        "retcode" / Default(Hex(Int32ul), 0),
        "descriptor" / HexDump(GreedyBytes),
    )

@reg_calltype
class GetProperty(EPICCall):
    TYPE = 0xa
    ARGS = Struct(
        "blank" / Const(0x0, Int32ul),
        "key" / Enum(Int32ul, AOPAudioPropKey),
    )
    RETS = Struct(
        #"blank" / Const(0x0, Int32ul),
        "value" / GreedyBytes,
    )

@reg_calltype
class WrappedCall(EPICCall):
    SUBCLASSES = {}
    TYPE = 0x20
    HDR = Struct(
        "blank" / Const(0x0, Int32ul),
        "unk1" / Hex(Const(0xffffffff, Int32ul)),
        "calltype" / Hex(Int32ul),
        "blank2" / ZPadding(16),
        "pad" / Hex(Int32ul),
        "len" / Hex(Int64ul),
        "residue" / HexDump(GreedyBytes),
    )

    @classmethod
    def from_stream(cls, f):
        payload = f.read()
        subsub = cls.HDR.parse(payload)
        calltype = int(subsub.calltype)
        subcls = cls.SUBCLASSES.get(calltype, None)
        if subcls is None:
            raise ValueError(f"unknown calltype {calltype:#x}")
        return subcls(subcls.ARGS.parse(payload))

    @classmethod
    def reg_subclass(cls, cls2):
        cls.SUBCLASSES[int(cls2.CALLTYPE)] = cls2
        return cls2

    @classmethod
    def matches(cls, hdr, sub):
        return sub.category == EPICCategory.NOTIFY and sub.type == cls.TYPE

    def check_retcode(self):
        if self.rets.retcode:
            self.dump()
            raise ValueError(f"retcode {self.rets.retcode} in {str(type(self))} (call dumped, see above)")

@WrappedCall.reg_subclass
class AttachDevice(WrappedCall):
    CALLTYPE = 0xc3_00_00_02
    ARGS = Struct(
        "blank" / Const(0x0, Int32ul),
        "unk1" / Hex(Const(0xffffffff, Int32ul)),
        "calltype" / Hex(Const(0xc3000002, Int32ul)),
        "blank2" / ZPadding(16),
        "pad" / Padding(4),
        "len" / Hex(Const(0x2c, Int64ul)),
        "devid" / FourCC,
        "pad" / Padding(4),
    )
    RETS = Struct(
        "retcode" / Default(Hex(Int32ul), 0),
        "unk" / HexDump(GreedyBytes),
    )

@WrappedCall.reg_subclass
class ProbeDevice(WrappedCall):
    CALLTYPE = 0xc3_00_00_01
    ARGS = Struct(
        "blank" / Const(0x0, Int32ul),
        "unk1" / Hex(Const(0xffffffff, Int32ul)),
        "calltype" / Hex(Const(0xc3000001, Int32ul)),
        "blank2" / ZPadding(16),
        "pad" / Padding(4),
        "len" / Hex(Const(0x28, Int64ul)),
        "devno" / Int32ul,
    )
    RETS = Struct(
        "retcode" / Default(Hex(Int32ul), 0),
        "devid" / FourCC,
        "blank2" / Const(0x0, Int32ul),
        "unk1" / Const(8, Int32ul),
        "blank3" / Const(0x0, Int32ul),
        "unk2" / Hex(Const(0x01_0d_1c_20, Int32ul)),
        "blank4" / Const(0x0, Int32ul),
        "remainder" / HexDump(GreedyBytes),
    )

PDMConfig = Struct(
    "unk1" / Int32ul,
    "clockSource" / FourCC,
    "pdmFrequency" / Int32ul,
    "unk3_clk" / Int32ul,
    "unk4_clk" / Int32ul,
    "unk5_clk" / Int32ul,
    "channelPolaritySelect" / Hex(Int32ul),
    "unk7" / Hex(Int32ul),
    "unk8" / Hex(Int32ul),
    "unk9" / Hex(Int16ul),
    "ratios" / Struct(
        "r1" / Int8ul,
        "r2" / Int8ul,
        "r3" / Int8ul,
        "pad" / Default(Int8ul, 0),
    ),
    "filterLengths" / Hex(Int32ul),
    "coeff_bulk" / Int32ul,
    #"coefficients" / Struct(
    #    "c1" / Int32sl[this._.ratios.r3 * 4 + 4],
    #    "c2" / Int32sl[this._.ratios.r2 * 4 + 4],
    #    "c3" / Int32sl[this._.ratios.r1 * 4 + 4],
    #),
    #"junk" / Padding(
    #    this.coeff_bulk * 4 - 48 \
    #    - (this.ratios.r1 + this.ratios.r2 + this.ratios.r3) * 16
    #),
    "coefficients" / Int32sl[
        (this.ratios.r1 + this.ratios.r2 + this.ratios.r3) * 4 + 12
    ],
    "junk" / Padding(
        lambda this: max(0,
            this.coeff_bulk * 4 - 48 \
            - (this.ratios.r1 + this.ratios.r2 + this.ratios.r3) * 16
        )
    ),
    "unk10" / Int32ul, # maybe
    "micTurnOnTimeMs" / Int32ul,
    "blank" / ZPadding(16),
    "unk11" / Int32ul,
    "micSettleTimeMs" / Int32ul,
    "blank2" / ZPadding(69),
)

DecimatorConfig = Struct(
    "latency" / Int32ul,
    "ratios" / Struct(
        "r1" / Int8ul,
        "r2" / Int8ul,
        "r3" / Int8ul,
        "pad" / Default(Int8ul, 0),
    ),
    "filterLengths" / Hex(Int32ul),
    "coeff_bulk" / Int32ul,
    "coefficients" / Int32sl[
        (this.ratios.r1 + this.ratios.r2 + this.ratios.r3) * 4 + 12
    ],
    "junk" / Padding(
        lambda this: max(0,
            this.coeff_bulk * 4 - 48 \
            - (this.ratios.r1 + this.ratios.r2 + this.ratios.r3) * 16
        )
    ),
)

PowerSetting = Struct(
    "devid" / FourCC,
    "cookie" / Int32ul,
    "pad" / Padding(4),
    "blank" / ZPadding(8),
    "target_pstate" / FourCC,
    "unk2" / Int32ul,
    "blank2" / ZPadding(20),
)

DEVPROPS = {
    ('hpai', 202): PowerSetting,
    ('lpai', 202): PowerSetting,
    ('hpai', 200): FourCC,
    ('lpai', 200): FourCC,
    ('pdm0', 200): PDMConfig,
    ('pdm0', 210): DecimatorConfig,
    ('lpai', 301): Struct(
        "unk1" / Int32ul,
        "unk2" / Int32ul,
        "unk3" / Int32ul,
        "unk4" / Int32ul,
    ),
}

@WrappedCall.reg_subclass
class GetDeviceProp(WrappedCall):
    CALLTYPE = 0xc3_00_00_04
    ARGS = Struct(
        "blank" / Const(0x0, Int32ul),
        "unk1" / Hex(Const(0xffffffff, Int32ul)),
        "calltype" / Hex(Const(0xc3000004, Int32ul)),
        "blank2" / ZPadding(16),
        "pad" / Padding(4),
        "len" / Hex(Const(0x30, Int64ul)),
        "devid" / FourCC,
        "modifier" / Int32ul,
        "unk6" / Hex(Const(0x01, Int32ul)),
    )
    RETS = Struct(
        "retcode" / Default(Hex(Int32ul), 0),
        "len" / Optional(Int32ul),
        "data" / Switch(lambda s: (s._params.devid, s._params.modifier),
            DEVPROPS,
        default=HexDump(GreedyBytes))
    )

    def read_resp(self, f):
        self.rets = self.RETS.parse_stream(f,
            devid=self.args.devid, modifier=self.args.modifier
        )

@WrappedCall.reg_subclass
class SetDeviceProp(WrappedCall):
    CALLTYPE = 0xc3_00_00_05
    ARGS = Struct(
        "blank" / Const(0x0, Int32ul),
        "unk1" / Hex(Const(0xffffffff, Int32ul)),
        "calltype" / Hex(Const(0xc3000005, Int32ul)),
        "blank2" / ZPadding(16),
        "pad" / Padding(4),
        "len" / Hex(Int64ul), # len(this.data) + 0x30
        "devid" / FourCC,
        "modifier" / Int32ul,
        "len2" / Hex(Int32ul), # len(this.data)
        "data" / Switch(lambda s: (s.devid, s.modifier),
            DEVPROPS,
        default=HexDump(GreedyBytes))
    )
    RETS = Struct(
        "retcode" / Default(Hex(Int32ul), 0),
        "unk" / HexDump(GreedyBytes),
    )

    def _args_fixup(self):
        data_len = len(self.ARGS.build(Container(len=0, len2=0, **self.args))) - 52
        if 'len' not in self.args:
            self.args.len = data_len + 0x30
        if 'len2' not in self.args:
            self.args.len2 = data_len

@reg_calltype
class IndirectCall(EPICCall):
    ARGS = EPICCmd
    RETS = EPICCmd

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.txbuf = None
        self.rxbuf = None

    @classmethod
    def matches(cls, hdr, sub):
        return sub.category == EPICCategory.COMMAND

    def read_txbuf(self, ep):
        cmd = self.args
        ep.dart.invalidate_cache()
        self.txbuf = ep.dart.ioread(0, cmd.txbuf, cmd.txlen)

        # dump the command data for offline replays of traces
        ep.log(f"===COMMAND TX DATA=== addr={cmd.txbuf:#x}")
        chexdump(self.txbuf)
        ep.log(f"===END DATA===")

    def read_rxbuf(self, ep):
        cmd = self.rets
        ep.dart.invalidate_cache()
        self.rxbuf = ep.dart.ioread(0, cmd.rxbuf, cmd.rxlen)

        ep.log(f"===COMMAND RX DATA=== addr={cmd.rxbuf:#x}")
        chexdump(self.rxbuf)
        ep.log(f"===END DATA===")

    def unwrap(self):
        fd = BytesIO()
        fd.write(b"\x00\x00\x00\x00")
        fd.write(self.txbuf)
        fd.seek(0)
        wrapped = WrappedCall.from_stream(fd)
        fd = BytesIO()
        fd.write(b"\x00\x00\x00\x00")
        fd.write(self.rxbuf)
        fd.seek(0)
        wrapped.read_resp(fd)
        return wrapped
