#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.dart8110 import DART8110, DART8110Regs
from m1n1.hw.prores import *
from m1n1.utils import *
import time


def divroundup(val, div):
    return (val + div - 1) // div


def bswp16(x):
    return (x >> 8) | ((x & 0xFF) << 8)

# ffmpeg -y -i prores-encode-large.png -c:v rawvideo -pix_fmt nv24 prores-encode-large.yuv
im_W = 1920
im_H = 1080
with open('prores-encode-large.yuv', 'rb') as f:
    im_data = f.read()
assert len(im_data) == (im_W*im_H) * 3
image_data_luma = im_data[:im_W*im_H]
image_data_chroma = im_data[im_W*im_H:]

p.pmgr_adt_clocks_enable(f'/arm-io/dart-apr0')
p.pmgr_adt_clocks_enable(f'/arm-io/apr0')

dart = DART8110.from_adt(u, f'/arm-io/dart-apr0')
dart.initialize()

apr_base, _ = u.adt[f'/arm-io/apr0'].get_reg(0)
apr = ProResRegs(u, apr_base)

print(f"Register 0 (ID?) {apr.REG_0x0}")

# TUNABLES
apr.MODE = 0x0
apr.REG_0x118 = apr.REG_0x118.val & ~0x07FF07FF | 0x00000600
apr.REG_0x148 = apr.REG_0x148.val & ~0x00000001 | 0x00000001
apr.REG_0x160 = apr.REG_0x160.val & ~0x800F3FFF | 0x800A04FF
apr.REG_0x164 = apr.REG_0x164.val & ~0x07FF07FF | 0x07800080
apr.REG_0x170 = apr.REG_0x170.val & ~0x800F3FFF | 0x800404FF
apr.REG_0x174 = apr.REG_0x174.val & ~0x07FF07FF | 0x06000080
apr.REG_0x180 = apr.REG_0x180.val & ~0x800F3FFF | 0x800504FF
apr.REG_0x184 = apr.REG_0x184.val & ~0x07FF07FF | 0x06800080
apr.REG_0x190 = apr.REG_0x190.val & ~0x800F3FFF | 0x800004FF
apr.REG_0x194 = apr.REG_0x194.val & ~0x000000FF | 0x00000040
apr.REG_0x1a0 = apr.REG_0x1a0.val & ~0x800F3FFF | 0x800104FF
apr.REG_0x1a4 = apr.REG_0x1a4.val & ~0x000000FF | 0x00000080
apr.REG_0x1b0 = apr.REG_0x1b0.val & ~0x800F3FFF | 0x800204FF
apr.REG_0x1b4 = apr.REG_0x1b4.val & ~0x000000FF | 0x00000040
apr.REG_0x1c0 = apr.REG_0x1c0.val & ~0x800F3FFF | 0x800304FF
apr.REG_0x1c4 = apr.REG_0x1c4.val & ~0x000000FF | 0x00000040
apr.REG_0x1d0 = apr.REG_0x1d0.val & ~0xBC00FF86 | 0xA4000786
apr.REG_0x1d4 = apr.REG_0x1d4.val & ~0x000000FF | 0x00000020
apr.REG_0x1d8 = apr.REG_0x1d8.val & ~0x000000FF | 0x000000FF
apr.REG_0x1dc = apr.REG_0x1dc.val & ~0x00FFFFFF | 0x00928170
apr.REG_0x270 = apr.REG_0x270.val & ~0x800F3FFF | 0x800B08FF
apr.REG_0x274 = apr.REG_0x274.val & ~0x07FF07FF | 0x07000080
apr.REG_0x280 = apr.REG_0x280.val & ~0xFFFFFFC0 | 0x00180000
apr.REG_0x290 = apr.REG_0x290.val & ~0x800F3FFF | 0x800004FF
apr.REG_0x294 = apr.REG_0x294.val & ~0x000000FF | 0x00000080
apr.REG_0x2a0 = apr.REG_0x2a0.val & ~0x800F3FFF | 0x800104FF
apr.REG_0x2a4 = apr.REG_0x2a4.val & ~0x000000FF | 0x00000080
apr.REG_0x2b0 = apr.REG_0x2b0.val & ~0x800F3FFF | 0x800204FF
apr.REG_0x2b4 = apr.REG_0x2b4.val & ~0x000000FF | 0x00000040
apr.REG_0x2c0 = apr.REG_0x2c0.val & ~0x800F3FFF | 0x800304FF
apr.REG_0x2c4 = apr.REG_0x2c4.val & ~0x000000FF | 0x00000040
apr.REG_0x2d0 = apr.REG_0x2d0.val & ~0x802FF04C | 0x80070040
apr.REG_0x2d4 = apr.REG_0x2d4.val & ~0x00000001 | 0x00000000
apr.REG_0x2d8 = apr.REG_0x2d8.val & ~0xFFFF0003 | 0x00FF0003
apr.REG_0x2e0 = apr.REG_0x2e0.val & ~0x07FF07FF | 0x06000040
apr.REG_0x2f8 = apr.REG_0x2f8.val & ~0x802FF04C | 0x80081040
apr.REG_0x2fc = apr.REG_0x2fc.val & ~0x00000001 | 0x00000000
apr.REG_0x300 = apr.REG_0x300.val & ~0xFFFF0003 | 0x00FF0003
apr.REG_0x308 = apr.REG_0x308.val & ~0x07FF07FF | 0x06400040
apr.REG_0x320 = apr.REG_0x320.val & ~0x802FF04C | 0x80092040
apr.REG_0x324 = apr.REG_0x324.val & ~0x00000001 | 0x00000000
apr.REG_0x328 = apr.REG_0x328.val & ~0xFFFF0003 | 0x00FF0003
apr.REG_0x330 = apr.REG_0x330.val & ~0x07FF07FF | 0x06800040
apr.REG_0x350 = apr.REG_0x350.val & ~0x800F3FFF | 0x800B08FF
apr.REG_0x354 = apr.REG_0x354.val & ~0x07FF07FF | 0x076000A0
apr.REG_0x360 = apr.REG_0x360.val & ~0xFFFFFFC0 | 0x00180000
apr.REG_0x370 = apr.REG_0x370.val & ~0x800F3FFF | 0x800604FF
apr.REG_0x374 = apr.REG_0x374.val & ~0x07FF07FF | 0x06C000A0
print("Applied tunables")

