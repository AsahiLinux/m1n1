#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.dart8110 import DART8110
from m1n1.hw.scaler import *
from m1n1.utils import *
import struct
import time
from PIL import Image, ImageDraw

SCALER_ADT = '/arm-io/scaler0'
DART_ADT = '/arm-io/dart-scaler0'

p.pmgr_adt_clocks_enable(DART_ADT)
p.pmgr_adt_clocks_enable(SCALER_ADT)

dart = DART8110.from_adt(u, DART_ADT)
dart.initialize()

scaler_base, _ = u.adt[SCALER_ADT].get_reg(0)
apiodma_base, _ = u.adt[SCALER_ADT].get_reg(1)
dpe_ctrl_base, _ = u.adt[SCALER_ADT].get_reg(2)

scaler = ScalerMainRegs(u, scaler_base)

def dpe_start():
    p.write32(dpe_ctrl_base + 0x400, 0x1)
    p.write32(dpe_ctrl_base + 0x404, 0x1)
    p.write32(dpe_ctrl_base + 0x438, 0xf)
    p.write32(dpe_ctrl_base + 0x43c, 0x5)
    p.write32(dpe_ctrl_base + 0x408, 0x1)
    p.write32(dpe_ctrl_base + 0x440, 0x5)
    p.write32(dpe_ctrl_base + 0x444, 0x4)
    p.write32(dpe_ctrl_base + 0x40c, 0x1)
    p.write32(dpe_ctrl_base + 0x448, 0x5)
    p.write32(dpe_ctrl_base + 0x44c, 0x5)
    p.write32(dpe_ctrl_base + 0x410, 0x1)
    p.write32(dpe_ctrl_base + 0x450, 0x7)
    p.write32(dpe_ctrl_base + 0x454, 0x7)
    p.write32(dpe_ctrl_base + 0x414, 0x1)
    p.write32(dpe_ctrl_base + 0x458, 0xd)
    p.write32(dpe_ctrl_base + 0x45c, 0xc)
    p.write32(dpe_ctrl_base + 0x418, 0x1)
    p.write32(dpe_ctrl_base + 0x460, 0x13)
    p.write32(dpe_ctrl_base + 0x464, 0x12)
    p.write32(dpe_ctrl_base + 0x41c, 0x1)
    p.write32(dpe_ctrl_base + 0x468, 0x9)
    p.write32(dpe_ctrl_base + 0x46c, 0xa)
    p.write32(dpe_ctrl_base + 0x420, 0x1)
    p.write32(dpe_ctrl_base + 0x470, 0x33)
    p.write32(dpe_ctrl_base + 0x474, 0x2c)
    p.write32(dpe_ctrl_base + 0x424, 0x1)
    p.write32(dpe_ctrl_base + 0x478, 0x15)
    p.write32(dpe_ctrl_base + 0x47c, 0x15)
    p.write32(dpe_ctrl_base + 0x428, 0x1)
    p.write32(dpe_ctrl_base + 0x480, 0xe)
    p.write32(dpe_ctrl_base + 0x484, 0x5)
    p.write32(dpe_ctrl_base + 0x42c, 0x1)
    p.write32(dpe_ctrl_base + 0x488, 0x27)
    p.write32(dpe_ctrl_base + 0x48c, 0x15)
    p.write32(dpe_ctrl_base + 0x430, 0x1)
    p.write32(dpe_ctrl_base + 0x490, 0x15)
    p.write32(dpe_ctrl_base + 0x494, 0xe)
    p.write32(dpe_ctrl_base + 0x434, 0x1)
    p.write32(dpe_ctrl_base + 0x498, 0x0)
    p.write32(dpe_ctrl_base + 0x49c, 0x0)
    p.write32(dpe_ctrl_base + 0x4, 0x1000)
    p.write32(dpe_ctrl_base + 0x0, 0x101)

def dpe_stop():
    p.write32(dpe_ctrl_base + 0x0, 0x103)
    while p.read32(dpe_ctrl_base + 0x0) & 0xC != 4:
        ...
    p.write32(dpe_ctrl_base + 0x0, p.read32(dpe_ctrl_base + 0x0) & 0xfffffffc)

print(f"Hardware version {scaler.HW_VERSION.val:08X}")

scaler.RESET = 1
scaler.RESET = 0

print(f"Hardware version after reset {scaler.HW_VERSION.val:08X}")

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} input.png output.png")
    sys.exit(-1)

input_image_fn = sys.argv[1]
output_image_fn = sys.argv[2]

in_data = b''
with Image.open(input_image_fn) as im:
    in_W, in_H = im.size
    in_BYTESPP = 4
    in_STRIDE = in_W * in_BYTESPP
    in_SZ = in_W * in_H * in_BYTESPP

    for y in range(in_H):
        for x in range(in_W):
            r, g, b = im.getpixel((x, y))
            in_data += struct.pack("BBBB", r, g, b, 255)

out_W = in_W * 5
out_H = in_H * 3
out_BYTESPP = 4
out_STRIDE = out_W * out_BYTESPP
out_SZ = out_W * out_H * out_BYTESPP * 2  # HACK: double size for testing purposes

for i in range(in_W * in_H):
    in_data += struct.pack("<I", i & 0xFFFFFFFF)
# chexdump(in_data)

out_buf_phys = u.heap.memalign(0x4000, out_SZ)
iface.writemem(out_buf_phys, b'\xAA' * out_SZ)
out_buf_iova = dart.iomap(0, out_buf_phys, out_SZ)
print(f"Output buffer @ phys {out_buf_phys:016X} iova {out_buf_iova:016X}")

in_buf_phys = u.heap.memalign(0x4000, in_SZ)
iface.writemem(in_buf_phys, in_data)
in_buf_iova = dart.iomap(0, in_buf_phys, in_SZ)
print(f"Input buffer @ phys {in_buf_phys:016X} iova {in_buf_iova:016X}")
dart.dump_all()



dpe_start()

# reset CM
p.write32(scaler_base + 0x3800, 0x0)

# RDMA control
p.write32(scaler_base + 0x180, 0x1)
p.write32(scaler_base + 0x184, 0x1e)
p.write32(scaler_base + 0x188, 0x0)
p.write32(scaler_base + 0x18c, 0x0)
p.write32(scaler_base + 0x190, 0x0)

# transform config (flip/rotate)
scaler.FLIP_ROTATE.set()

# cache hints
scaler.CACHE_HINTS_THING0[0].val = 0x7d311
scaler.CACHE_HINTS_THING0[1].val = 0x7d311
scaler.CACHE_HINTS_THING0[2].val = 0x7d311
scaler.CACHE_HINTS_THING0[3].val = 0x7d311
scaler.CACHE_HINTS_THING2[0].val = 0xbd311
scaler.CACHE_HINTS_THING2[1].val = 0xbd311
scaler.CACHE_HINTS_THING2[2].val = 0xbd311
# scaler.CACHE_HINTS_THING2[3].val = 0xbd311
scaler.CACHE_HINTS_THING1[0].val = 0x707
scaler.CACHE_HINTS_THING1[1].val = 0x707
scaler.CACHE_HINTS_THING1[2].val = 0x707
scaler.CACHE_HINTS_THING1[3].val = 0x707
scaler.CACHE_HINTS_THING3[0].val = 0xc0bd307
scaler.CACHE_HINTS_THING3[1].val = 0xc0bd307
scaler.CACHE_HINTS_THING3[2].val = 0xc0bd307
# scaler.CACHE_HINTS_THING3[3].val = 0xc0bd307

# tunables
scaler.TUNABLES_THING0[0].val = 0x20
scaler.TUNABLES_THING0[1].val = 0x20
scaler.TUNABLES_THING0[2].val = 0x20
scaler.TUNABLES_THING0[3].val = 0x20
scaler.TUNABLES_THING1[0].val = 0x4000720
scaler.TUNABLES_THING1[1].val = 0x4000720
scaler.TUNABLES_THING1[2].val = 0x4000720
# scaler.TUNABLES_THING1[3].val = 0x4000720

# dest base addresses
scaler.DST_PLANE1_LO = 0
scaler.DST_PLANE1_HI = 0
scaler.DST_PLANE0_LO = out_buf_iova & 0xFFFFFFFF
scaler.DST_PLANE0_HI = out_buf_iova >> 32
scaler.DST_PLANE2_LO = 0
scaler.DST_PLANE2_HI = 0

# src base addresses
scaler.SRC_PLANE1_LO = 0
scaler.SRC_PLANE1_HI = 0
scaler.SRC_PLANE0_LO = in_buf_iova & 0xFFFFFFFF
scaler.SRC_PLANE0_HI = in_buf_iova >> 32
scaler.SRC_PLANE2_LO = 0
scaler.SRC_PLANE2_HI = 0

# dest stride
scaler.DST_PLANE1_STRIDE = 0
scaler.DST_PLANE0_STRIDE = out_STRIDE
scaler.DST_PLANE2_STRIDE = 0

# src stride
scaler.SRC_PLANE1_STRIDE = 0
scaler.SRC_PLANE0_STRIDE = in_STRIDE
scaler.SRC_PLANE2_STRIDE = 0

# dest offset
scaler.DST_PLANE1_OFFSET = 0
scaler.DST_PLANE0_OFFSET = 0
scaler.DST_PLANE2_OFFSET = 0

# src offset
scaler.SRC_PLANE1_OFFSET = 0
scaler.SRC_PLANE0_OFFSET = 0
scaler.SRC_PLANE2_OFFSET = 0

# dest sizes
scaler.DST_W = out_W
scaler.DST_H = out_H

scaler.DST_SIZE_THING3 = 0
scaler.DST_SIZE_THING6 = 0
scaler.DST_SIZE_THING2 = 0
scaler.DST_SIZE_THING5 = 0
scaler.DST_SIZE_THING4 = 0
scaler.DST_SIZE_THING7 = 0

# src sizes
scaler.SRC_W = in_W
scaler.SRC_H = in_H

scaler.SRC_SIZE_THING3 = 0
scaler.SRC_SIZE_THING6 = 0
scaler.SRC_SIZE_THING2 = 0
scaler.SRC_SIZE_THING5 = 0
scaler.SRC_SIZE_THING4 = 0
scaler.SRC_SIZE_THING7 = 0

# swizzling
scaler.SRC_SWIZZLE = 0x03020100
scaler.DST_SWIZZLE = 0x03020100

# WDMA control
p.write32(scaler_base + 0x280, 0x1)
p.write32(scaler_base + 0x284, 0x81e)
p.write32(scaler_base + 0x288, 0x800)
p.write32(scaler_base + 0x28c, 0x800)

# pixel averaging
scaler.PIXEL_AVERAGING = 0

# ASE enhancement
p.write32(scaler_base + 0x16800, 0x0)

# ASE 3x1 transform
p.write32(scaler_base + 0x16080, 0x0)
p.write32(scaler_base + 0x16084, 0xb710367)
p.write32(scaler_base + 0x16088, 0x128)

# ASE interpolation
p.write32(scaler_base + 0x16600, 0x15)

# ASE angle detect
p.write32(scaler_base + 0x16504, 0x2000500)
p.write32(scaler_base + 0x16508, 0x3200)
p.write32(scaler_base + 0x16534, 0x8)
p.write32(scaler_base + 0x1651c, 0x851400)
p.write32(scaler_base + 0x16568, 0x250500)
p.write32(scaler_base + 0x16588, 0x496513)

# ASE config
p.write32(scaler_base + 0x16000, 0x0)

# chroma upsampling
p.write32(scaler_base + 0x800, 0xc)

# chroma downsampling
p.write32(scaler_base + 0x900, 0x0)

# DDA init V???
scaler.SCALE_H_DDA_THING0 = 0
scaler.SCALE_H_DDA_THING2 = 0
scaler.SCALE_V_DDA_THING1 = 0

