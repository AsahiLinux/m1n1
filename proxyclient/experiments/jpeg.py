#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.dart import DART, DARTRegs
from m1n1.hw.jpeg import *
from m1n1.utils import *
import argparse
import struct
import time
from enum import IntEnum
from PIL import Image, ImageDraw


def divroundup(val, div):
    return (val + div - 1) // div


def yuv2rgb(y, u, v):
    y -= 16
    u -= 128
    v -= 128

    y /= 255
    u /= 255
    v /= 255

    r = y + 1.13983 * v
    g = y - 0.39465 * u - 0.58060 * v
    b = y + 2.03211 * u

    r = min(255, max(0, int(r * 255)))
    g = min(255, max(0, int(g * 255)))
    b = min(255, max(0, int(b * 255)))

    return (r, g, b)


def rgb2yuv(r, g, b):
    r /= 255
    g /= 255
    b /= 255

    y = 0.299*r + 0.587*g + 0.114*b
    u = -0.14713*r - 0.28886*g + 0.436*b
    v = 0.615*r - 0.51499*g - 0.10001*b

    y = y * 255 + 16
    u = u * 255 + 128
    v = v * 255 + 128

    y = min(255, max(0, int(y)))
    u = min(255, max(0, int(u)))
    v = min(255, max(0, int(v)))

    return (y, u, v)


ap = argparse.ArgumentParser(description='JPEG block experiment')
ap.add_argument("--jpeg", dest='which_jpeg', type=str, default='jpeg0',
                help='which JPEG instance (jpeg0/jpeg1)')
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("-e", "--encode", action='store_true')
g.add_argument("-d", "--decode", action='store_true')
ap.add_argument("--raw-output", type=str, required=False)
ap.add_argument("--decode-scale", type=int, required=False, default=1)
ap.add_argument("--decode-pixelfmt", type=str, required=False, default='RGBA')
ap.add_argument("--decode-rgba-alpha", type=int, required=False, default=255)
ap.add_argument("--encode-subsampling", type=str, required=False, default='444')
ap.add_argument("--encode-rst-interval", type=int, required=False)
ap.add_argument("--encode-pixelfmt", type=str, required=False, default='RGB888')
ap.add_argument("input", type=str)
ap.add_argument("output", type=str)
args = ap.parse_args()

# print(args)

