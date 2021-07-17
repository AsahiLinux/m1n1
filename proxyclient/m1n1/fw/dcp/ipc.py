# SPDX-License-Identifier: MIT

import pprint

from m1n1.utils import *
from construct import *

class Pointer(Subconstruct):
    pass

class InPtr(Pointer):
    pass

class OutPtr(Pointer):
    pass

class InOutPtr(Pointer):
    pass

class InOut(Subconstruct):
    pass

Ptr = InOutPtr

class Method:
    def __init__(self, rtype, name, *args, **kwargs):
        self.rtype = rtype
        self.name = name

        if args and kwargs:
            raise Exception("Cannot specify args and kwargs")
        elif args:
            args = [(f"arg{i}", arg) for i, arg in enumerate(args)]
        elif kwargs:
            args = list(kwargs.items())
        else:
            args = []

        self.args = args

        in_size = 0
        out_size = 0
        self.in_fields = []
        self.out_fields = []

        if rtype is not None:
            args.append(("ret", rtype))

        self.dir = []
        self.nullable = []

        for i, (name, field) in enumerate(self.args):
            align = 1

            pfield = field
            dir = "in"

            if name == "ret":
                dir = "out"

            while isinstance(pfield, Subconstruct):
                if isinstance(pfield, InPtr):
                    dir = "in"
                elif isinstance(pfield, OutPtr):
                    dir = "out"
                elif isinstance(pfield, (InOut, InOutPtr)):
                    dir = "inout"
                pfield = pfield.subcon
            if isinstance(pfield, FormatField):
                align = min(4, pfield.length)

            if dir in ("in", "inout"):
                #if in_size % align:
                    #self.in_fields.append(Padding(align - (in_size % align)))
                    #in_size += align - (in_size % align)

                self.in_fields.append(name / field)
                in_size += field.sizeof()

            if dir in ("out", "inout"):
                #if out_size % align:
                    #self.out_fields.append(Padding(align - (out_size % align)))
                    #out_size += align - (out_size % align)

                self.out_fields.append(name / field)
                out_size += field.sizeof()

            self.dir.append(dir)

        for i, (name, field) in enumerate(self.args):
            nullable = False
            pfield = field

            while isinstance(pfield, Subconstruct):
                if isinstance(pfield, Pointer):
                    nullable = True
                pfield = pfield.subcon

            if nullable:
                self.in_fields.append((name + "_null") / bool_)
                in_size += 1

            self.nullable.append(nullable)

        if in_size % 4:
            self.in_fields.append(Padding(4 - (in_size % 4)))
        if out_size % 4:
            self.out_fields.append(Padding(4 - (out_size % 4)))

        self.in_struct = Struct(*self.in_fields)
        self.out_struct = Struct(*self.out_fields)

    def fmt_args(self, in_vals, out_vals=None):
        s = []

        for i, (name, field) in enumerate(self.args):
            if name == "ret":
                continue

            dir = self.dir[i]
            nullable = self.nullable[i]

            if nullable:
                null = in_vals.get(name + "_null", None)
                if null is None:
                    s.append(f"{name}=?")
                    continue
                elif null:
                    s.append(f"{name}=NULL")
                    continue

            if out_vals and name in out_vals:
                if self.is_long(out_vals[name]):
                    s.append(f"{name}=...")
                elif isinstance(out_vals[name], ListContainer):
                    s.append(f"{name}={list(out_vals[name])!r}")
                else:
                    s.append(f"{name}={out_vals[name]!r}")
            elif dir == "out":
                s.append(f"{name}=<out>")
            elif name in in_vals:
                if self.is_long(in_vals[name]):
                    s.append(f"{name}=...")
                elif isinstance(in_vals[name], ListContainer):
                    s.append(f"{name}={list(in_vals[name])!r}")
                else:
                    s.append(f"{name}={in_vals[name]!r}")
            else:
                s.append(f"{name}=?")

        return ", ".join(s)

    def print_long_args(self, indent, in_vals, out_vals=None):
        for i, (name, field) in enumerate(self.args):
            if name == "ret":
                continue

            dir = self.dir[i]

            if self.nullable[i] and in_vals.get(name + "_null", None):
                continue

            if out_vals and name in out_vals:
                val = out_vals[name]
            elif out_vals:
                continue
            elif name in in_vals:
                val = in_vals[name]
            else:
                continue

            if self.is_long(val):
                hdr = f"{indent}  {name} = "
                if isinstance(val, (ListContainer, Container)):
                    print(hdr + str(val).replace("\n", "\n" + indent))
                elif isinstance(val, bytes):
                    print(hdr + f"({len(val):#x} bytes)")
                    chexdump(val, indent=indent + "    ")
                else:
                    dindent = " " * len(hdr)
                    if isinstance(val, dict) and "_io" in val:
                        del val["_io"]
                    print(hdr + pprint.pformat(val, sort_dicts=False).replace("\n", "\n" + dindent))

    def is_long(self, arg):
        if isinstance(arg, (list, bytes)):
            return len(arg) > 4

        return isinstance(arg, (dict, list, bytes))

    def parse_input(self, data):
        vals = self.in_struct.parse(data)

        return Container({ k: v() if callable(v) else v for k,v in vals.items() })

    def parse_output(self, data, in_vals):
        context = dict(in_vals)

        if "data" in context:
            del context["data"]

        vals = self.out_struct.parse(data, **context)

        return Container({ k: v() if callable(v) else v for k,v in vals.items() })

