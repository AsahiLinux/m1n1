#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.fw.smc import SMCClient

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr, None)

smc.start()
smc.start_ep(0x20)

smc.smcep.write32("gP0d", 0x800001)
smc.smcep.write32("gP1a", 1)

smc.stop()
