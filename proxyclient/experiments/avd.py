#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, argparse
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.append("/home/eileen/asahi/avd")  # git clone https://github.com/eiln/avd.git
# Decode with our own generated instruction stream

from m1n1.setup import *
from m1n1.utils import *
from m1n1.fw.avd import *
from tools.common import ffprobe

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #
    # Usage:
    #     ffmpeg -i input.mp4 -c:v copy (or reencode libx264) input.264
    #     python3 experiments/avd.py -i input.264 -a
    #
    # - Supports .264, .265, and .ivf formats.
    # - Regarding the codec, it's whatever codec features are supported.
    #   Check avid for details.
    # - Also ensure to change the sys.path.append above to the avid repo
    #   as it does not install system-wide.
    #
    parser.add_argument('-i', '--input', type=str, required=True, help="path to input bitstream")
    parser.add_argument('-n', '--num', type=int, default=1, help="frame count")
    parser.add_argument('-a', '--all', action='store_true', help="run all frames")
    parser.add_argument('-x', '--stfu', action='store_true')
    parser.add_argument('-p', '--poll', action='store_true', help="poll iommu space")
    parser.add_argument('--save-raw', type=str, default="", help="file name to save raw yuv")
    parser.add_argument('--save-images', type=str, default="", help="dirname to save images")
    args = parser.parse_args()
    mode = ffprobe(args.input)

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
    nal_stop = 0 if args.all else 1
    units = dec.setup(args.input, nal_stop=nal_stop, num=args.num)

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

    rawvideo = b''
    num = len(units) if args.all else min(args.num, len(units))
    for i,unit in enumerate(units[:num]):
        print(unit)
        inst = dec.decode(unit)
        if (i == 0):
            avd.ioalloc_at(0x0, dec.allocator_top(), stream=0, val=0)
            if (args.poll):
                avd.iomon.add(0x0, dec.allocator_top())
        frame = avd.decoder.decode(dec.ctx, unit, inst)
        if (frame != None):
            if (args.save_raw):
                rawvideo += frame.y_data + frame.uv_data
            if (args.save_images):
                os.makedirs(f"data/out/{args.save_images}", exist_ok=True)
                path = os.path.join(f"data/out/{args.save_images}", "out%03d.png" % (avd.decoder.count))
                cv2.imwrite(path, frame.img)
    if (args.save_raw):
        path = os.path.join(f"data/out/{args.save_raw}")
        open(path, "wb").write(rawvideo)
