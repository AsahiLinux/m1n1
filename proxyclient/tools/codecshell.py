#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse

parser = argparse.ArgumentParser(description='Enter a shell for codec-poking')
parser.add_argument('-n', '--no-reset', action="store_true")
args = parser.parse_args()

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.hw.i2c import I2C, I2CRegMapDev
from m1n1.hw.codecs import *

i2c = {}

class TAS5770(I2CRegMapDev):
    REGMAP     = TAS5770Regs
    ADDRESSING = (1, 1)

class SN012776(I2CRegMapDev):
    REGMAP     = SN012776Regs
    ADDRESSING = (1, 1)

class CS42L84(I2CRegMapDev):
    REGMAP     = CS42L84Regs
    ADDRESSING = (0, 2)

gpios = {}
for node in u.adt["/arm-io"]:
    if node.name.endswith("gpio") or node.name.endswith("gpio0"):
        gpios[node._properties["AAPL,phandle"]] = node

spks = []
for node in u.adt["/arm-io"]:
    if not node.name.startswith("i2c"):
        continue

    n = int(node.name[3:])
    i2c[n] = bus = I2C(u, f"/arm-io/{node.name}")

    for devnode in node:
        if "compatible" not in devnode._properties:
            continue

        dcls = {
            "audio-control,tas5770": TAS5770,
            "audio-control,sn012776": SN012776,
            "audio-control,cs42l84": CS42L84,
        }.get(devnode.compatible[0], None)

        if not dcls:
            continue

        dev = dcls.from_adt(bus, f"/arm-io/{node.name}/{devnode.name}")
        dev.node = devnode
        i2c[n].devs.append(dev)

        if type(dev) in [TAS5770, SN012776]:
            spks.append(dev)
        else:
            hp = dev

        if "function-reset" in devnode._properties:
            prop = devnode.function_reset
            gpio_host = gpios[prop.phandle]
            addr = gpio_host.get_reg(0)[0] + prop.args[0] * 4
            if not args.no_reset:
                print(f"Releasing #RST of {devnode.name}")
                p.mask32(addr, 1, 0)
            print(f"Pulling #RST of {devnode.name}")
            p.mask32(addr, 1, 1)

        if "interrupts" in devnode._properties \
                and devnode.interrupt_parent in gpios:
            gpio_host = gpios[devnode.interrupt_parent]
            addr = gpio_host.get_reg(0)[0] + devnode.interrupts[0] * 4
            print(f"Monitoring IRQ of {devnode.name}")
            mon.add(addr, 4)

run_shell(globals(), msg="Have fun!")
