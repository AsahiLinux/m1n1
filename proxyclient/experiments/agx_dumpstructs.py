#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.constructutils import *
from m1n1.fw.agx import microsequence, initdata

#for v in initdata.__all__:
#for v in initdata.__dict__:
def dump(module):
    for v in module.__dict__:
        struct = getattr(module, v)
        if isinstance(struct, type) and issubclass(struct, ConstructClass) and struct is not ConstructClass:
            print(struct.to_rust())
            print()

dump(microsequence)
