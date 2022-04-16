# SPDX-License-Identifier: MIT

from ..hw.dart import *
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class DARTTracer(ADTDevTracer):
    RELOAD_DEPS = [DART]

    DEFAULT_MODE = TraceMode.ASYNC

    REGMAPS = [DARTRegs]
    NAMES = ["regs"]

    @classmethod
    def _reloadcls(cls, force=False):
        global DART
        DART = DART._reloadcls(force)
        return super()._reloadcls()

    def start(self):
        super().start()
        # prime cache
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
