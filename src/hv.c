/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "gxf.h"
#include "pcie.h"
#include "smp.h"
#include "usb.h"
#include "utils.h"

#define HV_TICK_RATE 1000

void hv_enter_guest(u64 x0, u64 x1, u64 x2, u64 x3, void *entry);

extern char _hv_vectors_start[0];

u64 hv_tick_interval;

void hv_init(void)
{
    pcie_shutdown();
    // reenable hpm interrupts for the guest for unused iodevs
    usb_hpm_restore_irqs(0);
    smp_start_secondaries();
    hv_wdt_init();

    // Enable physical timer for EL1
    msr(CNTHCTL_EL2, CNTHCTL_EL1PTEN | CNTHCTL_EL1PCTEN);

    hv_pt_init();

    // Configure hypervisor defaults
    msr(HCR_EL2, HCR_API |     // Allow PAuth instructions
                     HCR_APK | // Allow PAuth key registers
                     HCR_TEA | // Trap external aborts
                     HCR_E2H | // VHE mode (forced)
                     HCR_RW |  // AArch64 guest
                     HCR_AMO | // Trap SError exceptions
                     HCR_VM);  // Enable stage 2 translation

    // No guest vectors initially
    msr(VBAR_EL12, 0);

    // Compute tick interval
    hv_tick_interval = mrs(CNTFRQ_EL0) / HV_TICK_RATE;

    sysop("dsb ishst");
    sysop("tlbi alle1is");
    sysop("dsb ish");
    sysop("isb");
}

static void hv_set_gxf_vbar(void)
{
    msr(SYS_IMP_APL_VBAR_GL1, _hv_vectors_start);
}

void hv_start(void *entry, u64 regs[4])
{
    msr(VBAR_EL1, _hv_vectors_start);

    if (gxf_enabled())
        gl2_call(hv_set_gxf_vbar, 0, 0, 0, 0);

    hv_wdt_start();
    hv_arm_tick();
    hv_enter_guest(regs[0], regs[1], regs[2], regs[3], entry);
    hv_wdt_stop();

    printf("Exiting hypervisor.\n");
}

void hv_write_hcr(u64 val)
{
    if (gxf_enabled() && !in_gl12())
        gl2_call(hv_write_hcr, val, 0, 0, 0);
    else
        msr(HCR_EL2, val);
}

u64 hv_get_spsr(void)
{
    if (in_gl12())
        return mrs(SYS_IMP_APL_SPSR_GL1);
    else
        return mrs(SPSR_EL2);
}

void hv_set_spsr(u64 val)
{
    if (in_gl12())
        return msr(SYS_IMP_APL_SPSR_GL1, val);
    else
        return msr(SPSR_EL2, val);
}

u64 hv_get_esr(void)
{
    if (in_gl12())
        return mrs(SYS_IMP_APL_ESR_GL1);
    else
        return mrs(ESR_EL2);
}

u64 hv_get_far(void)
{
    if (in_gl12())
        return mrs(SYS_IMP_APL_FAR_GL1);
    else
        return mrs(FAR_EL2);
}

u64 hv_get_afsr1(void)
{
    if (in_gl12())
        return mrs(SYS_IMP_APL_AFSR1_GL1);
    else
        return mrs(AFSR1_EL2);
}

u64 hv_get_elr(void)
{
    if (in_gl12())
        return mrs(SYS_IMP_APL_ELR_GL1);
    else
        return mrs(ELR_EL2);
}

void hv_set_elr(u64 val)
{
    if (in_gl12())
        return msr(SYS_IMP_APL_ELR_GL1, val);
    else
        return msr(ELR_EL2, val);
}

void hv_arm_tick(void)
{
    msr(CNTP_TVAL_EL0, hv_tick_interval);
    msr(CNTP_CTL_EL0, CNTx_CTL_ENABLE);
}

void hv_tick(u64 *regs)
{
    hv_wdt_pet();
    iodev_handle_events(uartproxy_iodev);
    if (iodev_can_read(uartproxy_iodev))
        hv_exc_proxy(regs, START_HV, HV_USER_INTERRUPT, NULL);
}
