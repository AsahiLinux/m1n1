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

out_W = in_W
out_H = in_H
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
scaler.FLIP_ROTATE.set(FLIP_ROTATE=E_FLIP_ROTATE.NONE)

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

# pixel averaging -----
p.write32(scaler_base + 0xe4, 0x0)

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

# DDA init
p.write32(scaler_base + 0x2004, 0x0)
p.write32(scaler_base + 0x201c, 0x0)
p.write32(scaler_base + 0x1008, 0x0)

# vertical scaling
p.write32(scaler_base + 0x100c, 0x400000)
p.write32(scaler_base + 0x1020, 0x400000)
p.write32(scaler_base + 0x1010, 0x400000)
p.write32(scaler_base + 0x1014, 0x400000)
p.write32(scaler_base + 0x1018, 0x400000)
p.write32(scaler_base + 0x1024, 0x400000)
p.write32(scaler_base + 0x1000, 0x0)

# DDA init
p.write32(scaler_base + 0x2004, 0x0)
p.write32(scaler_base + 0x201c, 0x0)
p.write32(scaler_base + 0x2008, 0x0)

# horizontal scaling
p.write32(scaler_base + 0x200c, 0x400000)
p.write32(scaler_base + 0x2020, 0x400000)
p.write32(scaler_base + 0x2010, 0x400000)
p.write32(scaler_base + 0x2014, 0x400000)
p.write32(scaler_base + 0x2024, 0x400000)
p.write32(scaler_base + 0x2018, 0x400000)
p.write32(scaler_base + 0x2000, 0x0)

# pseudo linear scaling
p.write32(scaler_base + 0x480, 0x0)

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
