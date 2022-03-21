#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import serial
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

from m1n1 import adt

parser = argparse.ArgumentParser(description='Convert ADT PMGR nodes to Device Tree format')
parser.add_argument('input', type=pathlib.Path)
args = parser.parse_args()

adt_data = args.input.read_bytes()
dt = adt.load_adt(adt_data)

pmgr = dt["/arm-io/pmgr"]

dev_by_id = {dev.id: dev for dev in pmgr.devices}

blocks = {}
maxaddr = {}

for i, dev in enumerate(pmgr.devices):
    if dev.flags.no_ps:
        continue
    ps = pmgr.ps_regs[dev.psreg]
    block = pmgr.get_reg(ps.reg)
    blocks.setdefault(block, []).append(dev)
    offset = ps.offset + dev.psidx * 8
    maxaddr[block[0]] = max(maxaddr.get(block[0], 0), offset)

pmgr_compat = pmgr.compatible[0].split(",")[1]
compatible = f'"apple,{pmgr_compat}-pmgr", "apple,pmgr", "syscon", "simple-mfd"'
ps_compatible = f'"apple,{pmgr_compat}-pmgr-pwrstate", "apple,pmgr-pwrstate"'

for i, ((base, size), devices) in enumerate(sorted(blocks.items())):

    size = min(size, (maxaddr[base] + 0x3fff) & ~0x3fff)

    print(f"pmgr{i}: power-management@{base:x} {{")
    print(f"\tcompatible = {compatible};")
    print( "\t#address-cells = <1>;")
    print( "\t#size-cells = <1>;")
    print()
    print(f"\treg = <{base >> 32:#x} {base & 0xffffffff:#x} 0 {size:#x}>;")
    print( "};")
    print()

for i, ((base, size), devices) in enumerate(sorted(blocks.items())):
    print(f"&pmgr{i} {{")

    for dev in sorted(devices, key=lambda d: pmgr.ps_regs[d.psreg].offset + dev.psidx * 8):
        if dev.flags.no_ps:
            continue

        ps = pmgr.ps_regs[dev.psreg]
        offset = ps.offset + dev.psidx * 8
        addr = pmgr.get_reg(ps.reg)[0] + offset
        assert base <= addr <= (base + size)

        print()
        print(f"\tps_{dev.name.lower()}: power-controller@{offset:x} {{")
        print(f"\t\tcompatible = {ps_compatible};")
        print(f"\t\treg = <{offset:#x} 4>;")
        print( "\t\t#power-domain-cells = <0>;")
        print( "\t\t#reset-cells = <0>;")
        print(f'\t\tlabel = "{dev.name.lower()}";')
        if dev.flags.critical:
            print("\t\tapple,always-on;")

        if any(dev.parents):
            domains = [f"<&ps_{dev_by_id[idx].name.lower()}>" for idx in dev.parents if idx]
            print(f"\t\tpower-domains = {', '.join(domains)};")

        print( "\t};")
    print( "};")
    print()
