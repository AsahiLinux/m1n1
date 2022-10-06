# SPDX-License-Identifier: MIT
from .bootargs import ASCArgumentSection

class AOPBase:
    def __init__(self, u, adtnode):
        self.fw_base, self.fw_len = adtnode.get_reg(2)
        if u.adt["arm-io"].compatible[0] == "arm-io,t6000":
            # argh
            self.fw_base -= 0x2_0000_0000

    @property
    def _bootargs_span(self):
        base = self.fw_base + self.u.proxy.read32(self.fw_base + 0x224)
        length = self.u.proxy.read32(self.fw_base + 0x228)

        return (base, length)

    def read_bootargs(self):
        blob = self.u.proxy.iface.readmem(*self._bootargs_span)
        return ASCArgumentSection(blob)

    def write_bootargs(self, args):
        base, _ = self._bootargs_span
        self.u.proxy.iface.writemem(base, args.to_bytes())

    def update_bootargs(self, keyvals):
        args = self.read_bootargs()
        args.update(keyvals)
        self.write_bootargs(args)

__all__ = ["ASCArgumentSection", "AOPBase"]