# XXX test wrap around behavior
DESC_RING_SZ = 0x4000
desc_ring_phys = u.heap.memalign(0x4000, DESC_RING_SZ)
desc_ring_iova = dart.iomap(0, desc_ring_phys, DESC_RING_SZ)
print(f"Descriptor ring @ phys {desc_ring_phys:016X} iova {desc_ring_iova:016X}")

apr.DR_HEAD = 0
apr.DR_TAIL = 0
apr.DR_SIZE = DESC_RING_SZ
apr.DR_ADDR_LO = desc_ring_iova & 0xFFFFFFFF
apr.DR_ADDR_HI = desc_ring_iova >> 32

apr.MODE = 0xd  # FIXME: dunno what this means

# MATRICES
apr.QUANT_LUMA_EHQ[0].val       = 0x802802
apr.QUANT_CHROMA_EHQ[0].val     = 0x804804
apr.QUANT_LUMA_EHQ[1].val       = 0x802802
apr.QUANT_CHROMA_EHQ[1].val     = 0x804804
apr.QUANT_LUMA_EHQ[2].val       = 0x802802
apr.QUANT_CHROMA_EHQ[2].val     = 0x804804
apr.QUANT_LUMA_EHQ[3].val       = 0x802802
apr.QUANT_CHROMA_EHQ[3].val     = 0x804804
apr.QUANT_LUMA_EHQ[4].val       = 0x802802
apr.QUANT_CHROMA_EHQ[4].val     = 0x804804
apr.QUANT_LUMA_EHQ[5].val       = 0x802802
apr.QUANT_CHROMA_EHQ[5].val     = 0x804804
apr.QUANT_LUMA_EHQ[6].val       = 0x802802
apr.QUANT_CHROMA_EHQ[6].val     = 0x804804
apr.QUANT_LUMA_EHQ[7].val       = 0x802802
apr.QUANT_CHROMA_EHQ[7].val     = 0x804804
apr.QUANT_LUMA_EHQ[8].val       = 0x802802
apr.QUANT_CHROMA_EHQ[8].val     = 0x804804
apr.QUANT_LUMA_EHQ[9].val       = 0x802802
apr.QUANT_CHROMA_EHQ[9].val     = 0x804804
apr.QUANT_LUMA_EHQ[10].val      = 0x802802
apr.QUANT_CHROMA_EHQ[10].val    = 0x804804
apr.QUANT_LUMA_EHQ[11].val      = 0x802802
apr.QUANT_CHROMA_EHQ[11].val    = 0x804804
apr.QUANT_LUMA_EHQ[12].val      = 0x802802
apr.QUANT_CHROMA_EHQ[12].val    = 0x804804
apr.QUANT_LUMA_EHQ[13].val      = 0x802802
apr.QUANT_CHROMA_EHQ[13].val    = 0x804804
apr.QUANT_LUMA_EHQ[14].val      = 0x802802
apr.QUANT_CHROMA_EHQ[14].val    = 0x804804
apr.QUANT_LUMA_EHQ[15].val      = 0x803802
apr.QUANT_CHROMA_EHQ[15].val    = 0x805804
apr.QUANT_LUMA_EHQ[16].val      = 0x802802
apr.QUANT_CHROMA_EHQ[16].val    = 0x804804
apr.QUANT_LUMA_EHQ[17].val      = 0x802802
apr.QUANT_CHROMA_EHQ[17].val    = 0x804804
apr.QUANT_LUMA_EHQ[18].val      = 0x802802
apr.QUANT_CHROMA_EHQ[18].val    = 0x804804
apr.QUANT_LUMA_EHQ[19].val      = 0x803803
apr.QUANT_CHROMA_EHQ[19].val    = 0x805805
apr.QUANT_LUMA_EHQ[20].val      = 0x802802
apr.QUANT_CHROMA_EHQ[20].val    = 0x804804
apr.QUANT_LUMA_EHQ[21].val      = 0x802802
apr.QUANT_CHROMA_EHQ[21].val    = 0x804804
apr.QUANT_LUMA_EHQ[22].val      = 0x803802
apr.QUANT_CHROMA_EHQ[22].val    = 0x805804
apr.QUANT_LUMA_EHQ[23].val      = 0x803803
apr.QUANT_CHROMA_EHQ[23].val    = 0x806805
apr.QUANT_LUMA_EHQ[24].val      = 0x802802
apr.QUANT_CHROMA_EHQ[24].val    = 0x804804
apr.QUANT_LUMA_EHQ[25].val      = 0x802802
apr.QUANT_CHROMA_EHQ[25].val    = 0x804804
apr.QUANT_LUMA_EHQ[26].val      = 0x803803
apr.QUANT_CHROMA_EHQ[26].val    = 0x805805
apr.QUANT_LUMA_EHQ[27].val      = 0x804803
apr.QUANT_CHROMA_EHQ[27].val    = 0x807806
apr.QUANT_LUMA_EHQ[28].val      = 0x802802
apr.QUANT_CHROMA_EHQ[28].val    = 0x804804
apr.QUANT_LUMA_EHQ[29].val      = 0x802802
apr.QUANT_CHROMA_EHQ[29].val    = 0x804804
apr.QUANT_LUMA_EHQ[30].val      = 0x803803
apr.QUANT_CHROMA_EHQ[30].val    = 0x806805
apr.QUANT_LUMA_EHQ[31].val      = 0x804804
apr.QUANT_CHROMA_EHQ[31].val    = 0x807807