def dump_fields(fields):
    off = 0
    for f in fields:
        sizeof = f.sizeof()
        print(f"{off:#x}: {f} ({sizeof:#x})")
        off += sizeof

class Call(Method):
    pass

class Callback(Method):
    pass

int8_t = Int8sl
uint8_t = Int8ul
int16_t = Int16sl
uint16_t = Int16ul
int32_t = Int32sl
uint32_t = Int32ul
int64_t = Int64sl
uint64_t = Int64ul

uint = uint32_t
int_ = int32_t
ulong = uint64_t
long_ = int64_t

def Bool(c):
    return ExprAdapter(c, lambda d, ctx: bool(d & 1), lambda d, ctx: int(d))

def SizedArray(count, svar, subcon):
    return Lazy(Padded(subcon.sizeof() * count, Array(lambda ctx: ctx.get(svar) or ctx._.get(svar), subcon)))

def SizedBytes(count, svar):
    return Lazy(Padded(count, Bytes(lambda ctx: ctx.get(svar) or ctx._.get(svar))))

bool_ = Bool(int8_t)

class OSObject(Construct):
    TYPE = None

    def _parse(self, stream, context, path, recurse=False):
        tag = stream.read(1).decode("ascii")
        if not recurse and self.TYPE is not None and self.TYPE != tag:
            raise Exception("Object type mismatch")

        if tag == "d":
            count = Int32ul.parse_stream(stream)
            d = {}
            for i in range(count):
                k = self._parse(stream, context, path, True)
                v = self._parse(stream, context, path, True)
                d[k] = v
            return d
        elif tag == "n":
            return Int64ul.parse_stream(stream)
        elif tag == "s":
            length = Int32ul.parse_stream(stream)
            s = stream.read(length).decode("utf-8")
            assert stream.read(1) == b'\0'
            return s
        else:
            raise Exception(f"Unknown object tag {tag!r}")

    def _build(self, obj, stream, context, path):
        assert False

    def _sizeof(self, context, path):
        return None

class OSDictionary(OSObject):
    TYPE = 'd'

FourCC = ExprAdapter(uint32_t,
                     lambda d, ctx: d.to_bytes(4, "big").decode("ascii"),
                     lambda d, ctx: int.from_bytes(d.encode("ascii"), "big"))

void = None

def string(size):
    return Padded(size, CString("utf8"))

class IPCObject:
    @classmethod
    def methods(cls):
        ret = {}
        for c in cls.mro():
            ret.update({k: (cls, v) for k, v in cls.__dict__.items() if isinstance(v, Method)})

        return ret

rt_bw_config_t = Struct(
    "data" / HexDump(Bytes(0x3c)),
)

IOUserClient = Struct(
    "addr" / Hex(Int64ul),
    "unk" / Int32ul,
    "flag1" / Int8ul,
    "flag2" / Int8ul,
    Padding(2)
)

IOMFBStatus = Int32ul
IOMFBParameterName = Int32ul

BufferDescriptor = uint64_t

SwapCompleteData = Bytes(0x12)
SwapInfoBlob = Bytes(0x600)

IOMFBSwapRec = Bytes(0x274)
IOSurface = Bytes(0x204)

class UPPipeAP_H13P(IPCObject):
    A000 = Call(uint32_t, "late_init_signal")
    A029 = Call(void, "setup_video_limits")
    A034 = Call(void, "update_notify_clients_dcp", Array(11, uint))
    A036 = Call(bool_, "apt_supported")

    D000 = Callback(bool_, "did_boot_signal")
    D001 = Callback(bool_, "did_power_on_signal")
    D002 = Callback(void, "will_power_off_signal")
    D003 = Callback(void, "rt_bandwidth_setup_ap", config=OutPtr(rt_bw_config_t))

