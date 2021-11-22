#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from m1n1.setup import *
from m1n1.fw.smc import SMCClient

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr)
smc.start()
smc.start_ep(0x20)

smcep = smc.epmap[0x20]

def gpio_key(pin):
    assert(pin < (1 << 16))

    fourcc = 'gP' + ('00'+(hex(pin)[2:]))[-2:]
    return fourcc

# Enable wifi/bluetooth
RFKILL_PIN = 13
smcep.write(gpio_key(RFKILL_PIN), struct.pack('<I', 0x800000 | 0x0))
smcep.write(gpio_key(RFKILL_PIN), struct.pack('<I', 0x800000 | 0x1))
