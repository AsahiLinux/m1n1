# SPDX-License-Identifier: MIT

class Tracer:
    def __init__(self, hv):
        self.hv = hv
        self.ident = type(self).__name__
        super().__init__()

class PrintTracer(Tracer):
    def __init__(self, hv, device_addr_tbl):
        super().__init__(hv)
        self.device_addr_tbl = device_addr_tbl

    def event_mmio(self, evt):
        dev, zone = self.device_addr_tbl.lookup(evt.addr)
        t = "W" if evt.flags.WRITE else "R"
        m = "+" if evt.flags.MULTI else " "
        print(f"[0x{evt.pc:016x}] MMIO: {t}.{1<<evt.flags.WIDTH:<2}{m} " +
              f"0x{evt.addr:x} ({dev}, offset {evt.addr - zone.start:#04x}) = 0x{evt.data:x}")
