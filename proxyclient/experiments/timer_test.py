#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

HV_VTMR_CTL = (3, 5, 15, 1, 3)
HV_VTMR_CTL_VMASK = (1 << 0)
HV_VTMR_CTL_PMASK = (1 << 1)

HV_VTMR_LIST = (3, 5, 15, 1, 2)

TGE = (1<<27)

u.msr(CNTHCTL_EL2, 3 << 10) # EL1PTEN | EL1PCTEN

def run_test(ctl, tval):
    u.inst(0xd5033fdf) # isb

    u.msr(ctl, 0)
    u.msr(tval, int(freq * 0.8))
    u.msr(ctl, 1)

    for i in range(6):
        p.nop()
        time.sleep(0.2)
        #u.inst(0xd5033fdf, call=p.el1_call)
        print("      . (ISR_EL1=%d) CTL=%x VTMR_LIST=%x" % (u.mrs(ISR_EL1), u.mrs(ctl), u.mrs(HV_VTMR_LIST)))

    u.msr(ctl, 0)

def test_hv_timers():
    u.msr(DAIF, 0x3c0)
    print("Testing HV timers...")
    print("  TGE = 1")

    u.msr(HCR_EL2, u.mrs(HCR_EL2) | TGE | (1 << 3) | (1 << 4))

    print("    P:")
    run_test(CNTP_CTL_EL0, CNTP_TVAL_EL0)
    print("    V:")
    run_test(CNTV_CTL_EL0, CNTV_TVAL_EL0)

def test_guest_timers():
    u.msr(DAIF, 0)
    print("Testing guest timers...")

    print("  TGE = 1, vGIC mode=0, timers unmasked")
    u.msr(HCR_EL2, (u.mrs(HCR_EL2) | TGE) | (1 << 3) | (1 << 4))
    u.msr(HACR_EL2, 0)
    u.msr(HV_VTMR_CTL, 3)

    print("    P:")
    #run_test(CNTP_CTL_EL02, CNTP_TVAL_EL02)
    print("    V:")
    #run_test(CNTV_CTL_EL02, CNTV_TVAL_EL02)

    print("  TGE = 1, vGIC mode=0, timers masked")
    u.msr(HV_VTMR_CTL, 0)

    print("    P:")
    run_test(CNTP_CTL_EL02, CNTP_TVAL_EL02)
    print("    V:")
    run_test(CNTV_CTL_EL02, CNTV_TVAL_EL02)

    print("  TGE = 0, vGIC mode=0, timers unmasked")
    u.msr(HCR_EL2, (u.mrs(HCR_EL2) & ~TGE) | (1 << 3) | (1 << 4))
    u.msr(HACR_EL2, 0)
    u.msr(HV_VTMR_CTL, 3)

    print("    P:")
    run_test(CNTP_CTL_EL02, CNTP_TVAL_EL02)
    print("    V:")
    run_test(CNTV_CTL_EL02, CNTV_TVAL_EL02)

    print("  TGE = 0, vGIC mode=0, timers masked")
    u.msr(HV_VTMR_CTL, 0)

    print("    P:")
    run_test(CNTP_CTL_EL02, CNTP_TVAL_EL02)
    print("    V:")
    run_test(CNTV_CTL_EL02, CNTV_TVAL_EL02)

    print("  TGE = 0, vGIC mode=1, timers unmasked")
    u.msr(HCR_EL2, (u.mrs(HCR_EL2) & ~TGE) | (1 << 3) | (1 << 4))
    u.msr(HACR_EL2, 1<<20)
    u.msr(HV_VTMR_CTL, 3)

    print("    P:")
    run_test(CNTP_CTL_EL02, CNTP_TVAL_EL02)
    print("    V:")
    run_test(CNTV_CTL_EL02, CNTV_TVAL_EL02)

    print("  TGE = 0, vGIC mode=1, timers masked")
    u.msr(HV_VTMR_CTL, 0)

    print("    P:")
    run_test(CNTP_CTL_EL02, CNTP_TVAL_EL02)
    print("    V:")
    run_test(CNTV_CTL_EL02, CNTV_TVAL_EL02)

    return

freq = u.mrs(CNTFRQ_EL0)
print("Timer freq: %d" % freq)

test_hv_timers()
test_guest_timers()
