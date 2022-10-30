# SPDX-License-Identifier: MIT

from dataclasses import dataclass
import pprint
from enum import IntEnum

from ..common import *
from m1n1.utils import *
from construct import *

@dataclass
class ByRef:
    val: object

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

class NULL:
    def __str__(self):
        return "NULL"
    def __repr__(self):
        return "NULL"
NULL = NULL()

class Method:
    def __init__(self, rtype, name, *args, **kwargs):
        self.rtype = rtype
        self.name = name

        if args and kwargs:
            raise Exception("Cannot specify args and kwargs")
        elif args:
            args = [(f"arg{i}", arg) for i, arg in enumerate(args)]
            self.as_kwargs = False
        elif kwargs:
            args = list(kwargs.items())
            self.as_kwargs = True
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
        self.array_of_p = []

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
            array_size = None
            array_of_p = False
            nullable = False
            pfield = field

            while isinstance(pfield, Subconstruct):
                if isinstance(pfield, Array) and array_size is None:
                    array_size = pfield.count
                if isinstance(pfield, Pointer):
                    nullable = True
                    array_of_p = array_size is not None
                pfield = pfield.subcon

            if nullable:
                if array_of_p:
                    self.in_fields.append((name + "_null") / bool_[array_size])
                    in_size += array_size
                else:
                    self.in_fields.append((name + "_null") / bool_)
                    in_size += 1

            self.nullable.append(nullable)
            self.array_of_p.append(array_of_p)

        if in_size % 4:
            self.in_fields.append(Padding(4 - (in_size % 4)))
        if out_size % 4:
            self.out_fields.append(Padding(4 - (out_size % 4)))

        self.in_struct = Struct(*self.in_fields)
        self.out_struct = Struct(*self.out_fields)

    def get_field_val(self, i, in_vals, out_vals=None, nullobj=None):
        name, field = self.args[i]

        nullable = self.nullable[i]
        array_of_p = self.array_of_p[i]

        val = None

        if out_vals:
            val = out_vals.get(name, val)
        if val is None and in_vals:
            val = in_vals.get(name, val)

        if nullable and val is not None:
            null = in_vals.get(name + "_null", None)
            if null is None:
                return None
            if not array_of_p:
                val = nullobj if null else val
            else:
                val2 = [nullobj if n else val for val, n in zip(val, null)]
                if isinstance(val, ListContainer):
                    val2 = ListContainer(val2)
                val = val2

        return val

    def fmt_args(self, in_vals, out_vals=None):
        s = []

        for i, (name, field) in enumerate(self.args):
            if name == "ret":
                continue

            dir = self.dir[i]
            nullable = self.nullable[i]

            val = self.get_field_val(i, in_vals, out_vals, nullobj=NULL)

            if val is not None:
                if self.is_long(val):
                    s.append(f"{name}=...")
                elif isinstance(val, ListContainer):
                    s.append(f"{name}={list(val)!r}")
                else:
                    s.append(f"{name}={val!r}")
            elif dir == "out":
                s.append(f"{name}=<out>")
            else:
                s.append(f"{name}=?")

        return ", ".join(s)

    def print_long_args(self, indent, in_vals, out_vals=None):
        for i, (name, field) in enumerate(self.args):
            if name == "ret":
                continue

            val = self.get_field_val(i, in_vals, out_vals, nullobj=NULL)

            if name in in_vals and out_vals is not None and name not in out_vals:
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
            return len(arg) > 4 or any(self.is_long(i) for i in arg)

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

    def __str__(self):
        if self.rtype is None:
            rtype = "void"
        else:
            rtype = str(self.rtype)

        args = []
        for name, field in self.args:
            if name == "ret":
                continue
            args.append(f"{field} {name}")

        return f"{rtype} {self.name}({', '.join(args)})"

    def callback(self, func, in_data):
        in_vals = self.parse_input(in_data)

        args = []
        kwargs = {}

        out_vals = {}

        for i, (name, field) in enumerate(self.args):
            if name == "ret":
                continue

            dir = self.dir[i]

            val = self.get_field_val(i, in_vals, out_vals, nullobj=NULL)
            is_null = val is NULL
            if is_null:
                val = None

            if dir == "inout":
                if val is not None and not isinstance(val, list):
                    val = ByRef(val)
                out_vals[name] = val
            elif dir == "out" and not is_null:
                val = ByRef(None)
                out_vals[name] = val

            if self.as_kwargs:
                kwargs[name] = val
            else:
                args.append(val)

        retval = func(*args, **kwargs)

        if self.rtype is None:
            assert retval is None
        else:
            assert retval is not None
            out_vals["ret"] = retval

        out_vals = {k: v.val if isinstance(v, ByRef) else v for k, v in out_vals.items()}

        context = dict(in_vals)

        if "obj" in context:
            del context["obj"]

        out_data = self.out_struct.build(out_vals, **context)
        return out_data


    def call(self, call, *args, **kwargs):
        if args and kwargs:
            raise Exception("Cannot use both args and kwargs")

        if args:
            for arg, (name, field) in zip(args, self.args):
                kwargs[name] = arg

        in_vals = {}
        out_refs = {}

        for i, (name, field) in enumerate(self.args):
            if name == "ret":
                continue

            val = kwargs[name]
            dir = self.dir[i]
            nullable = self.nullable[i]
            array_of_p = self.array_of_p[i]

            if nullable:
                if not array_of_p:
                    in_vals[name + "_null"] = val is None
                else:
                    defaults = field.parse(b"\x00" * field.sizeof())
                    in_vals[name + "_null"] = [i is None for i in val]
                    val = [v if v is not None else defaults[i] for i, v in enumerate(val)]
            else:
                assert val is not None

            if val is None:
                continue

            if dir == "out":
                assert isinstance(val, ByRef)
                out_refs[name] = val
            elif dir == "inout":
                if isinstance(val, ByRef):
                    in_vals[name] = val.val
                    out_refs[name] = val
                elif val is not None:
                    in_vals[name] = val
            elif val is not None:
                in_vals[name] = val

        in_data = self.in_struct.build(in_vals)
        print(f"{self.name}({self.fmt_args(in_vals)})")

        out_data = call(in_data)
        out_vals = self.parse_output(out_data, in_vals)

        for k, v in out_refs.items():
            v.val = out_vals[k]

        if self.rtype is not None:
            return out_vals["ret"]

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

