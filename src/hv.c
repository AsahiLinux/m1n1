/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"

void hv_init(void)
{
    // Enable physical timer for EL1
    msr(CNTHCTL_EL2, CNTHCTL_EL1PCTEN);

    hv_pt_init();

    // Configure hypervisor defaults
    msr(HCR_EL2, HCR_API |     // Allow PAuth instructions
                     HCR_APK | // Allow PAuth key registers
                     HCR_TEA | // Trap external aborts
                     HCR_E2H | // VHE mode (forced)
                     HCR_RW |  // AArch64 guest
                     HCR_AMO | // Trap SError exceptions
                     HCR_VM);  // Enable stage 2 translation

    sysop("dsb ishst");
    sysop("tlbi alle1is");
    sysop("dsb ish");
    sysop("isb");
}
