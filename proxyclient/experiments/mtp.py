#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, fnmatch
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from m1n1.setup import *
from m1n1.fw.asc import StandardASC
from m1n1.hw.dart8110 import DART8110
from m1n1.hw.dockchannel import DockChannel
from m1n1.fw.smc import SMCClient, SMCError
from m1n1.shell import run_shell

from construct import *

p.dapf_init_all()

dart = DART8110.from_adt(u, "/arm-io/dart-mtp", iova_range=(0x8000, 0x100000))

dart.regs.TCR[1].set(BYPASS_DAPF=0, BYPASS_DART=0, TRANSLATE_ENABLE=1)

mtp_addr = u.adt["/arm-io/mtp"].get_reg(0)[0]
mtp = StandardASC(u, mtp_addr, dart, stream=1)
mtp.verbose = 3
mtp.allow_phys = True
mtp.start()

irq_base = u.adt["/arm-io/dockchannel-mtp"].get_reg(1)[0]
fifo_base = u.adt["/arm-io/dockchannel-mtp"].get_reg(2)[0]
dc = DockChannel(u, irq_base, fifo_base, 1)

for i in range(128):
    mtp.work()

dc.write(bytes.fromhex("08110c00010000008000020000000000b4010000c2ecf1ff"))
dc.write(bytes.fromhex("08110c00020000008000020000000000b4020000c1ebf1ff"))

def poll():
    v = dc.read_all()
    if v:
        chexdump(v)
    mtp.work()

mtp.stop()

#run_shell(locals(), poll_func=poll)