void = None

class IPCObject:
    @classmethod
    def methods(cls):
        ret = {}
        for c in cls.mro():
            ret.update({k: (cls, v) for k, v in cls.__dict__.items() if isinstance(v, Method)})

        return ret

rt_bw_config_t = Struct(
    "unk1" / UnkBytes(8),
    "reg1" / Int64ul,
    "reg2" / Int64ul,
    "unk2" / UnkBytes(4),
    "bit" / Int32ul,
    "padding" / UnkBytes(0x1c),
)

IOUserClient = Struct(
    "addr" / Hex(Int64ul),
    "unk" / Int32ul,
    "flag1" / Int8ul,
    "flag2" / Int8ul,
    Padding(2)
)

IOMobileFramebufferUserClient = IOUserClient

IOMFBStatus = Int32ul
IOMFBParameterName = Int32ul

BufferDescriptor = uint64_t

SwapCompleteData = Bytes(0x12)
SwapInfoBlob = Bytes(0x6c4)

SWAP_SURFACES = 4

Rect = NamedTuple("rect", "x y w h", Int32ul[4])

IOMFBSwapRec = Struct(
    "ts1" / Default(Int64ul, 0),
    "ts2" / Default(Int64ul, 0),
    "unk_10" / Default(Int64ul, 0),
    "unk_18" / Default(Int64ul, 0),
    "ts64_unk" / Default(Int64ul, 0),
    "unk_28" / Default(Int64ul, 0),
    "ts3" / Default(Int64ul, 0),
    "unk_38" / Default(Int64ul, 0),
    "flags1" / Hex(Int64ul),
    "flags2" / Hex(Int64ul),
    "swap_id" / Int32ul,
    "surf_ids" / Int32ul[SWAP_SURFACES],
    "src_rect" / Rect[SWAP_SURFACES],
    "surf_flags" / Int32ul[SWAP_SURFACES],
    "surf_unk" / Int32ul[SWAP_SURFACES],
    "dst_rect" / Rect[SWAP_SURFACES],
    "swap_enabled" / Hex(Int32ul),
    "swap_completed" / Hex(Int32ul),
    "unk_10c" / Hex(Default(Int32ul, 0)),
    "unk_110" / UnkBytes(0x1b8),
    "unk_2c8" / Hex(Default(Int32ul, 0)),
    "unk_2cc" / UnkBytes(0x14),
    "unk_2e0" / Hex(Default(Int32ul, 0)),
    "unk_2e2" / UnkBytes(0x2),
    "bl_unk" / Hex(Int64ul), # seen: 0x0, 0x1, 0x101, 0x1_0000, 0x101_010101
    "bl_val" / Hex(Int32ul), # range 0x10000000 - approximately 0x7fe07fc0 for 4 - 510 nits
    "bl_power" / Hex(Int8ul), # constant 0x40, 0x00: backlight off
    "unk_2f3" / UnkBytes(0x2d),
)

