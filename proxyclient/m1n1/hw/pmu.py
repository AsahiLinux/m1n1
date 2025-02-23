# SPDX-License-Identifier: MIT
import struct

from ..utils import *
from .spmi import SPMI
from .i2c import I2C

__all__ = ["PMU"]

class PMU:

    def __init__(self, u, adt_path=None):
        self.u = u
        if adt_path is None:
            (adt_path, bus_type) = PMU.find_primary_pmu(u.adt)

        self.node = u.adt[adt_path]
        self.bus_type = bus_type
        if bus_type == "spmi":
            self.spmi = SPMI(u, adt_path.rpartition('/')[0])
            self.primary = u.adt[adt_path].is_primary == 1
        elif bus_type == "i2c":
            self.i2c = I2C(u, adt_path.rpartition('/')[0])
            self.primary = u.adt[adt_path].name == "pmu"
        self.adt_path = adt_path
        self.reg = u.adt[adt_path].reg[0]

    def reset_panic_counter(self):
        if self.primary and self.bus_type == "spmi":
            leg_scrpad = self.node.info_leg__scrpad[0]
            self.spmi.write8(self.reg, leg_scrpad + 2, 0) # error counts
        elif self.primary and self.bus_type == "i2c":
            if self.node.compatible[0] in ["pmu,d2255", "pmu,d2257", "pmu,d2333", "pmu,d2365", "pmu,d2400"]:
                counter = 0x5002
            elif self.node.compatible[0] in ["pmu,d2045", "pmu,d2089", "pmu,d2186", "pmu,d2207"]:
                counter = 0x4002
            else:
                print("Reset panic unsupported")
                return
            self.i2c.write_reg(self.reg, counter, [0], regaddrlen=2)
        else:
            raise ValueError("Unsupported bus type") # should never happen

    @staticmethod
    def find_primary_pmu(adt):
        for child in adt["/arm-io"]:
            if child.name.startswith("nub-spmi") or child.name.startswith("spmi"):
                for pmu in child:
                    compat = getattr(pmu, "compatible")[0] if hasattr(pmu, "compatible") else "unset"
                    primary = (getattr(pmu, "is-primary") == 1) if hasattr(pmu, "is-primary")  else False
                    if compat in ("pmu,spmi", "pmu,d2422", "pmu,d2449") and primary:
                        return (pmu._path.removeprefix('/device-tree'), "spmi")
            elif child.name.startswith("i2c"):
                for dev in child:
                    if dev.name == "pmu":
                        return (dev._path.removeprefix('/device-tree'), "i2c")
        raise KeyError(f"primary pmu node not found")
