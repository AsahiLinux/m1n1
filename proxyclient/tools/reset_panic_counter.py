import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.spmi import SPMI

s = SPMI(u, "/arm-io/nub-spmi")
leg_scrpad = 0x9f00
s.write8(15, leg_scrpad + 2, 0) # error counts
