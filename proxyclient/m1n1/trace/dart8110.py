# SPDX-License-Identifier: MIT

from ..hw.dart8110 import *
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class DART8110Tracer(ADTDevTracer):
    RELOAD_DEPS = [DART8110]

    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [DART8110Regs]
    NAMES = ["regs"]

    @classmethod
    def _reloadcls(cls):
        global DART8110
        DART8110 = DART8110._reloadcls()
        return super()._reloadcls()

    def start(self):
        super().start()
        # prime cache
        for i in range(16):
            self.regs.TCR[i].val
            self.regs.TTBR[i].val

        for _ in range(8):
            self.regs.ENABLE_STREAMS[0].val

        self.dart = DART8110(self.hv.iface, self.regs)


    def w_TLB_OP(self, tlb_op):
        if tlb_op.OP == 0:
            self.log(f"Invalidate all")
            self.dart.invalidate_cache()
        elif tlb_op.OP == 1:
            self.log(f"Invalidate Stream: {tlb_op.STREAM}")
            self.dart.invalidate_cache()
        else:
            self.log(f"Unknown TLB op {tlb_op}")