apr.QUANT_LUMA_HQ[0].val        = 0x804804
apr.QUANT_CHROMA_HQ[0].val      = 0x804804
apr.QUANT_LUMA_HQ[1].val        = 0x804804
apr.QUANT_CHROMA_HQ[1].val      = 0x804804
apr.QUANT_LUMA_HQ[2].val        = 0x804804
apr.QUANT_CHROMA_HQ[2].val      = 0x804804
apr.QUANT_LUMA_HQ[3].val        = 0x804804
apr.QUANT_CHROMA_HQ[3].val      = 0x804804
apr.QUANT_LUMA_HQ[4].val        = 0x804804
apr.QUANT_CHROMA_HQ[4].val      = 0x804804
apr.QUANT_LUMA_HQ[5].val        = 0x804804
apr.QUANT_CHROMA_HQ[5].val      = 0x804804
apr.QUANT_LUMA_HQ[6].val        = 0x804804
apr.QUANT_CHROMA_HQ[6].val      = 0x804804
apr.QUANT_LUMA_HQ[7].val        = 0x804804
apr.QUANT_CHROMA_HQ[7].val      = 0x804804
apr.QUANT_LUMA_HQ[8].val        = 0x804804
apr.QUANT_CHROMA_HQ[8].val      = 0x804804
apr.QUANT_LUMA_HQ[9].val        = 0x804804
apr.QUANT_CHROMA_HQ[9].val      = 0x804804
apr.QUANT_LUMA_HQ[10].val       = 0x804804
apr.QUANT_CHROMA_HQ[10].val     = 0x804804
apr.QUANT_LUMA_HQ[11].val       = 0x804804
apr.QUANT_CHROMA_HQ[11].val     = 0x804804
apr.QUANT_LUMA_HQ[12].val       = 0x804804
apr.QUANT_CHROMA_HQ[12].val     = 0x804804
apr.QUANT_LUMA_HQ[13].val       = 0x804804
apr.QUANT_CHROMA_HQ[13].val     = 0x804804
apr.QUANT_LUMA_HQ[14].val       = 0x804804
apr.QUANT_CHROMA_HQ[14].val     = 0x804804
apr.QUANT_LUMA_HQ[15].val       = 0x805804
apr.QUANT_CHROMA_HQ[15].val     = 0x805804
apr.QUANT_LUMA_HQ[16].val       = 0x804804
apr.QUANT_CHROMA_HQ[16].val     = 0x804804
apr.QUANT_LUMA_HQ[17].val       = 0x804804
apr.QUANT_CHROMA_HQ[17].val     = 0x804804
apr.QUANT_LUMA_HQ[18].val       = 0x804804
apr.QUANT_CHROMA_HQ[18].val     = 0x804804
apr.QUANT_LUMA_HQ[19].val       = 0x805805
apr.QUANT_CHROMA_HQ[19].val     = 0x805805
apr.QUANT_LUMA_HQ[20].val       = 0x804804
apr.QUANT_CHROMA_HQ[20].val     = 0x804804
apr.QUANT_LUMA_HQ[21].val       = 0x804804
apr.QUANT_CHROMA_HQ[21].val     = 0x804804
apr.QUANT_LUMA_HQ[22].val       = 0x805804
apr.QUANT_CHROMA_HQ[22].val     = 0x805804
apr.QUANT_LUMA_HQ[23].val       = 0x806805
apr.QUANT_CHROMA_HQ[23].val     = 0x806805
apr.QUANT_LUMA_HQ[24].val       = 0x804804
apr.QUANT_CHROMA_HQ[24].val     = 0x804804
apr.QUANT_LUMA_HQ[25].val       = 0x804804
apr.QUANT_CHROMA_HQ[25].val     = 0x804804
apr.QUANT_LUMA_HQ[26].val       = 0x805805
apr.QUANT_CHROMA_HQ[26].val     = 0x805805
apr.QUANT_LUMA_HQ[27].val       = 0x807806
apr.QUANT_CHROMA_HQ[27].val     = 0x807806
apr.QUANT_LUMA_HQ[28].val       = 0x804804
apr.QUANT_CHROMA_HQ[28].val     = 0x804804
apr.QUANT_LUMA_HQ[29].val       = 0x804804
apr.QUANT_CHROMA_HQ[29].val     = 0x804804
apr.QUANT_LUMA_HQ[30].val       = 0x806805
apr.QUANT_CHROMA_HQ[30].val     = 0x806805
apr.QUANT_LUMA_HQ[31].val       = 0x807807
apr.QUANT_CHROMA_HQ[31].val     = 0x807807