# vertical scaling
scaler.SCALE_V_RATIO_0 = int(in_H / out_H * 0x400000)
scaler.SCALE_V_RATIO_4 = 0  # XXX what does this do?
scaler.SCALE_V_RATIO_1 = 0  # XXX what does this do?
scaler.SCALE_V_RATIO_2 = 0  # XXX what does this set do?
scaler.SCALE_V_RATIO_3 = 0  # XXX what does this set do?
scaler.SCALE_V_RATIO_5 = 0  # XXX what does this set do?
scaler.SCALE_V_FLAGS.set(EN=1)

# XXX this is a random filter grabbed from a random trace
scaler.SCALE_FILTER_V_BLOCK0[0].val = 0x0
scaler.SCALE_FILTER_V_BLOCK0[1].val = 0x50005
scaler.SCALE_FILTER_V_BLOCK1[0].val = 0x50000
scaler.SCALE_FILTER_V_BLOCK0[2].val = 0xb000b
scaler.SCALE_FILTER_V_BLOCK0[3].val = 0x100010
scaler.SCALE_FILTER_V_BLOCK1[1].val = 0x10000b
scaler.SCALE_FILTER_V_BLOCK0[4].val = 0x140014
scaler.SCALE_FILTER_V_BLOCK0[5].val = 0x180018
scaler.SCALE_FILTER_V_BLOCK1[2].val = 0x180014
scaler.SCALE_FILTER_V_BLOCK0[6].val = 0x1c001c
scaler.SCALE_FILTER_V_BLOCK0[7].val = 0x200020
scaler.SCALE_FILTER_V_BLOCK1[3].val = 0x20001c
scaler.SCALE_FILTER_V_BLOCK0[8].val = 0x230023
scaler.SCALE_FILTER_V_BLOCK0[9].val = 0x260026
scaler.SCALE_FILTER_V_BLOCK1[4].val = 0x260023
scaler.SCALE_FILTER_V_BLOCK0[10].val = 0x290029
scaler.SCALE_FILTER_V_BLOCK0[11].val = 0x2c002c
scaler.SCALE_FILTER_V_BLOCK1[5].val = 0x2c0029
scaler.SCALE_FILTER_V_BLOCK0[12].val = 0x2e002e
scaler.SCALE_FILTER_V_BLOCK0[13].val = 0x300030
scaler.SCALE_FILTER_V_BLOCK1[6].val = 0x30002e
scaler.SCALE_FILTER_V_BLOCK0[14].val = 0x320032
scaler.SCALE_FILTER_V_BLOCK0[15].val = 0x330033
scaler.SCALE_FILTER_V_BLOCK1[7].val = 0x330032
scaler.SCALE_FILTER_V_BLOCK0[16].val = 0xff87ff87
scaler.SCALE_FILTER_V_BLOCK0[17].val = 0xff90ff90
scaler.SCALE_FILTER_V_BLOCK1[8].val = 0xff90ff87
scaler.SCALE_FILTER_V_BLOCK0[18].val = 0xff99ff99
scaler.SCALE_FILTER_V_BLOCK0[19].val = 0xffa1ffa1
scaler.SCALE_FILTER_V_BLOCK1[9].val = 0xffa1ff99
scaler.SCALE_FILTER_V_BLOCK0[20].val = 0xffaaffaa
scaler.SCALE_FILTER_V_BLOCK0[21].val = 0xffb2ffb2
scaler.SCALE_FILTER_V_BLOCK1[10].val = 0xffb2ffaa
scaler.SCALE_FILTER_V_BLOCK0[22].val = 0xffbaffba
scaler.SCALE_FILTER_V_BLOCK0[23].val = 0xffc2ffc2
scaler.SCALE_FILTER_V_BLOCK1[11].val = 0xffc2ffba
scaler.SCALE_FILTER_V_BLOCK0[24].val = 0xffcaffca
scaler.SCALE_FILTER_V_BLOCK0[25].val = 0xffd2ffd2
scaler.SCALE_FILTER_V_BLOCK1[12].val = 0xffd2ffca
scaler.SCALE_FILTER_V_BLOCK0[26].val = 0xffd9ffd9
scaler.SCALE_FILTER_V_BLOCK0[27].val = 0xffe0ffe0
scaler.SCALE_FILTER_V_BLOCK1[13].val = 0xffe0ffd9
scaler.SCALE_FILTER_V_BLOCK0[28].val = 0xffe7ffe7
scaler.SCALE_FILTER_V_BLOCK0[29].val = 0xffeeffee
scaler.SCALE_FILTER_V_BLOCK1[14].val = 0xffeeffe7
scaler.SCALE_FILTER_V_BLOCK0[30].val = 0xfff4fff4
scaler.SCALE_FILTER_V_BLOCK0[31].val = 0xfffafffa
scaler.SCALE_FILTER_V_BLOCK1[15].val = 0xfffafff4
scaler.SCALE_FILTER_V_BLOCK0[32].val = 0xff06ff06
scaler.SCALE_FILTER_V_BLOCK0[33].val = 0xff0cff0c
scaler.SCALE_FILTER_V_BLOCK1[16].val = 0xff0cff06
scaler.SCALE_FILTER_V_BLOCK0[34].val = 0xff13ff13
scaler.SCALE_FILTER_V_BLOCK0[35].val = 0xff1aff1a
scaler.SCALE_FILTER_V_BLOCK1[17].val = 0xff1aff13
scaler.SCALE_FILTER_V_BLOCK0[36].val = 0xff21ff21
scaler.SCALE_FILTER_V_BLOCK0[37].val = 0xff28ff28
scaler.SCALE_FILTER_V_BLOCK1[18].val = 0xff28ff21
scaler.SCALE_FILTER_V_BLOCK0[38].val = 0xff30ff30
scaler.SCALE_FILTER_V_BLOCK0[39].val = 0xff38ff38
scaler.SCALE_FILTER_V_BLOCK1[19].val = 0xff38ff30
scaler.SCALE_FILTER_V_BLOCK0[40].val = 0xff41ff41
scaler.SCALE_FILTER_V_BLOCK0[41].val = 0xff49ff49
scaler.SCALE_FILTER_V_BLOCK1[20].val = 0xff49ff41
scaler.SCALE_FILTER_V_BLOCK0[42].val = 0xff52ff52
scaler.SCALE_FILTER_V_BLOCK0[43].val = 0xff5bff5b
scaler.SCALE_FILTER_V_BLOCK1[21].val = 0xff5bff52
scaler.SCALE_FILTER_V_BLOCK0[44].val = 0xff63ff63
scaler.SCALE_FILTER_V_BLOCK0[45].val = 0xff6cff6c
scaler.SCALE_FILTER_V_BLOCK1[22].val = 0xff6cff63
scaler.SCALE_FILTER_V_BLOCK0[46].val = 0xff75ff75
scaler.SCALE_FILTER_V_BLOCK0[47].val = 0xff7eff7e
scaler.SCALE_FILTER_V_BLOCK1[23].val = 0xff7eff75
scaler.SCALE_FILTER_V_BLOCK0[48].val = 0xff02ff02
scaler.SCALE_FILTER_V_BLOCK0[49].val = 0xfefcfefc
scaler.SCALE_FILTER_V_BLOCK1[24].val = 0xfefcff02
scaler.SCALE_FILTER_V_BLOCK0[50].val = 0xfef7fef7
scaler.SCALE_FILTER_V_BLOCK0[51].val = 0xfef3fef3
scaler.SCALE_FILTER_V_BLOCK1[25].val = 0xfef3fef7
scaler.SCALE_FILTER_V_BLOCK0[52].val = 0xfeeffeef
scaler.SCALE_FILTER_V_BLOCK0[53].val = 0xfeedfeed
scaler.SCALE_FILTER_V_BLOCK1[26].val = 0xfeedfeef
scaler.SCALE_FILTER_V_BLOCK0[54].val = 0xfeecfeec
scaler.SCALE_FILTER_V_BLOCK0[55].val = 0xfeebfeeb
scaler.SCALE_FILTER_V_BLOCK1[27].val = 0xfeebfeec
scaler.SCALE_FILTER_V_BLOCK0[56].val = 0xfeebfeeb
scaler.SCALE_FILTER_V_BLOCK0[57].val = 0xfeecfeec
scaler.SCALE_FILTER_V_BLOCK1[28].val = 0xfeecfeeb
scaler.SCALE_FILTER_V_BLOCK0[58].val = 0xfeeefeee
scaler.SCALE_FILTER_V_BLOCK0[59].val = 0xfef1fef1
scaler.SCALE_FILTER_V_BLOCK1[29].val = 0xfef1feee
scaler.SCALE_FILTER_V_BLOCK0[60].val = 0xfef4fef4
scaler.SCALE_FILTER_V_BLOCK0[61].val = 0xfef8fef8
scaler.SCALE_FILTER_V_BLOCK1[30].val = 0xfef8fef4
scaler.SCALE_FILTER_V_BLOCK0[62].val = 0xfefcfefc
scaler.SCALE_FILTER_V_BLOCK0[63].val = 0xff01ff01
scaler.SCALE_FILTER_V_BLOCK1[31].val = 0xff01fefc
scaler.SCALE_FILTER_V_BLOCK0[64].val = 0x0
scaler.SCALE_FILTER_V_BLOCK0[65].val = 0xffe7ffe7
scaler.SCALE_FILTER_V_BLOCK1[32].val = 0xffe70000
scaler.SCALE_FILTER_V_BLOCK0[66].val = 0xffcfffcf
scaler.SCALE_FILTER_V_BLOCK0[67].val = 0xffb9ffb9
scaler.SCALE_FILTER_V_BLOCK1[33].val = 0xffb9ffcf
scaler.SCALE_FILTER_V_BLOCK0[68].val = 0xffa4ffa4
scaler.SCALE_FILTER_V_BLOCK0[69].val = 0xff90ff90
scaler.SCALE_FILTER_V_BLOCK1[34].val = 0xff90ffa4
scaler.SCALE_FILTER_V_BLOCK0[70].val = 0xff7dff7d
scaler.SCALE_FILTER_V_BLOCK0[71].val = 0xff6bff6b
scaler.SCALE_FILTER_V_BLOCK1[35].val = 0xff6bff7d
scaler.SCALE_FILTER_V_BLOCK0[72].val = 0xff5bff5b
scaler.SCALE_FILTER_V_BLOCK0[73].val = 0xff4cff4c
scaler.SCALE_FILTER_V_BLOCK1[36].val = 0xff4cff5b
scaler.SCALE_FILTER_V_BLOCK0[74].val = 0xff3eff3e
scaler.SCALE_FILTER_V_BLOCK0[75].val = 0xff31ff31
scaler.SCALE_FILTER_V_BLOCK1[37].val = 0xff31ff3e
scaler.SCALE_FILTER_V_BLOCK0[76].val = 0xff26ff26
scaler.SCALE_FILTER_V_BLOCK0[77].val = 0xff1bff1b
scaler.SCALE_FILTER_V_BLOCK1[38].val = 0xff1bff26
scaler.SCALE_FILTER_V_BLOCK0[78].val = 0xff12ff12
scaler.SCALE_FILTER_V_BLOCK0[79].val = 0xff0aff0a
scaler.SCALE_FILTER_V_BLOCK1[39].val = 0xff0aff12
scaler.SCALE_FILTER_V_BLOCK0[80].val = 0x2210221
scaler.SCALE_FILTER_V_BLOCK0[81].val = 0x1f901f9
scaler.SCALE_FILTER_V_BLOCK1[40].val = 0x1f90221
scaler.SCALE_FILTER_V_BLOCK0[82].val = 0x1d001d0
scaler.SCALE_FILTER_V_BLOCK0[83].val = 0x1a901a9
scaler.SCALE_FILTER_V_BLOCK1[41].val = 0x1a901d0
scaler.SCALE_FILTER_V_BLOCK0[84].val = 0x1820182
scaler.SCALE_FILTER_V_BLOCK0[85].val = 0x15d015d
scaler.SCALE_FILTER_V_BLOCK1[42].val = 0x15d0182
scaler.SCALE_FILTER_V_BLOCK0[86].val = 0x1380138
scaler.SCALE_FILTER_V_BLOCK0[87].val = 0x1140114
scaler.SCALE_FILTER_V_BLOCK1[43].val = 0x1140138
scaler.SCALE_FILTER_V_BLOCK0[88].val = 0xf100f1
scaler.SCALE_FILTER_V_BLOCK0[89].val = 0xcf00cf
scaler.SCALE_FILTER_V_BLOCK1[44].val = 0xcf00f1
scaler.SCALE_FILTER_V_BLOCK0[90].val = 0xae00ae
scaler.SCALE_FILTER_V_BLOCK0[91].val = 0x8e008e
scaler.SCALE_FILTER_V_BLOCK1[45].val = 0x8e00ae
scaler.SCALE_FILTER_V_BLOCK0[92].val = 0x6f006f
scaler.SCALE_FILTER_V_BLOCK0[93].val = 0x520052
scaler.SCALE_FILTER_V_BLOCK1[46].val = 0x52006f
scaler.SCALE_FILTER_V_BLOCK0[94].val = 0x350035
scaler.SCALE_FILTER_V_BLOCK0[95].val = 0x1a001a
scaler.SCALE_FILTER_V_BLOCK1[47].val = 0x1a0035
scaler.SCALE_FILTER_V_BLOCK0[96].val = 0x4e404e4
scaler.SCALE_FILTER_V_BLOCK0[97].val = 0x4b804b8
scaler.SCALE_FILTER_V_BLOCK1[48].val = 0x4b804e4
scaler.SCALE_FILTER_V_BLOCK0[98].val = 0x48b048b
scaler.SCALE_FILTER_V_BLOCK0[99].val = 0x45f045f
scaler.SCALE_FILTER_V_BLOCK1[49].val = 0x45f048b
scaler.SCALE_FILTER_V_BLOCK0[100].val = 0x4320432
scaler.SCALE_FILTER_V_BLOCK0[101].val = 0x4050405
scaler.SCALE_FILTER_V_BLOCK1[50].val = 0x4050432
scaler.SCALE_FILTER_V_BLOCK0[102].val = 0x3d803d8
scaler.SCALE_FILTER_V_BLOCK0[103].val = 0x3ab03ab
scaler.SCALE_FILTER_V_BLOCK1[51].val = 0x3ab03d8
scaler.SCALE_FILTER_V_BLOCK0[104].val = 0x37e037e
scaler.SCALE_FILTER_V_BLOCK0[105].val = 0x3510351
scaler.SCALE_FILTER_V_BLOCK1[52].val = 0x351037e
scaler.SCALE_FILTER_V_BLOCK0[106].val = 0x3240324
scaler.SCALE_FILTER_V_BLOCK0[107].val = 0x2f802f8
scaler.SCALE_FILTER_V_BLOCK1[53].val = 0x2f80324
scaler.SCALE_FILTER_V_BLOCK0[108].val = 0x2cc02cc
scaler.SCALE_FILTER_V_BLOCK0[109].val = 0x2a102a1
scaler.SCALE_FILTER_V_BLOCK1[54].val = 0x2a102cc
scaler.SCALE_FILTER_V_BLOCK0[110].val = 0x2760276
scaler.SCALE_FILTER_V_BLOCK0[111].val = 0x24b024b
scaler.SCALE_FILTER_V_BLOCK1[55].val = 0x24b0276
scaler.SCALE_FILTER_V_BLOCK0[112].val = 0x73b073b
scaler.SCALE_FILTER_V_BLOCK0[113].val = 0x71e071e
scaler.SCALE_FILTER_V_BLOCK1[56].val = 0x71e073b
scaler.SCALE_FILTER_V_BLOCK0[114].val = 0x7000700
scaler.SCALE_FILTER_V_BLOCK0[115].val = 0x6e106e1
scaler.SCALE_FILTER_V_BLOCK1[57].val = 0x6e10700
scaler.SCALE_FILTER_V_BLOCK0[116].val = 0x6c006c0
scaler.SCALE_FILTER_V_BLOCK0[117].val = 0x69e069e
scaler.SCALE_FILTER_V_BLOCK1[58].val = 0x69e06c0
scaler.SCALE_FILTER_V_BLOCK0[118].val = 0x67a067a
scaler.SCALE_FILTER_V_BLOCK0[119].val = 0x6560656
scaler.SCALE_FILTER_V_BLOCK1[59].val = 0x656067a
scaler.SCALE_FILTER_V_BLOCK0[120].val = 0x6300630
scaler.SCALE_FILTER_V_BLOCK0[121].val = 0x6090609
scaler.SCALE_FILTER_V_BLOCK1[60].val = 0x6090630
scaler.SCALE_FILTER_V_BLOCK0[122].val = 0x5e205e2
scaler.SCALE_FILTER_V_BLOCK0[123].val = 0x5b905b9
scaler.SCALE_FILTER_V_BLOCK1[61].val = 0x5b905e2
scaler.SCALE_FILTER_V_BLOCK0[124].val = 0x5900590
scaler.SCALE_FILTER_V_BLOCK0[125].val = 0x5660566
scaler.SCALE_FILTER_V_BLOCK1[62].val = 0x5660590
scaler.SCALE_FILTER_V_BLOCK0[126].val = 0x53b053b
scaler.SCALE_FILTER_V_BLOCK0[127].val = 0x5100510
scaler.SCALE_FILTER_V_BLOCK1[63].val = 0x510053b
scaler.SCALE_FILTER_V_BLOCK0[128].val = 0x82c082c
scaler.SCALE_FILTER_V_BLOCK0[129].val = 0x82b082b
scaler.SCALE_FILTER_V_BLOCK1[64].val = 0x82b082c
scaler.SCALE_FILTER_V_BLOCK0[130].val = 0x8280828
scaler.SCALE_FILTER_V_BLOCK0[131].val = 0x8200820
scaler.SCALE_FILTER_V_BLOCK1[65].val = 0x8200828
scaler.SCALE_FILTER_V_BLOCK0[132].val = 0x81b081b
scaler.SCALE_FILTER_V_BLOCK0[133].val = 0x8130813
scaler.SCALE_FILTER_V_BLOCK1[66].val = 0x813081b
scaler.SCALE_FILTER_V_BLOCK0[134].val = 0x8080808
scaler.SCALE_FILTER_V_BLOCK0[135].val = 0x7fc07fc
scaler.SCALE_FILTER_V_BLOCK1[67].val = 0x7fc0808
scaler.SCALE_FILTER_V_BLOCK0[136].val = 0x7ed07ed
scaler.SCALE_FILTER_V_BLOCK0[137].val = 0x7dd07dd
scaler.SCALE_FILTER_V_BLOCK1[68].val = 0x7dd07ed
scaler.SCALE_FILTER_V_BLOCK0[138].val = 0x7cb07cb
scaler.SCALE_FILTER_V_BLOCK0[139].val = 0x7b607b6
scaler.SCALE_FILTER_V_BLOCK1[69].val = 0x7b607cb
scaler.SCALE_FILTER_V_BLOCK0[140].val = 0x7a207a2
scaler.SCALE_FILTER_V_BLOCK0[141].val = 0x78a078a
scaler.SCALE_FILTER_V_BLOCK1[70].val = 0x78a07a2
scaler.SCALE_FILTER_V_BLOCK0[142].val = 0x7710771
scaler.SCALE_FILTER_V_BLOCK0[143].val = 0x7570757
scaler.SCALE_FILTER_V_BLOCK1[71].val = 0x7570771
scaler.SCALE_FILTER_V_BLOCK0[144].val = 0x73d073d
scaler.SCALE_FILTER_V_BLOCK0[145].val = 0x7570757
scaler.SCALE_FILTER_V_BLOCK1[72].val = 0x757073d
scaler.SCALE_FILTER_V_BLOCK0[146].val = 0x7710771
scaler.SCALE_FILTER_V_BLOCK0[147].val = 0x78a078a
scaler.SCALE_FILTER_V_BLOCK1[73].val = 0x78a0771
scaler.SCALE_FILTER_V_BLOCK0[148].val = 0x7a207a2
scaler.SCALE_FILTER_V_BLOCK0[149].val = 0x7b607b6
scaler.SCALE_FILTER_V_BLOCK1[74].val = 0x7b607a2
scaler.SCALE_FILTER_V_BLOCK0[150].val = 0x7cb07cb
scaler.SCALE_FILTER_V_BLOCK0[151].val = 0x7dd07dd
scaler.SCALE_FILTER_V_BLOCK1[75].val = 0x7dd07cb
scaler.SCALE_FILTER_V_BLOCK0[152].val = 0x7ed07ed
scaler.SCALE_FILTER_V_BLOCK0[153].val = 0x7fc07fc
scaler.SCALE_FILTER_V_BLOCK1[76].val = 0x7fc07ed
scaler.SCALE_FILTER_V_BLOCK0[154].val = 0x8080808
scaler.SCALE_FILTER_V_BLOCK0[155].val = 0x8130813
scaler.SCALE_FILTER_V_BLOCK1[77].val = 0x8130808
scaler.SCALE_FILTER_V_BLOCK0[156].val = 0x81b081b
scaler.SCALE_FILTER_V_BLOCK0[157].val = 0x8200820
scaler.SCALE_FILTER_V_BLOCK1[78].val = 0x820081b
scaler.SCALE_FILTER_V_BLOCK0[158].val = 0x8280828
scaler.SCALE_FILTER_V_BLOCK0[159].val = 0x82b082b
scaler.SCALE_FILTER_V_BLOCK1[79].val = 0x82b0828
scaler.SCALE_FILTER_V_BLOCK0[160].val = 0x4e404e4
scaler.SCALE_FILTER_V_BLOCK0[161].val = 0x5100510
scaler.SCALE_FILTER_V_BLOCK1[80].val = 0x51004e4
scaler.SCALE_FILTER_V_BLOCK0[162].val = 0x53b053b
scaler.SCALE_FILTER_V_BLOCK0[163].val = 0x5660566
scaler.SCALE_FILTER_V_BLOCK1[81].val = 0x566053b
scaler.SCALE_FILTER_V_BLOCK0[164].val = 0x5900590
scaler.SCALE_FILTER_V_BLOCK0[165].val = 0x5b905b9
scaler.SCALE_FILTER_V_BLOCK1[82].val = 0x5b90590
scaler.SCALE_FILTER_V_BLOCK0[166].val = 0x5e205e2
scaler.SCALE_FILTER_V_BLOCK0[167].val = 0x6090609
scaler.SCALE_FILTER_V_BLOCK1[83].val = 0x60905e2
scaler.SCALE_FILTER_V_BLOCK0[168].val = 0x6300630
scaler.SCALE_FILTER_V_BLOCK0[169].val = 0x6560656
scaler.SCALE_FILTER_V_BLOCK1[84].val = 0x6560630
scaler.SCALE_FILTER_V_BLOCK0[170].val = 0x67a067a
scaler.SCALE_FILTER_V_BLOCK0[171].val = 0x69e069e
scaler.SCALE_FILTER_V_BLOCK1[85].val = 0x69e067a
scaler.SCALE_FILTER_V_BLOCK0[172].val = 0x6c006c0
scaler.SCALE_FILTER_V_BLOCK0[173].val = 0x6e106e1
scaler.SCALE_FILTER_V_BLOCK1[86].val = 0x6e106c0
scaler.SCALE_FILTER_V_BLOCK0[174].val = 0x7000700
scaler.SCALE_FILTER_V_BLOCK0[175].val = 0x71e071e
scaler.SCALE_FILTER_V_BLOCK1[87].val = 0x71e0700
scaler.SCALE_FILTER_V_BLOCK0[176].val = 0x2210221
scaler.SCALE_FILTER_V_BLOCK0[177].val = 0x24b024b
scaler.SCALE_FILTER_V_BLOCK1[88].val = 0x24b0221
scaler.SCALE_FILTER_V_BLOCK0[178].val = 0x2760276
scaler.SCALE_FILTER_V_BLOCK0[179].val = 0x2a102a1
scaler.SCALE_FILTER_V_BLOCK1[89].val = 0x2a10276
scaler.SCALE_FILTER_V_BLOCK0[180].val = 0x2cc02cc
scaler.SCALE_FILTER_V_BLOCK0[181].val = 0x2f802f8
scaler.SCALE_FILTER_V_BLOCK1[90].val = 0x2f802cc
scaler.SCALE_FILTER_V_BLOCK0[182].val = 0x3240324
scaler.SCALE_FILTER_V_BLOCK0[183].val = 0x3510351
scaler.SCALE_FILTER_V_BLOCK1[91].val = 0x3510324
scaler.SCALE_FILTER_V_BLOCK0[184].val = 0x37e037e
scaler.SCALE_FILTER_V_BLOCK0[185].val = 0x3ab03ab
scaler.SCALE_FILTER_V_BLOCK1[92].val = 0x3ab037e
scaler.SCALE_FILTER_V_BLOCK0[186].val = 0x3d803d8
scaler.SCALE_FILTER_V_BLOCK0[187].val = 0x4050405
scaler.SCALE_FILTER_V_BLOCK1[93].val = 0x40503d8
scaler.SCALE_FILTER_V_BLOCK0[188].val = 0x4320432
scaler.SCALE_FILTER_V_BLOCK0[189].val = 0x45f045f
scaler.SCALE_FILTER_V_BLOCK1[94].val = 0x45f0432
scaler.SCALE_FILTER_V_BLOCK0[190].val = 0x48b048b
scaler.SCALE_FILTER_V_BLOCK0[191].val = 0x4b804b8
scaler.SCALE_FILTER_V_BLOCK1[95].val = 0x4b8048b
scaler.SCALE_FILTER_V_BLOCK0[192].val = 0x0
scaler.SCALE_FILTER_V_BLOCK0[193].val = 0x1a001a
scaler.SCALE_FILTER_V_BLOCK1[96].val = 0x1a0000
scaler.SCALE_FILTER_V_BLOCK0[194].val = 0x350035
scaler.SCALE_FILTER_V_BLOCK0[195].val = 0x520052
scaler.SCALE_FILTER_V_BLOCK1[97].val = 0x520035
scaler.SCALE_FILTER_V_BLOCK0[196].val = 0x6f006f
scaler.SCALE_FILTER_V_BLOCK0[197].val = 0x8e008e
scaler.SCALE_FILTER_V_BLOCK1[98].val = 0x8e006f
scaler.SCALE_FILTER_V_BLOCK0[198].val = 0xae00ae
scaler.SCALE_FILTER_V_BLOCK0[199].val = 0xcf00cf
scaler.SCALE_FILTER_V_BLOCK1[99].val = 0xcf00ae
scaler.SCALE_FILTER_V_BLOCK0[200].val = 0xf100f1
scaler.SCALE_FILTER_V_BLOCK0[201].val = 0x1140114
scaler.SCALE_FILTER_V_BLOCK1[100].val = 0x11400f1
scaler.SCALE_FILTER_V_BLOCK0[202].val = 0x1380138
scaler.SCALE_FILTER_V_BLOCK0[203].val = 0x15d015d
scaler.SCALE_FILTER_V_BLOCK1[101].val = 0x15d0138
scaler.SCALE_FILTER_V_BLOCK0[204].val = 0x1820182
scaler.SCALE_FILTER_V_BLOCK0[205].val = 0x1a901a9
scaler.SCALE_FILTER_V_BLOCK1[102].val = 0x1a90182
scaler.SCALE_FILTER_V_BLOCK0[206].val = 0x1d001d0
scaler.SCALE_FILTER_V_BLOCK0[207].val = 0x1f901f9
scaler.SCALE_FILTER_V_BLOCK1[103].val = 0x1f901d0
scaler.SCALE_FILTER_V_BLOCK0[208].val = 0xff02ff02
scaler.SCALE_FILTER_V_BLOCK0[209].val = 0xff0aff0a
scaler.SCALE_FILTER_V_BLOCK1[104].val = 0xff0aff02
scaler.SCALE_FILTER_V_BLOCK0[210].val = 0xff12ff12
scaler.SCALE_FILTER_V_BLOCK0[211].val = 0xff1bff1b
scaler.SCALE_FILTER_V_BLOCK1[105].val = 0xff1bff12
scaler.SCALE_FILTER_V_BLOCK0[212].val = 0xff26ff26
scaler.SCALE_FILTER_V_BLOCK0[213].val = 0xff31ff31
scaler.SCALE_FILTER_V_BLOCK1[106].val = 0xff31ff26
scaler.SCALE_FILTER_V_BLOCK0[214].val = 0xff3eff3e
scaler.SCALE_FILTER_V_BLOCK0[215].val = 0xff4cff4c
scaler.SCALE_FILTER_V_BLOCK1[107].val = 0xff4cff3e
scaler.SCALE_FILTER_V_BLOCK0[216].val = 0xff5bff5b
scaler.SCALE_FILTER_V_BLOCK0[218].val = 0xff6bff6b
scaler.SCALE_FILTER_V_BLOCK1[108].val = 0xff6bff5b
scaler.SCALE_FILTER_V_BLOCK0[218].val = 0xff7dff7d
scaler.SCALE_FILTER_V_BLOCK0[219].val = 0xff90ff90
scaler.SCALE_FILTER_V_BLOCK1[109].val = 0xff90ff7d
scaler.SCALE_FILTER_V_BLOCK0[220].val = 0xffa4ffa4
scaler.SCALE_FILTER_V_BLOCK0[221].val = 0xffb9ffb9
scaler.SCALE_FILTER_V_BLOCK1[110].val = 0xffb9ffa4
scaler.SCALE_FILTER_V_BLOCK0[222].val = 0xffcfffcf
scaler.SCALE_FILTER_V_BLOCK0[223].val = 0xffe7ffe7
scaler.SCALE_FILTER_V_BLOCK1[111].val = 0xffe7ffcf
scaler.SCALE_FILTER_V_BLOCK0[224].val = 0xff06ff06
scaler.SCALE_FILTER_V_BLOCK0[225].val = 0xff01ff01
scaler.SCALE_FILTER_V_BLOCK1[112].val = 0xff01ff06
scaler.SCALE_FILTER_V_BLOCK0[226].val = 0xfefcfefc
scaler.SCALE_FILTER_V_BLOCK0[227].val = 0xfef8fef8
scaler.SCALE_FILTER_V_BLOCK1[113].val = 0xfef8fefc
scaler.SCALE_FILTER_V_BLOCK0[228].val = 0xfef4fef4
scaler.SCALE_FILTER_V_BLOCK0[229].val = 0xfef1fef1
scaler.SCALE_FILTER_V_BLOCK1[114].val = 0xfef1fef4
scaler.SCALE_FILTER_V_BLOCK0[230].val = 0xfeeefeee
scaler.SCALE_FILTER_V_BLOCK0[231].val = 0xfeecfeec
scaler.SCALE_FILTER_V_BLOCK1[115].val = 0xfeecfeee
scaler.SCALE_FILTER_V_BLOCK0[232].val = 0xfeebfeeb
scaler.SCALE_FILTER_V_BLOCK0[233].val = 0xfeebfeeb
scaler.SCALE_FILTER_V_BLOCK1[116].val = 0xfeebfeeb
scaler.SCALE_FILTER_V_BLOCK0[234].val = 0xfeecfeec
scaler.SCALE_FILTER_V_BLOCK0[235].val = 0xfeedfeed
scaler.SCALE_FILTER_V_BLOCK1[117].val = 0xfeedfeec
scaler.SCALE_FILTER_V_BLOCK0[236].val = 0xfeeffeef
scaler.SCALE_FILTER_V_BLOCK0[237].val = 0xfef3fef3
scaler.SCALE_FILTER_V_BLOCK1[118].val = 0xfef3feef
scaler.SCALE_FILTER_V_BLOCK0[238].val = 0xfef7fef7
scaler.SCALE_FILTER_V_BLOCK0[239].val = 0xfefcfefc
scaler.SCALE_FILTER_V_BLOCK1[119].val = 0xfefcfef7
scaler.SCALE_FILTER_V_BLOCK0[240].val = 0xff87ff87
scaler.SCALE_FILTER_V_BLOCK0[241].val = 0xff7eff7e
scaler.SCALE_FILTER_V_BLOCK1[120].val = 0xff7eff87
scaler.SCALE_FILTER_V_BLOCK0[242].val = 0xff75ff75
scaler.SCALE_FILTER_V_BLOCK0[243].val = 0xff6cff6c
scaler.SCALE_FILTER_V_BLOCK1[121].val = 0xff6cff75
scaler.SCALE_FILTER_V_BLOCK0[244].val = 0xff63ff63
scaler.SCALE_FILTER_V_BLOCK0[245].val = 0xff5bff5b
scaler.SCALE_FILTER_V_BLOCK1[122].val = 0xff5bff63
scaler.SCALE_FILTER_V_BLOCK0[246].val = 0xff52ff52
scaler.SCALE_FILTER_V_BLOCK0[247].val = 0xff49ff49
scaler.SCALE_FILTER_V_BLOCK1[123].val = 0xff49ff52
scaler.SCALE_FILTER_V_BLOCK0[248].val = 0xff41ff41
scaler.SCALE_FILTER_V_BLOCK0[249].val = 0xff38ff38
scaler.SCALE_FILTER_V_BLOCK1[124].val = 0xff38ff41
scaler.SCALE_FILTER_V_BLOCK0[250].val = 0xff30ff30
scaler.SCALE_FILTER_V_BLOCK0[251].val = 0xff28ff28
scaler.SCALE_FILTER_V_BLOCK1[125].val = 0xff28ff30
scaler.SCALE_FILTER_V_BLOCK0[252].val = 0xff21ff21
scaler.SCALE_FILTER_V_BLOCK0[253].val = 0xff1aff1a
scaler.SCALE_FILTER_V_BLOCK1[126].val = 0xff1aff21
scaler.SCALE_FILTER_V_BLOCK0[254].val = 0xff13ff13
scaler.SCALE_FILTER_V_BLOCK0[255].val = 0xff0cff0c
scaler.SCALE_FILTER_V_BLOCK1[127].val = 0xff0cff13
scaler.SCALE_FILTER_V_BLOCK0[256].val = 0x0
scaler.SCALE_FILTER_V_BLOCK0[257].val = 0xfffafffa
scaler.SCALE_FILTER_V_BLOCK1[128].val = 0xfffa0000
scaler.SCALE_FILTER_V_BLOCK0[258].val = 0xfff4fff4
scaler.SCALE_FILTER_V_BLOCK0[259].val = 0xffeeffee
scaler.SCALE_FILTER_V_BLOCK1[129].val = 0xffeefff4
scaler.SCALE_FILTER_V_BLOCK0[260].val = 0xffe7ffe7
scaler.SCALE_FILTER_V_BLOCK0[261].val = 0xffe0ffe0
scaler.SCALE_FILTER_V_BLOCK1[130].val = 0xffe0ffe7
scaler.SCALE_FILTER_V_BLOCK0[262].val = 0xffd9ffd9
scaler.SCALE_FILTER_V_BLOCK0[263].val = 0xffd2ffd2
scaler.SCALE_FILTER_V_BLOCK1[131].val = 0xffd2ffd9
scaler.SCALE_FILTER_V_BLOCK0[264].val = 0xffcaffca
scaler.SCALE_FILTER_V_BLOCK0[265].val = 0xffc2ffc2
scaler.SCALE_FILTER_V_BLOCK1[132].val = 0xffc2ffca
scaler.SCALE_FILTER_V_BLOCK0[266].val = 0xffbaffba
scaler.SCALE_FILTER_V_BLOCK0[267].val = 0xffb2ffb2
scaler.SCALE_FILTER_V_BLOCK1[133].val = 0xffb2ffba
scaler.SCALE_FILTER_V_BLOCK0[268].val = 0xffaaffaa
scaler.SCALE_FILTER_V_BLOCK0[269].val = 0xffa1ffa1
scaler.SCALE_FILTER_V_BLOCK1[134].val = 0xffa1ffaa
scaler.SCALE_FILTER_V_BLOCK0[270].val = 0xff99ff99
scaler.SCALE_FILTER_V_BLOCK0[271].val = 0xff90ff90
scaler.SCALE_FILTER_V_BLOCK1[135].val = 0xff90ff99
scaler.SCALE_FILTER_V_BLOCK0[272].val = 0x340034
scaler.SCALE_FILTER_V_BLOCK0[273].val = 0x330033
scaler.SCALE_FILTER_V_BLOCK1[136].val = 0x330034
scaler.SCALE_FILTER_V_BLOCK0[274].val = 0x320032
scaler.SCALE_FILTER_V_BLOCK0[275].val = 0x300030
scaler.SCALE_FILTER_V_BLOCK1[137].val = 0x300032
scaler.SCALE_FILTER_V_BLOCK0[276].val = 0x2e002e
scaler.SCALE_FILTER_V_BLOCK0[277].val = 0x2c002c
scaler.SCALE_FILTER_V_BLOCK1[138].val = 0x2c002e
scaler.SCALE_FILTER_V_BLOCK0[278].val = 0x290029
scaler.SCALE_FILTER_V_BLOCK0[279].val = 0x260026
scaler.SCALE_FILTER_V_BLOCK1[139].val = 0x260029
scaler.SCALE_FILTER_V_BLOCK0[280].val = 0x230023
scaler.SCALE_FILTER_V_BLOCK0[281].val = 0x200020
scaler.SCALE_FILTER_V_BLOCK1[140].val = 0x200023
scaler.SCALE_FILTER_V_BLOCK0[282].val = 0x1c001c
scaler.SCALE_FILTER_V_BLOCK0[283].val = 0x180018
scaler.SCALE_FILTER_V_BLOCK1[141].val = 0x18001c
scaler.SCALE_FILTER_V_BLOCK0[284].val = 0x140014
scaler.SCALE_FILTER_V_BLOCK0[285].val = 0x100010
scaler.SCALE_FILTER_V_BLOCK1[142].val = 0x100014
scaler.SCALE_FILTER_V_BLOCK0[286].val = 0xb000b
scaler.SCALE_FILTER_V_BLOCK0[287].val = 0x50005
scaler.SCALE_FILTER_V_BLOCK1[143].val = 0x5000b

