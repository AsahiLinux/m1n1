#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct

from m1n1.setup import *
from m1n1 import asm

class R_ERROR(Register32):
    FLAG = 31
    STREAM = 27, 24
    CODE = 23, 0
    READ_FAULT = 4
    WRITE_FAULT = 3
    NO_PTE = 2
    NO_PMD = 1
    NO_TTBR = 0

class R_STREAM_COMMAND(Register32):
    INVALIDATE = 20
    BUSY = 2

class R_TCR(Register32):
    BYPASS_DAPF = 12
    BYPASS_DART = 8
    TRANSLATE_ENABLE = 7

class R_TTBR(Register32):
    VALID = 31
    ADDR = 30, 0

class R_REMAP(Register32):
    MAP3 = 31, 24
    MAP2 = 23, 16
    MAP1 = 15, 8
    MAP0 = 7, 0

class DART(RegMap):
    STREAM_COMMAND  = 0x20, R_STREAM_COMMAND
    STREAM_SELECT   = 0x34, Register32
    ERROR           = 0x40, R_ERROR
    ERROR_ADDR_LO   = 0x50, Register32
    ERROR_ADDR_HI   = 0x54, Register32
    REMAP           = irange(0x80, 4, 4), R_REMAP

    TCR             = irange(0x100, 16, 4), R_TCR
    TTBR0           = irange(0x200, 16, 16), R_TTBR
    TTBR1           = irange(0x204, 16, 16), R_TTBR
    TTBR2           = irange(0x208, 16, 16), R_TTBR
    TTBR3           = irange(0x20c, 16, 16), R_TTBR

    def __init__(self, base):
        super().__init__(u, base)
        self.base = base

    def dump_table2(self, base, l1_addr):
        tbl = iface.readmem(l1_addr, 0x4000)

        for i in range(0, len(tbl)//8):
            pte = struct.unpack("<Q",tbl[i*8:i*8+8])[0]
            if not (pte & 0b01):
                #print("    page (%d): %08x ... %08x -> DISABLED" % (i, base + i*0x4000, base + (i+1)*0x4000))
                continue

            print("    page (%d): %08x ... %08x -> %016x [%s]" % (i, base + i*0x4000, base + (i+1)*0x4000, pte&~0b11, bin(pte&0b11)))

    def dump_table(self, base, l1_addr):
        tbl = iface.readmem(l1_addr, 0x4000)

        for i in range(0, len(tbl)//8):
            pte = struct.unpack("<Q",tbl[i*8:i*8+8])[0]
            if not (pte & 0b01):
                #print("  table (%d): %08x ... %08x -> DISABLED" % (i, base + i*0x2000000, base + (i+1)*0x2000000))
                continue

            print("  table (%d): %08x ... %08x -> %016x [%s]" % (i, base + i*0x2000000, base + (i+1)*0x2000000, pte&~0b11, bin(pte&0b11)))
            self.dump_table2(base + i*0x2000000, pte & ~0b11)

    def dump_ttbr(self, idx, ttbr):
        if not ttbr.VALID:
            return

        l1_addr = (ttbr.ADDR) << 12
        print("  TTBR%d: %09x" % (idx, l1_addr))

        self.dump_table(0, l1_addr)


    def dump_device(self, idx):
        tcr = self.TCR[idx].reg
        ttbrs = self.TTBR0[idx], self.TTBR1[idx], self.TTBR2[idx], self.TTBR3[idx]
        print(f"dev {idx:02x}: TCR={tcr!s} TTBRs = [{', '.join(map(str, ttbrs))}]")

        if tcr.TRANSLATE_ENABLE and tcr.BYPASS_DART:
            print("  mode: INVALID")
        elif tcr.TRANSLATE_ENABLE:
            print("  mode: TRANSLATE")

            for idx, ttbr in enumerate(ttbrs):
                self.dump_ttbr(idx, ttbr.reg)
        elif tcr.BYPASS_DART:
            print("  mode: BYPASS")
        else:
            print("  mode: UNKNOWN")

    def dump_all(self):
        for i in range(16):
            self.dump_device(i)

if len(sys.argv) > 1:
    dart_addr = int(sys.argv[1], 16)
else:
    dart_addr = 0x231304000
# disp0 DART
# note that there's another range just before this one
disp0 = DART(dart_addr)
disp0.dump_all()
disp0.dump_regs()