apr.QUANT_LUMA_NQ[0].val        = 0x804804
apr.QUANT_CHROMA_NQ[0].val      = 0x804804
apr.QUANT_LUMA_NQ[1].val        = 0x805805
apr.QUANT_CHROMA_NQ[1].val      = 0x805805
apr.QUANT_LUMA_NQ[2].val        = 0x807806
apr.QUANT_CHROMA_NQ[2].val      = 0x807806
apr.QUANT_LUMA_NQ[3].val        = 0x809807
apr.QUANT_CHROMA_NQ[3].val      = 0x809807
apr.QUANT_LUMA_NQ[4].val        = 0x804804
apr.QUANT_CHROMA_NQ[4].val      = 0x804804
apr.QUANT_LUMA_NQ[5].val        = 0x806805
apr.QUANT_CHROMA_NQ[5].val      = 0x806805
apr.QUANT_LUMA_NQ[6].val        = 0x807807
apr.QUANT_CHROMA_NQ[6].val      = 0x807807
apr.QUANT_LUMA_NQ[7].val        = 0x809809
apr.QUANT_CHROMA_NQ[7].val      = 0x809809
apr.QUANT_LUMA_NQ[8].val        = 0x805805
apr.QUANT_CHROMA_NQ[8].val      = 0x805805
apr.QUANT_LUMA_NQ[9].val        = 0x807806
apr.QUANT_CHROMA_NQ[9].val      = 0x807806
apr.QUANT_LUMA_NQ[10].val       = 0x809807
apr.QUANT_CHROMA_NQ[10].val     = 0x809807
apr.QUANT_LUMA_NQ[11].val       = 0x80a809
apr.QUANT_CHROMA_NQ[11].val     = 0x80a809
apr.QUANT_LUMA_NQ[12].val       = 0x805805
apr.QUANT_CHROMA_NQ[12].val     = 0x805805
apr.QUANT_LUMA_NQ[13].val       = 0x807806
apr.QUANT_CHROMA_NQ[13].val     = 0x807806
apr.QUANT_LUMA_NQ[14].val       = 0x809807
apr.QUANT_CHROMA_NQ[14].val     = 0x809807
apr.QUANT_LUMA_NQ[15].val       = 0x80a809
apr.QUANT_CHROMA_NQ[15].val     = 0x80a809
apr.QUANT_LUMA_NQ[16].val       = 0x806805
apr.QUANT_CHROMA_NQ[16].val     = 0x806805
apr.QUANT_LUMA_NQ[17].val       = 0x807807
apr.QUANT_CHROMA_NQ[17].val     = 0x807807
apr.QUANT_LUMA_NQ[18].val       = 0x809808
apr.QUANT_CHROMA_NQ[18].val     = 0x809808
apr.QUANT_LUMA_NQ[19].val       = 0x80c80a
apr.QUANT_CHROMA_NQ[19].val     = 0x80c80a
apr.QUANT_LUMA_NQ[20].val       = 0x807806
apr.QUANT_CHROMA_NQ[20].val     = 0x807806
apr.QUANT_LUMA_NQ[21].val       = 0x808807
apr.QUANT_CHROMA_NQ[21].val     = 0x808807
apr.QUANT_LUMA_NQ[22].val       = 0x80a809
apr.QUANT_CHROMA_NQ[22].val     = 0x80a809
apr.QUANT_LUMA_NQ[23].val       = 0x80f80c
apr.QUANT_CHROMA_NQ[23].val     = 0x80f80c
apr.QUANT_LUMA_NQ[24].val       = 0x807806
apr.QUANT_CHROMA_NQ[24].val     = 0x807806
apr.QUANT_LUMA_NQ[25].val       = 0x809807
apr.QUANT_CHROMA_NQ[25].val     = 0x809807
apr.QUANT_LUMA_NQ[26].val       = 0x80b80a
apr.QUANT_CHROMA_NQ[26].val     = 0x80b80a
apr.QUANT_LUMA_NQ[27].val       = 0x81180e
apr.QUANT_CHROMA_NQ[27].val     = 0x81180e
apr.QUANT_LUMA_NQ[28].val       = 0x807807
apr.QUANT_CHROMA_NQ[28].val     = 0x807807
apr.QUANT_LUMA_NQ[29].val       = 0x80a809
apr.QUANT_CHROMA_NQ[29].val     = 0x80a809
apr.QUANT_LUMA_NQ[30].val       = 0x80e80b
apr.QUANT_CHROMA_NQ[30].val     = 0x80e80b
apr.QUANT_LUMA_NQ[31].val       = 0x815811
apr.QUANT_CHROMA_NQ[31].val     = 0x815811

apr.QUANT_LUMA_LT[0].val        = 0x805804
apr.QUANT_CHROMA_LT[0].val      = 0x805804
apr.QUANT_LUMA_LT[1].val        = 0x807806
apr.QUANT_CHROMA_LT[1].val      = 0x807806
apr.QUANT_LUMA_LT[2].val        = 0x80b809
apr.QUANT_CHROMA_LT[2].val      = 0x80b809
apr.QUANT_LUMA_LT[3].val        = 0x80f80d
apr.QUANT_CHROMA_LT[3].val      = 0x80f80d
apr.QUANT_LUMA_LT[4].val        = 0x805805
apr.QUANT_CHROMA_LT[4].val      = 0x805805
apr.QUANT_LUMA_LT[5].val        = 0x808807
apr.QUANT_CHROMA_LT[5].val      = 0x808807
apr.QUANT_LUMA_LT[6].val        = 0x80d80b
apr.QUANT_CHROMA_LT[6].val      = 0x80d80b
apr.QUANT_LUMA_LT[7].val        = 0x81180f
apr.QUANT_CHROMA_LT[7].val      = 0x81180f
apr.QUANT_LUMA_LT[8].val        = 0x807806
apr.QUANT_CHROMA_LT[8].val      = 0x807806
apr.QUANT_LUMA_LT[9].val        = 0x80b809
apr.QUANT_CHROMA_LT[9].val      = 0x80b809
apr.QUANT_LUMA_LT[10].val       = 0x80f80d
apr.QUANT_CHROMA_LT[10].val     = 0x80f80d
apr.QUANT_LUMA_LT[11].val       = 0x81180f
apr.QUANT_CHROMA_LT[11].val     = 0x81180f
apr.QUANT_LUMA_LT[12].val       = 0x807807
apr.QUANT_CHROMA_LT[12].val     = 0x807807
apr.QUANT_LUMA_LT[13].val       = 0x80b809
apr.QUANT_CHROMA_LT[13].val     = 0x80b809
apr.QUANT_LUMA_LT[14].val       = 0x80f80d
apr.QUANT_CHROMA_LT[14].val     = 0x80f80d
apr.QUANT_LUMA_LT[15].val       = 0x813811
apr.QUANT_CHROMA_LT[15].val     = 0x813811
apr.QUANT_LUMA_LT[16].val       = 0x809807
apr.QUANT_CHROMA_LT[16].val     = 0x809807
apr.QUANT_LUMA_LT[17].val       = 0x80d80b
apr.QUANT_CHROMA_LT[17].val     = 0x80d80b
apr.QUANT_LUMA_LT[18].val       = 0x81080e
apr.QUANT_CHROMA_LT[18].val     = 0x81080e
apr.QUANT_LUMA_LT[19].val       = 0x817813
apr.QUANT_CHROMA_LT[19].val     = 0x817813
apr.QUANT_LUMA_LT[20].val       = 0x80b809
apr.QUANT_CHROMA_LT[20].val     = 0x80b809
apr.QUANT_LUMA_LT[21].val       = 0x80e80d
apr.QUANT_CHROMA_LT[21].val     = 0x80e80d
apr.QUANT_LUMA_LT[22].val       = 0x813810
apr.QUANT_CHROMA_LT[22].val     = 0x813810
apr.QUANT_LUMA_LT[23].val       = 0x81d817
apr.QUANT_CHROMA_LT[23].val     = 0x81d817
apr.QUANT_LUMA_LT[24].val       = 0x80b809
apr.QUANT_CHROMA_LT[24].val     = 0x80b809
apr.QUANT_LUMA_LT[25].val       = 0x80f80d
apr.QUANT_CHROMA_LT[25].val     = 0x80f80d
apr.QUANT_LUMA_LT[26].val       = 0x815811
apr.QUANT_CHROMA_LT[26].val     = 0x815811
apr.QUANT_LUMA_LT[27].val       = 0x82381c
apr.QUANT_CHROMA_LT[27].val     = 0x82381c
apr.QUANT_LUMA_LT[28].val       = 0x80d80b
apr.QUANT_CHROMA_LT[28].val     = 0x80d80b
apr.QUANT_LUMA_LT[29].val       = 0x811810
apr.QUANT_CHROMA_LT[29].val     = 0x811810
apr.QUANT_LUMA_LT[30].val       = 0x81c815
apr.QUANT_CHROMA_LT[30].val     = 0x81c815
apr.QUANT_LUMA_LT[31].val       = 0x829823
apr.QUANT_CHROMA_LT[31].val     = 0x829823