# DDA init H
scaler.SCALE_H_DDA_THING0 = 0
scaler.SCALE_H_DDA_THING2 = 0
scaler.SCALE_H_DDA_THING1 = 0

# horizontal scaling
scaler.SCALE_H_RATIO_0 = int(in_W / out_W * 0x400000)
scaler.SCALE_H_RATIO_4 = 0  # XXX what does this do?
scaler.SCALE_H_RATIO_1 = 0  # XXX what does this do?
scaler.SCALE_H_RATIO_2 = int(out_W / in_W * 0x400000)   # XXX what does this set do? zeroing this one out doesn't work
scaler.SCALE_H_RATIO_3 = 0  # XXX what does this set do?
scaler.SCALE_H_RATIO_5 = 0  # XXX what does this set do?
scaler.SCALE_H_FLAGS.set(EN=1)

scaler.SCALE_FILTER_H_BLOCK0[0].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[1].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[0].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[2].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[3].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[1].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[4].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[5].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[2].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[6].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[7].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[3].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[8].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[9].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[4].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[10].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[11].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[5].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[12].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[13].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[6].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[14].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[15].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[7].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[16].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[17].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[8].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[18].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[19].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[9].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[20].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[21].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[10].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[22].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[23].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[11].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[24].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[25].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[12].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[26].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[27].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[13].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[28].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[29].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[14].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[30].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[31].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[15].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[32].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[33].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[16].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[34].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[35].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[17].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[36].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[37].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[18].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[38].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[39].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[19].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[40].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[41].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[20].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[42].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[43].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[21].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[44].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[45].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[22].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[46].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[47].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[23].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[48].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[49].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[24].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[50].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[51].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[25].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[52].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[53].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[26].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[54].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[55].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[27].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[56].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[57].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[28].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[58].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[59].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[29].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[60].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[61].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[30].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[62].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[63].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[31].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[64].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[65].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[32].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[66].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[67].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[33].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[68].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[69].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[34].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[70].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[71].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[35].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[72].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[73].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[36].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[74].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[75].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[37].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[76].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[77].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[38].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[78].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[79].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[39].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[80].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[81].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[40].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[82].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[83].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[41].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[84].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[85].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[42].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[86].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[87].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[43].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[88].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[89].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[44].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[90].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[91].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[45].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[92].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[93].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[46].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[94].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[95].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[47].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[96].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[97].val = 0x50005
scaler.SCALE_FILTER_H_BLOCK1[48].val = 0x50000
scaler.SCALE_FILTER_H_BLOCK0[98].val = 0xb000b
scaler.SCALE_FILTER_H_BLOCK0[99].val = 0x100010
scaler.SCALE_FILTER_H_BLOCK1[49].val = 0x10000b
scaler.SCALE_FILTER_H_BLOCK0[100].val = 0x140014
scaler.SCALE_FILTER_H_BLOCK0[101].val = 0x180018
scaler.SCALE_FILTER_H_BLOCK1[50].val = 0x180014
scaler.SCALE_FILTER_H_BLOCK0[102].val = 0x1c001c
scaler.SCALE_FILTER_H_BLOCK0[103].val = 0x200020
scaler.SCALE_FILTER_H_BLOCK1[51].val = 0x20001c
scaler.SCALE_FILTER_H_BLOCK0[104].val = 0x230023
scaler.SCALE_FILTER_H_BLOCK0[105].val = 0x260026
scaler.SCALE_FILTER_H_BLOCK1[52].val = 0x260023
scaler.SCALE_FILTER_H_BLOCK0[106].val = 0x290029
scaler.SCALE_FILTER_H_BLOCK0[107].val = 0x2c002c
scaler.SCALE_FILTER_H_BLOCK1[53].val = 0x2c0029
scaler.SCALE_FILTER_H_BLOCK0[108].val = 0x2e002e
scaler.SCALE_FILTER_H_BLOCK0[109].val = 0x300030
scaler.SCALE_FILTER_H_BLOCK1[54].val = 0x30002e
scaler.SCALE_FILTER_H_BLOCK0[110].val = 0x320032
scaler.SCALE_FILTER_H_BLOCK0[111].val = 0x330033
scaler.SCALE_FILTER_H_BLOCK1[55].val = 0x330032
scaler.SCALE_FILTER_H_BLOCK0[112].val = 0xff87ff87
scaler.SCALE_FILTER_H_BLOCK0[113].val = 0xff90ff90
scaler.SCALE_FILTER_H_BLOCK1[56].val = 0xff90ff87
scaler.SCALE_FILTER_H_BLOCK0[114].val = 0xff99ff99
scaler.SCALE_FILTER_H_BLOCK0[115].val = 0xffa1ffa1
scaler.SCALE_FILTER_H_BLOCK1[57].val = 0xffa1ff99
scaler.SCALE_FILTER_H_BLOCK0[116].val = 0xffaaffaa
scaler.SCALE_FILTER_H_BLOCK0[117].val = 0xffb2ffb2
scaler.SCALE_FILTER_H_BLOCK1[58].val = 0xffb2ffaa
scaler.SCALE_FILTER_H_BLOCK0[118].val = 0xffbaffba
scaler.SCALE_FILTER_H_BLOCK0[119].val = 0xffc2ffc2
scaler.SCALE_FILTER_H_BLOCK1[59].val = 0xffc2ffba
scaler.SCALE_FILTER_H_BLOCK0[120].val = 0xffcaffca
scaler.SCALE_FILTER_H_BLOCK0[121].val = 0xffd2ffd2
scaler.SCALE_FILTER_H_BLOCK1[60].val = 0xffd2ffca
scaler.SCALE_FILTER_H_BLOCK0[122].val = 0xffd9ffd9
scaler.SCALE_FILTER_H_BLOCK0[123].val = 0xffe0ffe0
scaler.SCALE_FILTER_H_BLOCK1[61].val = 0xffe0ffd9
scaler.SCALE_FILTER_H_BLOCK0[124].val = 0xffe7ffe7
scaler.SCALE_FILTER_H_BLOCK0[125].val = 0xffeeffee
scaler.SCALE_FILTER_H_BLOCK1[62].val = 0xffeeffe7
scaler.SCALE_FILTER_H_BLOCK0[126].val = 0xfff4fff4
scaler.SCALE_FILTER_H_BLOCK0[127].val = 0xfffafffa
scaler.SCALE_FILTER_H_BLOCK1[63].val = 0xfffafff4
scaler.SCALE_FILTER_H_BLOCK0[128].val = 0xff06ff06
scaler.SCALE_FILTER_H_BLOCK0[129].val = 0xff0cff0c
scaler.SCALE_FILTER_H_BLOCK1[64].val = 0xff0cff06
scaler.SCALE_FILTER_H_BLOCK0[130].val = 0xff13ff13
scaler.SCALE_FILTER_H_BLOCK0[131].val = 0xff1aff1a
scaler.SCALE_FILTER_H_BLOCK1[65].val = 0xff1aff13
scaler.SCALE_FILTER_H_BLOCK0[132].val = 0xff21ff21
scaler.SCALE_FILTER_H_BLOCK0[133].val = 0xff28ff28
scaler.SCALE_FILTER_H_BLOCK1[66].val = 0xff28ff21
scaler.SCALE_FILTER_H_BLOCK0[134].val = 0xff30ff30
scaler.SCALE_FILTER_H_BLOCK0[135].val = 0xff38ff38
scaler.SCALE_FILTER_H_BLOCK1[67].val = 0xff38ff30
scaler.SCALE_FILTER_H_BLOCK0[136].val = 0xff41ff41
scaler.SCALE_FILTER_H_BLOCK0[137].val = 0xff49ff49
scaler.SCALE_FILTER_H_BLOCK1[68].val = 0xff49ff41
scaler.SCALE_FILTER_H_BLOCK0[138].val = 0xff52ff52
scaler.SCALE_FILTER_H_BLOCK0[139].val = 0xff5bff5b
scaler.SCALE_FILTER_H_BLOCK1[69].val = 0xff5bff52
scaler.SCALE_FILTER_H_BLOCK0[140].val = 0xff63ff63
scaler.SCALE_FILTER_H_BLOCK0[141].val = 0xff6cff6c
scaler.SCALE_FILTER_H_BLOCK1[70].val = 0xff6cff63
scaler.SCALE_FILTER_H_BLOCK0[142].val = 0xff75ff75
scaler.SCALE_FILTER_H_BLOCK0[143].val = 0xff7eff7e
scaler.SCALE_FILTER_H_BLOCK1[71].val = 0xff7eff75
scaler.SCALE_FILTER_H_BLOCK0[144].val = 0xff02ff02
scaler.SCALE_FILTER_H_BLOCK0[145].val = 0xfefcfefc
scaler.SCALE_FILTER_H_BLOCK1[72].val = 0xfefcff02
scaler.SCALE_FILTER_H_BLOCK0[146].val = 0xfef7fef7
scaler.SCALE_FILTER_H_BLOCK0[147].val = 0xfef3fef3
scaler.SCALE_FILTER_H_BLOCK1[73].val = 0xfef3fef7
scaler.SCALE_FILTER_H_BLOCK0[148].val = 0xfeeffeef
scaler.SCALE_FILTER_H_BLOCK0[149].val = 0xfeedfeed
scaler.SCALE_FILTER_H_BLOCK1[74].val = 0xfeedfeef
scaler.SCALE_FILTER_H_BLOCK0[150].val = 0xfeecfeec
scaler.SCALE_FILTER_H_BLOCK0[151].val = 0xfeebfeeb
scaler.SCALE_FILTER_H_BLOCK1[75].val = 0xfeebfeec
scaler.SCALE_FILTER_H_BLOCK0[152].val = 0xfeebfeeb
scaler.SCALE_FILTER_H_BLOCK0[153].val = 0xfeecfeec
scaler.SCALE_FILTER_H_BLOCK1[76].val = 0xfeecfeeb
scaler.SCALE_FILTER_H_BLOCK0[154].val = 0xfeeefeee
scaler.SCALE_FILTER_H_BLOCK0[155].val = 0xfef1fef1
scaler.SCALE_FILTER_H_BLOCK1[77].val = 0xfef1feee
scaler.SCALE_FILTER_H_BLOCK0[156].val = 0xfef4fef4
scaler.SCALE_FILTER_H_BLOCK0[157].val = 0xfef8fef8
scaler.SCALE_FILTER_H_BLOCK1[78].val = 0xfef8fef4
scaler.SCALE_FILTER_H_BLOCK0[158].val = 0xfefcfefc
scaler.SCALE_FILTER_H_BLOCK0[159].val = 0xff01ff01
scaler.SCALE_FILTER_H_BLOCK1[79].val = 0xff01fefc
scaler.SCALE_FILTER_H_BLOCK0[160].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[161].val = 0xffe7ffe7
scaler.SCALE_FILTER_H_BLOCK1[80].val = 0xffe70000
scaler.SCALE_FILTER_H_BLOCK0[162].val = 0xffcfffcf
scaler.SCALE_FILTER_H_BLOCK0[163].val = 0xffb9ffb9
scaler.SCALE_FILTER_H_BLOCK1[81].val = 0xffb9ffcf
scaler.SCALE_FILTER_H_BLOCK0[164].val = 0xffa4ffa4
scaler.SCALE_FILTER_H_BLOCK0[165].val = 0xff90ff90
scaler.SCALE_FILTER_H_BLOCK1[82].val = 0xff90ffa4
scaler.SCALE_FILTER_H_BLOCK0[166].val = 0xff7dff7d
scaler.SCALE_FILTER_H_BLOCK0[167].val = 0xff6bff6b
scaler.SCALE_FILTER_H_BLOCK1[83].val = 0xff6bff7d
scaler.SCALE_FILTER_H_BLOCK0[168].val = 0xff5bff5b
scaler.SCALE_FILTER_H_BLOCK0[169].val = 0xff4cff4c
scaler.SCALE_FILTER_H_BLOCK1[84].val = 0xff4cff5b
scaler.SCALE_FILTER_H_BLOCK0[170].val = 0xff3eff3e
scaler.SCALE_FILTER_H_BLOCK0[171].val = 0xff31ff31
scaler.SCALE_FILTER_H_BLOCK1[85].val = 0xff31ff3e
scaler.SCALE_FILTER_H_BLOCK0[172].val = 0xff26ff26
scaler.SCALE_FILTER_H_BLOCK0[173].val = 0xff1bff1b
scaler.SCALE_FILTER_H_BLOCK1[86].val = 0xff1bff26
scaler.SCALE_FILTER_H_BLOCK0[174].val = 0xff12ff12
scaler.SCALE_FILTER_H_BLOCK0[175].val = 0xff0aff0a
scaler.SCALE_FILTER_H_BLOCK1[87].val = 0xff0aff12
scaler.SCALE_FILTER_H_BLOCK0[176].val = 0x2210221
scaler.SCALE_FILTER_H_BLOCK0[177].val = 0x1f901f9
scaler.SCALE_FILTER_H_BLOCK1[88].val = 0x1f90221
scaler.SCALE_FILTER_H_BLOCK0[178].val = 0x1d001d0
scaler.SCALE_FILTER_H_BLOCK0[179].val = 0x1a901a9
scaler.SCALE_FILTER_H_BLOCK1[89].val = 0x1a901d0
scaler.SCALE_FILTER_H_BLOCK0[180].val = 0x1820182
scaler.SCALE_FILTER_H_BLOCK0[181].val = 0x15d015d
scaler.SCALE_FILTER_H_BLOCK1[90].val = 0x15d0182
scaler.SCALE_FILTER_H_BLOCK0[182].val = 0x1380138
scaler.SCALE_FILTER_H_BLOCK0[183].val = 0x1140114
scaler.SCALE_FILTER_H_BLOCK1[91].val = 0x1140138
scaler.SCALE_FILTER_H_BLOCK0[184].val = 0xf100f1
scaler.SCALE_FILTER_H_BLOCK0[185].val = 0xcf00cf
scaler.SCALE_FILTER_H_BLOCK1[92].val = 0xcf00f1
scaler.SCALE_FILTER_H_BLOCK0[186].val = 0xae00ae
scaler.SCALE_FILTER_H_BLOCK0[187].val = 0x8e008e
scaler.SCALE_FILTER_H_BLOCK1[93].val = 0x8e00ae
scaler.SCALE_FILTER_H_BLOCK0[188].val = 0x6f006f
scaler.SCALE_FILTER_H_BLOCK0[189].val = 0x520052
scaler.SCALE_FILTER_H_BLOCK1[94].val = 0x52006f
scaler.SCALE_FILTER_H_BLOCK0[190].val = 0x350035
scaler.SCALE_FILTER_H_BLOCK0[191].val = 0x1a001a
scaler.SCALE_FILTER_H_BLOCK1[95].val = 0x1a0035
scaler.SCALE_FILTER_H_BLOCK0[192].val = 0x4e404e4
scaler.SCALE_FILTER_H_BLOCK0[193].val = 0x4b804b8
scaler.SCALE_FILTER_H_BLOCK1[96].val = 0x4b804e4
scaler.SCALE_FILTER_H_BLOCK0[194].val = 0x48b048b
scaler.SCALE_FILTER_H_BLOCK0[195].val = 0x45f045f
scaler.SCALE_FILTER_H_BLOCK1[97].val = 0x45f048b
scaler.SCALE_FILTER_H_BLOCK0[196].val = 0x4320432
scaler.SCALE_FILTER_H_BLOCK0[197].val = 0x4050405
scaler.SCALE_FILTER_H_BLOCK1[98].val = 0x4050432
scaler.SCALE_FILTER_H_BLOCK0[198].val = 0x3d803d8
scaler.SCALE_FILTER_H_BLOCK0[199].val = 0x3ab03ab
scaler.SCALE_FILTER_H_BLOCK1[99].val = 0x3ab03d8
scaler.SCALE_FILTER_H_BLOCK0[200].val = 0x37e037e
scaler.SCALE_FILTER_H_BLOCK0[201].val = 0x3510351
scaler.SCALE_FILTER_H_BLOCK1[100].val = 0x351037e
scaler.SCALE_FILTER_H_BLOCK0[202].val = 0x3240324
scaler.SCALE_FILTER_H_BLOCK0[203].val = 0x2f802f8
scaler.SCALE_FILTER_H_BLOCK1[101].val = 0x2f80324
scaler.SCALE_FILTER_H_BLOCK0[204].val = 0x2cc02cc
scaler.SCALE_FILTER_H_BLOCK0[205].val = 0x2a102a1
scaler.SCALE_FILTER_H_BLOCK1[102].val = 0x2a102cc
scaler.SCALE_FILTER_H_BLOCK0[206].val = 0x2760276
scaler.SCALE_FILTER_H_BLOCK0[207].val = 0x24b024b
scaler.SCALE_FILTER_H_BLOCK1[103].val = 0x24b0276
scaler.SCALE_FILTER_H_BLOCK0[208].val = 0x73b073b
scaler.SCALE_FILTER_H_BLOCK0[209].val = 0x71e071e
scaler.SCALE_FILTER_H_BLOCK1[104].val = 0x71e073b
scaler.SCALE_FILTER_H_BLOCK0[210].val = 0x7000700
scaler.SCALE_FILTER_H_BLOCK0[211].val = 0x6e106e1
scaler.SCALE_FILTER_H_BLOCK1[105].val = 0x6e10700
scaler.SCALE_FILTER_H_BLOCK0[212].val = 0x6c006c0
scaler.SCALE_FILTER_H_BLOCK0[213].val = 0x69e069e
scaler.SCALE_FILTER_H_BLOCK1[106].val = 0x69e06c0
scaler.SCALE_FILTER_H_BLOCK0[214].val = 0x67a067a
scaler.SCALE_FILTER_H_BLOCK0[215].val = 0x6560656
scaler.SCALE_FILTER_H_BLOCK1[107].val = 0x656067a
scaler.SCALE_FILTER_H_BLOCK0[216].val = 0x6300630
scaler.SCALE_FILTER_H_BLOCK0[217].val = 0x6090609
scaler.SCALE_FILTER_H_BLOCK1[108].val = 0x6090630
scaler.SCALE_FILTER_H_BLOCK0[218].val = 0x5e205e2
scaler.SCALE_FILTER_H_BLOCK0[219].val = 0x5b905b9
scaler.SCALE_FILTER_H_BLOCK1[109].val = 0x5b905e2
scaler.SCALE_FILTER_H_BLOCK0[220].val = 0x5900590
scaler.SCALE_FILTER_H_BLOCK0[221].val = 0x5660566
scaler.SCALE_FILTER_H_BLOCK1[110].val = 0x5660590
scaler.SCALE_FILTER_H_BLOCK0[222].val = 0x53b053b
scaler.SCALE_FILTER_H_BLOCK0[223].val = 0x5100510
scaler.SCALE_FILTER_H_BLOCK1[111].val = 0x510053b
scaler.SCALE_FILTER_H_BLOCK0[224].val = 0x82c082c
scaler.SCALE_FILTER_H_BLOCK0[225].val = 0x82b082b
scaler.SCALE_FILTER_H_BLOCK1[112].val = 0x82b082c
scaler.SCALE_FILTER_H_BLOCK0[226].val = 0x8280828
scaler.SCALE_FILTER_H_BLOCK0[227].val = 0x8200820
scaler.SCALE_FILTER_H_BLOCK1[113].val = 0x8200828
scaler.SCALE_FILTER_H_BLOCK0[228].val = 0x81b081b
scaler.SCALE_FILTER_H_BLOCK0[229].val = 0x8130813
scaler.SCALE_FILTER_H_BLOCK1[114].val = 0x813081b
scaler.SCALE_FILTER_H_BLOCK0[230].val = 0x8080808
scaler.SCALE_FILTER_H_BLOCK0[231].val = 0x7fc07fc
scaler.SCALE_FILTER_H_BLOCK1[115].val = 0x7fc0808
scaler.SCALE_FILTER_H_BLOCK0[232].val = 0x7ed07ed
scaler.SCALE_FILTER_H_BLOCK0[233].val = 0x7dd07dd
scaler.SCALE_FILTER_H_BLOCK1[116].val = 0x7dd07ed
scaler.SCALE_FILTER_H_BLOCK0[234].val = 0x7cb07cb
scaler.SCALE_FILTER_H_BLOCK0[235].val = 0x7b607b6
scaler.SCALE_FILTER_H_BLOCK1[117].val = 0x7b607cb
scaler.SCALE_FILTER_H_BLOCK0[236].val = 0x7a207a2
scaler.SCALE_FILTER_H_BLOCK0[237].val = 0x78a078a
scaler.SCALE_FILTER_H_BLOCK1[118].val = 0x78a07a2
scaler.SCALE_FILTER_H_BLOCK0[238].val = 0x7710771
scaler.SCALE_FILTER_H_BLOCK0[239].val = 0x7570757
scaler.SCALE_FILTER_H_BLOCK1[119].val = 0x7570771
scaler.SCALE_FILTER_H_BLOCK0[240].val = 0x73d073d
scaler.SCALE_FILTER_H_BLOCK0[241].val = 0x7570757
scaler.SCALE_FILTER_H_BLOCK1[120].val = 0x757073d
scaler.SCALE_FILTER_H_BLOCK0[242].val = 0x7710771
scaler.SCALE_FILTER_H_BLOCK0[243].val = 0x78a078a
scaler.SCALE_FILTER_H_BLOCK1[121].val = 0x78a0771
scaler.SCALE_FILTER_H_BLOCK0[244].val = 0x7a207a2
scaler.SCALE_FILTER_H_BLOCK0[245].val = 0x7b607b6
scaler.SCALE_FILTER_H_BLOCK1[122].val = 0x7b607a2
scaler.SCALE_FILTER_H_BLOCK0[246].val = 0x7cb07cb
scaler.SCALE_FILTER_H_BLOCK0[247].val = 0x7dd07dd
scaler.SCALE_FILTER_H_BLOCK1[123].val = 0x7dd07cb
scaler.SCALE_FILTER_H_BLOCK0[248].val = 0x7ed07ed
scaler.SCALE_FILTER_H_BLOCK0[249].val = 0x7fc07fc
scaler.SCALE_FILTER_H_BLOCK1[124].val = 0x7fc07ed
scaler.SCALE_FILTER_H_BLOCK0[250].val = 0x8080808
scaler.SCALE_FILTER_H_BLOCK0[251].val = 0x8130813
scaler.SCALE_FILTER_H_BLOCK1[125].val = 0x8130808
scaler.SCALE_FILTER_H_BLOCK0[252].val = 0x81b081b
scaler.SCALE_FILTER_H_BLOCK0[253].val = 0x8200820
scaler.SCALE_FILTER_H_BLOCK1[126].val = 0x820081b
scaler.SCALE_FILTER_H_BLOCK0[254].val = 0x8280828
scaler.SCALE_FILTER_H_BLOCK0[255].val = 0x82b082b
scaler.SCALE_FILTER_H_BLOCK1[127].val = 0x82b0828
scaler.SCALE_FILTER_H_BLOCK0[256].val = 0x4e404e4
scaler.SCALE_FILTER_H_BLOCK0[257].val = 0x5100510
scaler.SCALE_FILTER_H_BLOCK1[128].val = 0x51004e4
scaler.SCALE_FILTER_H_BLOCK0[258].val = 0x53b053b
scaler.SCALE_FILTER_H_BLOCK0[259].val = 0x5660566
scaler.SCALE_FILTER_H_BLOCK1[129].val = 0x566053b
scaler.SCALE_FILTER_H_BLOCK0[260].val = 0x5900590
scaler.SCALE_FILTER_H_BLOCK0[261].val = 0x5b905b9
scaler.SCALE_FILTER_H_BLOCK1[130].val = 0x5b90590
scaler.SCALE_FILTER_H_BLOCK0[262].val = 0x5e205e2
scaler.SCALE_FILTER_H_BLOCK0[263].val = 0x6090609
scaler.SCALE_FILTER_H_BLOCK1[131].val = 0x60905e2
scaler.SCALE_FILTER_H_BLOCK0[264].val = 0x6300630
scaler.SCALE_FILTER_H_BLOCK0[265].val = 0x6560656
scaler.SCALE_FILTER_H_BLOCK1[132].val = 0x6560630
scaler.SCALE_FILTER_H_BLOCK0[266].val = 0x67a067a
scaler.SCALE_FILTER_H_BLOCK0[267].val = 0x69e069e
scaler.SCALE_FILTER_H_BLOCK1[133].val = 0x69e067a
scaler.SCALE_FILTER_H_BLOCK0[268].val = 0x6c006c0
scaler.SCALE_FILTER_H_BLOCK0[269].val = 0x6e106e1
scaler.SCALE_FILTER_H_BLOCK1[134].val = 0x6e106c0
scaler.SCALE_FILTER_H_BLOCK0[270].val = 0x7000700
scaler.SCALE_FILTER_H_BLOCK0[271].val = 0x71e071e
scaler.SCALE_FILTER_H_BLOCK1[135].val = 0x71e0700
scaler.SCALE_FILTER_H_BLOCK0[272].val = 0x2210221
scaler.SCALE_FILTER_H_BLOCK0[273].val = 0x24b024b
scaler.SCALE_FILTER_H_BLOCK1[136].val = 0x24b0221
scaler.SCALE_FILTER_H_BLOCK0[274].val = 0x2760276
scaler.SCALE_FILTER_H_BLOCK0[275].val = 0x2a102a1
scaler.SCALE_FILTER_H_BLOCK1[137].val = 0x2a10276
scaler.SCALE_FILTER_H_BLOCK0[276].val = 0x2cc02cc
scaler.SCALE_FILTER_H_BLOCK0[277].val = 0x2f802f8
scaler.SCALE_FILTER_H_BLOCK1[138].val = 0x2f802cc
scaler.SCALE_FILTER_H_BLOCK0[278].val = 0x3240324
scaler.SCALE_FILTER_H_BLOCK0[279].val = 0x3510351
scaler.SCALE_FILTER_H_BLOCK1[139].val = 0x3510324
scaler.SCALE_FILTER_H_BLOCK0[280].val = 0x37e037e
scaler.SCALE_FILTER_H_BLOCK0[281].val = 0x3ab03ab
scaler.SCALE_FILTER_H_BLOCK1[140].val = 0x3ab037e
scaler.SCALE_FILTER_H_BLOCK0[282].val = 0x3d803d8
scaler.SCALE_FILTER_H_BLOCK0[283].val = 0x4050405
scaler.SCALE_FILTER_H_BLOCK1[141].val = 0x40503d8
scaler.SCALE_FILTER_H_BLOCK0[284].val = 0x4320432
scaler.SCALE_FILTER_H_BLOCK0[285].val = 0x45f045f
scaler.SCALE_FILTER_H_BLOCK1[142].val = 0x45f0432
scaler.SCALE_FILTER_H_BLOCK0[286].val = 0x48b048b
scaler.SCALE_FILTER_H_BLOCK0[287].val = 0x4b804b8
scaler.SCALE_FILTER_H_BLOCK1[143].val = 0x4b8048b
scaler.SCALE_FILTER_H_BLOCK0[288].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[289].val = 0x1a001a
scaler.SCALE_FILTER_H_BLOCK1[144].val = 0x1a0000
scaler.SCALE_FILTER_H_BLOCK0[290].val = 0x350035
scaler.SCALE_FILTER_H_BLOCK0[291].val = 0x520052
scaler.SCALE_FILTER_H_BLOCK1[145].val = 0x520035
scaler.SCALE_FILTER_H_BLOCK0[292].val = 0x6f006f
scaler.SCALE_FILTER_H_BLOCK0[293].val = 0x8e008e
scaler.SCALE_FILTER_H_BLOCK1[146].val = 0x8e006f
scaler.SCALE_FILTER_H_BLOCK0[294].val = 0xae00ae
scaler.SCALE_FILTER_H_BLOCK0[295].val = 0xcf00cf
scaler.SCALE_FILTER_H_BLOCK1[147].val = 0xcf00ae
scaler.SCALE_FILTER_H_BLOCK0[296].val = 0xf100f1
scaler.SCALE_FILTER_H_BLOCK0[297].val = 0x1140114
scaler.SCALE_FILTER_H_BLOCK1[148].val = 0x11400f1
scaler.SCALE_FILTER_H_BLOCK0[298].val = 0x1380138
scaler.SCALE_FILTER_H_BLOCK0[299].val = 0x15d015d
scaler.SCALE_FILTER_H_BLOCK1[149].val = 0x15d0138
scaler.SCALE_FILTER_H_BLOCK0[300].val = 0x1820182
scaler.SCALE_FILTER_H_BLOCK0[301].val = 0x1a901a9
scaler.SCALE_FILTER_H_BLOCK1[150].val = 0x1a90182
scaler.SCALE_FILTER_H_BLOCK0[302].val = 0x1d001d0
scaler.SCALE_FILTER_H_BLOCK0[303].val = 0x1f901f9
scaler.SCALE_FILTER_H_BLOCK1[151].val = 0x1f901d0
scaler.SCALE_FILTER_H_BLOCK0[304].val = 0xff02ff02
scaler.SCALE_FILTER_H_BLOCK0[305].val = 0xff0aff0a
scaler.SCALE_FILTER_H_BLOCK1[152].val = 0xff0aff02
scaler.SCALE_FILTER_H_BLOCK0[306].val = 0xff12ff12
scaler.SCALE_FILTER_H_BLOCK0[307].val = 0xff1bff1b
scaler.SCALE_FILTER_H_BLOCK1[153].val = 0xff1bff12
scaler.SCALE_FILTER_H_BLOCK0[308].val = 0xff26ff26
scaler.SCALE_FILTER_H_BLOCK0[309].val = 0xff31ff31
scaler.SCALE_FILTER_H_BLOCK1[154].val = 0xff31ff26
scaler.SCALE_FILTER_H_BLOCK0[310].val = 0xff3eff3e
scaler.SCALE_FILTER_H_BLOCK0[311].val = 0xff4cff4c
scaler.SCALE_FILTER_H_BLOCK1[155].val = 0xff4cff3e
scaler.SCALE_FILTER_H_BLOCK0[312].val = 0xff5bff5b
scaler.SCALE_FILTER_H_BLOCK0[313].val = 0xff6bff6b
scaler.SCALE_FILTER_H_BLOCK1[156].val = 0xff6bff5b
scaler.SCALE_FILTER_H_BLOCK0[314].val = 0xff7dff7d
scaler.SCALE_FILTER_H_BLOCK0[315].val = 0xff90ff90
scaler.SCALE_FILTER_H_BLOCK1[157].val = 0xff90ff7d
scaler.SCALE_FILTER_H_BLOCK0[316].val = 0xffa4ffa4
scaler.SCALE_FILTER_H_BLOCK0[317].val = 0xffb9ffb9
scaler.SCALE_FILTER_H_BLOCK1[158].val = 0xffb9ffa4
scaler.SCALE_FILTER_H_BLOCK0[318].val = 0xffcfffcf
scaler.SCALE_FILTER_H_BLOCK0[319].val = 0xffe7ffe7
scaler.SCALE_FILTER_H_BLOCK1[159].val = 0xffe7ffcf
scaler.SCALE_FILTER_H_BLOCK0[320].val = 0xff06ff06
scaler.SCALE_FILTER_H_BLOCK0[321].val = 0xff01ff01
scaler.SCALE_FILTER_H_BLOCK1[160].val = 0xff01ff06
scaler.SCALE_FILTER_H_BLOCK0[322].val = 0xfefcfefc
scaler.SCALE_FILTER_H_BLOCK0[323].val = 0xfef8fef8
scaler.SCALE_FILTER_H_BLOCK1[161].val = 0xfef8fefc
scaler.SCALE_FILTER_H_BLOCK0[324].val = 0xfef4fef4
scaler.SCALE_FILTER_H_BLOCK0[325].val = 0xfef1fef1
scaler.SCALE_FILTER_H_BLOCK1[162].val = 0xfef1fef4
scaler.SCALE_FILTER_H_BLOCK0[326].val = 0xfeeefeee
scaler.SCALE_FILTER_H_BLOCK0[327].val = 0xfeecfeec
scaler.SCALE_FILTER_H_BLOCK1[163].val = 0xfeecfeee
scaler.SCALE_FILTER_H_BLOCK0[328].val = 0xfeebfeeb
scaler.SCALE_FILTER_H_BLOCK0[329].val = 0xfeebfeeb
scaler.SCALE_FILTER_H_BLOCK1[164].val = 0xfeebfeeb
scaler.SCALE_FILTER_H_BLOCK0[330].val = 0xfeecfeec
scaler.SCALE_FILTER_H_BLOCK0[331].val = 0xfeedfeed
scaler.SCALE_FILTER_H_BLOCK1[165].val = 0xfeedfeec
scaler.SCALE_FILTER_H_BLOCK0[332].val = 0xfeeffeef
scaler.SCALE_FILTER_H_BLOCK0[333].val = 0xfef3fef3
scaler.SCALE_FILTER_H_BLOCK1[166].val = 0xfef3feef
scaler.SCALE_FILTER_H_BLOCK0[334].val = 0xfef7fef7
scaler.SCALE_FILTER_H_BLOCK0[335].val = 0xfefcfefc
scaler.SCALE_FILTER_H_BLOCK1[167].val = 0xfefcfef7
scaler.SCALE_FILTER_H_BLOCK0[336].val = 0xff87ff87
scaler.SCALE_FILTER_H_BLOCK0[337].val = 0xff7eff7e
scaler.SCALE_FILTER_H_BLOCK1[168].val = 0xff7eff87
scaler.SCALE_FILTER_H_BLOCK0[338].val = 0xff75ff75
scaler.SCALE_FILTER_H_BLOCK0[339].val = 0xff6cff6c
scaler.SCALE_FILTER_H_BLOCK1[169].val = 0xff6cff75
scaler.SCALE_FILTER_H_BLOCK0[340].val = 0xff63ff63
scaler.SCALE_FILTER_H_BLOCK0[341].val = 0xff5bff5b
scaler.SCALE_FILTER_H_BLOCK1[170].val = 0xff5bff63
scaler.SCALE_FILTER_H_BLOCK0[342].val = 0xff52ff52
scaler.SCALE_FILTER_H_BLOCK0[343].val = 0xff49ff49
scaler.SCALE_FILTER_H_BLOCK1[171].val = 0xff49ff52
scaler.SCALE_FILTER_H_BLOCK0[344].val = 0xff41ff41
scaler.SCALE_FILTER_H_BLOCK0[345].val = 0xff38ff38
scaler.SCALE_FILTER_H_BLOCK1[172].val = 0xff38ff41
scaler.SCALE_FILTER_H_BLOCK0[346].val = 0xff30ff30
scaler.SCALE_FILTER_H_BLOCK0[347].val = 0xff28ff28
scaler.SCALE_FILTER_H_BLOCK1[173].val = 0xff28ff30
scaler.SCALE_FILTER_H_BLOCK0[348].val = 0xff21ff21
scaler.SCALE_FILTER_H_BLOCK0[349].val = 0xff1aff1a
scaler.SCALE_FILTER_H_BLOCK1[174].val = 0xff1aff21
scaler.SCALE_FILTER_H_BLOCK0[350].val = 0xff13ff13
scaler.SCALE_FILTER_H_BLOCK0[351].val = 0xff0cff0c
scaler.SCALE_FILTER_H_BLOCK1[175].val = 0xff0cff13
scaler.SCALE_FILTER_H_BLOCK0[352].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[353].val = 0xfffafffa
scaler.SCALE_FILTER_H_BLOCK1[176].val = 0xfffa0000
scaler.SCALE_FILTER_H_BLOCK0[354].val = 0xfff4fff4
scaler.SCALE_FILTER_H_BLOCK0[355].val = 0xffeeffee
scaler.SCALE_FILTER_H_BLOCK1[177].val = 0xffeefff4
scaler.SCALE_FILTER_H_BLOCK0[356].val = 0xffe7ffe7
scaler.SCALE_FILTER_H_BLOCK0[357].val = 0xffe0ffe0
scaler.SCALE_FILTER_H_BLOCK1[178].val = 0xffe0ffe7
scaler.SCALE_FILTER_H_BLOCK0[358].val = 0xffd9ffd9
scaler.SCALE_FILTER_H_BLOCK0[359].val = 0xffd2ffd2
scaler.SCALE_FILTER_H_BLOCK1[179].val = 0xffd2ffd9
scaler.SCALE_FILTER_H_BLOCK0[360].val = 0xffcaffca
scaler.SCALE_FILTER_H_BLOCK0[361].val = 0xffc2ffc2
scaler.SCALE_FILTER_H_BLOCK1[180].val = 0xffc2ffca
scaler.SCALE_FILTER_H_BLOCK0[362].val = 0xffbaffba
scaler.SCALE_FILTER_H_BLOCK0[363].val = 0xffb2ffb2
scaler.SCALE_FILTER_H_BLOCK1[181].val = 0xffb2ffba
scaler.SCALE_FILTER_H_BLOCK0[364].val = 0xffaaffaa
scaler.SCALE_FILTER_H_BLOCK0[365].val = 0xffa1ffa1
scaler.SCALE_FILTER_H_BLOCK1[182].val = 0xffa1ffaa
scaler.SCALE_FILTER_H_BLOCK0[366].val = 0xff99ff99
scaler.SCALE_FILTER_H_BLOCK0[367].val = 0xff90ff90
scaler.SCALE_FILTER_H_BLOCK1[183].val = 0xff90ff99
scaler.SCALE_FILTER_H_BLOCK0[368].val = 0x340034
scaler.SCALE_FILTER_H_BLOCK0[369].val = 0x330033
scaler.SCALE_FILTER_H_BLOCK1[184].val = 0x330034
scaler.SCALE_FILTER_H_BLOCK0[370].val = 0x320032
scaler.SCALE_FILTER_H_BLOCK0[371].val = 0x300030
scaler.SCALE_FILTER_H_BLOCK1[185].val = 0x300032
scaler.SCALE_FILTER_H_BLOCK0[372].val = 0x2e002e
scaler.SCALE_FILTER_H_BLOCK0[373].val = 0x2c002c
scaler.SCALE_FILTER_H_BLOCK1[186].val = 0x2c002e
scaler.SCALE_FILTER_H_BLOCK0[374].val = 0x290029
scaler.SCALE_FILTER_H_BLOCK0[375].val = 0x260026
scaler.SCALE_FILTER_H_BLOCK1[187].val = 0x260029
scaler.SCALE_FILTER_H_BLOCK0[376].val = 0x230023
scaler.SCALE_FILTER_H_BLOCK0[377].val = 0x200020
scaler.SCALE_FILTER_H_BLOCK1[188].val = 0x200023
scaler.SCALE_FILTER_H_BLOCK0[378].val = 0x1c001c
scaler.SCALE_FILTER_H_BLOCK0[379].val = 0x180018
scaler.SCALE_FILTER_H_BLOCK1[189].val = 0x18001c
scaler.SCALE_FILTER_H_BLOCK0[380].val = 0x140014
scaler.SCALE_FILTER_H_BLOCK0[381].val = 0x100010
scaler.SCALE_FILTER_H_BLOCK1[190].val = 0x100014
scaler.SCALE_FILTER_H_BLOCK0[382].val = 0xb000b
scaler.SCALE_FILTER_H_BLOCK0[383].val = 0x50005
scaler.SCALE_FILTER_H_BLOCK1[191].val = 0x5000b
scaler.SCALE_FILTER_H_BLOCK0[384].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[385].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[192].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[386].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[387].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[193].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[388].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[389].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[194].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[390].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[391].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[195].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[392].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[393].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[196].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[394].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[395].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[197].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[396].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[397].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[198].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[398].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[399].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[199].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[400].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[401].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[200].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[402].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[403].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[201].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[404].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[405].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[202].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[406].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[407].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[203].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[408].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[409].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[204].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[410].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[411].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[205].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[412].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[413].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[206].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[414].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[415].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[207].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[416].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[417].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[208].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[418].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[419].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[209].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[420].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[421].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[210].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[422].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[423].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[211].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[424].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[425].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[212].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[426].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[427].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[213].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[428].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[429].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[214].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[430].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[431].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[215].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[432].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[433].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[216].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[434].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[435].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[217].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[436].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[437].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[218].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[438].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[439].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[219].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[440].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[441].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[220].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[442].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[443].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[221].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[444].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[445].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[222].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[446].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[447].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[223].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[448].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[449].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[224].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[450].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[451].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[225].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[452].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[453].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[226].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[454].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[455].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[227].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[456].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[457].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[228].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[458].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[459].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[229].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[460].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[461].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[230].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[462].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[463].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[231].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[464].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[465].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[232].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[466].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[467].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[233].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[468].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[469].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[234].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[470].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[471].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[235].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[472].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[473].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[236].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[474].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[475].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[237].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[476].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[477].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[238].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[478].val = 0x0
scaler.SCALE_FILTER_H_BLOCK0[479].val = 0x0
scaler.SCALE_FILTER_H_BLOCK1[239].val = 0x0

