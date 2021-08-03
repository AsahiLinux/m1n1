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
from m1n1.fw.dcp.client import DCPClient
from m1n1.fw.dcp.manager import DCPManager
from m1n1.fw.dcp.ipc import ByRef
from m1n1.proxyutils import RegMonitor

mon = RegMonitor(u)

#mon.add(0x230000000, 0x18000)
#mon.add(0x230018000, 0x4000)
#mon.add(0x230068000, 0x8000)
#mon.add(0x2300b0000, 0x8000)
#mon.add(0x2300f0000, 0x4000)
#mon.add(0x230100000, 0x10000)
#mon.add(0x230170000, 0x10000)
#mon.add(0x230180000, 0x1c000)
#mon.add(0x2301a0000, 0x10000)
#mon.add(0x2301d0000, 0x4000)
#mon.add(0x230230000, 0x10000)
#mon.add(0x23038c000, 0x10000)
#mon.add(0x230800000, 0x10000)
#mon.add(0x230840000, 0xc000)
#mon.add(0x230850000, 0x2000)
##mon.add(0x230852000, 0x5000) # big curve / gamma table
#mon.add(0x230858000, 0x18000)
#mon.add(0x230870000, 0x4000)
#mon.add(0x230880000, 0x8000)
#mon.add(0x230894000, 0x4000)
#mon.add(0x2308a8000, 0x8000)
#mon.add(0x2308b0000, 0x8000)
#mon.add(0x2308f0000, 0x4000)
##mon.add(0x2308fc000, 0x4000) # stats / RGB color histogram
#mon.add(0x230900000, 0x10000)
#mon.add(0x230970000, 0x10000)
#mon.add(0x230980000, 0x10000)
#mon.add(0x2309a0000, 0x10000)
#mon.add(0x2309d0000, 0x4000)
#mon.add(0x230a30000, 0x20000)
#mon.add(0x230b8c000, 0x10000)
#mon.add(0x231100000, 0x8000)
#mon.add(0x231180000, 0x4000)
#mon.add(0x2311bc000, 0x10000)
#mon.add(0x231300000, 0x8000)
##mon.add(0x23130c000, 0x4000) # - DCP dart
#mon.add(0x231310000, 0x8000)
#mon.add(0x231340000, 0x8000)
##mon.add(0x231800000, 0x8000) # breaks DCP
##mon.add(0x231840000, 0x8000) # breaks DCP
##mon.add(0x231850000, 0x8000) # something DCP?
##mon.add(0x231920000, 0x8000) # breaks DCP
##mon.add(0x231960000, 0x8000) # breaks DCP
##mon.add(0x231970000, 0x10000) # breaks DCP
##mon.add(0x231c00000, 0x10000) # DCP mailbox

mon.add(0x230845840, 0x40) # error regs

mon.poll()

dart_addr = u.adt["arm-io/dart-dcp"].get_reg(0)[0]
dart = DART(iface, DARTRegs(u, dart_addr), u)

disp_dart_addr = u.adt["arm-io/dart-disp0"].get_reg(0)[0]
disp_dart = DART(iface, DARTRegs(u, disp_dart_addr), u)

disp_dart.dump_all()

dcp_addr = u.adt["arm-io/dcp"].get_reg(0)[0]
dcp = DCPClient(u, dcp_addr, dart)

dcp.start()
dcp.start_ep(0x37)
dcp.dcpep.initialize()

mgr = DCPManager(dcp.dcpep)

mon.poll()

mgr.start_signal()

mon.poll()

mgr.get_color_remap_mode(6)
mgr.enable_disable_video_power_savings(0)

mgr.update_notify_clients_dcp([0,0,0,0,0,0,1,1,1,0,1,1,1])
mgr.first_client_open()
print(f"keep on: {mgr.isKeepOnScreen()}")
print(f"main display: {mgr.is_main_display()}")
assert mgr.setPowerState(1, False, ByRef(0)) == 0

mon.poll()

assert mgr.set_display_device(2) == 0
assert mgr.set_parameter_dcp(14, [0], 1) == 0
#mgr.set_digital_out_mode(86, 38)

assert mgr.set_display_device(2) == 0
assert mgr.set_parameter_dcp(14, [0], 1) == 0
#mgr.set_digital_out_mode(89, 38)

t = ByRef(b"\x00" * 0xc0c)
assert mgr.get_gamma_table(t) == 2
assert mgr.set_contrast(0) == 0
assert mgr.setBrightnessCorrection(65536) == 0

assert mgr.set_display_device(2) == 0
assert mgr.set_parameter_dcp(14, [0], 1) == 0
#mgr.set_digital_out_mode(89, 72)

mon.poll()

# arg: IOUserClient
swapid = ByRef(0)
ret = mgr.swap_start(swapid, {
    "addr": 0xFFFFFE1667BA4A00,
    "unk": 0,
    "flag1": 0,
    "flag2": 1
})
assert ret == 0
print(f"swap ID: {swapid.val:#x}")

mgr.set_matrix(9, [[1<<32, 0, 0],
                   [0, 1<<32, 0],
                   [0, 0, 1<<32]])
mgr.setBrightnessCorrection(65536)
mgr.set_parameter_dcp(3, [65536], 1)
mgr.set_parameter_dcp(6, [65536], 1)

surface_id = 3

swap_rec = Container(
    flags1 = 0x861202,
    flags2 = 0x04,
    swap_id = swapid.val,
    surf_ids = [surface_id, 0, 0, 0],
    src_rect = [[0, 0, 1920, 1080],[0,0,0,0],[0,0,0,0],[0,0,0,0]],
    surf_flags = [1, 0, 0, 0],
    surf_unk = [0, 0, 0, 0],
    dst_rect = [[0, 0, 1920, 1080],[0,0,0,0],[0,0,0,0],[0,0,0,0]],
    swap_enabled = 0x80000007,
    swap_completed = 0x80000007,
)

surf = Container(
    is_tiled = False,
    unk_1 = False,
    unk_2 = False,
    plane_cnt = 0,
    plane_cnt2 = 0,
    format = "BGRA",
    unk_13 = 13,
    unk_14 = 1,
    stride = 1920 * 4,
    pix_size = 4,
    pel_w = 1,
    pel_h = 1,
    offset = 0,
    width = 1920,
    height = 1080,
    buf_size = 1920 * 1080 * 4,
    surface_id = surface_id,
    has_comp = True,
    has_planes = True,
    has_compr_info = False,
    unk_1f5 = 0,
    unk_1f9 = 0,
)

iova = 0x7e0000

surfaces = [surf, None, None, None]
surfAddr = [iova, 0, 0, 0]

outB = ByRef(False)

swaps = mgr.swaps

mon.poll()

buf = u.memalign(0x4000, 16<<20)

#iface.writemem(buf, open("fb0.bin", "rb").read())

p.memset8(buf, 0, 16<<20)
p.memset8(buf, 0xff, 65536)

iface.writemem(buf, open("cur1.bin", "rb").read())

disp_dart.iomap_at(0, iova, buf, 16<<20)

disp_dart.regs.dump_regs()

ret = mgr.swap_submit_dcp(swap_rec=swap_rec, surfaces=surfaces, surfAddr=surfAddr,
                          unkBool=False, unkFloat=0.0, unkInt=0, unkOutBool=outB)
print(f"swap returned {ret} / {outB}")

time.sleep(0.2)

mon.poll()
dcp.work()
mon.poll()
dcp.work()
mon.poll()

disp_dart.regs.dump_regs()

#while swaps == mgr.swaps:
    #dcp.work()
    
print("swap complete!")

run_shell(globals(), msg="Have fun!")