apr.QUANT_LUMA_PROXY[0].val     = 0x807804
apr.QUANT_CHROMA_PROXY[0].val   = 0x807804
apr.QUANT_LUMA_PROXY[1].val     = 0x80b809
apr.QUANT_CHROMA_PROXY[1].val   = 0x80b809
apr.QUANT_LUMA_PROXY[2].val     = 0x80e80d
apr.QUANT_CHROMA_PROXY[2].val   = 0x80e80d
apr.QUANT_LUMA_PROXY[3].val     = 0xfff83f
apr.QUANT_CHROMA_PROXY[3].val   = 0xfff83f
apr.QUANT_LUMA_PROXY[4].val     = 0x807807
apr.QUANT_CHROMA_PROXY[4].val   = 0x807807
apr.QUANT_LUMA_PROXY[5].val     = 0x80c80b
apr.QUANT_CHROMA_PROXY[5].val   = 0x80c80b
apr.QUANT_LUMA_PROXY[6].val     = 0x83f80e
apr.QUANT_CHROMA_PROXY[6].val   = 0x83f80e
apr.QUANT_LUMA_PROXY[7].val     = 0xffffff
apr.QUANT_CHROMA_PROXY[7].val   = 0xffffff
apr.QUANT_LUMA_PROXY[8].val     = 0x80b809
apr.QUANT_CHROMA_PROXY[8].val   = 0x80b809
apr.QUANT_LUMA_PROXY[9].val     = 0x80e80d
apr.QUANT_CHROMA_PROXY[9].val   = 0x80e80d
apr.QUANT_LUMA_PROXY[10].val    = 0xfff83f
apr.QUANT_CHROMA_PROXY[10].val  = 0xfff83f
apr.QUANT_LUMA_PROXY[11].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[11].val  = 0xffffff
apr.QUANT_LUMA_PROXY[12].val    = 0x80b80b
apr.QUANT_CHROMA_PROXY[12].val  = 0x80b80b
apr.QUANT_LUMA_PROXY[13].val    = 0x80e80d
apr.QUANT_CHROMA_PROXY[13].val  = 0x80e80d
apr.QUANT_LUMA_PROXY[14].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[14].val  = 0xffffff
apr.QUANT_LUMA_PROXY[15].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[15].val  = 0xffffff
apr.QUANT_LUMA_PROXY[16].val    = 0x80d80b
apr.QUANT_CHROMA_PROXY[16].val  = 0x80d80b
apr.QUANT_LUMA_PROXY[17].val    = 0xfff80e
apr.QUANT_CHROMA_PROXY[17].val  = 0xfff80e
apr.QUANT_LUMA_PROXY[18].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[18].val  = 0xffffff
apr.QUANT_LUMA_PROXY[19].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[19].val  = 0xffffff
apr.QUANT_LUMA_PROXY[20].val    = 0x80e80d
apr.QUANT_CHROMA_PROXY[20].val  = 0x80e80d
apr.QUANT_LUMA_PROXY[21].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[21].val  = 0xffffff
apr.QUANT_LUMA_PROXY[22].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[22].val  = 0xffffff
apr.QUANT_LUMA_PROXY[23].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[23].val  = 0xffffff
apr.QUANT_LUMA_PROXY[24].val    = 0xfff80d
apr.QUANT_CHROMA_PROXY[24].val  = 0xfff80d
apr.QUANT_LUMA_PROXY[25].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[25].val  = 0xffffff
apr.QUANT_LUMA_PROXY[26].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[26].val  = 0xffffff
apr.QUANT_LUMA_PROXY[27].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[27].val  = 0xffffff
apr.QUANT_LUMA_PROXY[28].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[28].val  = 0xffffff
apr.QUANT_LUMA_PROXY[29].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[29].val  = 0xffffff
apr.QUANT_LUMA_PROXY[30].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[30].val  = 0xffffff
apr.QUANT_LUMA_PROXY[31].val    = 0xffffff
apr.QUANT_CHROMA_PROXY[31].val  = 0xffffff

