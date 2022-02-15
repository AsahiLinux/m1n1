#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from m1n1.setup import *
from m1n1.fw.smc import SMCClient, SMCError

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr)
smc.start()
smc.start_ep(0x20)

smc.verbose = 0

smcep = smc.epmap[0x20]

def gpio_key(pin):
    assert(pin < (1 << 16))

    fourcc = 'gP' + ('00'+(hex(pin)[2:]))[-2:]
    return fourcc

## Enable wifi/bluetooth
#RFKILL_PIN = 13
#smcep.write(gpio_key(RFKILL_PIN), struct.pack('<I', 0x800000 | 0x0))
#smcep.write(gpio_key(RFKILL_PIN), struct.pack('<I', 0x800000 | 0x1))

count = smcep.read32b("#KEY")
print(f"Key count: {count}")

for i in range(count):
    k = smcep.get_key_by_index(i)
    length, type, flags = smcep.get_key_info(k)
    if flags & 0x80:
        try:
            val = smcep.read_type(k, length, type)
            print(f"#{i}: {k} = ({type}, {flags:#x}) {val}")
        except SMCError as e:
            print(f"#{i}: {k} = ({type}, {flags:#x}) <error {e}>")
    else:
        print(f"#{i}: {k} = ({type}, {flags:#x}) <not available>")


smc.stop()
