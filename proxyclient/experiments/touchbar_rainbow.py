#!/usr/bin/env python3

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.dart import DART
from m1n1.utils import *

dart = DART.from_adt(u, "arm-io/dart-dispdfr")

width = 2040
height = 60
stride = 64

fb_size = align_up(width * stride * 4, 8 * 0x4000)
buf = u.memalign(0x4000, fb_size)

colors = [0xDD0000, 0xFE6230, 0xFEF600, 0x00BB00, 0x009BFE, 0x000083, 0x30009B]
for i, color in enumerate(colors):
    lines = width // len(colors)
    offset = i * lines * stride * 4
    for j in range(lines):
        p.memset32(buf + offset + j * stride * 4, color, height * 2)
        p.memset32(buf + offset + j * stride * 4 + height * 2, 0xffffffff^color, height * 2)



iova = dart.iomap(0, buf, fb_size)
buf_mask = u.memalign(0x4000, fb_size)
p.memset32(buf_mask, 0xFFFFFFFF, fb_size)
iova_mask = dart.iomap(0, buf_mask, fb_size)
p.write32(0x228202200, iova_mask)

dart.dump_device(0)

#enable backlight
p.write32(0x228600070,0x8051)
p.write32(0x22860006c,0x229)

#enable fifo and vblank
p.write32(0x228400100, 0x613)

# Color correction magic (idk why but it makes colors actually work)
p.write32(0x228202074, 0x1)
p.write32(0x228202028, 0x10)
p.write32(0x22820202c, 0x1)
p.write32(0x228202020, 0x1)
p.write32(0x228202034, 0x1)


#layer enable
p.write32(0x228204020, 0x1)
p.write32(0x228204068, 0x1)
p.write32(0x2282040b4, 0x1)
p.write32(0x2282040f4, 0x1)
p.write32(0x2282040ac, 0x100000)
p.write32(0x228201038, 0x10001)

#layer size
p.write32(0x228204048, height << 16 | width)
p.write32(0x22820404c, height << 16 | width)
p.write32(0x22820407c, height << 16 | width)
p.write32(0x228204054, height << 16 | width)

#global size
p.write32(0x228201030, height << 16 | width)

#some more color correction
p.write32(0x22820402c, 0x53e4001)


pipe = [
    0x20014038,
    0x2a | (stride * 4),
    0x20014030,
    0x2a | iova,
]

pipe = [0xc0000001 | (len(pipe) << 16)] + pipe

def flush(pipe):
 for i in pipe:
  p.write32(0x2282010c0, i)

flush(pipe)