apr.DC_QUANT_SCALE[0].val       = 0x401
apr.DC_QUANT_SCALE[1].val       = 0x803
apr.DC_QUANT_SCALE[2].val       = 0xc05
apr.DC_QUANT_SCALE[3].val       = 0x1007
apr.DC_QUANT_SCALE[4].val       = 0x1409
apr.DC_QUANT_SCALE[5].val       = 0x180b
apr.DC_QUANT_SCALE[6].val       = 0x1c0d
apr.DC_QUANT_SCALE[7].val       = 0x200f
apr.DC_QUANT_SCALE[8].val       = 0x2411
apr.DC_QUANT_SCALE[9].val       = 0x2813
apr.DC_QUANT_SCALE[10].val      = 0x2c15
apr.DC_QUANT_SCALE[11].val      = 0x3017
apr.DC_QUANT_SCALE[12].val      = 0x3419
apr.DC_QUANT_SCALE[13].val      = 0x381b
apr.DC_QUANT_SCALE[14].val      = 0x3c1d
apr.DC_QUANT_SCALE[15].val      = 0x401f
apr.DC_QUANT_SCALE[16].val      = 0x4421
apr.DC_QUANT_SCALE[17].val      = 0x4823
apr.DC_QUANT_SCALE[18].val      = 0x4c25
apr.DC_QUANT_SCALE[19].val      = 0x5027
apr.DC_QUANT_SCALE[20].val      = 0x5429
apr.DC_QUANT_SCALE[21].val      = 0x582b
apr.DC_QUANT_SCALE[22].val      = 0x5c2d
apr.DC_QUANT_SCALE[23].val      = 0x602f
apr.DC_QUANT_SCALE[24].val      = 0x6431
apr.DC_QUANT_SCALE[25].val      = 0x6833
apr.DC_QUANT_SCALE[26].val      = 0x6c35
apr.DC_QUANT_SCALE[27].val      = 0x7037
apr.DC_QUANT_SCALE[28].val      = 0x7439
apr.DC_QUANT_SCALE[29].val      = 0x783b
apr.DC_QUANT_SCALE[30].val      = 0x7c3d
apr.DC_QUANT_SCALE[31].val      = 0x803f
apr.DC_QUANT_SCALE[32].val      = 0x8441
apr.DC_QUANT_SCALE[33].val      = 0x8843
apr.DC_QUANT_SCALE[34].val      = 0x8c45
apr.DC_QUANT_SCALE[35].val      = 0x9047
apr.DC_QUANT_SCALE[36].val      = 0x9449
apr.DC_QUANT_SCALE[37].val      = 0x984b
apr.DC_QUANT_SCALE[38].val      = 0x9c4d
apr.DC_QUANT_SCALE[39].val      = 0xa04f
apr.DC_QUANT_SCALE[40].val      = 0xa451
apr.DC_QUANT_SCALE[41].val      = 0xa853
apr.DC_QUANT_SCALE[42].val      = 0xac55
apr.DC_QUANT_SCALE[43].val      = 0xb057
apr.DC_QUANT_SCALE[44].val      = 0xb459
apr.DC_QUANT_SCALE[45].val      = 0xb85b
apr.DC_QUANT_SCALE[46].val      = 0xbc5d
apr.DC_QUANT_SCALE[47].val      = 0xc05f
apr.DC_QUANT_SCALE[48].val      = 0xc461
apr.DC_QUANT_SCALE[49].val      = 0xc863
apr.DC_QUANT_SCALE[50].val      = 0xcc65
apr.DC_QUANT_SCALE[51].val      = 0xd067
apr.DC_QUANT_SCALE[52].val      = 0xd469
apr.DC_QUANT_SCALE[53].val      = 0xd86b
apr.DC_QUANT_SCALE[54].val      = 0xdc6d
apr.DC_QUANT_SCALE[55].val      = 0xe06f
apr.DC_QUANT_SCALE[56].val      = 0xe471
apr.DC_QUANT_SCALE[57].val      = 0xe873
apr.DC_QUANT_SCALE[58].val      = 0xec75
apr.DC_QUANT_SCALE[59].val      = 0xf077
apr.DC_QUANT_SCALE[60].val      = 0xf479
apr.DC_QUANT_SCALE[61].val      = 0xf87b
apr.DC_QUANT_SCALE[62].val      = 0xfc7d
apr.DC_QUANT_SCALE[63].val      = 0x1007f
apr.DC_QUANT_SCALE[64].val      = 0x11084
apr.DC_QUANT_SCALE[65].val      = 0x1208c
apr.DC_QUANT_SCALE[66].val      = 0x13094
apr.DC_QUANT_SCALE[67].val      = 0x1409c
apr.DC_QUANT_SCALE[68].val      = 0x150a4
apr.DC_QUANT_SCALE[69].val      = 0x160ac
apr.DC_QUANT_SCALE[70].val      = 0x170b4
apr.DC_QUANT_SCALE[71].val      = 0x180bc
apr.DC_QUANT_SCALE[72].val      = 0x190c4
apr.DC_QUANT_SCALE[73].val      = 0x1a0cc
apr.DC_QUANT_SCALE[74].val      = 0x1b0d4
apr.DC_QUANT_SCALE[75].val      = 0x1c0dc
apr.DC_QUANT_SCALE[76].val      = 0x1d0e4
apr.DC_QUANT_SCALE[77].val      = 0x1e0ec
apr.DC_QUANT_SCALE[78].val      = 0x1f0f4
apr.DC_QUANT_SCALE[79].val      = 0x200fc
apr.DC_QUANT_SCALE[80].val      = 0x21104
apr.DC_QUANT_SCALE[81].val      = 0x2210c
apr.DC_QUANT_SCALE[82].val      = 0x23114
apr.DC_QUANT_SCALE[83].val      = 0x2411c
apr.DC_QUANT_SCALE[84].val      = 0x25124
apr.DC_QUANT_SCALE[85].val      = 0x2612c
apr.DC_QUANT_SCALE[86].val      = 0x27134
apr.DC_QUANT_SCALE[87].val      = 0x2813c
apr.DC_QUANT_SCALE[88].val      = 0x29144
apr.DC_QUANT_SCALE[89].val      = 0x2a14c
apr.DC_QUANT_SCALE[90].val      = 0x2b154
apr.DC_QUANT_SCALE[91].val      = 0x2c15c
apr.DC_QUANT_SCALE[92].val      = 0x2d164
apr.DC_QUANT_SCALE[93].val      = 0x2e16c
apr.DC_QUANT_SCALE[94].val      = 0x2f174
apr.DC_QUANT_SCALE[95].val      = 0x3017c
apr.DC_QUANT_SCALE[96].val      = 0x31184
apr.DC_QUANT_SCALE[97].val      = 0x3218c
apr.DC_QUANT_SCALE[98].val      = 0x33194
apr.DC_QUANT_SCALE[99].val      = 0x3419c
apr.DC_QUANT_SCALE[100].val     = 0x351a4
apr.DC_QUANT_SCALE[101].val     = 0x361ac
apr.DC_QUANT_SCALE[102].val     = 0x371b4
apr.DC_QUANT_SCALE[103].val     = 0x381bc
apr.DC_QUANT_SCALE[104].val     = 0x391c4
apr.DC_QUANT_SCALE[105].val     = 0x3a1cc
apr.DC_QUANT_SCALE[106].val     = 0x3b1d4
apr.DC_QUANT_SCALE[107].val     = 0x3c1dc
apr.DC_QUANT_SCALE[108].val     = 0x3d1e4
apr.DC_QUANT_SCALE[109].val     = 0x3e1ec
apr.DC_QUANT_SCALE[110].val     = 0x3f1f4
apr.DC_QUANT_SCALE[111].val     = 0x1fc
print("Set matrices")