class UnifiedPipeline2(IPCObject):
    A357 = Call(void, "set_create_DFB")

    D100 = Callback(void, "match_pmu_service")
    D101 = Callback(uint32_t, "UNK_get_some_field")
    D103 = Callback(void, "set_boolean_property", key=string(0x40), value=bool_)
    D106 = Callback(void, "removeProperty", key=string(0x40))
    D107 = Callback(bool_, "create_provider_service")
    D108 = Callback(bool_, "create_product_service")
    D109 = Callback(bool_, "create_PMU_service")
    D110 = Callback(bool_, "create_iomfb_service")
    D111 = Callback(bool_, "create_backlight_service")
    D116 = Callback(bool_, "start_hardware_boot")
    D119 = Callback(bool_, "read_edt_data", key=string(0x40), count=uint, value=InOut(SizedArray(8, "count", uint32_t)))

    D121 = Callback(bool_, "setDCPAVPropStart", length=uint)
    D122 = Callback(bool_, "setDCPAVPropChunk", data=HexDump(SizedBytes(0x1000, "length")), offset=uint, length=uint)
    D123 = Callback(bool_, "setDCPAVPropEnd", key=string(0x40))

class UPPipe2(IPCObject):
    A103 = Call(uint64_t, "test_control", cmd=uint64_t, arg=uint)

    D201 = Callback(uint32_t, "map_buf", InPtr(BufferDescriptor), OutPtr(ulong), OutPtr(ulong), bool_)

    D206 = Callback(bool_, "match_pmu_service")
    D207 = Callback(bool_, "match_backlight_service")
    D208 = Callback(uint64_t, "get_calendar_time_ms")

class PropRelay(IPCObject):
    D300 = Callback(void, "publish", prop_id=uint32_t, value=int_)

class IOMobileFramebufferAP(IPCObject):
    A401 = Call(uint32_t, "start_signal")

    A407 = Call(uint32_t, "swap_start", InOutPtr(uint), InOutPtr(IOUserClient))
    A408 = Call(uint32_t, "swap_submit_dcp",
                swap_rec=InPtr(IOMFBSwapRec),
                surf0=InPtr(IOSurface),
                surf1=InPtr(IOSurface),
                surf2=InPtr(IOSurface),
                surfInfo=Array(3, uint),
                unkBool=bool_,
                unkFloat=Float64l,
                unkInt=uint,
                unkOutBool=OutPtr(bool_))

    A410 = Call(uint32_t, "set_display_device", uint)
    A412 = Call(uint32_t, "set_digital_out_mode", uint, uint)
    A419 = Call(uint32_t, "get_gamma_table", InOutPtr(Bytes(0xc0c)))
    A422 = Call(uint32_t, "set_matrix", uint, InPtr(Array(3, Array(3, ulong))))
    A423 = Call(uint32_t, "set_contrast", InOutPtr(Float32l))
    A426 = Call(uint32_t, "get_color_remap_mode", InOutPtr(uint32_t))
    A427 = Call(uint32_t, "setBrightnessCorrection", uint)

    A435 = Call(uint32_t, "set_block_dcp", arg1=uint64_t, arg2=uint, arg3=uint, arg4=Array(8, ulong), arg5=uint, data=SizedBytes(0x1000, "length"), length=ulong)
    A438 = Call(uint32_t, "set_parameter_dcp", param=IOMFBParameterName, value=SizedArray(4, "count", ulong), count=uint)

    A441 = Call(void, "get_display_size", OutPtr(uint), OutPtr(uint))
    A442 = Call(int_, "do_create_default_frame_buffer")
    A446 = Call(int_, "enable_disable_video_power_savings", uint)
    A453 = Call(void, "first_client_open")
    A455 = Call(bool_, "writeDebugInfo", ulong)
    A459 = Call(bool_, "setDisplayRefreshProperties")
    A462 = Call(void, "flush_supportsPower", bool_)
    A467 = Call(uint32_t, "setPowerState", ulong, bool_, OutPtr(uint))
    A468 = Call(bool_, "isKeepOnScreen")

    D552 = Callback(bool_, "setProperty<OSDictionary>", key=string(0x40), value=InPtr(Padded(0x1000, OSDictionary())))
    D561 = Callback(bool_, "setProperty<OSDictionary>", key=string(0x40), value=InPtr(Padded(0x1000, OSDictionary())))
    D563 = Callback(bool_, "setProperty<OSNumber>", key=string(0x40), value=InPtr(uint64_t))
    D565 = Callback(bool_, "setProperty<OSBoolean>", key=string(0x40), value=InPtr(Bool(uint32_t)))
    D567 = Callback(bool_, "setProperty<AFKString>", key=string(0x40), value=string(0x40))

    D574 = Callback(IOMFBStatus, "powerUpDART", bool_)

    D576 = Callback(void, "hotPlug_notify_gated", ulong)
    D577 = Callback(void, "powerstate_notify", bool_, bool_)

    D583 = Callback(bool_, "serializeDebugInfoCb", ulong, InPtr(uint64_t), uint)

    D589 = Callback(void, "swap_complete_ap_gated", uint, bool_, InPtr(SwapCompleteData), SwapInfoBlob, uint)

    D591 = Callback(void, "swap_complete_intent_gated", uint, bool_, uint32_t, uint, uint)
    D598 = Callback(void, "find_swap_function_gated")

