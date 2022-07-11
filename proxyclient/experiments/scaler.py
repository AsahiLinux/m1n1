#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.dart8110 import DART8110
from m1n1.hw.scaler import *
from m1n1.utils import *

SCALER_ADT = '/arm-io/scaler0'
DART_ADT = '/arm-io/dart-scaler0'

p.pmgr_adt_clocks_enable(DART_ADT)
p.pmgr_adt_clocks_enable(SCALER_ADT)

dart = DART8110.from_adt(u, DART_ADT)
dart.initialize()

scaler_base, _ = u.adt[SCALER_ADT].get_reg(0)
apiodma_base, _ = u.adt[SCALER_ADT].get_reg(1)
dpe_ctrl_base, _ = u.adt[SCALER_ADT].get_reg(2)

scaler = ScalerMainRegs(u, scaler_base)

def dpe_start():
    p.write32(dpe_ctrl_base + 0x400, 0x1)
    p.write32(dpe_ctrl_base + 0x404, 0x1)
    p.write32(dpe_ctrl_base + 0x438, 0xf)
    p.write32(dpe_ctrl_base + 0x43c, 0x5)
    p.write32(dpe_ctrl_base + 0x408, 0x1)
    p.write32(dpe_ctrl_base + 0x440, 0x5)
    p.write32(dpe_ctrl_base + 0x444, 0x4)
    p.write32(dpe_ctrl_base + 0x40c, 0x1)
    p.write32(dpe_ctrl_base + 0x448, 0x5)
    p.write32(dpe_ctrl_base + 0x44c, 0x5)
    p.write32(dpe_ctrl_base + 0x410, 0x1)
    p.write32(dpe_ctrl_base + 0x450, 0x7)
    p.write32(dpe_ctrl_base + 0x454, 0x7)
    p.write32(dpe_ctrl_base + 0x414, 0x1)
    p.write32(dpe_ctrl_base + 0x458, 0xd)
    p.write32(dpe_ctrl_base + 0x45c, 0xc)
    p.write32(dpe_ctrl_base + 0x418, 0x1)
    p.write32(dpe_ctrl_base + 0x460, 0x13)
    p.write32(dpe_ctrl_base + 0x464, 0x12)
    p.write32(dpe_ctrl_base + 0x41c, 0x1)
    p.write32(dpe_ctrl_base + 0x468, 0x9)
    p.write32(dpe_ctrl_base + 0x46c, 0xa)
    p.write32(dpe_ctrl_base + 0x420, 0x1)
    p.write32(dpe_ctrl_base + 0x470, 0x33)
    p.write32(dpe_ctrl_base + 0x474, 0x2c)
    p.write32(dpe_ctrl_base + 0x424, 0x1)
    p.write32(dpe_ctrl_base + 0x478, 0x15)
    p.write32(dpe_ctrl_base + 0x47c, 0x15)
    p.write32(dpe_ctrl_base + 0x428, 0x1)
    p.write32(dpe_ctrl_base + 0x480, 0xe)
    p.write32(dpe_ctrl_base + 0x484, 0x5)
    p.write32(dpe_ctrl_base + 0x42c, 0x1)
    p.write32(dpe_ctrl_base + 0x488, 0x27)
    p.write32(dpe_ctrl_base + 0x48c, 0x15)
    p.write32(dpe_ctrl_base + 0x430, 0x1)
    p.write32(dpe_ctrl_base + 0x490, 0x15)
    p.write32(dpe_ctrl_base + 0x494, 0xe)
    p.write32(dpe_ctrl_base + 0x434, 0x1)
    p.write32(dpe_ctrl_base + 0x498, 0x0)
    p.write32(dpe_ctrl_base + 0x49c, 0x0)
    p.write32(dpe_ctrl_base + 0x4, 0x1000)
    p.write32(dpe_ctrl_base + 0x0, 0x101)

def dpe_stop():
    p.write32(dpe_ctrl_base + 0x0, 0x103)
    while p.read32(dpe_ctrl_base + 0x0) & 0xC != 4:
        ...
    p.write32(dpe_ctrl_base + 0x0, p.read32(dpe_ctrl_base + 0x0) & 0xfffffffc)

print(f"Hardware version {scaler.HW_VERSION.val:08X}")

scaler.RESET = 1
scaler.RESET = 0

print(f"Hardware version after reset {scaler.HW_VERSION.val:08X}")