# dunno how this gets calculated
OUT_SZ = 0x1000000
out_buf_phys = u.heap.memalign(0x4000, OUT_SZ)
iface.writemem(out_buf_phys, b'\xAA' * OUT_SZ)
out_buf_iova = dart.iomap(0, out_buf_phys, OUT_SZ)
print(f"Output buffer @ phys {out_buf_phys:016X} iova {out_buf_iova:016X}")

IN_SZ_LUMA = align_up(im_W*im_H)
in_buf_luma_phys = u.heap.memalign(0x4000, IN_SZ_LUMA)
iface.writemem(in_buf_luma_phys, image_data_luma + b'\xaa' * (IN_SZ_LUMA - len(image_data_luma)))
in_buf_luma_iova = dart.iomap(0, in_buf_luma_phys, IN_SZ_LUMA)
print(f"Input buffer luma @ phys {in_buf_luma_phys:016X} iova {in_buf_luma_iova:016X}")
IN_SZ_CHROMA = align_up(im_W*2*im_H)
in_buf_chroma_phys = u.heap.memalign(0x4000, IN_SZ_CHROMA)
iface.writemem(in_buf_chroma_phys, image_data_chroma + b'\xaa' * (IN_SZ_CHROMA - len(image_data_chroma)))
in_buf_chroma_iova = dart.iomap(0, in_buf_chroma_phys, IN_SZ_CHROMA)
print(f"Input buffer chroma @ phys {in_buf_chroma_phys:016X} iova {in_buf_chroma_iova:016X}")
dart.dump_all()

desc = EncodeNotRawDescriptor(
    flags=0x373c,
    flags2=0,
    output_iova=out_buf_iova,
    max_out_sz=OUT_SZ,
    offset_x=0,
    offset_y=0,
    # this is the important set
    pix_surface_w_2_=im_W,
    pix_surface_h_2_=im_H,
    # changing this doesn't seem to break anything
    pix_surface_w=im_W,
    pix_surface_h=im_H,
    # XXX how does the div work exactly? it's different in "tiled" mode
    luma_stride=divroundup(im_W, 64),
    chroma_stride=divroundup(im_W*2, 64),
    alpha_stride=divroundup(im_W, 64),
    unk_pad_0x26_=b'\x00\x00',

    luma_iova=in_buf_luma_iova,
    pix_plane0_tileheader_thing_=0,
    chroma_iova=in_buf_chroma_iova,
    pix_plane1_tileheader_thing_=0,
    alpha_iova=in_buf_luma_iova,
    pix_plane2_tileheader_thing_=0,

    # changing this does add extra 0 bytes
    frame_header_sz=bswp16(0x94),
    unk_pad_0x5a_=b'\x00',
    bitstream_version=0,
    encoder_identifier=0xcafeface,
    # cannot change arbitrily, will break
    pix_surface_w_byteswap_=bswp16(im_W),
    pix_surface_h_byteswap_=bswp16(im_H),
    # seemingly can change arbitrarily
    chroma_format_interlace_mode=0xc0,
    aspect_ratio_frame_rate=0,
    color_primaries=2,
    transfer_characteristic=2,
    matrix_coefficients=1,
    alpha_channel_type=1,
    # tables will still be output even if bits not set here
    frame_hdr_reserved14=b'\x00\x03',
    unk_pad_0x6c_=b'\x00' * 128,
    deprecated_number_of_slices=0,
    # this one affects the encoding not just the header
    log2_desired_slice_size_in_mb=0x30,
    quantization_index=0x2,

    # this impacts the quality somehow, not quite understood
    # might be a target bitrate
    unk_0xf0_=0xffff,
    unk_0xf2_=0xffff,

    # none of this stuff is understood, and it never seems to change
    unk_0xf4_=0x8000402015100c0c,
    unk_0xfc_=0x2c8080,
    unk_0x100_0_=0x880080,
    unk_0x100_1_=0x4e00c5,
    unk_0x100_2_=0x9000d0,
    unk_0x100_3_=0x200122,
    unk_0x110_0_=0x400200,  # looks like a quant table, but ??? not used ???
    unk_0x110_1_=0x400200,
    unk_0x110_2_=0x400200,
    unk_0x110_3_=0x400200,
    unk_0x110_4_=0x400200,
    unk_0x110_5_=0x400200,
    unk_0x110_6_=0x400200,
    unk_0x110_7_=0x400200,
    unk_0x110_8_=0x400200,
    unk_0x110_9_=0x400200,
    unk_0x110_10_=0x400200,
    unk_0x110_11_=0x400200,
    unk_0x110_12_=0x400200,
    unk_0x110_13_=0x400200,
    unk_0x110_14_=0x400200,
    unk_0x110_15_=0x400200,

    quant_table_sel=0x23,
    unk_pad_0x154_=b'\x00' * 44,
)
desc_bytes = struct.pack(ENCODE_NOT_RAW_STRUCT, *desc)
chexdump(desc_bytes)

