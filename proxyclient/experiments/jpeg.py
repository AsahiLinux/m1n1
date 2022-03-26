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


ap = argparse.ArgumentParser(description='JPEG block experiment')
ap.add_argument("--jpeg", dest='which_jpeg', type=str, default='jpeg0',
                help='which JPEG instance (jpeg0/jpeg1)')
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("-e", "--encode", action='store_true')
g.add_argument("-d", "--decode", action='store_true')
ap.add_argument("--raw-output", type=str, required=False)
ap.add_argument("input", type=str)
ap.add_argument("output", type=str)
args = ap.parse_args()

# print(args)

# Perform necessary pre-parsing
if args.decode:
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

    if jpeg_MODE == '444':
        macroblock_W, macroblock_H = 8, 8
    elif jpeg_MODE == '400':
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
    surface_W = divroundup(jpeg_W, macroblock_W) * macroblock_W
    surface_H = divroundup(jpeg_H, macroblock_H) * macroblock_H
    BYTESPP = 4
    surface_stride = surface_W * BYTESPP

    input_mem_sz = align_up(len(jpeg_data))
    print(f"Using size {input_mem_sz:08X} for JPEG data")

    output_mem_sz = align_up(surface_stride*surface_H)
    print(f"Using size {output_mem_sz:08X} for output image")
else:
    assert False
    # TODO

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
    jpeg.REG_0x15c.val = 0
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
    jpeg.REG_0x124.val = 0
    jpeg.REG_0x128.val = 0
    jpeg.REG_0x12c.val = 0
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
    jpeg.CODEC.set(CODEC=E_CODEC._444)
    jpeg.DECODE_PIXEL_FORMAT.set(FORMAT=E_DECODE_PIXEL_FORMAT.RGBA8888)

    jpeg.PX_USE_PLANE1 = 0
    jpeg.PX_PLANE0_WIDTH = jpeg_W*BYTESPP - 1
    jpeg.PX_PLANE0_HEIGHT = jpeg_H - 1
    # TODO P1
    jpeg.TIMEOUT.val = 266000000

    jpeg.REG_0x94 = 0x1f
    jpeg.REG_0x98 = 1

    jpeg.DECODE_MACROBLOCKS_W.val = divroundup(jpeg_W, macroblock_W)
    jpeg.DECODE_MACROBLOCKS_H.val = divroundup(jpeg_H, macroblock_H)
    # right_edge_px = jpeg_W - divroundup(jpeg_W, 8)*8 + 8
    # bot_edge_px = jpeg_H - divroundup(jpeg_H, 8)*8 + 8
    # # XXX changing this does not seem to do anything
    # jpeg.RIGHT_EDGE_PIXELS.val = right_edge_px
    # jpeg.BOTTOM_EDGE_PIXELS.val = bot_edge_px
    # jpeg.RIGHT_EDGE_SAMPLES.val = right_edge_px // 2
    # jpeg.BOTTOM_EDGE_SAMPLES.val = bot_edge_px // 2

    jpeg.PX_TILES_H.val = divroundup(jpeg_H, macroblock_W)
    jpeg.PX_TILES_W.val = divroundup(jpeg_W, macroblock_H)
    jpeg.PX_PLANE0_TILING_H.val = 4
    jpeg.PX_PLANE0_TILING_V.val = 8
    jpeg.PX_PLANE1_TILING_H.val = 1
    jpeg.PX_PLANE1_TILING_V.val = 1

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

    jpeg.RGBA_ALPHA.val = 0xff
    jpeg.RGBA_ORDER.val = 1

    jpeg.SCALE_FACTOR.val = 0

    jpeg.INPUT_START1.val = input_buf_iova
    jpeg.INPUT_START2.val = 0xdeadbeef
    jpeg.INPUT_END.val = input_buf_iova + input_mem_sz
    jpeg.OUTPUT_START1.val = output_buf_iova
    # jpeg.OUTPUT_START2.val = output_buf_iova + jpeg_W * 4   # HACK
    jpeg.OUTPUT_START2.val = 0xdeadbeef
    jpeg.OUTPUT_END.val = output_buf_iova + output_mem_sz
    jpeg.PX_PLANE0_STRIDE.val = surface_stride
    # jpeg.PX_PLANE1_STRIDE.val = output_W * 4    # HACK

    jpeg.REG_0x1ac.val = 0x0
    jpeg.REG_0x1b0.val = 0x0
    jpeg.REG_0x1b4.val = 0x0
    jpeg.REG_0x1bc.val = 0x0
    jpeg.REG_0x1c0.val = 0x0
    jpeg.REG_0x1c4.val = 0x0

    jpeg.REG_0x118.val = 0x0
    jpeg.REG_0x11c.val = 0x1

    jpeg.MODE.val = 0x177
    jpeg.REG_0x1028.val = 0x400

    jpeg.JPEG_IO_FLAGS.val = 0x3f
    jpeg.REG_0x0.val = 0x1
    jpeg.REG_0x1004 = 0x1

    # FIXME: we don't actually know when it's done
    time.sleep(1)

    print(jpeg.STATUS.reg)
    print(jpeg.PERFCOUNTER.reg)

    output_data = iface.readmem(output_buf_phys, output_mem_sz)
    if args.raw_output is not None:
        with open(args.raw_output, 'wb') as f:
            f.write(output_data)

    with Image.new(mode='RGBA', size=(jpeg_W, jpeg_H)) as im:
        for y in range(jpeg_H):
            for x in range(jpeg_W):
                block = output_data[
                    y*surface_stride + x*BYTESPP:
                    y*surface_stride + (x+1)*BYTESPP]

                r, g, b, a = block
                im.putpixel((x, y), (r, g, b, a))
        im.save(args.output)