assert IOMFBSwapRec.sizeof() == 0x320

MAX_PLANES = 3

ComponentTypes = Struct(
    "count" / Int8ul,
    "types" / SizedArray(7, "count", Int8ul),
)

#ComponentTypes = Bytes(8)

PlaneInfo = Struct(
    "width" / Int32ul,
    "height" / Int32ul,
    "base" / Hex(Int32ul),
    "offset" / Hex(Int32ul),
    "stride" / Hex(Int32ul),
    "size" / Hex(Int32ul),
    "tile_size" / Int16ul,
    "tile_w" / Int8ul,
    "tile_h" / Int8ul,
    "unk1" / UnkBytes(0xd),
    "unk2" / Hex(Int8ul),
    "unk3" / UnkBytes(0x26),
)

assert PlaneInfo.sizeof() == 0x50

IOSurface = Struct(
    "is_tiled" / bool_,
    "unk_1" / bool_,
    "unk_2" / bool_,
    "plane_cnt" / Int32ul,
    "plane_cnt2" / Int32ul,
    "format" / FourCC,
    "unk_f" / Default(Hex(Int32ul), 0),
    "xfer_func" / Int8ul,
    "colorspace" / Int8ul,
    "stride" / Int32ul,
    "pix_size" / Int16ul,
    "pel_w" / Int8ul,
    "pel_h" / Int8ul,
    "offset" / Default(Hex(Int32ul), 0),
    "width" / Int32ul,
    "height" / Int32ul,
    "buf_size" / Hex(Int32ul),
    "unk_2d" / Default(Int32ul, 0),
    "unk_31" / Default(Int32ul, 0),
    "surface_id" / Int32ul,
    "comp_types" / Default(SizedArray(MAX_PLANES, "plane_cnt", ComponentTypes), []),
    "has_comp" / Bool(Int64ul),
    "planes" / Default(SizedArray(MAX_PLANES, "plane_cnt", PlaneInfo), []),
    "has_planes" / Bool(Int64ul),
    "compression_info" / Default(SizedArray(MAX_PLANES, "plane_cnt", UnkBytes(0x34)), []),
    "has_compr_info" / Bool(Int64ul),
    "unk_1f5" / Int32ul,
    "unk_1f9" / Int32ul,
    "padding" / UnkBytes(7),
)

assert IOSurface.sizeof() == 0x204

