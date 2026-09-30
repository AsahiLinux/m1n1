# SPDX-License-Identifier: GPL-2.0-or-later

from ..hw.spi import *
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class SPITracer(ADTDevTracer):
    REGMAPS = [SPIRegs]
    NAMES = ["spi"]
