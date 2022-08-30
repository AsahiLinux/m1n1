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
from m1n1.fw.dcp.dcpav import *
from m1n1.proxyutils import RegMonitor

dart = DART.from_adt(u, "arm-io/dart-dcpext0")
disp_dart = DART.from_adt(u, "arm-io/dart-dispext0")
#disp_dart.dump_all()

dcp_addr = u.adt["arm-io/dcpext0"].get_reg(0)[0]
dcp = DCPIBootClient(u, dcp_addr, dart, disp_dart)
dcp.dva_offset = getattr(u.adt["/arm-io/dcpext0"][0], "asc_dram_mask", 0)

dcp.start()
dcp.start_ep(0x20)
dcp.start_ep(0x23)
dcp.start_ep(0x24)
dcp.start_ep(0x27)
dcp.start_ep(0x2a)

dcp.system.wait_for("system")
dcp.iboot.wait_for("disp0")
dcp.dptx.wait_for("dcpav0")
dcp.dptx.wait_for("dcpav1")
dcp.dptx.wait_for("dcpdp0")
dcp.dptx.wait_for("dcpdp1")
dcp.dpport.wait_for("port0")
dcp.dpport.wait_for("port1")

dcp.system.wait_for("system")
dcp.system.system.setProperty("gAFKConfigLogMask", 0xffff)

print("Connect...")
dcp.dpport.port0.open()
dcp.dpport.port0.getLocation()
dcp.dpport.port0.getLocation()
dcp.dpport.port0.getUnit()
# this triggers the power up message
dcp.dpport.port0.displayRequest()
# these seem to not work/do anything?
dcp.dpport.port0.connectTo(True, ATC0, DPPHY, 0)

#dcp.dcpav.controller.setPower(False)
#dcp.dcpav.controller.forceHotPlugDetect()
#dcp.dcpav.controller.setVirtualDeviceMode(0)
#dcp.dcpav.controller.setPower(True)
#dcp.dcpav.controller.wakeDisplay()
#dcp.dcpav.controller.sleepDisplay()
#dcp.dcpav.controller.wakeDisplay()

print("Waiting for HPD...")
while True:
    hpd, ntim, ncolor = dcp.iboot.disp0.getModeCount()
    if hpd:
        break

print("HPD asserted")

print(f"Connected:{hpd} Timing modes:{ntim} Color modes:{ncolor}")
dcp.iboot.disp0.setPower(True)

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

run_shell(globals(), msg="Have fun!")

# full shutdown!
dcp.stop(1)
p.pmgr_reset(0, "DISP0_CPU0")
