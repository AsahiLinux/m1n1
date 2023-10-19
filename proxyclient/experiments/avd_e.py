#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, argparse, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.append("/home/eileen/asahi/avd")  # git clone https://github.com/eiln/avd.git
# Decode via firmware-emulated AVD instruction stream

from m1n1.setup import *
from m1n1.utils import *
from m1n1.fw.avd import *

from avd_emu import AVDEmulator
from tools.common import ffprobe

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', type=str, required=True, help="input bitstream")
    parser.add_argument('-d', '--dir', type=str, required=True, help="path to trace dir")
    parser.add_argument('-f', '--firmware', type=str, default="data/fw.bin", help="path to fw")
    parser.add_argument('-n', '--num', type=int, default=1, help="count")
    parser.add_argument('-a', '--all', action='store_true', help="run all")
    parser.add_argument('-x', '--stfu', action='store_true')
    parser.add_argument('-p', '--poll', action='store_true', help="poll iommu space")
    parser.add_argument('--save-raw', action='store_true', help="save raw yuv")
    args = parser.parse_args()
    mode = ffprobe(args.input)

    emu = AVDEmulator(args.firmware, stfu=True)
    emu.start()
    paths = os.listdir(os.path.join(args.dir))
    paths = sorted([os.path.join(args.dir, path) for path in paths if "frame" in path])
    assert(len(paths))
    num = len(paths) if args.all else args.num
    num = min(len(paths), num)

    if   (mode == "h264"):
        from avid.h264.decoder import AVDH264Decoder
        dec = AVDH264Decoder()
    elif (mode == "h265"):
        from avid.h265.decoder import AVDH265Decoder
        dec = AVDH265Decoder()
    elif (mode == "vp09"):
        from avid.vp9.decoder import AVDVP9Decoder
        dec = AVDVP9Decoder()
    else:
        raise RuntimeError("unsupported codec")
    if (args.stfu):
        dec.stfu = True
        dec.hal.stfu = True
    units = dec.setup(args.input)

    avd = AVDDevice(u)
    if   (mode == "h264"):
        avd.decoder = AVDH264Dec(avd)
    elif (mode == "h265"):
        avd.decoder = AVDH265Dec(avd)
    elif (mode == "vp09"):
        avd.decoder = AVDVP9Dec(avd)
    else:
        raise RuntimeError("unsupported codec")
    avd.decoder.winname = args.input
    if (args.stfu):
        avd.stfu = True
    avd.boot()
    avd.ioalloc_at(0x0, 0xf000000, stream=0)
    if (args.poll):
        avd.iomon.add(0x0, 0xf000000)

    for i,unit in enumerate(units[:num]):
        print(unit)
        inst = dec.decode(unit)
        path = paths[i]
        print(path)
        inst = emu.avd_cm3_cmd_decode(path)
        avd.decoder.decode(dec.ctx, unit, inst)
        if (args.save_raw):
            y_data = avd.ioread(dec.ctx.y_addr, dec.ctx.luma_size, stream=0)
            uv_data = avd.ioread(dec.ctx.uv_addr, dec.ctx.chroma_size, stream=0)
            open("data/raw-emu/%03d.bin" % (i), "wb").write(y_data + uv_data)
