#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from construct import *

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.hw.dart import DART, DARTRegs
from m1n1.fw.asc import StandardASC, ASCDummyEndpoint
from m1n1.fw.asc.base import *
from m1n1.fw.aop import *

class OSLogMessage(Register64):
    TYPE        = 63, 56

class OSLog_Init(OSLogMessage):
    TYPE        = 63, 56, Constant(1)
    UNK         = 51, 0
    DVA         = 7, 0

class AOPOSLogEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = OSLogMessage
    SHORT = "oslog"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = False

    @msg_handler(1, OSLog_Init)
    def Init(self, msg):
        self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(0x1_0000)
        self.send(OSLog_Init(DVA=self.iobuffer_dva//0x1000))
        self.started = True
        return True

class AOPClient(StandardASC):
    ENDPOINTS = {
        8: AOPOSLogEndpoint,

        0x20: ASCDummyEndpoint,
        0x21: ASCDummyEndpoint,
        0x22: ASCDummyEndpoint,
        0x23: ASCDummyEndpoint,
        0x24: ASCDummyEndpoint,
        0x25: ASCDummyEndpoint,
        0x26: ASCDummyEndpoint,
        0x27: ASCDummyEndpoint,
        0x28: ASCDummyEndpoint
    }

    def __init__(self, u, adtpath, dart=None):
        node = u.adt[adtpath]
        self.base = node.get_reg(0)[0]
        self.fw_base, self.fw_len = node.get_reg(2)

        if u.adt["arm-io"].compatible[0] == "arm-io,t6000":
            # argh
            self.fw_base -= 0x2_0000_0000

        super().__init__(u, self.base, dart)

    @property
    def _bootargs_span(self):
        base = self.fw_base + self.p.read32(self.fw_base + 0x224)
        length = self.p.read32(self.fw_base + 0x228)

        return (base, length)

    def read_bootargs(self):
        blob = self.iface.readmem(*self._bootargs_span)
        return ASCArgumentSection(blob)

    def write_bootargs(self, args):
        base, _ = self._bootargs_span
        self.iface.writemem(base, args.to_bytes())

    def update_bootargs(self, keyvals):
        args = self.read_bootargs()
        args.update(keyvals)
        self.write_bootargs(args)

p.dapf_init_all()

dart = DART.from_adt(u, "/arm-io/dart-aop")
dart.initialize()

dart.regs.TCR[0].set( BYPASS_DAPF=0, BYPASS_DART=0, TRANSLATE_ENABLE=1)
dart.regs.TCR[15].set(BYPASS_DAPF=0, BYPASS_DART=1, TRANSLATE_ENABLE=0)

aop = AOPClient(u, "/arm-io/aop", dart)

aop.update_bootargs({
    'p0CE': 0x20000,
#    'laCn': 0x0,
#    'tPOA': 0x1,
})

aop.verbose = 4

try:
    aop.boot()
except KeyboardInterrupt:
    pass

run_shell(locals())
