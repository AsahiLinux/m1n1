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

class ASCArgumentSection:
    def __init__(self, bytes_):
        self.blob = bytearray(bytes_)
        self.index = self.build_index()

    def build_index(self):
        off = 0
        fields = []
        while off < len(self.blob):
            snip = self.blob[off:]
            key = snip[0:4]
            length = int.from_bytes(snip[4:8], byteorder='little')
            fields.append((key.decode('ascii'), (off + 8, length)))
            off += 8 + length

        if off > len(self.blob):
            raise ValueError('blob overran during parsing')

        return dict(fields)

    def items(self):
        for key, span in self.index.items():
            off, length = span
            yield key, self.blob[off:off + length]

    def __getitem__(self, key):
        off, length = self.index[key]
        return bytes(self.blob[off:off + length])

    def __setitem__(self, key, value):
        off, length = self.index[key]

        if type(value) is int:
            value = int.to_bytes(value, length, byteorder='little')
        elif type(value) is str:
            value = value.encode('ascii')

        if len(value) > length:
            raise ValueError(f'field {key:s} overflown')

        self.blob[off:off + length] = value

    def update(self, keyvals):
        for key, val in keyvals.items():
            self[key] = val

    def keys(self):
        return self.index.keys()

    def dump(self):
        for key, val in self.items():
            print(f"{key:4s} = {val}")

    def dump_diff(self, other):
        assert self.index == other.index

        for key in self.keys():
            if self[key] != other[key]:
                print(f"Differs: {key:4s} = {self[key]} / {other[key]}")

    def to_bytes(self):
        return bytes(self.blob)


class AOPClient(StandardASC):
    ENDPOINTS = {
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

    def _bootargs_span(self):
        base = self.fw_base + self.p.read32(self.fw_base + 0x224)
        length = self.p.read32(self.fw_base + 0x228)

        return (base, length)

    def read_bootargs(self):
        blob = self.iface.readmem(*self._bootargs_span())
        return ASCArgumentSection(blob)

    def write_bootargs(self, args):
        base, _ = self._bootargs_span()
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
