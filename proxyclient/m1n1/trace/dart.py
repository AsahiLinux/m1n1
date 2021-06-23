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
    def _reloadcls(cls):
        global DART
        DART = DART._reloadcls()
        return super()._reloadcls()

    def start(self):
        super().start()
        self.dart = DART(self.hv.iface, self.regs.cached)

    def w_STREAM_COMMAND(self, stream_command):
        if stream_command.INVALIDATE:
            self.log(f"Invalidate Stream: {self.regs.cached.STREAM_SELECT.reg}")
            self.dart.invalidate_cache()
