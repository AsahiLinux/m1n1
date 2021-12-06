# SPDX-License-Identifier: MIT

from ..hw.spi import *
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class SPITracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.UNBUF

    REGMAPS = [SPIRegs]
    NAMES = ["spi"]
