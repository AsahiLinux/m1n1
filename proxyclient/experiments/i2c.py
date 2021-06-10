#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct

from m1n1.setup import *
from m1n1 import asm

base = 0x235010000

# register defines from https://github.com/torvalds/linux/blob/master/drivers/i2c/busses/i2c-pasemi.c
# Copyright (C) 2006-2007 PA Semi, Inc
# SMBus host driver for PA Semi PWRficient
REG_MTXFIFO = 0x00
REG_MRXFIFO = 0x04
REG_SMSTA = 0x14
REG_CTL = 0x1c

MTXFIFO_READ = 0x00000400
MTXFIFO_STOP = 0x00000200
MTXFIFO_START = 0x00000100
MTXFIFO_DATA_M = 0x000000ff

MRXFIFO_EMPTY = 0x00000100
MRXFIFO_DATA_M = 0x000000ff

SMSTA_XEN = 0x08000000
SMSTA_MTN = 0x00200000

CTL_MRR = 0x00000400
CTL_MTR = 0x00000200
CTL_CLK_M = 0x000000ff

CLK_100K_DIV = 84
CLK_400K_DIV = 21


def i2c_read_reg(addr, reg, reg_size):
    p.set32(base + REG_CTL, CTL_MTR | CTL_MRR)
    p.write32(base + REG_SMSTA, 0xffffffff)

    p.write32(base + REG_MTXFIFO, MTXFIFO_START | (addr << 1))
    p.write32(base + REG_MTXFIFO, MTXFIFO_STOP | reg)

    while not (p.read32(base + REG_SMSTA) & SMSTA_XEN):
        pass

    p.write32(base + REG_MTXFIFO, MTXFIFO_START | (addr << 1) | 1)
    p.write32(base + REG_MTXFIFO, MTXFIFO_READ | MTXFIFO_STOP | reg_size + 1)

    res = []
    while len(res) < reg_size+1:
        v = p.read32(base + REG_MRXFIFO)
        if v & 0x100:
            continue
        res.append(v)

    if res[0] < reg_size:
        print("only read %d instead of %d bytes" % (res[0], reg_size))
    return res[1:]


def i2c_write_reg(addr, reg, data):
    p.set32(base + REG_CTL, CTL_MTR | CTL_MRR)
    p.write32(base + REG_SMSTA, 0xffffffff)

    p.write32(base + REG_MTXFIFO, MTXFIFO_START | (addr << 1))
    p.write32(base + REG_MTXFIFO, reg)
    for i in range(len(data)-1):
        p.write32(base + REG_MTXFIFO, data[i])
    p.write32(base + REG_MTXFIFO, data[-1] | MTXFIFO_STOP)

    while not (p.read32(base + REG_SMSTA) & SMSTA_XEN):
        pass


def i2c_read16(addr, reg):
    data = struct.pack(">2b", *i2c_read_reg(addr, reg, 2))
    return struct.unpack(">H", data)[0]


def i2c_read32(addr, reg):
    data = struct.pack(">4b", *i2c_read_reg(addr, reg, 4))
    return struct.unpack(">I", data)[0]


def tps6598x_exec_cmd(addr, cmd, data_in, out_len):
    if data_in:
        data = [len(data_in)] + data_in

        # TPS_REG_DATA1
        i2c_write_reg(addr, 0x09, data)

    # TPS_REG_CMD1
    cmd = [4] + list(map(ord, cmd))
    i2c_write_reg(addr, 0x08, cmd)

    # TPS_REG_CMD1
    v = i2c_read32(addr, 0x08)
    while v != 0:
        if v == 0x21434d44:  # !CMD
            raise Exception("Invalid command!")
        v = i2c_read32(addr, 0x08)

    if not out_len:
        return

    # TPS_REG_DATA1
    return i2c_read_reg(addr, 0x09, out_len)


print("make sure to run pmgr_adt_clocks_enable for /arm-io/i2c0 before this script.")

# apple-specific command to bring the power state to zero
# (or any other value specified as an argument)
tps6598x_exec_cmd(0x3f, "SSPS", [0], 0)
tps6598x_exec_cmd(0x38, "SSPS", [0], 0)

tps6598x_exec_cmd(0x3f, "SWDF", None, 0)
tps6598x_exec_cmd(0x3f, "SWSr", None, 0)
tps6598x_exec_cmd(0x38, "SWDF", None, 0)
tps6598x_exec_cmd(0x38, "SWSr", None, 0)
