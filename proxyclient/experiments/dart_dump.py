#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct

from m1n1.setup import *
from m1n1 import asm
from m1n1.hw.dart import DART
from m1n1.hw.dart8110 import DART8110

if len(sys.argv) > 1:
    dart_path = "/arm-io/" + sys.argv[1]
else:
    dart_path = "/arm-io/dart-disp0"

if u.adt[dart_path].compatible[0] == "dart,t8110":
    dart = DART8110.from_adt(u, dart_path)
else:
    dart = DART.from_adt(u, dart_path)

dart.dump_all()
dart.regs.dump_regs()
