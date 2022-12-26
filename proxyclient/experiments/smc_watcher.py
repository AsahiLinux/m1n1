#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, fnmatch, signal
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.fw.smc import SMCClient, SMCError

smc_addr = u.adt["arm-io/smc"].get_reg(0)[0]
smc = SMCClient(u, smc_addr)
smc.start()
smc.start_ep(0x20)

smc.verbose = 0

smcep = smc.epmap[0x20]

count = smcep.read32b("#KEY")
print(f"Key count: {count}")

print("Scanning keys...")

pats = sys.argv[1:]

vals = {}

fmts = {
    "D?CR": "#x",
    "AC-I": "#x",
    "D?FC": "#x",
    "D?VM": lambda v: (v>>8) | ((v&0xff)<<8),
    "D?VX": lambda v: (v>>8) | ((v&0xff)<<8),
    "B0RM": lambda v: (v>>8) | ((v&0xff)<<8),
    ##"BAAC": lambda v: ((v&0xff00)>>8) | ((v&0xff)<<8),
}

smcep.write8("NTAP", 1)

for i in range(count):
    k = smcep.get_key_by_index(i)
    if not any(fnmatch.fnmatchcase(k, i) for i in pats):
        continue
    if any(fnmatch.fnmatchcase('-' + k, i) for i in pats):
        continue
    length, type, flags = smcep.get_key_info(k)
    if type in ("ch8*",  "{jst"):
        continue
    if flags & 0x80:
        try:
            val = smcep.read_type(k, length, type)
            fmt = None
            for fk, fv in fmts.items():
                if fnmatch.fnmatchcase(k, fk):
                    fmt = fv
            if fmt is None:
                fmt = lambda a: ("%.02f" % a) if isinstance(a, float) else a
            elif isinstance(fmt, str):
                def ff(fmt):
                    return lambda a: f"{a:{fmt}}"
                fmt = ff(fmt)
            vals[k] = val, length, type, fmt
            print(f"#{i}: {k} = ({type}, {flags:#x}) {fmt(val)}")
        except SMCError as e:
            print(f"#{i}: {k} = ({type}, {flags:#x}) <error {e}>")
    else:
        print(f"#{i}: {k} = ({type}, {flags:#x}) <not available>")

slots = {}

def poll():
    global cnt
    reprint = cnt % 10 == 0
    changed = set()
    for k, (oval, length, type, fmt) in vals.items():
        val = smcep.read_type(k, length, type)
        if val != oval:
            if k not in slots:
                reprint = True
            slots[k] = fmt(val)
            changed.add(k)
            vals[k] = val, length, type, fmt
    if reprint:
        print("\x1b[1;4m", end="")
        for k, v in slots.items():
            wd = len(f"{v:>8}")
            print(f"{k:>{wd}s}", end=" ")
        print("\x1b[m")
    for k, v in slots.items():
        if k in changed:
            print("\x1b[32m", end="")
        print(f"{v:>8}\x1b[m", end=" ")
    print()
    cnt += 1
    time.sleep(1)

def handle_sigint(signal=None, stack=None):
    global doshell
    doshell = True

signal.signal(signal.SIGINT, handle_sigint)

doshell = False
try:
    cnt = 0
    while True:
        poll()
        if doshell:
            run_shell(globals(), msg="Interrupted")
            doshell = False
finally:
    smc.stop()
    