IOMFBColorFixedMatrix = Array(5, Array(3, ulong))

class PropID(IntEnum):
    BrightnessCorrection = 14

class UPPipeAP_H13P(IPCObject):
    A000 = Call(bool_, "late_init_signal")
    A029 = Call(void, "setup_video_limits")
    A034 = Call(void, "update_notify_clients_dcp", Array(14, uint))
    A035 = Call(bool_, "is_hilo")
    A036 = Call(bool_, "apt_supported")
    A037 = Call(uint, "get_dfb_info", InOutPtr(uint), InOutPtr(Array(4, ulong)), InOutPtr(uint))
    A038 = Call(uint, "get_dfb_compression_info", InOutPtr(uint))

    D000 = Callback(bool_, "did_boot_signal")
    D001 = Callback(bool_, "did_power_on_signal")
    D002 = Callback(void, "will_power_off_signal")
    D003 = Callback(void, "rt_bandwidth_setup_ap", config=OutPtr(rt_bw_config_t))

IdleCachingState = uint32_t

class UnifiedPipeline2(IPCObject):
    A352 = Call(bool_, "applyProperty", uint, uint)
    A353 = Call(uint, "get_system_type")
    A357 = Call(void, "set_create_DFB")
    A358 = Call(IOMFBStatus, "vi_set_temperature_hint")

    D100 = Callback(void, "match_pmu_service")
    D101 = Callback(uint32_t, "UNK_get_some_field")
    D102 = Callback(void, "set_number_property", key=string(0x40), value=uint)
    D103 = Callback(void, "set_boolean_property", key=string(0x40), value=bool_)
    D106 = Callback(void, "removeProperty", key=string(0x40))
    D107 = Callback(bool_, "create_provider_service")
    D108 = Callback(bool_, "create_product_service")
    D109 = Callback(bool_, "create_PMU_service")
    D110 = Callback(bool_, "create_iomfb_service")
    D111 = Callback(bool_, "create_backlight_service")
    D112 = Callback(void, "set_idle_caching_state_ap", IdleCachingState, uint)
    D116 = Callback(bool_, "start_hardware_boot")
    D117 = Callback(bool_, "is_dark_boot")
    D118 = Callback(bool_, "is_waking_from_hibernate")
    D120 = Callback(bool_, "read_edt_data", key=string(0x40), count=uint, value=InOut(Lazy(SizedArray(8, "count", uint32_t))))

    D122 = Callback(bool_, "setDCPAVPropStart", length=uint)
    D123 = Callback(bool_, "setDCPAVPropChunk", data=HexDump(SizedBytes(0x1000, "length")), offset=uint, length=uint)
    D124 = Callback(bool_, "setDCPAVPropEnd", key=string(0x40))

class UPPipe2(IPCObject):
    A102 = Call(uint64_t, "test_control", cmd=uint64_t, arg=uint)
    A103 = Call(void, "get_config_frame_size", width=InOutPtr(uint), height=InOutPtr(uint))
    A104 = Call(void, "set_config_frame_size", width=uint, height=uint)
    A105 = Call(void, "program_config_frame_size")
    A130 = Call(bool_, "init_ca_pmu")
    A131 = Call(bool_, "pmu_service_matched")
    A132 = Call(bool_, "backlight_service_matched")

    D201 = Callback(uint32_t, "map_buf", buf=InPtr(BufferDescriptor), vaddr=OutPtr(ulong), dva=OutPtr(ulong), unk=bool_)
    D202 = Callback(void, "unmap_buf", buf=InPtr(BufferDescriptor), unk1=uint, unk2=ulong, unkB=uint)

    D206 = Callback(bool_, "match_pmu_service_2")
    D207 = Callback(bool_, "match_backlight_service")
    D208 = Callback(uint64_t, "get_calendar_time_ms")
    D211 = Callback(void, "update_backlight_factor_prop", int_)

