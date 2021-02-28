from setup import *

HV_VTMR_CTL = (3, 5, 15, 1, 3)
HV_VTMR_CTL_VMASK = (1 << 0)
HV_VTMR_CTL_PMASK = (1 << 1)

HV_VTMR_LIST = (3, 5, 15, 1, 2)

TGE = (1<<27)

def test_hv_timers():
    u.msr(DAIF, 0)
    print("Testing HV timers...")

    u.msr(HCR_EL2, u.mrs(HCR_EL2) | TGE)

    u.inst(0xd5033fdf) # isb

    u.msr(CNTHP_CTL_EL2, 0)
    u.msr(CNTHP_TVAL_EL2, freq // 2)
    u.msr(CNTHP_CTL_EL2, 1)

    u.msr(CNTHV_CTL_EL2, 0)
    u.msr(CNTHV_TVAL_EL2, freq * 1)
    u.msr(CNTHV_CTL_EL2, 1)

    for i in range(6):
        p.nop()
        time.sleep(0.2)
        print(". %x %x" % (u.mrs(CNTHP_CTL_EL2), u.mrs(CNTHV_CTL_EL2)))

def test_guest_timers():
    u.msr(DAIF, 0)
    print("Testing guest timers...")

    u.msr(HCR_EL2, (u.mrs(HCR_EL2) & (~TGE)) | (1 << 3) | (1 << 4))
    u.msr(HACR_EL2, 1<<20)
    u.msr(HV_VTMR_CTL, 3)

    u.inst(0xd5033fdf) # isb

    u.msr(CNTP_CTL_EL02, 0)
    u.msr(CNTP_TVAL_EL02, int(freq * 1))

    u.msr(CNTV_CTL_EL02, 0)
    u.msr(CNTV_TVAL_EL02, int(freq * 1.5))

    u.msr(HV_VTMR_LIST, 0)

    u.msr(CNTP_CTL_EL02, 1)
    u.msr(CNTV_CTL_EL02, 1)

    for i in range(15):
        p.nop()
        time.sleep(0.2)
        print(". %x %x %x" % (u.mrs(CNTP_CTL_EL02), u.mrs(CNTV_CTL_EL02), u.mrs(HV_VTMR_LIST)))

freq = u.mrs(CNTFRQ_EL0)
print("Timer freq: %d" % freq)

test_hv_timers()
test_guest_timers()
