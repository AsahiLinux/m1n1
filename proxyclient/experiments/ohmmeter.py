#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.hw.i2c import I2C, I2CRegMapDev
from m1n1.hw.codecs.cs42l84 import *

class CS42L84(I2CRegMapDev):
    REGMAP = CS42L84Regs
    ADDRESSING = (0, 2)

def read_devid():
    pass

def sense_Z():
    r = l84.regs

    r.HS_CLAMP_DISABLE.set(HS_CLAMP_DISABLE=1)
    r.DAC_CTRL2.set(PULLDOWN_R=E_PULLDOWN_R.R_1K1OHMS)
    r.DCID_CTRL1.set(Z_RANGE=E_DCID_Z_RANGE.UNK2)
    r.DCID_CTRL2.set(GND_SEL=E_DCID_GND_SEL.HS3)
    r.MSM_BLOCK_EN3.set(DCID_EN=1)
    r.DCID_CTRL3.set(START=0)
    r.DCID_CTRL3.set(START=1)

    while not r.DCID_STATUS.reg.DONE:
        pass

    reading = r.DCID_STATUS.reg.OVERALL
    offset_trim = r.DCID_TRIM_OFFSET.val - 128
    slope_trim = r.DCID_TRIM_SLOPE.val - 128
    pulldown_trim = r.DCID_PULLDOWN_TRIM.val - 128

    Y_overall = ((reading + 0.5) * 0.01086 - 1.0 / (1 - slope_trim * 0.001375)) \
        / (614.0 + offset_trim * 0.125)
    Y_pulldown = 1.0 / (1100 - pulldown_trim*2)

    if Y_overall > Y_pulldown:
        Z_headphones = 1.0 / (Y_overall - Y_pulldown)
    else:
        Z_headphones = float('inf')

    r.MSM_BLOCK_EN3.set(DCID_EN=0)
    r.DAC_CTRL2.set(PULLDOWN_R=E_PULLDOWN_R.NONE)

    return Z_headphones

def init_ring_tip_sense():
    l84.regs.MIC_DET_CTRL4.set(LATCH_TO_VP=1)
    l84.regs.TIP_SENSE_CTRL2.set(CTRL=E_TIP_SENSE_CTRL.SHORT_DET)

    l84.regs.RING_SENSE_CTRL.set(INV=1, UNK1=1,
        RISETIME=E_DEBOUNCE_TIME.T_125MS, FALLTIME=E_DEBOUNCE_TIME.T_125MS)
    l84.regs.TIP_SENSE_CTRL.set(INV=1,
        RISETIME=E_DEBOUNCE_TIME.T_500MS, FALLTIME=E_DEBOUNCE_TIME.T_125MS)
    l84.regs.MSM_BLOCK_EN3.set(TR_SENSE_EN=1)

def wait_for_plug():
    while not l84.regs.TR_SENSE_STATUS.reg.TIP_PLUG:
        time.sleep(0.001)

def wait_for_unplug():
    while l84.regs.TR_SENSE_STATUS.reg.TIP_UNPLUG:
        time.sleep(0.001)


p.pmgr_adt_clocks_enable("/arm-io/i2c2")
i2c2 = I2C(u, "/arm-io/i2c2")

p.write32(0x2921f0010, 0x76a02) # invoke reset
p.write32(0x2921f0010, 0x76a03) # out of reset

l84 = CS42L84(i2c2, 0x4b)

init_ring_tip_sense()

while True:
    print("Waiting for plug... ", end=""); sys.stdout.flush()
    wait_for_plug()

    print("measuring... ", end=""); sys.stdout.flush()
    print(f"{sense_Z():.1f} ohms... ", end=""); sys.stdout.flush()

    wait_for_unplug()
    print("yanked")
