# SPDX-License-Identifier: MIT
from construct import *

from ...utils import *
from ..asc import StandardASC
from ..afk.epic import *
from .dcpav import *

EOTF = "EOTF" / Enum(Int32ul,
    GAMMA_SDR = 1,
    GAMMA_HDR = 2,
)

Encoding = "Encoding" / Enum(Int32ul,
    RGB = 1,
    YCBCR_444 = 3,
    YCBCR_422 = 4,
    YCBCR_420 = 5,
)

Colorimetry = "Colorimetry" / Enum(Int32ul,
    BT601_709 = 1,
    BT2020 = 2,
    DCIP3 = 3,
)

SurfaceFormat = "SurfaceFormat" / Enum(Int32ul,
    BGRA = 1,
    BGRA2 = 2,
    RGBA = 3,
    w18p = 4,
    BGRA3 = 5,
    _444v = 6,
    _422v = 7,
    _420v = 8,
    w30r = 9,
    w40a = 10,
)

Transform = "Transform" / Enum(Int8ul,
    NONE = 0,
    XFLIP = 1,
    YFLIP = 2,
    ROT_90 = 3,
    ROT_180 = 4,
    ROT_270 = 5,
)

AddrFormat = "AddrFormat" / Enum(Int32ul,
    PLANAR = 1,
    TILED = 2,
    AGX = 3
)

TimingMode = Struct(
    "valid" / Bool(Int32ul),
    "width" / Int32ul,
    "height" / Int32ul,
    "fps_frac" / Int16ul,
    "fps_int" / Int16ul,
    Padding(8),
)

TimingModeList = Struct(
    "count" / Int32ul,
    "list" / GreedyRange(TimingMode),
)

ColorMode = Struct(
    "valid" / Bool(Int32ul),
    "colorimetry" / Colorimetry,
    "eotf" / EOTF,
    "encoding" / Encoding,
    "bpp" / Int32ul,
    Padding(4),
)

ColorModeList = Struct(
    "count" / Int32ul,
    "list" / GreedyRange(ColorMode),
)

SwapInfo = Struct(
    "unk1" / Int32ul,
    "unk2" / Int32ul,
    "unk3" / Int32ul,
    "swap_id" / Int32ul,
    "unk5" / Int32ul,
)

IBootPlaneInfo = Struct(
    "unk1" / Default(Int32ul, 0),
    "addr" / Default(Int64ul, 0),
    "tile_size" / Default(Int32ul, 0),
    "stride" / Default(Int32ul, 0),
    "unk5" / Default(Int32ul, 0),
    "unk6" / Default(Int32ul, 0),
    "unk7" / Default(Int32ul, 0),
    "unk8" / Default(Int32ul, 0),
    "addr_format" / Default(AddrFormat, 0),
    "unk9" / Default(Int32ul, 0),
)

IBootLayerInfo = Struct(
    "planes" / Array(3, IBootPlaneInfo),
    "unk" / Default(Int32ul, 0),
    "plane_cnt" / Int32ul,
    "width" / Int32ul,
    "height" / Int32ul,
    "surface_fmt" / SurfaceFormat,
    "colorspace" / Int32ul,
    "eotf" / EOTF,
    "transform" / Transform,
    Padding(3)
)

SwapSetLayer = Struct(
    "unk" / Default(Int32ul, 0),
    "layer_id" / Int32ul,
    "layer_info" / IBootLayerInfo,
    "src_w" / Int32ul,
    "src_h" / Int32ul,
    "src_x" / Int32ul,
    "src_y" / Int32ul,
    "dst_w" / Int32ul,
    "dst_h" / Int32ul,
    "dst_x" / Int32ul,
    "dst_y" / Int32ul,
    "unk2" / Default(Int32ul, 0),
)

class DCPIBootService(EPICService):
    NAME = "disp0-service"
    SHORT = "disp0"

    def send_cmd(self, op, data=b'', replen=None):
        msg = struct.pack("<IIII", op, 16 + len(data), 0, 0) + data
        if replen is not None:
            replen += 8
        resp = super().send_cmd(0xc0, msg, replen)
        if not resp:
            return
        rcmd, rlen = struct.unpack("<II", resp[:8])
        return resp[8:rlen]

    def setPower(self, power):
        self.send_cmd(2, b"\x01" if power else b"\x00")

    def getModeCount(self):
        buf = self.send_cmd(3, b"", 12)
        hpd, timing_cnt, color_cnt = struct.unpack("<B3xII", buf)
        return bool(hpd), timing_cnt, color_cnt

    def getTimingModes(self):
        return TimingModeList.parse(self.send_cmd(4, replen=4096)).list

    def getColorModes(self):
        return ColorModeList.parse(self.send_cmd(5, replen=4096)).list

    def setMode(self, timing_mode, color_mode):
        data = TimingMode.build(timing_mode) + ColorMode.build(color_mode)
        self.send_cmd(6, data)

    def swapBegin(self):
        return SwapInfo.parse(self.send_cmd(15, replen=128))

    def swapSetLayer(self, layer_id, info, src_rect, dst_rect):
        data = Container()
        data.layer_id = layer_id
        data.layer_info = info
        data.src_w, data.src_h, data.src_x, data.src_y = src_rect
        data.dst_w, data.dst_h, data.dst_x, data.dst_y = dst_rect
        return self.send_cmd(16, SwapSetLayer.build(data), replen=128)

    def swapSetTimestamp(self):
        pass
        # 17

    def swapEnd(self):
        return self.send_cmd(18, b"\x00" * 12, replen=128)

    #def swapWait(self, swap_id):
        #buf = struct.pack("<IIII", 1, swap_id, 0, swap_id)
        #return self.send_cmd(19, buf, replen=128)

class DCPIBootEndpoint(EPICEndpoint):
    SHORT = "iboot"
    
    SERVICES = [
        DCPIBootService,
    ]


class DCPIBootClient(StandardASC):
    DVA_OFFSET = 0xf00000000

    ENDPOINTS = {
        0x20: AFKSystemEndpoint,
        0x23: DCPIBootEndpoint,
        0x24: DCPDPTXEndpoint,
        0x2a: DCPDPTXPortEndpoint,
        0x27: DCPAVDeviceEndpoint,
        0x28: DCPAVServiceEndpoint,
        0x29: DCPAVVideoEndpoint,
    }

    def __init__(self, u, asc_base, dart=None, disp_dart=None):
        super().__init__(u, asc_base, dart)
        self.disp_dart = disp_dart
