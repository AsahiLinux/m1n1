from m1n1.trace import ADTDevTracer
from m1n1.trace.dart8110 import DART8110Tracer
from m1n1.hw.prores import *
from m1n1.utils import *
import struct

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

    def w_DR_TAIL(self, val):
        self.log(f"DR_TAIL = {val}")
        self._dr_tail = val

    def w_DR_HEAD(self, val):
        self.log(f"DR_HEAD = {val}")
        self.dart_tracer.dart.dump_all()

        dr_addr = int(self._dr_addr_hi) << 32 | int(self._dr_addr_lo)
        dr_size = int(self._dr_size)
        self.log(f"desc ring @ {dr_addr:016X} sz {dr_size:08X}")

        dr = self.dart_tracer.dart.ioread(0, dr_addr, dr_size)
        chexdump(dr)

        # FIXME there are other descriptor types
        # also, what if there are multiple in the ring?
        dr_head = int(val)
        dr_tail = int(self._dr_tail)

        if dr_head - dr_tail == 0x180:
            desc = EncodeNotRawDescriptor._make(struct.unpack(ENCODE_NOT_RAW_STRUCT, dr[dr_tail:dr_head]))
            print(desc)

            p0_iova = desc.luma_iova
            p1_iova = desc.chroma_iova
            p2_iova = desc.alpha_iova

            if p0_iova:
                print(f"P0 iova {p0_iova:016X}")
                data = self.dart_tracer.dart.ioread(0, p0_iova, 0x1000)
                chexdump(data)
            if p1_iova:
                print(f"P1 iova {p1_iova:016X}")
                data = self.dart_tracer.dart.ioread(0, p1_iova, 0x1000)
                chexdump(data)
            if p2_iova:
                print(f"P2 iova {p2_iova:016X}")
                data = self.dart_tracer.dart.ioread(0, p2_iova, 0x1000)
                chexdump(data)


ProResTracer = ProResTracer._reloadcls()

p.pmgr_adt_clocks_enable('/arm-io/apr0')
p.pmgr_adt_clocks_enable('/arm-io/apr1')

tracer0 = ProResTracer(hv, '/arm-io/apr0', dart0_tracer)
tracer0.start()
print(tracer0)
tracer1 = ProResTracer(hv, '/arm-io/apr1', dart1_tracer)
tracer1.start()
print(tracer1)
