#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from construct import *

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1 import asm
from m1n1.hw.dart import DART, DARTRegs
from m1n1.fw.dcp.iboot import DCPIBootClient, SurfaceFormat, EOTF, Transform, AddrFormat
from m1n1.proxyutils import RegMonitor

print(f"Framebuffer at {u.ba.video.base:#x}")

dart = DART.from_adt(u, "arm-io/dart-dcp")
disp_dart = DART.from_adt(u, "arm-io/dart-disp0")
disp_dart.dump_all()

dcp_addr = u.adt["arm-io/dcp"].get_reg(0)[0]
dcp = DCPIBootClient(u, dcp_addr, dart, disp_dart)

dcp.start()
dcp.start_ep(0x23)

dcp.iboot.disp0.wait()
dcp.iboot.disp0.setPower(True)

hpd, ntim, ncolor = dcp.iboot.disp0.getModeCount()

print(f"Connected:{hpd} Timing modes:{ntim} Color modes:{ncolor}")

timing_modes = dcp.iboot.disp0.getTimingModes()
print("Timing modes:")
print(timing_modes)

color_modes = dcp.iboot.disp0.getColorModes()
print("Color modes:")
print(color_modes)

timing_modes.sort(key=lambda c: (c.valid, c.width <= 1920, c.fps_int <= 60, c.width, c.height, c.fps_int, c.fps_frac))
timing_mode = timing_modes[-1]

color_modes.sort(key=lambda c: (c.valid, c.bpp <= 32, c.bpp, -int(c.colorimetry), -int(c.encoding), -int(c.eotf)))
color_mode = color_modes[-1]

print("Chosen timing mode:", timing_mode)
print("Chosen color mode:", color_mode)

dcp.iboot.disp0.setMode(timing_mode, color_mode)

w, h = timing_mode.width, timing_mode.height

layer = Container(
    planes = [
        Container(
            addr = 0x013ec000,
            stride = u.ba.video.stride,
            addr_format = AddrFormat.PLANAR,
        ),
        Container(),
        Container()
    ],
    plane_cnt = 1,
    width = u.ba.video.width,
    height = u.ba.video.height,
    surface_fmt = SurfaceFormat.w30r,
    colorspace = 2,
    eotf = EOTF.GAMMA_SDR,
    transform = Transform.NONE,
)

mw = min(w, u.ba.video.width)
mh = min(h, u.ba.video.height)

swap = dcp.iboot.disp0.swapBegin()
print(swap)
dcp.iboot.disp0.swapSetLayer(0, layer, (mw, mh, 0, 0), (mw, mh, 0, 0))
dcp.iboot.disp0.swapEnd()
#dcp.iboot.disp0.swapWait(swap.swap_id)


dcp.stop()

run_shell(globals(), msg="Have fun!")