# pseudo linear scaling
scaler.PSEUDO_LINEAR_SCALING = 0

# reshape
p.write32(scaler_base + 0xe8, 0x0)

# reset CM 3x
p.write32(scaler_base + 0x3800, 0x0)
p.write32(scaler_base + 0x3800, 0x0)
p.write32(scaler_base + 0x3800, 0x0)

# enable prescaler
p.write32(scaler_base + 0x824, 0xc)

# alpha override
p.write32(scaler_base + 0x8c, 0xffff)

# dither
p.write32(scaler_base + 0xa00, 0x0)

# commit convert
p.write32(scaler_base + 0x13808, 0x0)
p.write32(scaler_base + 0x1380c, 0x0)
p.write32(scaler_base + 0x13800, 0x0)
p.write32(scaler_base + 0x13804, 0x0)

# convert map
p.write32(scaler_base + 0x13810, 0x8)
p.write32(scaler_base + 0x13814, 0x8)
p.write32(scaler_base + 0x13818, 0x8)
p.write32(scaler_base + 0x1381c, 0x8)
p.write32(scaler_base + 0x13804, 0x0)
p.write32(scaler_base + 0x13c04, 0x0)
p.write32(scaler_base + 0x13c10, 0x8)
p.write32(scaler_base + 0x13c14, 0x8)
p.write32(scaler_base + 0x13c18, 0x8)
p.write32(scaler_base + 0x13c1c, 0x8)

# commit revert
p.write32(scaler_base + 0x13c00, 0x1)

# (don't) program histogram
p.write32(scaler_base + 0x3000, 0x0)
p.write32(scaler_base + 0x124, 0x0)

# tag transform registers
p.write32(scaler_base + 0x110, 0x1)

# start
p.write32(scaler_base + 0x98, 0xfffffffe)
scaler.START = 1

start_time = time.time()
while scaler.MSR_GLBL_IRQSTS.reg.DONE == 0:
    if time.time() - start_time > 5:
        print("TIMED OUT!!!")
        break

print(f"IRQ status is now {scaler.MSR_GLBL_IRQSTS}")
print(f"Debug status is now {scaler.MSR_CTRL_DBGSTS}")

out_buf_new = iface.readmem(out_buf_phys, out_SZ)
chexdump(out_buf_new)

with Image.new(mode='RGBA', size=(out_W, out_H)) as im:
    for y in range(out_H):
        for x in range(out_W):
            block = out_buf_new[
                y*out_STRIDE + x*out_BYTESPP:
                y*out_STRIDE + (x+1)*out_BYTESPP]

            r, g, b, a = block
            im.putpixel((x, y), (r, g, b, a))

    im.save(output_image_fn)
