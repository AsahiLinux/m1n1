#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import atexit, sys

from m1n1.setup import *
from m1n1.constructutils import Ver
from m1n1.utils import *

Ver.set_version(u)

from m1n1.agx import AGX
from m1n1.agx.render import *

from m1n1 import asm

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")

agx = AGX(u)
mon = RegMonitor(u, ascii=True, bufsize=0x8000000)
agx.mon = mon

sgx = agx.sgx_dev

try:
    agx.start()
    agx.uat.dump(0)

    print("==========================================")
    print("## After init")
    print("==========================================")
    mon.poll()
    agx.poll_objects()

    ctx = GPUContext(agx)
    ctx.bind(63)

    f = GPUFrame(ctx, sys.argv[1], track=False)

    r = GPURenderer(ctx, 16, bm_slot=0, queue=1)
    print("==========================================")
    print("## Submitting")
    print("==========================================")

    w = r.submit(f.cmdbuf)

    print("==========================================")
    print("## Submitted")
    print("==========================================")

    print("==========================================")
    print("## Run")
    print("==========================================")

    r.run()

    while not r.ev_3d.fired:
        agx.asc.work()
        agx.poll_channels()

    agx.poll_objects()
    mon.poll()
    r.wait()

    time.sleep(3)

finally:
    #agx.poll_objects()
    p.reboot()
