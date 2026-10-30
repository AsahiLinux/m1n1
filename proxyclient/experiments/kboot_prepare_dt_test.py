#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

parser = argparse.ArgumentParser(description='Test program for kboot_prepare_dt()')
parser.add_argument('dtb', type=pathlib.Path)
args = parser.parse_args()

dtb = args.dtb.read_bytes()

dtb_addr = u.malloc(len(dtb))
print("Loading DTB to 0x%x..." % dtb_addr)

iface.writemem(dtb_addr, dtb)

if p.kboot_prepare_dt(dtb_addr):
    print("DT prepare failed")

u.free(dtb_addr)
