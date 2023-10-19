# SPDX-License-Identifier: MIT
from m1n1.trace import Tracer
from m1n1.trace.dart import DARTTracer
from m1n1.utils import *
from m1n1.proxyutils import RegMonitor
hv.p.hv_set_time_stealing(0, 1)

# Usage
#
# 2023/12/25: Only tested on J293AP (AVD revision "Viola"/V3).
#             Should work on all baseline M1s.
#
# 1. Start tracer under the hypervisor
#
# 2. Send over the bitstream(s) to the target machine
#    Supported formats: .264, .265, .ivf (unless you want to add a demuxer to avid/codecs)
#
# 3. The tracer is purposely not activated at boot. As of 13.5, it takes ~2 HEVC runs
#    to get to the login screen - it's probably decoding the login screen. By "activate",
#    I mean the tracer variable "outdir" is NULLed s.t. the tracer will not save the
#    traced data and merely log the IPC transactions.
#
#       [cpu0] [AVDTracer@/arm-io/avd] sent fw command at 0x108eb30
#       00000000  00000801 00030007 0050c000 000002a8 00000003 01091a70 01091a78 00000001
#       00000020  0050caa4 01091af0 01091bc0 01091c50 0050c2a4 0050c210 0050c28c 00000000
#       00000040  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
#       [cpu0] [0xfffffe00149d9984] MMIO: W.4   0x269098054 (avd[0], offset 0x1098054) = 0x108eb30
#       [cpu7] [0xfffffe00149d99b0] MMIO: R.4   0x269098048 (avd[0], offset 0x1098048) = 0x9
#
# 4. To save the trace contents, break into the hypervisor console and set
#
#       >>> tracer.outdir = "matrix_1080X512"
#
#    The output data dir will become 'data/[inferred codec name]/$outdir'.
#    The data dir will be created if it does not exist. The directory structure is
#    meant to look like this:
#
#    proxyclient/
#       data/
#          h264/*
#          h265/*
#          vp9/*
#
# 5. After the directory name is configured, trigger avd from the target machine:
#
#       ffmpeg -hwaccel videotoolbox -i matrix_1080X512.ivf
#
#    Or you can access VT directly yourself with some Obj-C (but why would you want to do that..)
#    Though I may need to do that to test some sekrit undocumented features.
#    The input bitstream is hopefully the matching one as the directory name just set.
#
# 6. If all goes well (i.e. the bitstream is decoding on AVD), the tracer will save:
#
#       >> ~/m1n1/proxyclient $ ls data/*
#       data/vp9/matrix_1080X512:
#       frame.2023-12-17T21:17:47.519048.00004000.bin  probs.2023-12-17T21:17:47.519048.00004000.00004000.bin
#       frame.2023-12-17T21:17:47.578537.000bc000.bin  probs.2023-12-17T21:17:47.578537.000bc000.0000c000.bin
#       frame.2023-12-17T21:17:47.633768.00174000.bin  probs.2023-12-17T21:17:47.633768.00174000.00014000.bin
#       frame.2023-12-17T21:17:47.688067.0022c000.bin  probs.2023-12-17T21:17:47.688067.0022c000.0001c000.bin
#
#   The "frame" is the macOS source frame_params struct, and this directory is the
#   one intended to be supplied to all the avid tools (e.g. emulator, differs).
#   For VP9 (and presumably AV1) the tracer will additionally save the "probs" blob.
#   You can also bypass FairPlay encryption and save the coded bitstream, but that's
#   an exercise left for the reader.
#
# 7. Copy the data directory over to `avd/data/*` & have fun :D
#
#    python3 avd_emu.py -i frame.2023-12-17T21:17:47.519048.00004000.bin  # emulate single fp
#    python3 avd_emu.py -d vp9/matrix_1080X512 -a  # emulate all using trace dir name
#    python3 tools/test.py -m vp9 -d vp9/matrix_1080X512 -e -a  # test against emulated output
#
#    Optionally save the firmware to run on the emulator via
#       >>> tracer.save_firmware("data/fw.bin")

import datetime
import os
import struct
import time

