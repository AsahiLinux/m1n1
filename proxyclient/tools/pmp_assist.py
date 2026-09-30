#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
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

pmp_node = dt['/arm-io/pmp']
pmp_base = pmp_node.get_reg(pmp_node.ptd_update_reg_index)[0] - 0x10000
print("PMP base", hex(pmp_base))
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

soc_dev = dt['/arm-io/pmp/iop-pmp-nub'].soc_device
bw_dev = {}
j = 0
for i in range(len(soc_dev) // 124):
    id, _, has_bw_req, _, name = struct.unpack('<I44sI64s8s', soc_dev[i*124:(i+1)*124])
    if has_bw_req:
        bw_dev[id] = j
        j += 1

print()
print('bw-scratch:')
pmgr_devs = {x.id2:x for x in dt['/arm-io/pmgr'].devices}
for seg in ['disp', 'dispext', 'isp']:
    i = 0
    while 1:
        name = f'{seg}{i}'
        path = f'/arm-io/{name}'
        if path not in dt:
            break
        node = dt[path]
        i += 1
        for sfx in ['', '0']:
            prop = node._properties.get(f'function-bw_req_interrupt{sfx}')
            if prop is None:
                continue
            pmgr_id = prop.args[0]
            pmp_id = pmgr_devs[pmgr_id].id1
            offs = (bw_dev[pmp_id] + pmp_ptd_range_map[b'SOC-DEV-BWR']) * 8 + 0x10000 + pmp_base
            print(f'\t{name} {hex(offs)}')
            break
