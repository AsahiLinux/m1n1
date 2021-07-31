#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct

from m1n1.setup import *
from m1n1 import asm
from m1n1.hw.dart import DART, DARTRegs

dart_addr = u.adt["arm-io/dart-dcp"].get_reg(0)[0]
disp0 = DART(iface, DARTRegs(u, dart_addr), u)
disp0.dump_all()
disp0.regs.dump_regs()

buf = u.memalign(16384, 65536)

disp0.iomap(0, 0x08010000, buf, 65536)
assert disp0.iotranslate(0, 0x08010000, 65536) == [(buf, 65536)]

disp0.dump_all()
