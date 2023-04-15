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

def make_fb():
    width = 2040
    fb_size = align_up(width * stride * 4, 8 * 0x4000)
    buf = u.memalign(0x4000, fb_size)
    return (dart.iomap(0, buf, fb_size), buf)


width = 2040
fb_size = align_up(width * stride * 4, 8 * 0x4000)
buf_mask = u.memalign(0x4000, fb_size)
p.memset32(buf_mask, 0, fb_size)
p.memset32(buf_mask, 0xFFFFFFFF, 10*stride)
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

def make_pipe(iova):
    pipe = [
        0x20014038,
        0x2a | (stride * 4),
        0x20014030,
        0x2a | iova,
    ]
    pipe = [0xc0000001 | (len(pipe) << 16)] + pipe
    return pipe

def flush(pipe):
 for i in pipe:
  p.write32(0x2282010c0, i)

def play(f):
    frame = 0
    iova, base = make_fb()
    while True:
        data = f.read(80 * 64 * 4)
        if not data:
            break
        for i in range(25):
            iface.writemem(base + i * 80 * 64 * 4, data)
        flush(make_pipe(iova))
        time.sleep(0.033)
        frame += 1

with open('out.bin', 'rb') as f:
    play(f)