iface.writemem(desc_ring_phys, desc_bytes)

# let's go
apr.DR_HEAD = len(desc_bytes)

start_time = time.time()
while apr.IRQ_STATUS.val == 0:
    if time.time() - start_time > 5:
        print("TIMED OUT!!!")
        break

print(f"Done, IRQ status is {apr.IRQ_STATUS}")
print(f"ST0 = {apr.ST0}")
print(f"ST1 = {apr.ST1}")
print(f"REG_0x1c = {apr.REG_0x1c}")
print(f"REG_0x3c = {apr.REG_0x3c}")
print(f"REG_0x44 = {apr.REG_0x44}")

print(f"DR_HEAD = {apr.DR_HEAD}")
print(f"DR_TAIL = {apr.DR_TAIL}")

print(f"unk REG_0x38 = {apr.REG_0x38}")
print(f"unk REG_0x40 = {apr.REG_0x40}")
print(f"unk REG_0x48 = {apr.REG_0x48}")
print(f"unk REG_0x50 = {apr.REG_0x50}")
print(f"unk REG_0x54 = {apr.REG_0x54}")

apr.IRQ_STATUS = apr.IRQ_STATUS.val

dr_memory_new = iface.readmem(desc_ring_phys, DESC_RING_SZ)
chexdump(dr_memory_new)

out_buf_new = iface.readmem(out_buf_phys, OUT_SZ)
with open('prores.bin', 'wb') as f:
    f.write(out_buf_new)

outlen = struct.unpack(">I", out_buf_new[:4])[0]
if outlen <= len(out_buf_new):
    with open('prores.mov', 'wb') as f:
        f.write(b'\x00\x00\x00\x14\x66\x74\x79\x70\x71\x74\x20\x20\x00\x00\x02\x00\x71\x74\x20\x20\x00\x00\x00\x08\x77\x69\x64\x65')
        f.write(struct.pack(">I", outlen + 8))
        f.write(b'mdat')
        f.write(out_buf_new[:outlen])
        f.write(b'\x00\x00\x03\x1e\x6d\x6f\x6f\x76\x00\x00\x00\x6c\x6d\x76\x68\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xe8\x00\x00\x00\x11\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x02\x89\x74\x72\x61\x6b\x00\x00\x00\x5c\x74\x6b\x68\x64\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x11\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x07\x80\x00\x00\x04\x38\x00\x00\x00\x00\x00\x24\x65\x64\x74\x73\x00\x00\x00\x1c\x65\x6c\x73\x74\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x11\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x02\x01\x6d\x64\x69\x61\x00\x00\x00\x20\x6d\x64\x68\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x3c\x00\x00\x00\x01\x00\x7f\xff\x00\x00\x00\x00\x00\x2d\x68\x64\x6c\x72\x00\x00\x00\x00\x6d\x68\x6c\x72\x76\x69\x64\x65\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0c\x56\x69\x64\x65\x6f\x48\x61\x6e\x64\x6c\x65\x72\x00\x00\x01\xac\x6d\x69\x6e\x66\x00\x00\x00\x14\x76\x6d\x68\x64\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x2c\x68\x64\x6c\x72\x00\x00\x00\x00\x64\x68\x6c\x72\x75\x72\x6c\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0b\x44\x61\x74\x61\x48\x61\x6e\x64\x6c\x65\x72\x00\x00\x00\x24\x64\x69\x6e\x66\x00\x00\x00\x1c\x64\x72\x65\x66\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x0c\x75\x72\x6c\x20\x00\x00\x00\x01\x00\x00\x01\x40\x73\x74\x62\x6c\x00\x00\x00\xdc\x73\x74\x73\x64\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xcc\x61\x70\x63\x6e\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x46\x46\x4d\x50\x00\x00\x02\x00\x00\x00\x02\x00\x07\x80\x04\x38\x00\x48\x00\x00\x00\x48\x00\x00\x00\x00\x00\x00\x00\x01\x1f\x4c\x61\x76\x63\x35\x39\x2e\x32\x35\x2e\x31\x30\x30\x20\x70\x72\x6f\x72\x65\x73\x5f\x76\x69\x64\x65\x6f\x74\x6f\x6f\x6c\x62\x00\x18\xff\xff\x00\x00\x00\x6c\x67\x6c\x62\x6c\x00\x00\x00\x64\x61\x70\x63\x6e\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xff\x07\x80\x04\x38\x00\x48\x00\x00\x00\x48\x00\x00\x00\x00\x00\x00\x00\x01\x10\x41\x70\x70\x6c\x65\x20\x50\x72\x6f\x52\x65\x73\x20\x34\x32\x32\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18\xff\xff\x00\x00\x00\x0a\x66\x69\x65\x6c\x01\x00\x00\x00\x00\x00\x00\x00\x00\x0a\x66\x69\x65\x6c\x01\x00\x00\x00\x00\x18\x73\x74\x74\x73\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x1c\x73\x74\x73\x63\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x14\x73\x74\x73\x7a\x00\x00\x00\x00')
        f.write(struct.pack(">I", outlen))
        f.write(b'\x00\x00\x00\x01\x00\x00\x00\x14\x73\x74\x63\x6f\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x24\x00\x00\x00\x21\x75\x64\x74\x61\x00\x00\x00\x19\xa9\x73\x77\x72\x00\x0d\x55\xc4\x4c\x61\x76\x66\x35\x39\x2e\x32\x30\x2e\x31\x30\x31')
# ffmpeg -i prores.mov prores-dec%d.png
