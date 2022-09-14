# SPDX-License-Identifier: MIT

from m1n1.utils import RegMap
from m1n1.trace.i2c import I2CTracer, I2CRegMapTracer
from m1n1.hw.codecs import *

hv.p.hv_set_time_stealing(0, 1)

class SN012776Tracer(I2CRegMapTracer):
    REGMAP = SN012776Regs
    ADDRESSING = (1, 1)

class TAS5770Tracer(I2CRegMapTracer):
    REGMAP = TAS5770Regs
    ADDRESSING = (1, 1)

class CS42L84Tracer(I2CRegMapTracer):
    REGMAP = CS42L84Regs
    ADDRESSING = (0, 2)

i2c_tracers = {}

for node in hv.adt["/arm-io"]:
    if not node.name.startswith("i2c"):
        continue

    n = int(node.name[3:])
    i2c_tracers[n] = bus = I2CTracer(hv, f"/arm-io/{node.name}")

    for devnode in node:
        if "compatible" not in devnode._properties: # thanks Apple
            continue

        dcls = {
            "audio-control,tas5770": TAS5770Tracer,
            "audio-control,sn012776": SN012776Tracer,
            "audio-control,cs42l84": CS42L84Tracer,
        }.get(devnode.compatible[0], None)
        if dcls:
            bus.add_device(
                devnode.reg[0] & 0xff,
                dcls(name=devnode.name)
            )

    bus.start()
