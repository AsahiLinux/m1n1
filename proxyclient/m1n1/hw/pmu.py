# SPDX-License-Identifier: MIT
import struct

from ..utils import *
from .spmi import SPMI

__all__ = ["PMU"]

class PMU:

    def __init__(self, u, adt_path=None):
        self.u = u
        if adt_path is None:
            adt_path = PMU.find_primary_pmu(u.adt)

        self.spmi = SPMI(u, adt_path.rpartition('/')[0])
        self.adt_path = adt_path
        self.primary = getattr(u.adt[adt_path], "is-primary") == 1

    def reset_panic_counter(self):
        if self.primary:
            leg_scrpad = self.u.adt[self.adt_path].info_leg__scrpad[0]
            self.spmi.write8(15, leg_scrpad + 2, 0) # error counts

    @staticmethod
    def find_primary_pmu(adt):
        for child in adt["/arm-io"]:
            if child.name.startswith("nub-spmi"):
                for pmu in child:
                    compat = getattr(pmu, "compatible")[0] if hasattr(pmu, "compatible") else "unset"
                    primary = (getattr(pmu, "is-primary") == 1) if hasattr(pmu, "is-primary")  else False
                    if compat == "pmu,spmi" and primary:
                        return pmu._path.removeprefix('/device-tree')
        raise KeyError(f"primary 'pmu,spmi' node not found")