class ServiceRelay(IPCObject):
    D401 = Callback(bool_, "get_uint_prop", obj=FourCC, key=string(0x40), value=InOutPtr(ulong))
    D408 = Callback(uint64_t, "getClockFrequency", uint, uint)
    D411 = Callback(IOMFBStatus, "mapDeviceMemoryWithIndex", uint, uint, uint, OutPtr(ulong), OutPtr(ulong))
    D413 = Callback(bool_, "setProperty<OSDictionary>", obj=FourCC, key=string(0x40), value=InPtr(Padded(0x1000, OSDictionary())))
    D414 = Callback(bool_, "setProperty<OSNumber>", obj=FourCC, key=string(0x40), value=InPtr(uint64_t))
    D415 = Callback(bool_, "setProperty<OSBoolean>", obj=FourCC, key=string(0x40), value=InPtr(Bool(uint32_t)))

class MemDescRelay(IPCObject):
    D451 = Callback(uint, "allocate_buffer", uint, ulong, uint, OutPtr(ulong), OutPtr(ulong), OutPtr(ulong))
    D452 = Callback(uint, "map_physical", ulong, ulong, uint, OutPtr(ulong), OutPtr(ulong))

ALL_CLASSES = [
    UPPipeAP_H13P,
    UnifiedPipeline2,
    IOMobileFramebufferAP,
    ServiceRelay,
    PropRelay,
    UPPipe2,
    MemDescRelay,
]

ALL_METHODS = {}

for cls in ALL_CLASSES:
    ALL_METHODS.update(cls.methods())

SHORT_CHANNELS = {
    "CB": "d",
    "CMD": "C",
    "ASYNC": "a",
    "OOB": "O",
}

RDIR = { ">": "<", "<": ">" }

class Call:
    def __init__(self, dir, chan, off, msg, in_size, out_size, in_data=b''):
        self.dir = dir
        self.chan = chan
        self.msg = msg
        self.off = off
        self.in_size = in_size
        self.out_size = out_size
        self.in_data = in_data
        self.out_data = None
        self.complete = False
        self.ret = None

    def ack(self, out_data):
        self.out_data = out_data
        self.complete = True

    def print_req(self, indent=""):
        log = f"{indent}{self.dir}{SHORT_CHANNELS[self.chan]}[{self.off:#x}] {self.msg} "

        cls, method = ALL_METHODS.get(self.msg, (None, None))
        if cls is None:
            print(log + f"{self.in_size:#x}/{self.out_size:#x}")
            return

        log += f"{cls.__name__}::{method.name}("
        in_size = method.in_struct.sizeof()

        if in_size != len(self.in_data):
            print(f"{log} !! Expected {in_size:#x} bytes, got {len(self.in_data):#x} bytes (in)")
            dump_fields(method.in_fields)
            chexdump(self.in_data)
            self.in_vals = {}
            return

        self.in_vals = method.parse_input(self.in_data)

        log += f"{method.fmt_args(self.in_vals)})"

        print(log)

        method.print_long_args(indent, self.in_vals)
        #if method.in_fields:
            #print(self.in_vals)

    def print_reply(self, indent=""):
        assert self.complete
        log = f"{indent}{RDIR[self.dir]}{SHORT_CHANNELS[self.chan]}[{self.off:#x}] {self.msg} "

        cls, method = ALL_METHODS.get(self.msg, (None, None))
        if cls is None:
            print(log + f"{self.in_size:#x}/{self.out_size:#x}")
            return

        log += f"{cls.__name__}::{method.name}("
        out_size = method.out_struct.sizeof()

        if out_size != len(self.out_data):
            print(f"{log} !! Expected {out_size:#x} bytes, got {len(self.out_data):#x} bytes (out)")
            dump_fields(method.out_fields)
            chexdump(self.out_data)
            return

        self.out_vals = method.parse_output(self.out_data, self.in_vals)

        log += f"{method.fmt_args(self.in_vals, self.out_vals)})"

        if "ret" in self.out_vals:
            self.ret = self.out_vals.ret
            del self.out_vals["ret"]
            log += f" = {self.ret!r}"

        print(log)

        method.print_long_args(indent, self.in_vals, self.out_vals)
        #if len(method.out_fields) - (self.ret is not None):
            #print(self.out_vals)
