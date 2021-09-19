#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1 import adt
from m1n1.setup import *

dt = u.adt

pmgr = dt["/arm-io/pmgr"]

dev_by_id = {dev.id: dev for dev in pmgr.devices}
pd_by_id = {pd.id: pd for pd in pmgr.power_domains}
clk_by_id = {clk.id: clk for clk in pmgr.clocks}

print("=== PS Regs ===")
for i, r in enumerate(pmgr.ps_regs):
    print(f" #{i:2d} reg: {r.reg} off: {r.offset:05x} mask:{r.mask:08x}")

print()
print("=== PWR Gate Regs ===")
for i, r in enumerate(pmgr.pwrgate_regs):
    print(f" #{i:2d} reg: {r.reg} off: {r.offset:05x} mask:{r.mask:08x} unk:{r.unk:08x}")

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
    ps = pmgr.ps_regs[dev.psreg]
    s = f" #{i:3d} {dev.name:20s} id: {dev.id:3d} psreg: {dev.psreg:2d}:{dev.psidx:2d} "
    s += f" unk1_0: {dev.unk1_0} unk1_1: {dev.unk1_1} unk0: {dev.unk0:#4x}"
    s += f" unk: {dev.unk:#05x} unk3: {dev.unk3:3d} {dev.unk2_0:2d} {dev.unk2_2:2d} {dev.unk2_3:3d}"
    if dev.psidx or dev.psreg:
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
    print(f" #{i:3d} {clk.name:20s} id: {clk.id:3d} {clk.a:#5x} {clk.b:2d}")

print()
print("=== Power Domains ===")
for i, pd in enumerate(pmgr.power_domains):
    print(f" #{i:3d} {pd.name:20s} id: {pd.id:3d} {pd.a:#5x} {pd.b:2d}")

arm_io = dt["/arm-io"]

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
        v = "nco: "
        for off in range(6):
            v += f"{p.read32(reg+off*4):#x} "
        
    
    print(f"#{i:3}: {freq:10d} {nclk} {clk_type:#x}/{reg:#x}: {v}")
    for j in clock_users.get(i + 256, []):
        print(f"  User: {j}")
