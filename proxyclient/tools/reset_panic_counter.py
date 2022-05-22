#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.spmi import SPMI

compatible = u.adt["/arm-io"].compatible[0]

if compatible == "arm-io,t6000":
    s = SPMI(u, "/arm-io/nub-spmi0")
    leg_scrpad = u.adt["/arm-io/nub-spmi0/spmi-mpmu"].info_leg__scrpad[0]
elif compatible == "arm-io,t8103":
    s = SPMI(u, "/arm-io/nub-spmi")
    leg_scrpad = u.adt["/arm-io/nub-spmi/spmi-pmu"].info_leg__scrpad[0]
else:
    print(f"Unknown SoC comaptible '{compatible}'")
    exit()

s.write8(15, leg_scrpad + 2, 0) # error counts