class AVDTracer(Tracer):
    DEFAULT_MODE = TraceMode.SYNC

    def __init__(self, hv, dev_path, dart_tracer, verbose=False):
        super().__init__(hv, verbose=verbose, ident=type(self).__name__ + "@" + dev_path)
        self.dev = hv.adt[dev_path]
        self.dart_tracer = dart_tracer
        self.base = self.dev.get_reg(0)[0] # 0x268000000
        self.p = hv.p
        self.u = hv.u
        self.dart = dart_tracer.dart

        mon = RegMonitor(hv.u)
        AVD_REGS = [
            #(0x1000000, 0x4000, "unk0"),
            #(0x1010000, 0x4000, "dart"),
            #(0x1002000, 0x1000, "unk2"),
            (0x1070000, 0x4000, "piodma"),
            (0x1088000, 0x4000, "sram"),
            (0x108c000, 0xc000, "cmd"),
            #(0x1098000, 0x4000, "mbox"),
            #(0x10a3000, 0x1000, "unka"),
            (0x1100000, 0xc000, "config"),
            (0x110c000, 0x4000, "dma"),
            #(0x1400000, 0x4000, "wrap"),
        ]
        #for (offset, size, name) in AVD_REGS: mon.add(self.base + offset, size, name=name)
        self.mon = mon

        iomon = RegMonitor(hv.u, ascii=True)
        iomon1 = RegMonitor(hv.u, ascii=True)
        def readmem_iova(addr, size, readfn=None):
            try:
                return dart_tracer.dart.ioread(0, addr, size)
            except Exception as e:
                print(e)
                return None
        iomon.readmem = readmem_iova
        def readmem_iova(addr, size, readfn=None):
            try:
                return dart_tracer.dart.ioread(1, addr, size)
            except Exception as e:
                print(e)
                return None
        iomon1.readmem = readmem_iova
        self.iomon = iomon
        self.iomon1 = iomon1
        self.state_active = False
        self.outdir = ""

    def avd_r32(self, off): return self.p.read32(self.base + off)
    def avd_w32(self, off, x): return self.p.write32(self.base + off, x)
    def avd_r64(self, off): return self.p.read64(self.base + off)
    def avd_w64(self, off, x): return self.p.write64(self.base + off, x)

    def start(self):
        self.hv.trace_range(irange(self.dev.get_reg(0)[0], self.dev.get_reg(0)[1]), mode=TraceMode.SYNC)
        self.hv.trace_range(irange(self.base + 0x1080000, 0x18000), False)
        self.hv.add_tracer(irange(self.base + 0x1098054, 4), "avd-mbox-54", TraceMode.SYNC, self.evt_rw_hook, self.w_AVD_MBOX_0054)
        self.hv.add_tracer(irange(self.base + 0x1098064, 4), "avd-mbox-64", TraceMode.SYNC, self.r_AVD_MBOX_0064, self.evt_rw_hook)

    def poll(self):
        self.mon.poll()
        self.iomon.poll()
        self.iomon1.poll()

    def evt_rw_hook(self, x):
        self.poll()

    def w_AVD_MBOX_0054(self, x):
        if ((x.data >= 0x1080000) and (x.data <= 0x10a0000)):
            self.log("Sent fw command at 0x%x" % (x.data))
            self.poll()
            cmd = self.read_regs(self.base + x.data, 0x60)
            chexdump32(cmd)

            opcode = struct.unpack("<I", cmd[:4])[0] & 0xf
            if (opcode == 0):
                self.log("Command start")
                self.state_active = True
                self.access_idx = 0

            elif (opcode == 1):
                frame_params_iova = self.p.read32(self.base + x.data + 0x8)
                if (self.outdir) and (frame_params_iova != 0x0):
                    t = datetime.datetime.now().isoformat()
                    frame_params = self.dart.ioread(1, frame_params_iova, 0xb0000)

                    word = self.p.read32(self.base + x.data)
                    if   (word & 0x000) == 0x000: # h265
                        name = "h265"
                    elif (word & 0x400) == 0x400: # h264
                        name = "h264"
                    elif (word & 0x800) == 0x800: # vp9
                        name = "vp9"
                    else:
                        name = "unk"
                    outdir = os.path.join("data", name, self.outdir)
                    os.makedirs(outdir, exist_ok=True)
                    open(os.path.join(outdir, f'frame.{t}.{frame_params_iova:08x}.bin'), "wb").write(frame_params)

                    if (word & 0x800) == 0x800: # save probs for vp9
                        iova = [0x4000, 0xc000, 0x14000, 0x1c000][self.access_idx % 4]
                        open(os.path.join(outdir, f'probs.{t}.{frame_params_iova:08x}.{iova:08x}.bin'), "wb").write(self.dart.ioread(0, iova, 0x4000))
                self.access_idx += 1

            elif (opcode == 2):
                self.log("Command end")
                self.state_active = False
                self.access_idx = 0

    def r_AVD_MBOX_0064(self, x):
        if ((x.data >= 0x1080000) and (x.data <= 0x10a0000)):
            self.log("Received fw command at 0x%x" % (x.data))
            cmd = self.read_regs(self.base + x.data, 0x60)
            chexdump32(cmd)
            self.poll()

    def read_regs(self, addr, size):
        scratch = self.u.malloc(size)
        p.memcpy32(scratch, addr, size)
        return self.p.iface.readmem(scratch, size)

    def read_iova(self, start, end, stream=0):
            data = b''
            for i in range((end - start) // 0x4000):
                try:
                    d = self.dart_tracer.dart.ioread(stream, start + (i * 0x4000), 0x4000)
                except:
                    d = b'\0' * 0x4000
                data += d
            return data

    def save_firmware(self, path="fw.bin"):
        firmware = self.read_regs(self.base + 0x1080000, 0x10000)
        open(path, "wb").write(firmware)

p.pmgr_adt_clocks_enable('/arm-io/dart-avd')
p.pmgr_adt_clocks_enable('/arm-io/avd')
dart_tracer = DARTTracer(hv, "/arm-io/dart-avd", verbose=0)
dart_tracer.start()
dart = dart_tracer.dart
tracer = AVDTracer(hv, '/arm-io/avd', dart_tracer, verbose=3)
tracer.start()
