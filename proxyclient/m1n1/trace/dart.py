# SPDX-License-Identifier: MIT

from ..hw.dart import *
from ..hw.dart8020 import *
from ..hw.dart8110 import *
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class DARTTracer(ADTDevTracer):

    DEFAULT_MODE = TraceMode.ASYNC

    NAMES = ["regs"]

    @classmethod
    def _reloadcls(cls, force=False):
        global DART8020
        global DART8020Regs
        global DART8110
        global DART8110Regs
        DART8020 = DART8020._reloadcls(force)
        DART8020Regs = DART8020Regs._reloadcls(force)
        DART8110 = DART8110._reloadcls(force)
        DART8110Regs = DART8110Regs._reloadcls(force)
        return super()._reloadcls(force)

    def __init__(self, hv, devpath, **kwargs):
        compat = hv.adt[devpath].compatible[0]
        if compat in ["dart,t6000", "dart,t8020"]:
            self.REGMAPS = [DART8020Regs]
        elif compat in ["dart,t8110"]:
            self.REGMAPS = [DART8110Regs]

        return super().__init__(hv, devpath, **kwargs)

    def start(self):
        super().start()
        # prime cache
        if self.dev.compatible[0] == "dart,t8110":
            for i in range(16):
                self.regs.TCR[i].val
                self.regs.TTBR[i].val
            for _ in range(8):
                self.regs.ENABLE_STREAMS[_].val
        else:
            for i in range(16):
                self.regs.TCR[i].val
                for j in range(4):
                    self.regs.TTBR[i, j].val
            self.regs.ENABLED_STREAMS.val

        self.dart = DART(self.hv.iface, self.regs, compat=self.dev.compatible[0])


    def w_STREAM_COMMAND(self, stream_command):
        if stream_command.INVALIDATE:
            self.log(f"Invalidate Stream: {self.regs.cached.STREAM_SELECT.reg}")
            self.dart.invalidate_cache()

    def w_TLB_OP(self, tlb_op):
        if tlb_op.OP == 0:
            self.log(f"Invalidate all")
            self.dart.invalidate_cache()
        elif tlb_op.OP == 1:
            self.log(f"Invalidate Stream: {tlb_op.STREAM}")
            self.dart.invalidate_cache()
        else:
            self.log(f"Unknown TLB op {tlb_op}")