# Perform necessary pre-parsing
if args.decode:
    assert args.decode_scale in [1, 2, 4, 8]
    decode_scale = args.decode_scale
    # FIXME: verify behavior on non-evenly-divisible sizes

    assert args.decode_pixelfmt in [
        'RGBA',
        'BGRA',
        'RGB565',
        'YUV422-CbYCrY',
        'YUV422-YCbYCr',
        'YUV422-planar',
        'YUV420-planar',
        'YUV444-planar',
    ]
    pixfmt = args.decode_pixelfmt

    with open(args.input, 'rb') as f:
        jpeg_data = f.read()

    found_sof0 = False

    jpeg_work = jpeg_data
    while jpeg_work:
        seg_marker = struct.unpack(">H", jpeg_work[:2])[0]
        print(f"Seg {seg_marker:04X}")
        if seg_marker == 0xFFD8:
            # SOI
            jpeg_work = jpeg_work[2:]
        elif seg_marker == 0xFFDA:
            # SOS
            break
        else:
            seg_len = struct.unpack(">H", jpeg_work[2:4])[0]
            assert seg_len >= 2
            seg_data = jpeg_work[4:4 + seg_len - 2]
            jpeg_work = jpeg_work[4 + seg_len - 2:]

            if seg_marker == 0xFFC0:
                # SOF0
                assert not found_sof0
                found_sof0 = True
                sof0 = struct.unpack(">BHHB", seg_data[:6])
                (jpeg_bpp, jpeg_H, jpeg_W, jpeg_components_cnt) = sof0
                # it is not yet verified what the requirements are for inputs
                assert jpeg_bpp == 8
                assert jpeg_components_cnt == 1 or jpeg_components_cnt == 3
                if jpeg_components_cnt == 1:
                    jpeg_MODE = '400'
                else:
                    jpeg_components = {}
                    for i in range(jpeg_components_cnt):
                        comp_id, comp_sampling, _ = seg_data[6+3*i:6+3*(i+1)]
                        jpeg_components[comp_id] = comp_sampling
                    assert 1 in jpeg_components
                    comp_Y = jpeg_components[1]
                    assert 2 in jpeg_components
                    comp_Cb = jpeg_components[2]
                    assert 3 in jpeg_components
                    comp_Cr = jpeg_components[3]

                    if (comp_Y, comp_Cb, comp_Cr) == (0x11, 0x11, 0x11):
                        jpeg_MODE = '444'
                    elif (comp_Y, comp_Cb, comp_Cr) == (0x21, 0x11, 0x11):
                        jpeg_MODE = '422'
                    elif (comp_Y, comp_Cb, comp_Cr) == (0x22, 0x11, 0x11):
                        jpeg_MODE = '420'
                    elif (comp_Y, comp_Cb, comp_Cr) == (0x41, 0x11, 0x11):
                        jpeg_MODE = '411'
                    else:
                        # TODO: 422-vertical, others???
                        # Is it possible to implement them?
                        print("Unsupported subsampling mode")
                        assert False

    assert found_sof0
    print(f"JPEG is {jpeg_W}x{jpeg_H} with subsampling {jpeg_MODE}")

    if jpeg_MODE == '444' or jpeg_MODE == '400':
        macroblock_W, macroblock_H = 8, 8
    elif jpeg_MODE == '422':
        macroblock_W, macroblock_H = 16, 8
    elif jpeg_MODE == '420':
        macroblock_W, macroblock_H = 16, 16
    elif jpeg_MODE == '411':
        macroblock_W, macroblock_H = 32, 8
    else:
        assert False

    # FIXME: Exactly how much extra memory do we need to allocate?
    surface_W = divroundup(jpeg_W // decode_scale, macroblock_W) * macroblock_W
    surface_H = divroundup(jpeg_H // decode_scale, macroblock_H) * macroblock_H
    if pixfmt in ['RGBA', 'BGRA']:
        BYTESPP = 4
    elif pixfmt in ['RGB565', 'YUV422-CbYCrY', 'YUV422-YCbYCr']:
        BYTESPP = 2
    elif pixfmt in ['YUV422-planar', 'YUV420-planar', 'YUV444-planar']:
        BYTESPP = 1
    else:
        assert False
    surface_stride = surface_W * BYTESPP
    surface_sz = surface_stride*surface_H

    if pixfmt == 'YUV422-planar':
        P1_MULW = 1     # FIXME UGLY
        P1_DIVW = 1
        P1_DIVH = 1
    elif pixfmt == 'YUV420-planar':
        P1_MULW = 1
        P1_DIVW = 1
        P1_DIVH = 2
    elif pixfmt == 'YUV444-planar':
        P1_MULW = 2
        P1_DIVW = 1
        P1_DIVH = 1
    if pixfmt in ['YUV422-planar', 'YUV420-planar', 'YUV444-planar']:
        surface_P1_W = surface_W * P1_MULW // P1_DIVW
        surface_P1_H = surface_H // P1_DIVH
        surface_P1_stride = surface_P1_W
        surface_P1_off = surface_sz
        surface_sz += surface_P1_stride*surface_P1_H
    else:
        surface_P1_stride = 0
        surface_P1_off = 0

    input_mem_sz = align_up(len(jpeg_data))
    print(f"Using size {input_mem_sz:08X} for JPEG data")

    output_mem_sz = align_up(surface_sz)
    print(f"Using size {output_mem_sz:08X} for output image")
else:
    assert args.encode_subsampling in ['444', '422', '420', '400']
    if args.encode_subsampling == '444' or args.encode_subsampling == '400':
        macroblock_W, macroblock_H = 8, 8
    elif args.encode_subsampling == '422':
        macroblock_W, macroblock_H = 16, 8
    elif args.encode_subsampling == '420':
        macroblock_W, macroblock_H = 16, 16
    else:
        assert False

    assert args.encode_pixelfmt in [
        'RGB888',
        'RGB101010',
        'RGB565',
        'YUV10',
        'YUV-linear',
        'YUV444-planar',
        'YUV422-planar',
        'YUV420-planar',
    ]
    pixfmt = args.encode_pixelfmt

    # Driver doesn't support this either
    if pixfmt == 'YUV-linear' and args.encode_subsampling == '444':
        print("WARNING: This combination does not appear to work!!!")
    if pixfmt == 'YUV422-planar' and args.encode_subsampling == '444':
        print("WARNING: This combination does not appear to work!!!")
    if pixfmt == 'YUV420-planar' and args.encode_subsampling == '444':
        print("WARNING: This combination does not appear to work!!!")

    image_data = b''
    image_data_P1 = b''
    with Image.open(args.input) as im:
        im_W, im_H = im.size

        if pixfmt != 'YUV420-planar':
            for y in range(im_H):
                for x in range(im_W):
                    r, g, b = im.getpixel((x, y))
                    if pixfmt == 'RGB888':
                        image_data += struct.pack("BBBB", r, g, b, 255)
                    elif pixfmt == 'RGB101010':
                        image_data += struct.pack("<I", (r << 2) | (g << 12) | (b << 22))
                    elif pixfmt == 'RGB565':
                        image_data += struct.pack("<H", (r >> 3) | ((g >> 2) << 5) | ((b >> 3) << 11))
                    elif pixfmt == 'YUV10':
                        # absolute garbage color space conversion
                        # for demonstration purposes only
                        y_, u_, v_ = rgb2yuv(r, g, b)
                        image_data += struct.pack("<I", (y_ << 2) | (u_ << 12) | (v_ << 22))
                    elif pixfmt == 'YUV-linear':
                        # garbage color space conversion, garbage subsampling
                        # for demonstration purposes only
                        y_, u_, v_ = rgb2yuv(r, g, b)
                        if x & 1 == 0:
                            color = u_
                        else:
                            color = v_
                        image_data += struct.pack("BB", y_, color)
                    elif pixfmt == 'YUV444-planar':
                        # garbage color space conversion
                        # for demonstration purposes only
                        y_, u_, v_ = rgb2yuv(r, g, b)
                        image_data += struct.pack("B", y_)
                        image_data_P1 += struct.pack("BB", u_, v_)
                    elif pixfmt == 'YUV422-planar':
                        # garbage color space conversion, garbage subsampling
                        # for demonstration purposes only
                        y_, u_, v_ = rgb2yuv(r, g, b)
                        if x & 1 == 0:
                            color = u_
                        else:
                            color = v_
                        image_data += struct.pack("B", y_)
                        image_data_P1 += struct.pack("B", color)
                    else:
                        assert False
        else:
            for y in range(im_H):
                for x in range(im_W):
                    r, g, b = im.getpixel((x, y))
                    # garbage color space conversion, garbage subsampling
                    # for demonstration purposes only
                    y_, u_, v_ = rgb2yuv(r, g, b)
                    if x & 1 == 0:
                        color = u_
                    else:
                        color = v_
                    image_data += struct.pack("B", y_)
                    if y & 1 == 0:
                        image_data_P1 += struct.pack("B", color)

    if pixfmt in ['RGB888', 'RGB101010', 'YUV10']:
        BYTESPP = 4
        BYTESPP_P1 = 0
        P1_DIVH = 1
    elif pixfmt in ['RGB565', 'YUV-linear']:
        BYTESPP = 2
        BYTESPP_P1 = 0
        P1_DIVH = 1
    elif pixfmt == 'YUV444-planar':
        BYTESPP = 1
        BYTESPP_P1 = 2
        P1_DIVH = 1
    elif pixfmt == 'YUV422-planar':
        BYTESPP = 1
        BYTESPP_P1 = 1
        P1_DIVH = 1
    elif pixfmt == 'YUV420-planar':
        BYTESPP = 1
        BYTESPP_P1 = 1
        P1_DIVH = 2
    else:
        assert False
    surface_stride = im_W * BYTESPP
    surface_sz = surface_stride * im_H
    surface_P1_off = surface_sz
    print(f"Plane 1 offset at {surface_P1_off:08X}")
    surface_P1_stride = im_W * BYTESPP_P1
    surface_sz += surface_P1_stride * im_H // P1_DIVH
    input_mem_sz = align_up(surface_sz)

    output_mem_sz = input_mem_sz

    print(f"Using size {input_mem_sz:08X} for input image")
    print(f"Using size {output_mem_sz:08X} for output data")

# Turn on the JPEG block
p.pmgr_adt_clocks_enable(f'/arm-io/dart-{args.which_jpeg}')
p.pmgr_adt_clocks_enable(f'/arm-io/{args.which_jpeg}')

dart = DART.from_adt(u, f'/arm-io/dart-{args.which_jpeg}')
dart.initialize()

jpeg_base, _ = u.adt[f'/arm-io/{args.which_jpeg}'].get_reg(0)
jpeg = JPEGRegs(u, jpeg_base)


def reset_block():
    jpeg.MODE.val = 0x100
    jpeg.MODE.val = 0x13e

    set_default_regs()

    jpeg.MODE.val = 0x17f
    for _ in range(10000):
        v = jpeg.REG_0x1004.val
        if v == 0:
            break
        print(f"reset 1 -- {v}")
    if (v := jpeg.REG_0x1004.val) != 0:
        print(f"reset 1 failed! -- {v}")
        assert False

    jpeg.RST_INTERVAL.val = 1
    for _ in range(2500):
        v = jpeg.RST_INTERVAL.val
        if v == 1:
            break
        print(f"reset 2 -- {v}")
    if (v := jpeg.RST_INTERVAL.val) != 1:
        print(f"reset 2 failed! -- {v}")
        assert False
    jpeg.RST_INTERVAL.val = 0

    jpeg.ENABLE_RST_LOGGING.val = 0
    jpeg.REG_0x1a8.val = 0
    jpeg.REG_0x1ac.val = 0
    jpeg.REG_0x1b0.val = 0
    jpeg.REG_0x1b4.val = 0
    jpeg.REG_0x1bc.val = 0
    jpeg.REG_0x1c0.val = 0
    jpeg.REG_0x1c4.val = 0
    jpeg.REG_0x1c8.val = 0
    jpeg.REG_0x1cc.val = 0
    jpeg.REG_0x1d0.val = 0
    jpeg.REG_0x1d4.val = 0

    jpeg.MODE.val = 0x143


def set_default_regs(param1=0):
    jpeg.REG_0x0.val = 0
    jpeg.REG_0x0.val = 0
    jpeg.REG_0x4.val = 0
    jpeg.CODEC.val = 0
    jpeg.REG_0x2c.val = 0
    jpeg.REG_0x30.val = 0
    jpeg.REG_0x34.val = 1
    jpeg.REG_0x38.val = 1
    jpeg.CHROMA_HALVE_H_TYPE1.val = 0
    jpeg.CHROMA_HALVE_H_TYPE2.val = 0
    jpeg.CHROMA_HALVE_V_TYPE1.val = 0
    jpeg.CHROMA_HALVE_V_TYPE2.val = 0
    jpeg.CHROMA_DOUBLE_H.val = 0
    jpeg.CHROMA_QUADRUPLE_H.val = 0
    jpeg.CHROMA_DOUBLE_V.val = 0
    jpeg.PLANAR_CHROMA_HALVING.val = 0
    jpeg.PX_USE_PLANE1.val = 0
    jpeg.PX_TILES_W.val = 1
    jpeg.PX_TILES_H.val = 1
    jpeg.PX_PLANE0_WIDTH.val = 1
    jpeg.PX_PLANE0_HEIGHT.val = 1
    jpeg.PX_PLANE0_TILING_H.val = 1
    jpeg.PX_PLANE0_TILING_V.val = 1
    jpeg.PX_PLANE0_STRIDE.val = 1
    jpeg.PX_PLANE1_WIDTH.val = 1
    jpeg.PX_PLANE1_HEIGHT.val = 1
    jpeg.PX_PLANE1_TILING_H.val = 1
    jpeg.PX_PLANE1_TILING_V.val = 1
    jpeg.PX_PLANE1_STRIDE.val = 1
    jpeg.INPUT_START1.val = 0
    jpeg.INPUT_START2.val = 0
    jpeg.REG_0x94.val = 1
    jpeg.REG_0x98.val = 1
    jpeg.INPUT_END.val = 0xffffffff
    jpeg.OUTPUT_START1.val = 0
    jpeg.OUTPUT_START2.val = 0
    jpeg.OUTPUT_END.val = 0xffffffff
    for i in range(11):
        jpeg.MATRIX_MULT[i].val = 0
    for i in range(10):
        jpeg.DITHER[i].val = 0xff
    jpeg.ENCODE_PIXEL_FORMAT.val = 0
    jpeg.ENCODE_COMPONENT0_POS.val = 0
    jpeg.ENCODE_COMPONENT1_POS.val = 0
    jpeg.ENCODE_COMPONENT2_POS.val = 0
    jpeg.ENCODE_COMPONENT3_POS.val = 0
    jpeg.CONVERT_COLOR_SPACE.val = 0
    jpeg.REG_0x118.val = 0
    jpeg.REG_0x11c.val = 0
    jpeg.REG_0x120.val = 0
    jpeg.TILING_ENABLE.val = 0
    jpeg.TILING_PLANE0.val = 0
    jpeg.TILING_PLANE1.val = 0
    jpeg.DECODE_MACROBLOCKS_W.val = 0
    jpeg.DECODE_MACROBLOCKS_H.val = 0
    jpeg.SCALE_FACTOR.val = 0
    jpeg.DECODE_PIXEL_FORMAT.val = 0
    jpeg.YUV422_ORDER.val = 0
    jpeg.RGBA_ORDER.val = 0
    jpeg.RGBA_ALPHA.val = 0
    jpeg.RIGHT_EDGE_PIXELS.val = 0
    jpeg.BOTTOM_EDGE_PIXELS.val = 0
    jpeg.RIGHT_EDGE_SAMPLES.val = 0
    jpeg.BOTTOM_EDGE_SAMPLES.val = 0

    # this is always done on the m1 max hwrev
    jpeg.REG_0x1fc.val = 0
    jpeg.REG_0x200.val = 0
    jpeg.REG_0x204.val = 0
    jpeg.REG_0x208.val = 0
    jpeg.REG_0x214.val = 0
    jpeg.REG_0x218.val = 0
    jpeg.REG_0x21c.val = 0
    jpeg.REG_0x220.val = 0
    jpeg.REG_0x224.val = 0
    jpeg.REG_0x228.val = 0
    jpeg.REG_0x22c.val = 0
    jpeg.REG_0x230.val = 0
    jpeg.REG_0x234.val = 0x1f40
    jpeg.REG_0x244.val = 0
    jpeg.REG_0x248.val = 0
    jpeg.REG_0x258.val = 0
    jpeg.REG_0x25c.val = 0
    jpeg.REG_0x23c.val = 0
    jpeg.REG_0x240.val = 0
    jpeg.REG_0x250.val = 0
    jpeg.REG_0x254.val = 0

    jpeg.REG_0x160.val = param1
    jpeg.TIMEOUT.val = 0
    jpeg.REG_0x20.val = 0xff


print(f"HW revision is {jpeg.HWREV}")
reset_block()

input_buf_phys = u.heap.memalign(0x4000, input_mem_sz)
output_buf_phys = u.heap.memalign(0x4000, output_mem_sz)
print(f"buffers (phys) {input_buf_phys:016X} {output_buf_phys:016X}")

input_buf_iova = dart.iomap(0, input_buf_phys, input_mem_sz)
output_buf_iova = dart.iomap(0, output_buf_phys, output_mem_sz)
print(f"buffers (iova) {input_buf_iova:08X} {output_buf_iova:08X}")
# dart.dump_all()

iface.writemem(input_buf_phys, b'\xAA' * input_mem_sz)
iface.writemem(output_buf_phys, b'\xAA' * output_mem_sz)


if args.decode:
    iface.writemem(input_buf_phys, jpeg_data)
    print("JPEG uploaded")

    jpeg.REG_0x34 = 1
    jpeg.REG_0x2c = 0
    jpeg.REG_0x38 = 0
    if jpeg_MODE == '444':
        jpeg.CODEC.set(CODEC=E_CODEC._444)
    elif jpeg_MODE == '400':
        jpeg.CODEC.set(CODEC=E_CODEC._400)
    elif jpeg_MODE == '422':
        jpeg.CODEC.set(CODEC=E_CODEC._422)
    elif jpeg_MODE == '420':
        jpeg.CODEC.set(CODEC=E_CODEC._420)
    elif jpeg_MODE == '411':
        jpeg.CODEC.set(CODEC=E_CODEC._411)
    else:
        assert False
    if pixfmt == 'RGBA' or pixfmt == 'BGRA':
        jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.RGBA8888)
    elif pixfmt == 'RGB565':
        jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.RGB565)
    elif pixfmt == 'YUV422-CbYCrY' or pixfmt == 'YUV422-YCbYCr':
        jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.YUV422_linear)
    elif pixfmt == 'YUV422-planar':
        jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.YUV422_planar)
    elif pixfmt == 'YUV420-planar':
        jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.YUV420_planar)
    elif pixfmt == 'YUV444-planar':
        jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.YUV444_planar)
    else:
        assert False

    if pixfmt in ['YUV422-planar', 'YUV420-planar', 'YUV444-planar']:
        jpeg.PX_USE_PLANE1 = 1
        jpeg.PX_PLANE1_WIDTH = jpeg_W * P1_MULW // P1_DIVW // decode_scale - 1
        jpeg.PX_PLANE1_HEIGHT = jpeg_H // P1_DIVH // decode_scale - 1
    else:
        jpeg.PX_USE_PLANE1 = 0
    jpeg.PX_PLANE0_WIDTH = jpeg_W*BYTESPP // decode_scale - 1
    jpeg.PX_PLANE0_HEIGHT = jpeg_H // decode_scale - 1
    jpeg.TIMEOUT = 266000000

    jpeg.REG_0x94 = 0x1f
    jpeg.REG_0x98 = 1

    jpeg.DECODE_MACROBLOCKS_W = divroundup(jpeg_W, macroblock_W)
    jpeg.DECODE_MACROBLOCKS_H = divroundup(jpeg_H, macroblock_H)
    right_edge_px = \
        jpeg_W - divroundup(jpeg_W, macroblock_W)*macroblock_W + macroblock_W
    bot_edge_px = \
        jpeg_H - divroundup(jpeg_H, macroblock_H)*macroblock_H + macroblock_H
    # XXX changing this does not seem to do anything.
    # Does it possibly affect scaling down?
    jpeg.RIGHT_EDGE_PIXELS.val = right_edge_px
    jpeg.BOTTOM_EDGE_PIXELS.val = bot_edge_px
    jpeg.RIGHT_EDGE_SAMPLES.val = right_edge_px // (macroblock_W // 8)
    jpeg.BOTTOM_EDGE_SAMPLES.val = bot_edge_px // (macroblock_H // 8)

    jpeg.PX_TILES_H = divroundup(jpeg_H, macroblock_H)
    # FIXME explain this
    if pixfmt in ['RGBA', 'BGRA', 'RGB565', 'YUV444-planar']:
        jpeg.PX_TILES_W = divroundup(jpeg_W // decode_scale, macroblock_W)
    else:
        jpeg.PX_TILES_W = divroundup(jpeg_W // decode_scale, max(macroblock_W, 16))
    if pixfmt == 'RGBA' or pixfmt == 'BGRA':
        if jpeg_MODE == '444' or jpeg_MODE == '400':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif jpeg_MODE == '422':
            jpeg.PX_PLANE0_TILING_H = 8
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif jpeg_MODE == '420':
            jpeg.PX_PLANE0_TILING_H = 8
            jpeg.PX_PLANE0_TILING_V = 16 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        elif jpeg_MODE == '411':
            jpeg.PX_PLANE0_TILING_H = 16
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        else:
            assert False
    elif pixfmt == 'RGB565':
        if jpeg_MODE == '444' or jpeg_MODE == '400':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif jpeg_MODE == '422':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif jpeg_MODE == '420':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 16 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        elif jpeg_MODE == '411':
            jpeg.PX_PLANE0_TILING_H = 8
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        else:
            assert False
    elif pixfmt == 'YUV422-CbYCrY' or pixfmt == 'YUV422-YCbYCr':
        if jpeg_MODE == '444' or jpeg_MODE == '400':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif jpeg_MODE == '422':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif jpeg_MODE == '420':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 16 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        elif jpeg_MODE == '411':
            jpeg.PX_PLANE0_TILING_H = 8
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        else:
            assert False
    elif pixfmt == 'YUV422-planar':
        if jpeg_MODE == '444' or jpeg_MODE == '400':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        elif jpeg_MODE == '422':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        elif jpeg_MODE == '420':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 16 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 16 // decode_scale
        elif jpeg_MODE == '411':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 4
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        else:
            assert False
    elif pixfmt == 'YUV420-planar':
        if jpeg_MODE == '444' or jpeg_MODE == '400':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 4 // decode_scale
        elif jpeg_MODE == '422':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 4 // decode_scale
        elif jpeg_MODE == '420':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 16 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        elif jpeg_MODE == '411':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 4
            jpeg.PX_PLANE1_TILING_V = 4 // decode_scale
        else:
            assert False
    elif pixfmt == 'YUV444-planar':
        if jpeg_MODE == '444' or jpeg_MODE == '400':
            jpeg.PX_PLANE0_TILING_H = 1
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        elif jpeg_MODE == '422':
            # The driver doesn't use this, but guessing seems to be fine?
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 4
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        elif jpeg_MODE == '420':
            # The driver doesn't use this, but guessing seems to be fine?
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 16 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 4
            jpeg.PX_PLANE1_TILING_V = 16 // decode_scale
        elif jpeg_MODE == '411':
            # The driver doesn't use this, but guessing seems to be fine?
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8 // decode_scale
            jpeg.PX_PLANE1_TILING_H = 8
            jpeg.PX_PLANE1_TILING_V = 8 // decode_scale
        else:
            assert False
    else:
        assert False

    if pixfmt in ['RGBA', 'BGRA', 'RGB565', 'YUV444-planar']:
        if jpeg_MODE in ['422', '420']:
            jpeg.CHROMA_DOUBLE_H = 1

        if jpeg_MODE == '411':
            jpeg.CHROMA_QUADRUPLE_H = 1

        if jpeg_MODE == '420':
            jpeg.CHROMA_DOUBLE_V = 1
    elif pixfmt in ["YUV422-CbYCrY", "YUV422-YCbYCr", "YUV422-planar"]:
        if jpeg_MODE == '444':
            jpeg.CHROMA_HALVE_H_TYPE1 = 1

        if jpeg_MODE == '411':
            jpeg.CHROMA_DOUBLE_H = 1

        if jpeg_MODE == '420':
            jpeg.CHROMA_DOUBLE_V = 1
    elif pixfmt in ["YUV420-planar"]:
        if jpeg_MODE == '444':
            jpeg.CHROMA_HALVE_H_TYPE1 = 1

        if jpeg_MODE in ['444', '422', '411']:
            jpeg.CHROMA_HALVE_V_TYPE1 = 1

        if jpeg_MODE == '411':
            jpeg.CHROMA_DOUBLE_H = 1
    else:
        assert False

    jpeg.MATRIX_MULT[0].val = 0x100
    jpeg.MATRIX_MULT[1].val = 0x0
    jpeg.MATRIX_MULT[2].val = 0x167
    jpeg.MATRIX_MULT[3].val = 0x100
    jpeg.MATRIX_MULT[4].val = 0xffffffa8
    jpeg.MATRIX_MULT[5].val = 0xffffff49
    jpeg.MATRIX_MULT[6].val = 0x100
    jpeg.MATRIX_MULT[7].val = 0x1c6
    jpeg.MATRIX_MULT[8].val = 0x0
    jpeg.MATRIX_MULT[9].val = 0x0
    jpeg.MATRIX_MULT[10].val = 0xffffff80

    jpeg.RGBA_ALPHA = args.decode_rgba_alpha
    jpeg.RGBA_ORDER = pixfmt == "RGBA"
    jpeg.YUV422_ORDER = pixfmt == "YUV422-YCbYCr"

    if decode_scale == 1:
        jpeg.SCALE_FACTOR.set(SCALE=E_SCALE.DIV1)
    elif decode_scale == 2:
        jpeg.SCALE_FACTOR.set(SCALE=E_SCALE.DIV2)
    elif decode_scale == 4:
        jpeg.SCALE_FACTOR.set(SCALE=E_SCALE.DIV4)
    elif decode_scale == 8:
        jpeg.SCALE_FACTOR.set(SCALE=E_SCALE.DIV8)
    else:
        assert False

    jpeg.INPUT_START1 = input_buf_iova
    jpeg.INPUT_START2 = 0xdeadbeef
    jpeg.INPUT_END = input_buf_iova + input_mem_sz
    jpeg.OUTPUT_START1 = output_buf_iova
    jpeg.OUTPUT_START2 = output_buf_iova + surface_P1_off
    jpeg.OUTPUT_END = output_buf_iova + output_mem_sz
    jpeg.PX_PLANE0_STRIDE = surface_stride
    jpeg.PX_PLANE1_STRIDE = surface_P1_stride

    jpeg.REG_0x1ac = 0x0
    jpeg.REG_0x1b0 = 0x0
    jpeg.REG_0x1b4 = 0x0
    jpeg.REG_0x1bc = 0x0
    jpeg.REG_0x1c0 = 0x0
    jpeg.REG_0x1c4 = 0x0

    jpeg.REG_0x118 = 0x0
    jpeg.REG_0x11c = 0x1

    jpeg.MODE = 0x177
    jpeg.REG_0x1028 = 0x400

    jpeg.JPEG_IO_FLAGS = 0x3f
    jpeg.REG_0x0 = 0x1
    jpeg.REG_0x1004 = 0x1

    # FIXME: we don't actually know when it's done
    time.sleep(1)

    print(jpeg.STATUS.reg)
    print(jpeg.PERFCOUNTER.reg)

    output_data = iface.readmem(output_buf_phys, output_mem_sz)
    if args.raw_output is not None:
        with open(args.raw_output, 'wb') as f:
            f.write(output_data)

    # Just for demonstration purposes, wrangle everything back into RGB
    with Image.new(
            mode='RGBA',
            size=(jpeg_W // decode_scale, jpeg_H // decode_scale)) as im:
        if pixfmt in ["RGBA", "BGRA", "RGB565"]:
            for y in range(jpeg_H // decode_scale):
                for x in range(jpeg_W // decode_scale):
                    block = output_data[
                        y*surface_stride + x*BYTESPP:
                        y*surface_stride + (x+1)*BYTESPP]

                    if pixfmt == "RGBA":
                        r, g, b, a = block
                    elif pixfmt == "BGRA":
                        b, g, r, a = block
                    elif pixfmt == "RGB565":
                        rgb = struct.unpack("<H", block)[0]
                        b = (rgb & 0b11111) << 3
                        g = ((rgb >> 5) & 0b111111) << 2
                        r = ((rgb >> 11) & 0b11111) << 3
                        a = 255
                    else:
                        assert False
                    im.putpixel((x, y), (r, g, b, a))
        elif pixfmt in ["YUV422-CbYCrY", "YUV422-YCbYCr"]:
            for y in range(jpeg_H // decode_scale):
                for x in range(0, jpeg_W // decode_scale, 2):
                    block = output_data[
                        y*surface_stride + x*BYTESPP:
                        y*surface_stride + (x+2)*BYTESPP]

                    if pixfmt == "YUV422-CbYCrY":
                        cb, y0, cr, y1 = block
                    elif pixfmt == "YUV422-YCbYCr":
                        y0, cb, y1, cr = block

                    r0, g0, b0 = yuv2rgb(y0, cb, cr)
                    r1, g1, b1 = yuv2rgb(y1, cb, cr)

                    im.putpixel((x, y), (r0, g0, b0, 255))
                    # XXX this really needs some fixing
                    if x+1 < jpeg_W // decode_scale:
                        im.putpixel((x+1, y), (r1, g1, b1, 255))
        elif pixfmt == "YUV422-planar":
            for y in range(jpeg_H // decode_scale):
                for x in range(jpeg_W // decode_scale):
                    y_ = output_data[y*surface_stride + x]
                    cb = output_data[surface_P1_off + y*surface_P1_stride + x&~1]
                    cr = output_data[surface_P1_off + y*surface_P1_stride + (x&~1)+1]

                    r, g, b = yuv2rgb(y_, cb, cr)

                    im.putpixel((x, y), (r, g, b, 255))
        elif pixfmt == "YUV420-planar":
            for y in range(jpeg_H // decode_scale):
                for x in range(jpeg_W // decode_scale):
                    y_ = output_data[y*surface_stride + x]
                    cb = output_data[surface_P1_off + (y//2)*surface_P1_stride + x&~1]
                    cr = output_data[surface_P1_off + (y//2)*surface_P1_stride + (x&~1)+1]

                    r, g, b = yuv2rgb(y_, cb, cr)

                    im.putpixel((x, y), (r, g, b, 255))
        elif pixfmt == "YUV444-planar":
            for y in range(jpeg_H // decode_scale):
                for x in range(jpeg_W // decode_scale):
                    y_ = output_data[y*surface_stride + x]
                    cb = output_data[surface_P1_off + y*surface_P1_stride + x*2]
                    cr = output_data[surface_P1_off + y*surface_P1_stride + x*2+1]

                    r, g, b = yuv2rgb(y_, cb, cr)

                    im.putpixel((x, y), (r, g, b, 255))
        else:
            assert False
        im.save(args.output)

if args.encode:
    iface.writemem(input_buf_phys, image_data)
    iface.writemem(input_buf_phys + surface_P1_off, image_data_P1)
    print("Pixel data uploaded")

    jpeg.MODE = 0x17f
    jpeg.REG_0x38 = 0x1     # if not set nothing happens
    jpeg.REG_0x2c = 0x1     # if not set only header is output
    jpeg.REG_0x34 = 0x0     # if set output is a JPEG but weird with no footer

    if args.encode_subsampling == '444':
        jpeg.CODEC.set(CODEC=E_CODEC._444)
    elif args.encode_subsampling == '422':
        jpeg.CODEC.set(CODEC=E_CODEC._422)
    elif args.encode_subsampling == '420':
        jpeg.CODEC.set(CODEC=E_CODEC._420)
    elif args.encode_subsampling == '400':
        jpeg.CODEC.set(CODEC=E_CODEC._400)
    else:
        assert False

    if BYTESPP_P1 != 0:
        jpeg.PX_USE_PLANE1 = 1
        jpeg.PX_PLANE1_WIDTH = im_W*BYTESPP_P1 - 1
        jpeg.PX_PLANE1_HEIGHT = im_H // P1_DIVH - 1
    else:
        jpeg.PX_USE_PLANE1 = 0
        jpeg.PX_PLANE1_WIDTH = 0xffffffff
        jpeg.PX_PLANE1_HEIGHT = 0xffffffff
    jpeg.PX_PLANE0_WIDTH = im_W*BYTESPP - 1
    jpeg.PX_PLANE0_HEIGHT = im_H - 1
    jpeg.TIMEOUT = 266000000

    jpeg.PX_TILES_W = divroundup(im_W, macroblock_W)
    jpeg.PX_TILES_H = divroundup(im_H, macroblock_H)
    if pixfmt in ['RGB888', 'RGB101010', 'YUV10']:
        if args.encode_subsampling == '444' or args.encode_subsampling == '400':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif args.encode_subsampling == '422':
            jpeg.PX_PLANE0_TILING_H = 8
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif args.encode_subsampling == '420':
            jpeg.PX_PLANE0_TILING_H = 8
            jpeg.PX_PLANE0_TILING_V = 16
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        else:
            assert False
    elif pixfmt == 'RGB565':
        if args.encode_subsampling == '444' or args.encode_subsampling == '400':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif args.encode_subsampling == '422':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif args.encode_subsampling == '420':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 16
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        else:
            assert False
    elif pixfmt == 'YUV-linear':
        if args.encode_subsampling == '444' or args.encode_subsampling == '400':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif args.encode_subsampling == '422':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 1
        elif args.encode_subsampling == '420':
            jpeg.PX_PLANE0_TILING_H = 4
            jpeg.PX_PLANE0_TILING_V = 16
            jpeg.PX_PLANE1_TILING_H = 0
            jpeg.PX_PLANE1_TILING_V = 0
        else:
            assert False
    elif pixfmt == 'YUV444-planar':
        if args.encode_subsampling == '444' or args.encode_subsampling == '400':
            jpeg.PX_PLANE0_TILING_H = 1
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8
        elif args.encode_subsampling == '422':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 4
            jpeg.PX_PLANE1_TILING_V = 8
        elif args.encode_subsampling == '420':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 16
            jpeg.PX_PLANE1_TILING_H = 4
            jpeg.PX_PLANE1_TILING_V = 16
        else:
            assert False
    elif pixfmt == 'YUV422-planar':
        if args.encode_subsampling == '444' or args.encode_subsampling == '400':
            jpeg.PX_PLANE0_TILING_H = 1
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 8
        elif args.encode_subsampling == '422':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8
        elif args.encode_subsampling == '420':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 16
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 16
        else:
            assert False
    elif pixfmt == 'YUV420-planar':
        if args.encode_subsampling == '444' or args.encode_subsampling == '400':
            jpeg.PX_PLANE0_TILING_H = 1
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 1
            jpeg.PX_PLANE1_TILING_V = 4
        elif args.encode_subsampling == '422':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 8
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 4
        elif args.encode_subsampling == '420':
            jpeg.PX_PLANE0_TILING_H = 2
            jpeg.PX_PLANE0_TILING_V = 16
            jpeg.PX_PLANE1_TILING_H = 2
            jpeg.PX_PLANE1_TILING_V = 8
        else:
            assert False
    else:
        assert False
    jpeg.PX_PLANE0_STRIDE = surface_stride
    jpeg.PX_PLANE1_STRIDE = surface_P1_stride

    if pixfmt in ['RGB888', 'RGB101010', 'RGB565', 'YUV10', 'YUV444-planar']:
        if args.encode_subsampling in ['422', '420']:
            jpeg.CHROMA_HALVE_H_TYPE1 = 1
        if args.encode_subsampling == '420':
            jpeg.CHROMA_HALVE_V_TYPE1 = 1
    elif pixfmt in ['YUV-linear', 'YUV422-planar']:
        if args.encode_subsampling == '420':
            jpeg.CHROMA_HALVE_V_TYPE1 = 1
    elif pixfmt == 'YUV420-planar':
        if args.encode_subsampling in ['422', '444']:
            jpeg.CHROMA_DOUBLE_V = 1
    else:
        assert False

    # none of this seems to affect anything????
    jpeg.REG_0x94 = 0xc     # c/2 for 444; 8/2 for 422; 3/1 for 411; b/2 for 400
    jpeg.REG_0x98 = 0x2
    jpeg.REG_0x20c = im_W
    jpeg.REG_0x210 = im_H

    if pixfmt in ['RGB888', 'RGB101010', 'RGB565']:
        jpeg.CONVERT_COLOR_SPACE = 1
    jpeg.MATRIX_MULT[0].val = 0x4d
    jpeg.MATRIX_MULT[1].val = 0x96
    jpeg.MATRIX_MULT[2].val = 0x1d
    jpeg.MATRIX_MULT[3].val = 0xffffffd5
    jpeg.MATRIX_MULT[4].val = 0xffffffab
    jpeg.MATRIX_MULT[5].val = 0x80
    jpeg.MATRIX_MULT[6].val = 0x80
    jpeg.MATRIX_MULT[7].val = 0xffffff95
    jpeg.MATRIX_MULT[8].val = 0xffffffeb
    jpeg.MATRIX_MULT[9].val = 0x0
    jpeg.MATRIX_MULT[10].val = 0x80

    if pixfmt == 'RGB888':
        jpeg.ENCODE_PIXEL_FORMAT.set(FORMAT=E_ENCODE_PIXEL_FORMAT.RGB888)
    elif pixfmt == 'RGB101010':
        jpeg.ENCODE_PIXEL_FORMAT.set(FORMAT=E_ENCODE_PIXEL_FORMAT.RGB101010)
    elif pixfmt == 'RGB565':
        jpeg.ENCODE_PIXEL_FORMAT.set(FORMAT=E_ENCODE_PIXEL_FORMAT.RGB565)
    elif pixfmt == 'YUV10':
        jpeg.ENCODE_PIXEL_FORMAT.set(FORMAT=E_ENCODE_PIXEL_FORMAT.YUV10_linear)
    elif pixfmt == 'YUV-linear':
        jpeg.ENCODE_PIXEL_FORMAT.set(FORMAT=E_ENCODE_PIXEL_FORMAT.YUV_linear)
    elif pixfmt in ['YUV444-planar', 'YUV422-planar', 'YUV420-planar']:
        jpeg.ENCODE_PIXEL_FORMAT.set(FORMAT=E_ENCODE_PIXEL_FORMAT.YUV_planar)
    else:
        assert False
    if pixfmt == 'YUV-linear':
        jpeg.ENCODE_COMPONENT0_POS = 0
        jpeg.ENCODE_COMPONENT1_POS = 1
        jpeg.ENCODE_COMPONENT2_POS = 3
        jpeg.ENCODE_COMPONENT3_POS = 2
    elif pixfmt in ['YUV422-planar', 'YUV420-planar', 'YUV444-planar']:
        jpeg.ENCODE_COMPONENT0_POS = 0
        jpeg.ENCODE_COMPONENT1_POS = 0
        jpeg.ENCODE_COMPONENT2_POS = 1
        jpeg.ENCODE_COMPONENT3_POS = 3
    else:
        jpeg.ENCODE_COMPONENT0_POS = 0
        jpeg.ENCODE_COMPONENT1_POS = 1
        jpeg.ENCODE_COMPONENT2_POS = 2
        jpeg.ENCODE_COMPONENT3_POS = 3

    jpeg.INPUT_START1 = input_buf_iova
    jpeg.INPUT_START2 = input_buf_iova + surface_P1_off
    jpeg.INPUT_END = input_buf_iova + input_mem_sz + 7  # NOTE +7
    jpeg.OUTPUT_START1 = output_buf_iova
    jpeg.OUTPUT_START2 = 0xdeadbeef
    jpeg.OUTPUT_END = output_buf_iova + output_mem_sz

    jpeg.REG_0x118 = 0x1
    jpeg.REG_0x11c = 0x0

    jpeg.ENABLE_RST_LOGGING = args.encode_rst_interval is not None

    jpeg.MODE = 0x16f
    if args.encode_subsampling == '444':
        jpeg_subsampling = E_JPEG_IO_FLAGS_SUBSAMPLING._444
    elif args.encode_subsampling == '422':
        jpeg_subsampling = E_JPEG_IO_FLAGS_SUBSAMPLING._422
    elif args.encode_subsampling == '420':
        jpeg_subsampling = E_JPEG_IO_FLAGS_SUBSAMPLING._420
    elif args.encode_subsampling == '400':
        jpeg_subsampling = E_JPEG_IO_FLAGS_SUBSAMPLING._400
    else:
        assert False
    jpeg.JPEG_IO_FLAGS.set(
        OUTPUT_8BYTE_CHUNKS_CORRECTLY=1,
        OUTPUT_MACROBLOCKS_UNFLIPPED_H=1,
        SUBSAMPLING_MODE=jpeg_subsampling
    )
    jpeg.JPEG_WIDTH = im_W
    jpeg.JPEG_HEIGHT = im_H
    if args.encode_rst_interval is not None:
        jpeg.RST_INTERVAL = args.encode_rst_interval
    else:
        jpeg.RST_INTERVAL = 0
    jpeg.JPEG_OUTPUT_FLAGS = 0

    jpeg.QTBL[0].val =  0xa06e64a0
    jpeg.QTBL[1].val =  0xf0ffffff
    jpeg.QTBL[2].val =  0x78788cbe
    jpeg.QTBL[3].val =  0xffffffff
    jpeg.QTBL[4].val =  0x8c82a0f0
    jpeg.QTBL[5].val =  0xffffffff
    jpeg.QTBL[6].val =  0x8caadcff
    jpeg.QTBL[7].val =  0xffffffff
    jpeg.QTBL[8].val =  0xb4dcffff
    jpeg.QTBL[9].val =  0xffffffff
    jpeg.QTBL[10].val = 0xf0ffffff
    jpeg.QTBL[11].val = 0xffffffff
    jpeg.QTBL[12].val = 0xffffffff
    jpeg.QTBL[13].val = 0xffffffff
    jpeg.QTBL[14].val = 0xffffffff
    jpeg.QTBL[15].val = 0xffffffff

    jpeg.QTBL[16].val = 0xaab4f0ff
    jpeg.QTBL[17].val = 0xffffffff
    jpeg.QTBL[18].val = 0xb4d2ffff
    jpeg.QTBL[19].val = 0xffffffff
    jpeg.QTBL[20].val = 0xf0ffffff
    jpeg.QTBL[21].val = 0xffffffff
    jpeg.QTBL[22].val = 0xffffffff
    jpeg.QTBL[23].val = 0xffffffff
    jpeg.QTBL[24].val = 0xffffffff
    jpeg.QTBL[25].val = 0xffffffff
    jpeg.QTBL[26].val = 0xffffffff
    jpeg.QTBL[27].val = 0xffffffff
    jpeg.QTBL[28].val = 0xffffffff
    jpeg.QTBL[29].val = 0xffffffff
    jpeg.QTBL[30].val = 0xffffffff
    jpeg.QTBL[31].val = 0xffffffff

    jpeg.QTBL[32].val = 0x01010201
    jpeg.QTBL[33].val = 0x01020202
    jpeg.QTBL[34].val = 0x02030202
    jpeg.QTBL[35].val = 0x03030604
    jpeg.QTBL[36].val = 0x03030303
    jpeg.QTBL[37].val = 0x07050804
    jpeg.QTBL[38].val = 0x0608080a
    jpeg.QTBL[39].val = 0x0908070b
    jpeg.QTBL[40].val = 0x080a0e0d
    jpeg.QTBL[41].val = 0x0b0a0a0c
    jpeg.QTBL[42].val = 0x0a08080b
    jpeg.QTBL[43].val = 0x100c0c0d
    jpeg.QTBL[44].val = 0x0f0f0f0f
    jpeg.QTBL[45].val = 0x090b1011
    jpeg.QTBL[46].val = 0x0f0e110d
    jpeg.QTBL[47].val = 0x0e0e0e01

    jpeg.QTBL[48].val = 0x04040405
    jpeg.QTBL[49].val = 0x04050905
    jpeg.QTBL[50].val = 0x05090f0a
    jpeg.QTBL[51].val = 0x080a0f1a
    jpeg.QTBL[52].val = 0x13090913
    jpeg.QTBL[53].val = 0x1a1a1a1a
    jpeg.QTBL[54].val = 0x0d1a1a1a
    jpeg.QTBL[55].val = 0x1a1a1a1a
    jpeg.QTBL[56].val = 0x1a1a1a1a
    jpeg.QTBL[57].val = 0x1a1a1a1a
    jpeg.QTBL[58].val = 0x1a1a1a1a
    jpeg.QTBL[59].val = 0x1a1a1a1a
    jpeg.QTBL[60].val = 0x1a1a1a1a
    jpeg.QTBL[61].val = 0x1a1a1a1a
    jpeg.QTBL[62].val = 0x1a1a1a1a
    jpeg.QTBL[63].val = 0x1a1a1a1a

    jpeg.HUFFMAN_TABLE.val = 0x3c
    jpeg.QTBL_SEL.val = 0xff
    jpeg.REG_0x0.val = 0x1
    jpeg.REG_0x1004.val = 0x1

    # FIXME: we don't actually know when it's done
    time.sleep(1)

    print(jpeg.STATUS.reg)
    print(jpeg.PERFCOUNTER.reg)
    jpeg_out_sz = jpeg.COMPRESSED_BYTES.val
    print(f"JPEG output is {jpeg_out_sz} bytes")

    rst_log_n = jpeg.RST_LOG_ENTRIES.val
    for i in range(rst_log_n):
        print(f"RST log[{i}] = 0x{jpeg.RSTLOG[i].val:X}")

    output_data = iface.readmem(output_buf_phys, output_mem_sz)
    if args.raw_output is not None:
        with open(args.raw_output, 'wb') as f:
            f.write(output_data)
    with open(args.output, 'wb') as f:
        f.write(output_data[:jpeg_out_sz])
