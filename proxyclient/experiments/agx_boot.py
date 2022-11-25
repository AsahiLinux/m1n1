#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.constructutils import Ver
from m1n1.utils import *

Ver.set_version(u)

from m1n1.shell import run_shell

from m1n1.fw.agx import Agx

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")

agx = Agx(u)
agx.verbose = 10

#agx.uat.dump(0)

agx.build_initdata()

run_shell(globals(), msg="Have fun!")
