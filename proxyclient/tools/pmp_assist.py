#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import serial
import struct
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

from m1n1 import adt

parser = argparse.ArgumentParser(description='PMP device tree helper')
parser.add_argument('input', type=pathlib.Path)
args = parser.parse_args()

adt_data = args.input.read_bytes()
dt = adt.load_adt(adt_data)


pmp_ptd_range = dt['/arm-io/pmp/iop-pmp-nub'].ptd_range
pmp_ptd_range_map = {}
for i in range(len(pmp_ptd_range) // 32):
    id, offset, _, name = struct.unpack('<II8s16s', pmp_ptd_range[i*32:(i+1)*32])
    pmp_ptd_range_map[name.strip(b'\x00')] = offset

print("DEV_STATUS_TGT_RD:", hex(pmp_ptd_range_map[b'SOC-DEV-PS-REQ'] * 16))
print("DEV_STATUS_TGT_WR:", hex(pmp_ptd_range_map[b'SOC-DEV-PS-REQ'] * 8 + 0x10000))
print("DEV_STATUS_ACT:", hex(pmp_ptd_range_map[b'SOC-DEV-PS-ACK'] * 16))
print("PMP_STATUS:", hex(pmp_ptd_range_map[b'PMP-STATUS'] * 16))
print()

for dev in sorted(dt['/arm-io/pmgr'].devices, key=lambda dev: dev.id1):
    if dev.id1 == 0:
        continue
    s = f"\t{hex(dev.id1 - 1)}:\t{dev.name}"
    if dev.flags.notify_pmp:
        s += " (notify_pmp)"
    print(s)
