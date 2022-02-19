#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct

from m1n1.setup import *
from m1n1 import asm
from m1n1.hw.dart import DART, DARTRegs

if len(sys.argv) > 1:
    dart_name = sys.argv[1]
else:
    dart_name = "dart-disp0"

# disp0 DART
# note that there's another range just before this one
disp0 = DART.from_adt(u, "arm-io/" + dart_name)
disp0.dump_all()
disp0.regs.dump_regs()
