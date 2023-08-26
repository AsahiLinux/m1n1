#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from construct import *

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1 import asm
from m1n1.hw.dart import DART
from m1n1.fw.dcp.iboot import DCPIBootClient, SurfaceFormat, EOTF, Transform, AddrFormat, Colorspace
from m1n1.proxyutils import RegMonitor

from m1n1.fw.smc import SMCClient, SMCError

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr)
smc.start()
smc.start_ep(0x20)

smc.verbose = 0

smcep = smc.epmap[0x20]

class Phy:
    def __init__(self, phy_regs):
        self.phy_regs = phy_regs
    def activate(self):
        pass
    def set_link_rate(self):
        pass
    def set_active_lane_count(self, lanes):
        pass

class dptx_phy(Phy):
    def activate(self):
        print(f"dptx phy activate")

        # MMIO: R.4   0x23c500010 (dptx-phy[1], offset 0x10) = 0x0
        p.read32(self.phy_regs[1] + 0x10);
        p.write32(self.phy_regs[1] + 0x10, 0x0);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x444
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x454);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x454
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x474);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x474
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x434);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x434
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x534);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x534
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x734);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x734
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x334);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x334
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x335);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x335
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x337);
        # MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x337
        p.read32(self.phy_regs[1] + 0x48);
        p.write32(self.phy_regs[1] + 0x48, 0x333);
        # MMIO: R.4   0x23c542014 (dptx-phy[0], offset 0x2014) = 0x80a0c
        p.read32(self.phy_regs[0] + 0x2014);
        p.write32(self.phy_regs[0] + 0x2014, 0x300a0c);
        # MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x644800
        p.read32(self.phy_regs[0] + 0x20b8);
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800);
        # MMIO: R.4   0x23c542220 (dptx-phy[0], offset 0x2220) = 0x11090a2
        p.read32(self.phy_regs[0] + 0x2220);
        p.write32(self.phy_regs[0] + 0x2220, 0x11090a0);
        # MMIO: R.4   0x23c54222c (dptx-phy[0], offset 0x222c) = 0x103003
        p.read32(self.phy_regs[0] + 0x222c);
        p.write32(self.phy_regs[0] + 0x222c, 0x103803);
        # MMIO: R.4   0x23c54222c (dptx-phy[0], offset 0x222c) = 0x103803
        p.read32(self.phy_regs[0] + 0x222c);
        p.write32(self.phy_regs[0] + 0x222c, 0x103903);
        # MMIO: R.4   0x23c542230 (dptx-phy[0], offset 0x2230) = 0x2308804
        p.read32(self.phy_regs[0] + 0x2230);
        p.write32(self.phy_regs[0] + 0x2230, 0x2208804);
        # MMIO: R.4   0x23c542278 (dptx-phy[0], offset 0x2278) = 0x18300811
        p.read32(self.phy_regs[0] + 0x2278);
        p.write32(self.phy_regs[0] + 0x2278, 0x10300811);
        # MMIO: R.4   0x23c5422a4 (dptx-phy[0], offset 0x22a4) = 0x1044200
        p.read32(self.phy_regs[0] + 0x22a4);
        p.write32(self.phy_regs[0] + 0x22a4, 0x1044201);
        # MMIO: R.4   0x23c544008 (dptx-phy[0], offset 0x4008) = 0x18030
        p.read32(self.phy_regs[0] + 0x4008);
        p.write32(self.phy_regs[0] + 0x4008, 0x30030);
        # MMIO: R.4   0x23c544008 (dptx-phy[0], offset 0x4008) = 0x30030
        p.read32(self.phy_regs[0] + 0x4008);
        p.write32(self.phy_regs[0] + 0x4008, 0x30010);
        # MMIO: R.4   0x23c54420c (dptx-phy[0], offset 0x420c) = 0x88e3
        p.read32(self.phy_regs[0] + 0x420c);
        p.write32(self.phy_regs[0] + 0x420c, 0x88c3);
        # MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x0
        p.read32(self.phy_regs[0] + 0x4600);
        p.write32(self.phy_regs[0] + 0x4600, 0x8000000);
        # MMIO: R.4   0x23c545040 (dptx-phy[0], offset 0x5040) = 0x21780
        p.read32(self.phy_regs[0] + 0x5040);
        p.write32(self.phy_regs[0] + 0x5040, 0x221780);
        # MMIO: R.4   0x23c546040 (dptx-phy[0], offset 0x6040) = 0x21780
        p.read32(self.phy_regs[0] + 0x6040);
        p.write32(self.phy_regs[0] + 0x6040, 0x221780);
        # MMIO: R.4   0x23c547040 (dptx-phy[0], offset 0x7040) = 0x21780
        p.read32(self.phy_regs[0] + 0x7040);
        p.write32(self.phy_regs[0] + 0x7040, 0x221780);
        # MMIO: R.4   0x23c548040 (dptx-phy[0], offset 0x8040) = 0x21780
        p.read32(self.phy_regs[0] + 0x8040);
        p.write32(self.phy_regs[0] + 0x8040, 0x221780);
        # MMIO: R.4   0x23c545040 (dptx-phy[0], offset 0x5040) = 0x221780
        p.read32(self.phy_regs[0] + 0x5040);
        p.write32(self.phy_regs[0] + 0x5040, 0x2a1780);
        # MMIO: R.4   0x23c546040 (dptx-phy[0], offset 0x6040) = 0x221780
        p.read32(self.phy_regs[0] + 0x6040);
        p.write32(self.phy_regs[0] + 0x6040, 0x2a1780);
        # MMIO: R.4   0x23c547040 (dptx-phy[0], offset 0x7040) = 0x221780
        p.read32(self.phy_regs[0] + 0x7040);
        p.write32(self.phy_regs[0] + 0x7040, 0x2a1780);
        # MMIO: R.4   0x23c548040 (dptx-phy[0], offset 0x8040) = 0x221780
        p.read32(self.phy_regs[0] + 0x8040);
        p.write32(self.phy_regs[0] + 0x8040, 0x2a1780);
        # MMIO: R.4   0x23c545244 (dptx-phy[0], offset 0x5244) = 0x18
        p.read32(self.phy_regs[0] + 0x5244);
        p.write32(self.phy_regs[0] + 0x5244, 0x8);
        # MMIO: R.4   0x23c546244 (dptx-phy[0], offset 0x6244) = 0x18
        p.read32(self.phy_regs[0] + 0x6244);
        p.write32(self.phy_regs[0] + 0x6244, 0x8);
        # MMIO: R.4   0x23c547244 (dptx-phy[0], offset 0x7244) = 0x18
        p.read32(self.phy_regs[0] + 0x7244);
        p.write32(self.phy_regs[0] + 0x7244, 0x8);
        # MMIO: R.4   0x23c548244 (dptx-phy[0], offset 0x8244) = 0x18
        p.read32(self.phy_regs[0] + 0x8244);
        p.write32(self.phy_regs[0] + 0x8244, 0x8);
        # MMIO: R.4   0x23c542214 (dptx-phy[0], offset 0x2214) = 0x1e0
        p.read32(self.phy_regs[0] + 0x2214);
        p.write32(self.phy_regs[0] + 0x2214, 0x1e1);
        # MMIO: R.4   0x23c542224 (dptx-phy[0], offset 0x2224) = 0x20086001
        p.read32(self.phy_regs[0] + 0x2224);
        p.write32(self.phy_regs[0] + 0x2224, 0x20086000);
        # MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2000
        p.read32(self.phy_regs[0] + 0x2200);
        p.write32(self.phy_regs[0] + 0x2200, 0x2002);
        # MMIO: R.4   0x23c541000 (dptx-phy[0], offset 0x1000) = 0xe0000003
        p.read32(self.phy_regs[0] + 0x1000);
        p.write32(self.phy_regs[0] + 0x1000, 0xe0000001);
        # MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x41
        p.read32(self.phy_regs[0] + 0x4004);
        p.write32(self.phy_regs[0] + 0x4004, 0x49);
        # MMIO: R.4   0x23c544404 (dptx-phy[0], offset 0x4404) = 0x555d444
        p.read32(self.phy_regs[0] + 0x4404);
        p.write32(self.phy_regs[0] + 0x4404, 0x555d444);
        # MMIO: R.4   0x23c544404 (dptx-phy[0], offset 0x4404) = 0x555d444
        p.read32(self.phy_regs[0] + 0x4404);
        p.write32(self.phy_regs[0] + 0x4404, 0x555d444);

        self.set_active_lane_count(0)

        # MMIO: R.4   0x23c544200 (dptx-phy[0], offset 0x4200) = 0x4002430
        p.read32(self.phy_regs[0] + 0x4200);
        p.write32(self.phy_regs[0] + 0x4200, 0x4002420);
        # MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000000
        p.read32(self.phy_regs[0] + 0x4600);
        p.write32(self.phy_regs[0] + 0x4600, 0x8000000);
        # MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000000
        p.read32(self.phy_regs[0] + 0x4600);
        p.write32(self.phy_regs[0] + 0x4600, 0x8000001);
        # MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000001
        p.read32(self.phy_regs[0] + 0x4600);
        p.write32(self.phy_regs[0] + 0x4600, 0x8000003);
        # MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000043
        p.read32(self.phy_regs[0] + 0x4600);
        # MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000043
        p.read32(self.phy_regs[0] + 0x4600);
        p.write32(self.phy_regs[0] + 0x4600, 0x8000041);
        # MMIO: R.4   0x23c544408 (dptx-phy[0], offset 0x4408) = 0x482
        p.read32(self.phy_regs[0] + 0x4408);
        p.write32(self.phy_regs[0] + 0x4408, 0x482);
        # MMIO: R.4   0x23c544408 (dptx-phy[0], offset 0x4408) = 0x482
        p.read32(self.phy_regs[0] + 0x4408);
        p.write32(self.phy_regs[0] + 0x4408, 0x483);

    def set_link_rate(self):
        print(f"dptx phy set_link_rate")

        # MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
        p.read32(self.phy_regs[0] + 0x4004);
        p.write32(self.phy_regs[0] + 0x4004, 0x49);
        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac);
        # MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
        p.read32(self.phy_regs[0] + 0x4004);
        p.write32(self.phy_regs[0] + 0x4004, 0x41);
        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac);
        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac);
        # MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2002
        p.read32(self.phy_regs[0] + 0x2200);
        # MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2002
        p.read32(self.phy_regs[0] + 0x2200);
        p.write32(self.phy_regs[0] + 0x2200, 0x2000);
        # MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
        p.read32(self.phy_regs[0] + 0x100c);
        p.write32(self.phy_regs[0] + 0x100c, 0xf000);
        # MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
        p.read32(self.phy_regs[0] + 0x100c);
        p.write32(self.phy_regs[0] + 0x100c, 0xf008);
        # MMIO: R.4   0x23c541014 (dptx-phy[0], offset 0x1014) = 0x1
        p.read32(self.phy_regs[0] + 0x1014);
        # MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf008
        p.read32(self.phy_regs[0] + 0x100c);
        p.write32(self.phy_regs[0] + 0x100c, 0xf000);
        # MMIO: R.4   0x23c541008 (dptx-phy[0], offset 0x1008) = 0x1
        p.read32(self.phy_regs[0] + 0x1008);
        # MMIO: R.4   0x23c542220 (dptx-phy[0], offset 0x2220) = 0x11090a0
        p.read32(self.phy_regs[0] + 0x2220);
        p.write32(self.phy_regs[0] + 0x2220, 0x1109020);
        # MMIO: R.4   0x23c5420b0 (dptx-phy[0], offset 0x20b0) = 0x1e0e01c2
        p.read32(self.phy_regs[0] + 0x20b0);
        p.write32(self.phy_regs[0] + 0x20b0, 0x1e0e01c2);
        # MMIO: R.4   0x23c5420b4 (dptx-phy[0], offset 0x20b4) = 0x7fffffe
        p.read32(self.phy_regs[0] + 0x20b4);
        p.write32(self.phy_regs[0] + 0x20b4, 0x7fffffe);
        # MMIO: R.4   0x23c5420b4 (dptx-phy[0], offset 0x20b4) = 0x7fffffe
        p.read32(self.phy_regs[0] + 0x20b4);
        p.write32(self.phy_regs[0] + 0x20b4, 0x7fffffe);
        # MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8);
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800);
        # MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8);
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800);
        # MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8);
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800);
        # MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8);
        p.write32(self.phy_regs[0] + 0x20b8, 0x454800);
        # MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x454800
        p.read32(self.phy_regs[0] + 0x20b8);
        p.write32(self.phy_regs[0] + 0x20b8, 0x454800);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x0
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0x8);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0xc);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0x4000c);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x4000c
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0xc);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0x8000c);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8000c
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0xc);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0x8);
        # MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8
        p.read32(self.phy_regs[1] + 0xa0);
        p.write32(self.phy_regs[1] + 0xa0, 0x0);
        # MMIO: R.4   0x23c542000 (dptx-phy[0], offset 0x2000) = 0x2
        p.read32(self.phy_regs[0] + 0x2000);
        p.write32(self.phy_regs[0] + 0x2000, 0x2);
        # MMIO: R.4   0x23c542018 (dptx-phy[0], offset 0x2018) = 0x0
        p.read32(self.phy_regs[0] + 0x2018);
        p.write32(self.phy_regs[0] + 0x2018, 0x0);
        # MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
        p.read32(self.phy_regs[0] + 0x100c);
        p.write32(self.phy_regs[0] + 0x100c, 0xf007);
        # MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf007
        p.read32(self.phy_regs[0] + 0x100c);
        p.write32(self.phy_regs[0] + 0x100c, 0xf00f);
        # MMIO: R.4   0x23c541014 (dptx-phy[0], offset 0x1014) = 0x38f
        p.read32(self.phy_regs[0] + 0x1014);
        # MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf00f
        p.read32(self.phy_regs[0] + 0x100c);
        p.write32(self.phy_regs[0] + 0x100c, 0xf007);
        # MMIO: R.4   0x23c541008 (dptx-phy[0], offset 0x1008) = 0x9
        p.read32(self.phy_regs[0] + 0x1008);
        # MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2000
        p.read32(self.phy_regs[0] + 0x2200);
        p.write32(self.phy_regs[0] + 0x2200, 0x2002);
        # MMIO: R.4   0x23c545010 (dptx-phy[0], offset 0x5010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x5010);
        p.write32(self.phy_regs[0] + 0x5010, 0x18003000);
        # MMIO: R.4   0x23c546010 (dptx-phy[0], offset 0x6010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x6010);
        p.write32(self.phy_regs[0] + 0x6010, 0x18003000);
        # MMIO: R.4   0x23c547010 (dptx-phy[0], offset 0x7010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x7010);
        p.write32(self.phy_regs[0] + 0x7010, 0x18003000);
        # MMIO: R.4   0x23c548010 (dptx-phy[0], offset 0x8010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x8010);
        p.write32(self.phy_regs[0] + 0x8010, 0x18003000);
        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, 0x51021ac);
        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x51021ac
        p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, 0x71021ac);
        # MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x41
        p.read32(self.phy_regs[0] + 0x4004);
        p.write32(self.phy_regs[0] + 0x4004, 0x49);
        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x71021ac
        p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, 0x71021ec);
        # MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
        p.read32(self.phy_regs[0] + 0x4004);
        p.write32(self.phy_regs[0] + 0x4004, 0x48);

    def set_active_lane_count(self, lanes):
        print(f"dptx phy set_active_lane_count({lanes})")
        if lanes == 0:
            val1 = val2 = 0x300
        else:
            val1 = 0x100
            val2 = 0

        # MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
        program =  p.read32(self.phy_regs[0] + 0x4000);
        p.write32(self.phy_regs[0] + 0x4000, program);
        # MMIO: R.4   0x23c545000 (dptx-phy[0], offset 0x5000) = 0x300
        p.read32(self.phy_regs[0] + 0x5000);
        p.write32(self.phy_regs[0] + 0x5000, val1);
        # MMIO: R.4   0x23c546000 (dptx-phy[0], offset 0x6000) = 0x300
        p.read32(self.phy_regs[0] + 0x6000);
        p.write32(self.phy_regs[0] + 0x6000, val1);
        # MMIO: R.4   0x23c547000 (dptx-phy[0], offset 0x7000) = 0x300
        p.read32(self.phy_regs[0] + 0x7000);
        p.write32(self.phy_regs[0] + 0x7000, val1);
        # MMIO: R.4   0x23c548000 (dptx-phy[0], offset 0x8000) = 0x300
        p.read32(self.phy_regs[0] + 0x8000);
        p.write32(self.phy_regs[0] + 0x8000, val1);
        # MMIO: R.4   0x23c545000 (dptx-phy[0], offset 0x5000) = 0x300
        p.read32(self.phy_regs[0] + 0x5000);
        p.write32(self.phy_regs[0] + 0x5000, val2);
        # MMIO: R.4   0x23c546000 (dptx-phy[0], offset 0x6000) = 0x300
        p.read32(self.phy_regs[0] + 0x6000);
        p.write32(self.phy_regs[0] + 0x6000, val2);
        # MMIO: R.4   0x23c547000 (dptx-phy[0], offset 0x7000) = 0x300
        p.read32(self.phy_regs[0] + 0x7000);
        p.write32(self.phy_regs[0] + 0x7000, val2);
        # MMIO: R.4   0x23c548000 (dptx-phy[0], offset 0x8000) = 0x300
        p.read32(self.phy_regs[0] + 0x8000);
        p.write32(self.phy_regs[0] + 0x8000, val2);

        if lanes > 0:
            p.clear32(self.phy_regs[0] + 0x4000, 0x4000000)

