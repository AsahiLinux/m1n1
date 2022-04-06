from m1n1.trace import ADTDevTracer
from m1n1.trace.dart8110 import DART8110Tracer
from m1n1.hw.prores import *
from m1n1.utils import *

p.pmgr_adt_clocks_enable('/arm-io/dart-apr0')
p.pmgr_adt_clocks_enable('/arm-io/dart-apr1')

dart0_tracer = DART8110Tracer(hv, "/arm-io/dart-apr0", verbose=1)
dart0_tracer.start()
print(dart0_tracer)
dart1_tracer = DART8110Tracer(hv, "/arm-io/dart-apr1", verbose=1)
dart1_tracer.start()
print(dart1_tracer)


class ProResTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC
    REGMAPS = [ProResRegs]
    NAMES = ['prores']

    def __init__(self, hv, devpath, dart_tracer):
        super().__init__(hv, devpath, verbose=3)
        self.dart_tracer = dart_tracer

    def w_DR_SIZE(self, val):
        self._dr_size = val

    def w_DR_ADDR_HI(self, val):
        self._dr_addr_hi = val

    def w_DR_ADDR_LO(self, val):
        self._dr_addr_lo = val

    def w_DR_HEAD(self, val):
        self.log(f"DR_HEAD = {val}")
        self.dart_tracer.dart.dump_all()

        dr_addr = int(self._dr_addr_hi) << 32 | int(self._dr_addr_lo)
        dr_size = int(self._dr_size)
        self.log(f"desc ring @ {dr_addr:016X} sz {dr_size:08X}")

        dr = self.dart_tracer.dart.ioread(0, dr_addr, dr_size)
        chexdump(dr)


ProResTracer = ProResTracer._reloadcls()

p.pmgr_adt_clocks_enable('/arm-io/apr0')
p.pmgr_adt_clocks_enable('/arm-io/apr1')

tracer0 = ProResTracer(hv, '/arm-io/apr0', dart0_tracer)
tracer0.start()
print(tracer0)
tracer1 = ProResTracer(hv, '/arm-io/apr1', dart1_tracer)
tracer1.start()
print(tracer1)
