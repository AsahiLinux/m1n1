#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.fw.smc import SMCClient

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr, None)
smc.verbose = 3

smc.start()
smc.start_ep(0x20)

smcep = smc.epmap[0x20]

# dp2hdmi-gpio.function-reset - not used at all by macos
# smcep.write('gP09', struct.pack("<I", 0x100001))
# smcep.write('gP09', struct.pack("<I", 0x100000))
smcep.write('gP16', struct.pack("<I", 0x800001))
smcep.write('gP15', struct.pack("<I", 0x800001))

force_dfp_pin = 0x28
hpd_pin = 0x31

gpio = u.adt["/arm-io/aop-gpio"]
base, size = gpio.get_reg(0)

print(f"gpio base: {base:#x}")

# macos reads force_dfp_pin only?
# p.write32(base + force_dfp_pin*4, 0x76a03)
p.write32(base + hpd_pin*4, 0x54b8d)

hdmi_hpd = p.read32(base + hpd_pin*4) & 0x1
print(f"HDMI hpd:{hdmi_hpd}")

# manual display config
config = u.malloc(256)
p.iface.writemem(config, b'1920x1080@60\0')
p.display_configure(config)

run_shell(globals(), msg="Have fun!")