class lpdptx_phy(Phy):

    def activate(self):
        print(f"dptx phy activate")
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000010 (lpdptx-phy0[1], offset 0x10) = 0x0
        p.read32(self.phy_regs[1] + 0x10)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000010 (lpdptx-phy0[1], offset 0x10) = 0x0
        p.write32(self.phy_regs[1] + 0x10, 0x0)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.read32(self.phy_regs[1] + 0x48)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c000048 (lpdptx-phy0[1], offset 0x48) = 0x333
        p.write32(self.phy_regs[1] + 0x48, 0x333)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042014 (lpdptx-phy0[0], offset 0x2014) = 0x300a0c
        p.read32(self.phy_regs[0] + 0x2014)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042014 (lpdptx-phy0[0], offset 0x2014) = 0x300a0c
        p.write32(self.phy_regs[0] + 0x2014, 0x300a0c)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042220 (lpdptx-phy0[0], offset 0x2220) = 0x11090a0
        p.read32(self.phy_regs[0] + 0x2220)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042220 (lpdptx-phy0[0], offset 0x2220) = 0x11090a0
        p.write32(self.phy_regs[0] + 0x2220, 0x11090a0)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c04222c (lpdptx-phy0[0], offset 0x222c) = 0x103903
        p.read32(self.phy_regs[0] + 0x222c)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c04222c (lpdptx-phy0[0], offset 0x222c) = 0x103903
        p.write32(self.phy_regs[0] + 0x222c, 0x103903)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c04222c (lpdptx-phy0[0], offset 0x222c) = 0x103903
        p.read32(self.phy_regs[0] + 0x222c)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c04222c (lpdptx-phy0[0], offset 0x222c) = 0x103903
        p.write32(self.phy_regs[0] + 0x222c, 0x103903)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042230 (lpdptx-phy0[0], offset 0x2230) = 0x2208804
        p.read32(self.phy_regs[0] + 0x2230)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042230 (lpdptx-phy0[0], offset 0x2230) = 0x2208804
        p.write32(self.phy_regs[0] + 0x2230, 0x2208804)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042278 (lpdptx-phy0[0], offset 0x2278) = 0x10300811
        p.read32(self.phy_regs[0] + 0x2278)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042278 (lpdptx-phy0[0], offset 0x2278) = 0x10300811
        p.write32(self.phy_regs[0] + 0x2278, 0x10300811)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c0422a4 (lpdptx-phy0[0], offset 0x22a4) = 0x1044201
        p.read32(self.phy_regs[0] + 0x22a4)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c0422a4 (lpdptx-phy0[0], offset 0x22a4) = 0x1044201
        p.write32(self.phy_regs[0] + 0x22a4, 0x1044201)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044008 (lpdptx-phy0[0], offset 0x4008) = 0x30010
        p.read32(self.phy_regs[0] + 0x4008)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044008 (lpdptx-phy0[0], offset 0x4008) = 0x30010
        p.write32(self.phy_regs[0] + 0x4008, 0x30010)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044008 (lpdptx-phy0[0], offset 0x4008) = 0x30010
        p.read32(self.phy_regs[0] + 0x4008)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044008 (lpdptx-phy0[0], offset 0x4008) = 0x30010
        p.write32(self.phy_regs[0] + 0x4008, 0x30010)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c04420c (lpdptx-phy0[0], offset 0x420c) = 0x38c3
        p.read32(self.phy_regs[0] + 0x420c)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c04420c (lpdptx-phy0[0], offset 0x420c) = 0x38c3
        p.write32(self.phy_regs[0] + 0x420c, 0x38c3)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000041
        p.read32(self.phy_regs[0] + 0x4600)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000041
        p.write32(self.phy_regs[0] + 0x4600, 0x8000041)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c045040 (lpdptx-phy0[0], offset 0x5040) = 0xa1780
        p.read32(self.phy_regs[0] + 0x5040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c045040 (lpdptx-phy0[0], offset 0x5040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x5040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c046040 (lpdptx-phy0[0], offset 0x6040) = 0xa1780
        p.read32(self.phy_regs[0] + 0x6040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c046040 (lpdptx-phy0[0], offset 0x6040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x6040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c047040 (lpdptx-phy0[0], offset 0x7040) = 0xa1780
        p.read32(self.phy_regs[0] + 0x7040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c047040 (lpdptx-phy0[0], offset 0x7040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x7040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c048040 (lpdptx-phy0[0], offset 0x8040) = 0xa1780
        p.read32(self.phy_regs[0] + 0x8040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c048040 (lpdptx-phy0[0], offset 0x8040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x8040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c045040 (lpdptx-phy0[0], offset 0x5040) = 0x2a1780
        p.read32(self.phy_regs[0] + 0x5040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c045040 (lpdptx-phy0[0], offset 0x5040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x5040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c046040 (lpdptx-phy0[0], offset 0x6040) = 0x2a1780
        p.read32(self.phy_regs[0] + 0x6040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c046040 (lpdptx-phy0[0], offset 0x6040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x6040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c047040 (lpdptx-phy0[0], offset 0x7040) = 0x2a1780
        p.read32(self.phy_regs[0] + 0x7040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c047040 (lpdptx-phy0[0], offset 0x7040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x7040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c048040 (lpdptx-phy0[0], offset 0x8040) = 0x2a1780
        p.read32(self.phy_regs[0] + 0x8040)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c048040 (lpdptx-phy0[0], offset 0x8040) = 0x2a1780
        p.write32(self.phy_regs[0] + 0x8040, 0x2a1780)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c045244 (lpdptx-phy0[0], offset 0x5244) = 0x8
        p.read32(self.phy_regs[0] + 0x5244)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c045244 (lpdptx-phy0[0], offset 0x5244) = 0x8
        p.write32(self.phy_regs[0] + 0x5244, 0x8)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c046244 (lpdptx-phy0[0], offset 0x6244) = 0x8
        p.read32(self.phy_regs[0] + 0x6244)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c046244 (lpdptx-phy0[0], offset 0x6244) = 0x8
        p.write32(self.phy_regs[0] + 0x6244, 0x8)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c047244 (lpdptx-phy0[0], offset 0x7244) = 0x8
        p.read32(self.phy_regs[0] + 0x7244)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c047244 (lpdptx-phy0[0], offset 0x7244) = 0x8
        p.write32(self.phy_regs[0] + 0x7244, 0x8)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c048244 (lpdptx-phy0[0], offset 0x8244) = 0x8
        p.read32(self.phy_regs[0] + 0x8244)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c048244 (lpdptx-phy0[0], offset 0x8244) = 0x8
        p.write32(self.phy_regs[0] + 0x8244, 0x8)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042214 (lpdptx-phy0[0], offset 0x2214) = 0x1e1
        p.read32(self.phy_regs[0] + 0x2214)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042214 (lpdptx-phy0[0], offset 0x2214) = 0x1e1
        p.write32(self.phy_regs[0] + 0x2214, 0x1e1)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042224 (lpdptx-phy0[0], offset 0x2224) = 0x20086000
        p.read32(self.phy_regs[0] + 0x2224)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042224 (lpdptx-phy0[0], offset 0x2224) = 0x20086000
        p.write32(self.phy_regs[0] + 0x2224, 0x20086000)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2002
        p.read32(self.phy_regs[0] + 0x2200)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2002
        p.write32(self.phy_regs[0] + 0x2200, 0x2002)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c041000 (lpdptx-phy0[0], offset 0x1000) = 0xe0000001
        p.read32(self.phy_regs[0] + 0x1000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c041000 (lpdptx-phy0[0], offset 0x1000) = 0xe0000001
        p.write32(self.phy_regs[0] + 0x1000, 0xe0000001)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x49
        p.read32(self.phy_regs[0] + 0x4004)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x49
        p.write32(self.phy_regs[0] + 0x4004, 0x49)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044404 (lpdptx-phy0[0], offset 0x4404) = 0x555d444
        p.read32(self.phy_regs[0] + 0x4404)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044404 (lpdptx-phy0[0], offset 0x4404) = 0x555d444
        p.write32(self.phy_regs[0] + 0x4404, 0x555d444)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044404 (lpdptx-phy0[0], offset 0x4404) = 0x555d444
        p.read32(self.phy_regs[0] + 0x4404)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044404 (lpdptx-phy0[0], offset 0x4404) = 0x555d444
        p.write32(self.phy_regs[0] + 0x4404, 0x555d444)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x100
        p.read32(self.phy_regs[0] + 0x5000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.write32(self.phy_regs[0] + 0x5000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x100
        p.read32(self.phy_regs[0] + 0x6000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.write32(self.phy_regs[0] + 0x6000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x100
        p.read32(self.phy_regs[0] + 0x7000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.write32(self.phy_regs[0] + 0x7000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x100
        p.read32(self.phy_regs[0] + 0x8000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.write32(self.phy_regs[0] + 0x8000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.read32(self.phy_regs[0] + 0x5000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.write32(self.phy_regs[0] + 0x5000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.read32(self.phy_regs[0] + 0x6000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.write32(self.phy_regs[0] + 0x6000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.read32(self.phy_regs[0] + 0x7000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.write32(self.phy_regs[0] + 0x7000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.read32(self.phy_regs[0] + 0x8000)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.write32(self.phy_regs[0] + 0x8000, 0x300)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044200 (lpdptx-phy0[0], offset 0x4200) = 0x4002420
        p.read32(self.phy_regs[0] + 0x4200)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044200 (lpdptx-phy0[0], offset 0x4200) = 0x4002420
        p.write32(self.phy_regs[0] + 0x4200, 0x4002420)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000041
        p.read32(self.phy_regs[0] + 0x4600)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000040
        p.write32(self.phy_regs[0] + 0x4600, 0x8000040)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000000
        p.read32(self.phy_regs[0] + 0x4600)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000001
        p.write32(self.phy_regs[0] + 0x4600, 0x8000001)
        # [cpu0] [0xfffffe0014c965b0] MMIO: R.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000001
        p.read32(self.phy_regs[0] + 0x4600)
        # [cpu0] [0xfffffe0014c9678c] MMIO: W.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000003
        p.write32(self.phy_regs[0] + 0x4600, 0x8000003)
        # [cpu2] [0xfffffe0014c965b0] MMIO: R.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000043
        p.read32(self.phy_regs[0] + 0x4600)
        # [cpu2] [0xfffffe0014c965b0] MMIO: R.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000043
        p.read32(self.phy_regs[0] + 0x4600)
        # [cpu2] [0xfffffe0014c9678c] MMIO: W.4   0x39c044600 (lpdptx-phy0[0], offset 0x4600) = 0x8000041
        p.write32(self.phy_regs[0] + 0x4600, 0x8000041)
        # [cpu2] [0xfffffe0014c965b0] MMIO: R.4   0x39c044408 (lpdptx-phy0[0], offset 0x4408) = 0x483
        p.read32(self.phy_regs[0] + 0x4408)
        # [cpu2] [0xfffffe0014c9678c] MMIO: W.4   0x39c044408 (lpdptx-phy0[0], offset 0x4408) = 0x483
        p.write32(self.phy_regs[0] + 0x4408, 0x483)
        # [cpu2] [0xfffffe0014c965b0] MMIO: R.4   0x39c044408 (lpdptx-phy0[0], offset 0x4408) = 0x483
        p.read32(self.phy_regs[0] + 0x4408)
        # [cpu2] [0xfffffe0014c9678c] MMIO: W.4   0x39c044408 (lpdptx-phy0[0], offset 0x4408) = 0x483
        p.write32(self.phy_regs[0] + 0x4408, 0x483)

    def set_link_rate(self):
        print(f"dptx phy set_link_rate")
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x49
        p.write32(self.phy_regs[0] + 0x4004, 0x49)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x49
        p.read32(self.phy_regs[0] + 0x4004)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x41
        p.write32(self.phy_regs[0] + 0x4004, 0x41)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.write32(self.phy_regs[0] + 0x4000, 0x41021ac)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2002
        p.read32(self.phy_regs[0] + 0x2200)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2002
        p.read32(self.phy_regs[0] + 0x2200)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2000
        p.write32(self.phy_regs[0] + 0x2200, 0x2000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf000
        p.read32(self.phy_regs[0] + 0x100c)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf000
        p.write32(self.phy_regs[0] + 0x100c, 0xf000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf000
        p.read32(self.phy_regs[0] + 0x100c)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf008
        p.write32(self.phy_regs[0] + 0x100c, 0xf008)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c041014 (lpdptx-phy0[0], offset 0x1014) = 0x1
        p.read32(self.phy_regs[0] + 0x1014)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf008
        p.read32(self.phy_regs[0] + 0x100c)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf000
        p.write32(self.phy_regs[0] + 0x100c, 0xf000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c041008 (lpdptx-phy0[0], offset 0x1008) = 0x1
        p.read32(self.phy_regs[0] + 0x1008)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c042220 (lpdptx-phy0[0], offset 0x2220) = 0x11090a0
        p.read32(self.phy_regs[0] + 0x2220)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c042220 (lpdptx-phy0[0], offset 0x2220) = 0x1109020
        p.write32(self.phy_regs[0] + 0x2220, 0x1109020)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b0 (lpdptx-phy0[0], offset 0x20b0) = 0x1e0e01c2
        p.read32(self.phy_regs[0] + 0x20b0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b0 (lpdptx-phy0[0], offset 0x20b0) = 0x1e0e02a3
        p.write32(self.phy_regs[0] + 0x20b0, 0x1e0e02a3)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b4 (lpdptx-phy0[0], offset 0x20b4) = 0x7fffffe
        p.read32(self.phy_regs[0] + 0x20b4)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b4 (lpdptx-phy0[0], offset 0x20b4) = 0xbff7ffe
        p.write32(self.phy_regs[0] + 0x20b4, 0xbff7ffe)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b4 (lpdptx-phy0[0], offset 0x20b4) = 0xbff7ffe
        p.read32(self.phy_regs[0] + 0x20b4)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b4 (lpdptx-phy0[0], offset 0x20b4) = 0xbff7ffc
        p.write32(self.phy_regs[0] + 0x20b4, 0xbff7ffc)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.write32(self.phy_regs[0] + 0x20b8, 0x654800)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x654800
        p.read32(self.phy_regs[0] + 0x20b8)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x664800
        p.write32(self.phy_regs[0] + 0x20b8, 0x664800)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x664800
        p.read32(self.phy_regs[0] + 0x20b8)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x464800
        p.write32(self.phy_regs[0] + 0x20b8, 0x464800)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x464800
        p.read32(self.phy_regs[0] + 0x20b8)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0420b8 (lpdptx-phy0[0], offset 0x20b8) = 0x464800
        p.write32(self.phy_regs[0] + 0x20b8, 0x464800)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x0
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x8
        p.write32(self.phy_regs[1] + 0xa0, 0x8)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x8
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0xc
        p.write32(self.phy_regs[1] + 0xa0, 0xc)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0xc
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x4000c
        p.write32(self.phy_regs[1] + 0xa0, 0x4000c)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x4000c
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0xc
        p.write32(self.phy_regs[1] + 0xa0, 0xc)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0xc
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x8000c
        p.write32(self.phy_regs[1] + 0xa0, 0x8000c)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x8000c
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0xc
        p.write32(self.phy_regs[1] + 0xa0, 0xc)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0xc
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x8
        p.write32(self.phy_regs[1] + 0xa0, 0x8)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x8
        p.read32(self.phy_regs[1] + 0xa0)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c0000a0 (lpdptx-phy0[1], offset 0xa0) = 0x0
        p.write32(self.phy_regs[1] + 0xa0, 0x0)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c042000 (lpdptx-phy0[0], offset 0x2000) = 0x2
        p.read32(self.phy_regs[0] + 0x2000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c042000 (lpdptx-phy0[0], offset 0x2000) = 0x2
        p.write32(self.phy_regs[0] + 0x2000, 0x2)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c042018 (lpdptx-phy0[0], offset 0x2018) = 0x0
        p.read32(self.phy_regs[0] + 0x2018)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c042018 (lpdptx-phy0[0], offset 0x2018) = 0x0
        p.write32(self.phy_regs[0] + 0x2018, 0x0)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf000
        p.read32(self.phy_regs[0] + 0x100c)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf007
        p.write32(self.phy_regs[0] + 0x100c, 0xf007)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf007
        p.read32(self.phy_regs[0] + 0x100c)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf00f
        p.write32(self.phy_regs[0] + 0x100c, 0xf00f)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c041014 (lpdptx-phy0[0], offset 0x1014) = 0x38f
        p.read32(self.phy_regs[0] + 0x1014)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf00f
        p.read32(self.phy_regs[0] + 0x100c)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c04100c (lpdptx-phy0[0], offset 0x100c) = 0xf007
        p.write32(self.phy_regs[0] + 0x100c, 0xf007)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c041008 (lpdptx-phy0[0], offset 0x1008) = 0x9
        p.read32(self.phy_regs[0] + 0x1008)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2000
        p.read32(self.phy_regs[0] + 0x2200)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c042200 (lpdptx-phy0[0], offset 0x2200) = 0x2002
        p.write32(self.phy_regs[0] + 0x2200, 0x2002)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c045010 (lpdptx-phy0[0], offset 0x5010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x5010)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c045010 (lpdptx-phy0[0], offset 0x5010) = 0x18003000
        p.write32(self.phy_regs[0] + 0x5010, 0x18003000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c046010 (lpdptx-phy0[0], offset 0x6010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x6010)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c046010 (lpdptx-phy0[0], offset 0x6010) = 0x18003000
        p.write32(self.phy_regs[0] + 0x6010, 0x18003000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c047010 (lpdptx-phy0[0], offset 0x7010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x7010)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c047010 (lpdptx-phy0[0], offset 0x7010) = 0x18003000
        p.write32(self.phy_regs[0] + 0x7010, 0x18003000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c048010 (lpdptx-phy0[0], offset 0x8010) = 0x18003000
        p.read32(self.phy_regs[0] + 0x8010)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c048010 (lpdptx-phy0[0], offset 0x8010) = 0x18003000
        p.write32(self.phy_regs[0] + 0x8010, 0x18003000)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x51021ac
        p.write32(self.phy_regs[0] + 0x4000, 0x51021ac)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x51021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x71021ac
        p.write32(self.phy_regs[0] + 0x4000, 0x71021ac)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x41
        p.read32(self.phy_regs[0] + 0x4004)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x49
        p.write32(self.phy_regs[0] + 0x4004, 0x49)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x71021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x71021ec
        p.write32(self.phy_regs[0] + 0x4000, 0x71021ec)
        # [cpu1] [0xfffffe0014c965b0] MMIO: R.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x49
        p.read32(self.phy_regs[0] + 0x4004)
        # [cpu1] [0xfffffe0014c9678c] MMIO: W.4   0x39c044004 (lpdptx-phy0[0], offset 0x4004) = 0x48
        p.write32(self.phy_regs[0] + 0x4004, 0x48)


    def set_active_lane_count(self, lanes):
        print(f"dptx phy set_active_lane_count({lanes})")
        if lanes == 0:
            val1 = val2 = 0x300
        else:
            val1 = 0x100
            val2 = 0

        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.read32(self.phy_regs[0] + 0x4000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c044000 (lpdptx-phy0[0], offset 0x4000) = 0x41021ac
        p.clear32(self.phy_regs[0] + 0x4000, 0x4000000)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.read32(self.phy_regs[0] + 0x5000)
        # [cpu3] [DCPTracer@/arm-io/dcp0] [dcpep] >ACK CB.0 (0x42 (TYPE=0x2, LEN=0x0, OFF=0x0, CTX=0x0(CB), ACK=1))
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.write32(self.phy_regs[0] + 0x5000, val1)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.read32(self.phy_regs[0] + 0x6000)
        # [cpu3] [DCPTracer@/arm-io/dcp0] [dcpep] 0x1c00000002 (TYPE=0x2, LEN=0x1c, OFF=0x0, CTX=0x0(CB), ACK=0)
        # [cpu3] [DCPTracer@/arm-io/dcp0] [dcpep] <CB.0 D300:void IOMFB::PropRelay::publish(IOMFB::RuntimeProperty, unsigned int) (0x1c00000002 (TYPE=0x2, LEN=0x1c, OFF=0x0, CTX=0x0(CB), ACK=0))
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.write32(self.phy_regs[0] + 0x6000, val1)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.read32(self.phy_regs[0] + 0x7000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.write32(self.phy_regs[0] + 0x7000, val1)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.read32(self.phy_regs[0] + 0x8000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.write32(self.phy_regs[0] + 0x8000, val1)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.read32(self.phy_regs[0] + 0x5000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c045000 (lpdptx-phy0[0], offset 0x5000) = 0x300
        p.write32(self.phy_regs[0] + 0x5000, val2)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.read32(self.phy_regs[0] + 0x6000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c046000 (lpdptx-phy0[0], offset 0x6000) = 0x300
        p.write32(self.phy_regs[0] + 0x6000, val2)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.read32(self.phy_regs[0] + 0x7000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c047000 (lpdptx-phy0[0], offset 0x7000) = 0x300
        p.write32(self.phy_regs[0] + 0x7000, val2)
        # [cpu0] [0xfffffe0014c365b0] MMIO: R.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.read32(self.phy_regs[0] + 0x8000)
        # [cpu0] [0xfffffe0014c3678c] MMIO: W.4   0x39c048000 (lpdptx-phy0[0], offset 0x8000) = 0x300
        p.write32(self.phy_regs[0] + 0x8000, val2)

        if lanes != 0:
            p.clear32(self.phy_regs[0] + 0x4000, 0x4000000)


print(f"Framebuffer at {u.ba.video.base:#x}")

p.display_shutdown(DCP_SHUTDOWN_MODE.QUIESCED)

target_type = u.adt.getprop('target-type')
if target_type in ["J474s", "J475c"]: # t6020/t6021
    dart = DART.from_adt(u, "arm-io/dart-dcp0")
    disp_dart = DART.from_adt(u, "arm-io/dart-disp0")
    #disp_dart.dump_all()

    dart.dump_all()

    dcp_addr = u.adt["arm-io/dcp0"].get_reg(0)[0]
    dcp = DCPIBootClient(u, dcp_addr, dart, disp_dart)
    dcp.dva_offset = getattr(u.adt["/arm-io/dcp0"][0], "asc_dram_mask", 0)
    if not dcp.dva_offset:
        dcp.dva_offset = getattr(u.adt["/arm-io/dart-dcp0"], "vm-base", 0)
    dcp.stream = u.adt["/arm-io/dart-dcp0/mapper-dcp0"].reg

    phy_node = u.adt["/arm-io/lpdptx-phy0"]
    dp2hdmi_node = u.adt["/arm-io/dp2hdmi-gpio0"]
    phy_regs = [phy_node.get_reg(0)[0], phy_node.get_reg(1)[0]]
    phy = lpdptx_phy(phy_regs)

elif target_type in ["J473"]: # t8112
    dart = DART.from_adt(u, "arm-io/dart-dcp")
    disp_dart = DART.from_adt(u, "arm-io/dart-disp0")
    #disp_dart.dump_all()

    dart.dump_all()

    dcp_addr = u.adt["arm-io/dcp"].get_reg(0)[0]
    dcp = DCPIBootClient(u, dcp_addr, dart, disp_dart)
    dcp.dva_offset = getattr(u.adt["/arm-io/dcp"][0], "asc_dram_mask", 0)
    if not dcp.dva_offset:
        dcp.dva_offset = getattr(u.adt["/arm-io/dart-dcp"], "vm-base", 0)
    dcp.stream = u.adt["/arm-io/dart-dcp/mapper-dcp"].reg
    dcp.dva_offset = 0;

    phy_node = u.adt["/arm-io/dptx-phy"]
    dp2hdmi_node = u.adt["/arm-io/dp2hdmi-gpio"]
    phy_regs = [phy_node.get_reg(0)[0], phy_node.get_reg(1)[0]]
    phy = dptx_phy(phy_regs)
else:
    raise ValueError(target_type)

print(f"DVA offset: {dcp.dva_offset:#x}")

dcp.start()
dcp.start_ep(0x20)
dcp.start_ep(0x22)
dcp.start_ep(0x23)
dcp.start_ep(0x24)
dcp.start_ep(0x2a)

dcp.system.wait_for("system")
dcp.system.system.setProperty("gAFKConfigLogMask", 0xffff)

dcp.dcpexpert.wait_for("dcpexpert")
dcp.iboot.wait_for("disp0")
dcp.dptx.wait_for("dcpav0")
dcp.dptx.wait_for("dcpdp0")
dcp.dpport.wait_for("port0")

hdmi_pwr_en_gpio = dp2hdmi_node.getprop('function-hdmi_pwr_en').args[0].to_bytes(4, byteorder='big').decode()
dp2hdmi_pwr_en_gpio = dp2hdmi_node.getprop('function-dp2hdmi_pwr_en').args[0].to_bytes(4, byteorder='big').decode()

print(f"dp2hdmi_pwr_enable:{dp2hdmi_pwr_en_gpio} hdmi_pwr_enable:{hdmi_pwr_en_gpio}")
smcep.write32(hdmi_pwr_en_gpio, 0x800001)
smcep.write32(dp2hdmi_pwr_en_gpio, 0x800001)

dcp.dpport.port0.phy = phy
dfp_endpoint = phy_node.getprop('dp-switch-dfp-endpoint')
print(f"connect dfp-endpoint: {dfp_endpoint}")
dcp.dpport.port0.connectTo(port=0x800 + dfp_endpoint, connected=0, unit=0)
print("request")
dcp.dpport.port0.displayRequest()

#dcp.dptx.dcpav0.forceHotPlugDetect()
#dcp.dptx.dcpav0.setVirtualDeviceMode(0)
#dcp.dptx.dcpav0.setPower(True)
#dcp.dptx.dcpav0.wakeDisplay()
#dcp.dptx.dcpav0.sleepDisplay()
#dcp.dptx.dcpav0.wakeDisplay()

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

fb_size = align_up(w * h * 4, 8 * 0x4000)
print(f"Display {w}x{h}, fb size: {fb_size}")

buf = u.memalign(0x4000, fb_size)

colors = [0xDD0000, 0xFE6230, 0xFEF600, 0x00BB00, 0x009BFE, 0x000083, 0x30009B]


for i, color in enumerate(colors):
    lines = h // len(colors)
    offset = i * lines * w * 4
    p.memset32(buf + offset, color, lines * w * 4)

iova = disp_dart.iomap(0, buf, fb_size)

layer = Container(
    planes = [
        Container(
            addr = iova,
            stride = u.ba.video.stride,
            addr_format = AddrFormat.PLANAR,
        ),
        Container(),
        Container()
    ],
    plane_cnt = 1,
    width = w,
    height = h,
    surface_fmt = SurfaceFormat.BGRA,
    colorspace = Colorspace.SRGB,
    eotf = EOTF.GAMMA_SDR,
    transform = Transform.NONE,
)

mw = min(w, u.ba.video.width)
mh = min(h, u.ba.video.height)

# swap = dcp.iboot.disp0.swapBegin()
# print(swap)
# dcp.iboot.disp0.swapSetLayer(0, layer, (mw, mh, 0, 0), (mw, mh, 0, 0))
# dcp.iboot.disp0.swapEnd()
#dcp.iboot.disp0.swapWait(swap.swap_id)

print("setSurface")
dcp.iboot.disp0.setSurface(layer)

run_shell(globals(), msg="Have fun!")

# full shutdown!
dcp.stop(1)
p.pmgr_reset(0, "DISP0_CPU0")
