#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.shell import run_shell

from m1n1.fw.ane import ANE

import numpy as np
from anect import anect_convert  # pip install anect
def f16encode(x): return np.float16(x).tobytes()
def f16decode(b): return np.frombuffer(b[:2], dtype=np.float16)[0]


ane = ANE(u)
ane.power_up()
if 1:
	rnges = [(0x26bc04000, 0x26bc28000, 'engine'),]
	mon = RegMonitor(u)
	for (start, end, name) in rnges:
		mon.add(start, end-start, name=name)
	mon.poll() # should work after ane.power_up()

# curl -LJO https://www.dropbox.com/s/lpjap6w0kdlom1h/add.hwx?dl=0
anec = anect_convert("add.hwx")
req = ane.fw.setup(anec)

x1 = f16encode(1.0)
x2 = f16encode(2.0)
ane.fw.send_src(req, x1, 0)
ane.fw.send_src(req, x2, 1)

ane.tm.enqueue_tq(req)
ane.tm.execute_tq(req)

x3 = ane.fw.read_dst(req, 0)
print("what's 1+2? = %f" % f16decode(x3[:2]))


run_shell(globals(), msg="Have fun!")