class PropRelay(IPCObject):
    D300 = Callback(void, "pr_publish", prop_id=uint32_t, value=int_)

class IOMobileFramebufferAP(IPCObject):
    A401 = Call(uint32_t, "start_signal")

    A407 = Call(uint32_t, "swap_start", swap_id=InOutPtr(uint), client=InOutPtr(IOUserClient))
    A408 = Call(uint32_t, "swap_submit_dcp",
                swap_rec=InPtr(IOMFBSwapRec),
                surfaces=Array(4, InPtr(IOSurface)),
                surfAddr=Array(4, Hex(ulong)),
                unkBool=bool_,
                unkFloat=Float64l,
                unkInt=uint,
                unkOutBool=OutPtr(bool_))

    A410 = Call(uint32_t, "set_display_device", uint)
    A411 = Call(bool_, "is_main_display")
    A438 = Call(uint32_t, "swap_set_color_matrix", matrix=InOutPtr(IOMFBColorFixedMatrix), func=uint32_t, unk=uint)
#"A438": "IOMobileFramebufferAP::swap_set_color_matrix(IOMFBColorFixedMatrix*, IOMFBColorMatrixFunction, unsigned int)",

    A412 = Call(uint32_t, "set_digital_out_mode", uint, uint)
    A413 = Call(uint32_t, "get_digital_out_state", InOutPtr(uint))
    A414 = Call(uint32_t, "get_display_area", InOutPtr(ulong))
    A419 = Call(uint32_t, "get_gamma_table", InOutPtr(Bytes(0xc0c)))
    A422 = Call(uint32_t, "set_matrix", uint, InPtr(Array(3, Array(3, ulong))))
    A423 = Call(uint32_t, "set_contrast", InOutPtr(Float32l))
    A426 = Call(uint32_t, "get_color_remap_mode", InOutPtr(uint32_t))
    A427 = Call(uint32_t, "setBrightnessCorrection", uint)

    A435 = Call(uint32_t, "set_block_dcp", arg1=uint64_t, arg2=uint, arg3=uint, arg4=Array(8, ulong), arg5=uint, data=SizedBytes(0x1000, "length"), length=ulong)
    A439 = Call(uint32_t, "set_parameter_dcp", param=IOMFBParameterName, value=Lazy(SizedArray(4, "count", ulong)), count=uint)

    A440 = Call(uint, "display_width")
    A441 = Call(uint, "display_height")
    A442 = Call(void, "get_display_size", OutPtr(uint), OutPtr(uint))
    A443 = Call(int_, "do_create_default_frame_buffer")
    A444 = Call(void, "printRegs")
    A447 = Call(int_, "enable_disable_video_power_savings", uint)
    A454 = Call(void, "first_client_open")
    A455 = Call(void, "last_client_close_dcp", OutPtr(uint))
    A456 = Call(bool_, "writeDebugInfo", ulong)
    A457 = Call(void, "flush_debug_flags", uint)
    A458 = Call(bool_, "io_fence_notify", uint, uint, ulong, IOMFBStatus)
    A460 = Call(bool_, "setDisplayRefreshProperties")
    A463 = Call(void, "flush_supportsPower", bool_)
    A464 = Call(uint, "abort_swaps_dcp", InOutPtr(IOMobileFramebufferUserClient))

    A467 = Call(uint, "update_dfb", surf=InPtr(IOSurface))
    A468 = Call(uint32_t, "setPowerState", ulong, bool_, OutPtr(uint))
    A469 = Call(bool_, "isKeepOnScreen")

    D552 = Callback(bool_, "setProperty_dict", key=string(0x40), value=InPtr(Padded(0x1000, OSDictionary())))
    D561 = Callback(bool_, "setProperty_dict", key=string(0x40), value=InPtr(Padded(0x1000, OSDictionary())))
    D563 = Callback(bool_, "setProperty_int", key=string(0x40), value=InPtr(uint64_t))
    D565 = Callback(bool_, "setProperty_bool", key=string(0x40), value=InPtr(Bool(uint32_t)))
    D567 = Callback(bool_, "setProperty_str", key=string(0x40), value=string(0x40))

    D574 = Callback(IOMFBStatus, "powerUpDART", bool_)

    D575 = Callback(bool_, "get_dot_pitch", OutPtr(uint))
    D576 = Callback(void, "hotPlug_notify_gated", ulong)
    D577 = Callback(void, "powerstate_notify", bool_, bool_)
    D578 = Callback(bool_, "idle_fence_create", IdleCachingState)
    D579 = Callback(void, "idle_fence_complete")

    D581 = Callback(void, "swap_complete_head_of_line", uint, bool_, uint, bool_)
    D582 = Callback(bool_, "create_default_fb_surface", uint, uint)
    D583 = Callback(bool_, "serializeDebugInfoCb", ulong, InPtr(uint64_t), uint)
    D584 = Callback(void, "clear_default_surface")

    D588 = Callback(void, "resize_default_fb_surface_gated")
    D589 = Callback(void, "swap_complete_ap_gated", swap_id=uint, unkBool=bool_, swap_data=InPtr(SwapCompleteData), swap_info=SwapInfoBlob, unkUint=uint)

    D591 = Callback(void, "swap_complete_intent_gated", swap_id=uint, unkB=bool_, unkInt=uint32_t, width=uint, height=uint)
    D593 = Callback(void, "enable_backlight_message_ap_gated", bool_)
    D594 = Callback(void, "setSystemConsoleMode", bool_)

    D596 = Callback(bool_, "isDFBAllocated")
    D597 = Callback(bool_, "preserveContents")
    D598 = Callback(void, "find_swap_function_gated")

