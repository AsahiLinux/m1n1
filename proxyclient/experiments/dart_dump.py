#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct

from m1n1.setup import *
from m1n1 import asm
from m1n1.hw.dart import DART, DARTRegs

if len(sys.argv) > 1:
    dart_addr = int(sys.argv[1], 16)
else:
    dart_addr = 0x231304000
# disp0 DART
# note that there's another range just before this one
disp0 = DART(iface, DARTRegs(u, dart_addr))
disp0.dump_all()
disp0.regs.dump_regs()
