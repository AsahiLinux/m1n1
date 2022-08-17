#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import atexit, sys

from m1n1.agx import AGX
from m1n1.agx.render import *

from m1n1.setup import *

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")

agx = AGX(u)

mon = RegMonitor(u, ascii=True, bufsize=0x8000000)
agx.mon = mon

sgx = agx.sgx_dev
#mon.add(sgx.gpu_region_base, sgx.gpu_region_size, "contexts")
#mon.add(sgx.gfx_shared_region_base, sgx.gfx_shared_region_size, "gfx-shared")
#mon.add(sgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

#mon.add(agx.initdasgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

atexit.register(p.reboot)
agx.start()

ctx = GPUContext(agx)
ctx.bind(2)

renderer = GPURenderer(ctx, 256, bm_slot=2, queue=1)

f = GPUFrame(ctx, sys.argv[1], track=False)

renderer.submit(f.cmdbuf)
renderer.wait()

time.sleep(2)