class ServiceRelay(IPCObject):
    D400 = Callback(void, "get_property", obj=FourCC, key=string(0x40), value=OutPtr(Bytes(0x200)), lenght=InOutPtr(uint))
    D401 = Callback(bool_, "sr_get_uint_prop", obj=FourCC, key=string(0x40), value=InOutPtr(ulong))
    D404 = Callback(void, "sr_set_uint_prop", obj=FourCC, key=string(0x40), value=uint)
    D406 = Callback(void, "set_fx_prop", obj=FourCC, key=string(0x40), value=uint)
    D408 = Callback(uint64_t, "sr_getClockFrequency", obj=FourCC, arg=uint)
    D411 = Callback(IOMFBStatus, "sr_mapDeviceMemoryWithIndex", obj=FourCC, index=uint, flags=uint, addr=OutPtr(ulong), length=OutPtr(ulong))
    D413 = Callback(bool_, "sr_setProperty_dict", obj=FourCC, key=string(0x40), value=InPtr(Padded(0x1000, OSDictionary())))
    D414 = Callback(bool_, "sr_setProperty_int", obj=FourCC, key=string(0x40), value=InPtr(uint64_t))
    D415 = Callback(bool_, "sr_setProperty_bool", obj=FourCC, key=string(0x40), value=InPtr(Bool(uint32_t)))

mem_desc_id = uint

class MemDescRelay(IPCObject):
    D451 = Callback(mem_desc_id, "allocate_buffer", uint, ulong, uint, OutPtr(ulong), OutPtr(ulong), OutPtr(ulong))
    D452 = Callback(mem_desc_id, "map_physical", paddr=ulong, size=ulong, flags=uint, dva=OutPtr(ulong), dvasize=OutPtr(ulong))
    D453 = Callback(mem_desc_id, "withAddressRange", ulong, ulong, uint, uint64_t, OutPtr(uint), OutPtr(ulong))
    D454 = Callback(IOMFBStatus, "prepare", uint, uint)
    D455 = Callback(IOMFBStatus, "complete", uint, uint)
    D456 = Callback(bool_, "release_descriptor", uint)

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
    "OOBCMD": "O",
    "OOBCB": "o",
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
