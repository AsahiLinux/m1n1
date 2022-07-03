#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1 import adt
from m1n1.setup import *
from m1n1.hw.nco import NCO

dt = u.adt

pmgr = dt["/arm-io/pmgr"]

dev_by_id = {dev.id: dev for dev in pmgr.devices}
pd_by_id = {pd.id: pd for pd in pmgr.power_domains}
clk_by_id = {clk.id: clk for clk in pmgr.clocks}

print("=== PS Regs ===")
for i, r in enumerate(pmgr.ps_regs):
    print(f" #{i:2d} reg: {r.reg} off: {r.offset:05x} mask:{r.mask:08x}")

print()
print("=== Perf Regs ===")
for i, r in enumerate(pmgr.perf_regs):
    print(f" #{i:2d} reg: {r.reg} off: {r.offset:05x} size:{r.size:05x} unk:{r.unk:08x}")

#print()
#print("=== PWR Gate Regs ===")
#for i, r in enumerate(pmgr.pwrgate_regs):
    #print(f" #{i:2d} reg: {r.reg} off: {r.offset:05x} mask:{r.mask:08x} unk:{r.unk:08x}")

clock_users = {}
dev_users = {}

for dev in dt["/arm-io"]:
    if hasattr(dev, "clock_ids") and dev.clock_ids:
        for i, clk in enumerate(dev.clock_ids):
            clock_users.setdefault(clk, []).append(f"{dev._path}.clk[{i}]")
    if hasattr(dev, "clock_gates") and dev.clock_gates:
        for i, pdev in enumerate(dev.clock_gates):
            dev_users.setdefault(pdev, []).append(f"{dev._path}.clkgate[{i}]")
    if hasattr(dev, "power_gates") and dev.power_gates:
        for i, pdev in enumerate(dev.power_gates):
            dev_users.setdefault(pdev, []).append(f"{dev._path}.pwrgate[{i}]")

print()
print("=== Devices ===")
for i, dev in enumerate(pmgr.devices):
    flags = ", ".join(k for k in dev.flags if k[0] != "_" and dev.flags[k])
    s = f" #{i:3d} {dev.name:20s} id: {dev.id:3d} psreg: {dev.psreg:2d}:{dev.psidx:2d} "
    s += f" flags: {flags:24s} unk1_0: {dev.unk1_0} unk1_1: {dev.unk1_1} unk1_2: {dev.unk1_2} "
    s += f" perf_reg: {dev.perf_block}:{dev.perf_idx:#04x} unk3: {dev.unk3:3d} {dev.unk2_0:2d} {dev.ps_cfg16:2d} {dev.unk2_3:3d}"

    if not dev.flags.no_ps:
        ps = pmgr.ps_regs[dev.psreg]
        addr = pmgr.get_reg(ps.reg)[0] + ps.offset + dev.psidx * 8
        val = p.read32(addr)
        s += f" @ {addr:#x} = {val:#010x}"
    else:
        s += f" @                         "
    if dev.pd:
        pd = pd_by_id[dev.pd]
        s += f" pd: {pd.name:20s}"
    else:
        s += "                         "
    if any(dev.parents):
        s += " parents: " + ", ".join(dev_by_id[idx].name if idx in dev_by_id else f"#{idx}" for idx in dev.parents if idx)
    print(s)
    for i in dev_users.get(dev.id, []):
        print(f"  User: {i}")

print()
print("=== Clocks ===")
for i, clk in enumerate(pmgr.clocks):
    perf = pmgr.perf_regs[clk.perf_block]
    reg = pmgr.get_reg(perf.reg)[0] + 0x100 + clk.perf_idx * 0x10
    print(f" #{i:3d} {clk.name:20s} id: {clk.id:3d} reg:{clk.perf_block}:{clk.perf_idx:#4x} ({reg:#x}) {clk.unk:#x}")

print()
print("=== Power Domains ===")
for i, pd in enumerate(pmgr.power_domains):
    perf = pmgr.perf_regs[pd.perf_block]
    reg = pmgr.get_reg(perf.reg)[0] + 0x100 + pd.perf_idx * 0x10
    print(f" #{i:3d} {pd.name:20s} id: {pd.id:3d} reg:{pd.perf_block}:{pd.perf_idx:#4x} ({reg:#x})")

print()
print("=== Events ===")
for i, ev in enumerate(pmgr.events):
    perf = pmgr.perf_regs[ev.perf_block]
    reg = pmgr.get_reg(perf.reg)[0] + 0x100 + ev.perf_idx * 0x10
    v = f" #{i:3d} {ev.name:20s} unk:{ev.unk1:#3x}/{ev.unk2}/{ev.unk3} id: {ev.id:3d} reg:{ev.perf_block}:{ev.perf_idx:#4x} ({reg:#x})"
    if ev.perf2_idx:
        perf2 = pmgr.perf_regs[ev.perf2_block]
        reg2 = pmgr.get_reg(perf2.reg)[0] + 0x100 + ev.perf2_idx * 0x10
        v += f" reg2:{ev.perf2_block}:{ev.perf2_idx:#4x} ({reg2:#x})"
    print(v)

arm_io = dt["/arm-io"]

print()
print("=== Fixed clocks ===")
for clk in range(256):
    users = clock_users.get(clk, [])
    if users:
        print(f" #{clk}")
        for j in users:
            print(f"  User: {j}")

print()
print("=== Boot clocks ===")
for i, (freq, reg, nclk) in enumerate(zip(arm_io.clock_frequencies,
                                          arm_io.clock_frequencies_regs,
                                          arm_io.clock_frequencies_nclk)):
    v = ""
    clk_type = reg >> 56
    reg = reg & 0xFFFFFFFFFFFFFF
    
    if clk_type == 0x9c:
        v = f"fixed: {reg}"
    elif clk_type in (0xa0, 0xa1, 0xa4, 0xa5):
        v = f"regval: {p.read32(reg):#x}"
    elif clk_type == 0xa8:
        regvals = [p.read32(reg+off*4) for off in range(5)]
        try:
            # we are using the freq value from ADT as fin of NCO,
            # that's not exactly correct
            nco_freq = NCO.calc_rate(freq, regvals)
        except ValueError as e:
            nco_freq = 0

        v = f"nco: (calculated rate: {nco_freq:d}) "
        for val in regvals:
            v += f"{val:#x} "
        
    
    print(f"#{i:3}: {freq:10d} {nclk} {clk_type:#x}/{reg:#x}: {v}")
    for j in clock_users.get(i + 256, []):
        print(f"  User: {j}")
