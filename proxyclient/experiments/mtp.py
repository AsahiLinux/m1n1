#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, fnmatch
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from m1n1.setup import *
from m1n1.fw.asc import StandardASC
from m1n1.hw.dart import DART
from m1n1.hw.dockchannel import DockChannel
from m1n1.fw.smc import SMCClient, SMCError
from m1n1.shell import run_shell
from m1n1.fw.mtp import *

from construct import *

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr)
smc.start()
smc.start_ep(0x20)
smc.verbose = 0

p.dapf_init_all()

dart = DART.from_adt(u, "/arm-io/dart-mtp", iova_range=(0x8000, 0x100000))

dart.dart.regs.TCR[1].set(BYPASS_DAPF=0, BYPASS_DART=0, TRANSLATE_ENABLE=1)

irq_base = u.adt["/arm-io/dockchannel-mtp"].get_reg(1)[0]
fifo_base = u.adt["/arm-io/dockchannel-mtp"].get_reg(2)[0]
dc = DockChannel(u, irq_base, fifo_base, 1)

node = u.adt["/arm-io/dockchannel-mtp/mtp-transport"]

while dc.rx_count:
    dc.read(dc.rx_count)

mtp_addr = u.adt["/arm-io/mtp"].get_reg(0)[0]
mtp = StandardASC(u, mtp_addr, dart, stream=1)
mtp.boot()
mtp.verbose = 3
mtp.allow_phys = True
print("pre start")

def poll():
    mtp.work()
    mp.work_pending()

try:
    mp = MTPProtocol(u, node, mtp, dc, smc)

    mp.wait_init("keyboard")
    #mp.wait_init("multi_touch")
    mp.wait_init("stm")

    mtp.stop()
    mtp.start()
    mon.poll()

    for i in range(256):
        mp.stm.get_report(i)
        mtp.work()
        mp.work_pending()

    #for i in range(256):
        #if i in (0x40, 0x42):
            #continue
        #m = UnkDeviceControlMsg()
        #m.command = i
        #for args in (b"", b"\x00", b"\x01", b"\x02",
                     #b"\x01\x00", b"\x01\x01", b"\x01\x02",
                     #b"\x00\x01", b"\x00\x02", b"\x00\x00",
                     #b"\x00\x00\x00",
                     #b"\x00\x00\x00\x00",
                     #b"\x00\x00\x00\x00\x00",
                     #b"\x00\x00\x00\x00\x00\x00",
                     #b"\x00\x00\x00\x00\x00\x00\x00",
                     #b"\x00\x00\x00\x00\x00\x00\x00\x00",):
            #m.args = args
            #print(f"{m.command:#x} {m.args.hex()}")
            #mp.comm.device_control(m)

    #mon.poll()
    #mtp.stop()
    #mon.poll()
    #mtp.start()

    #mon.poll()
    #mtp.stop(1)
    ##reset(1)
    ##p.dapf_init_all()

    #mtp.boot()

    run_shell(locals(), poll_func=poll)

finally:
    #mtp.stop()
    p.reboot()
