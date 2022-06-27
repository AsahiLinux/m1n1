/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "display.h"
#include "gxf.h"
#include "memory.h"
#include "pcie.h"
#include "smp.h"
#include "string.h"
#include "usb.h"
#include "utils.h"

#define HV_TICK_RATE 1000

DECLARE_SPINLOCK(bhl);

void hv_enter_guest(u64 x0, u64 x1, u64 x2, u64 x3, void *entry);
void hv_exit_guest(void) __attribute__((noreturn));

extern char _hv_vectors_start[0];

u64 hv_tick_interval;

int hv_pinned_cpu;
int hv_want_cpu;

static bool hv_should_exit;
bool hv_started_cpus[MAX_CPUS];
u32 hv_cpus_in_guest;
u64 hv_saved_sp[MAX_CPUS];

struct hv_secondary_info_t {
    uint64_t hcr;
    uint64_t hacr;
    uint64_t vtcr, vttbr;
    uint64_t mdcr;
    uint64_t mdscr;
    uint64_t amx_ctl;
    uint64_t apvmkeylo, apvmkeyhi, apsts;
    uint64_t actlr_el2;
    uint64_t actlr_el1;
    uint64_t cnthctl;
    uint64_t sprr_config;
    uint64_t gxf_config;
};

static struct hv_secondary_info_t hv_secondary_info;

void hv_init(void)
{
    pcie_shutdown();
    // Make sure we wake up DCP if we put it to sleep, just quiesce it to match ADT
    if (display_is_external && display_start_dcp() >= 0)
        display_shutdown(DCP_QUIESCED);
    // reenable hpm interrupts for the guest for unused iodevs
    usb_hpm_restore_irqs(0);
    smp_start_secondaries();
    smp_set_wfe_mode(true);
    hv_wdt_init();

    // Enable physical timer for EL1
    msr(CNTHCTL_EL2, CNTHCTL_EL1PTEN | CNTHCTL_EL1PCTEN);

    hv_pt_init();

    // Configure hypervisor defaults
    hv_write_hcr(HCR_API | // Allow PAuth instructions
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
    hv_should_exit = false;
    memset(hv_started_cpus, 0, sizeof(hv_started_cpus));
    hv_started_cpus[0] = 1;

    msr(VBAR_EL1, _hv_vectors_start);

    if (gxf_enabled())
        gl2_call(hv_set_gxf_vbar, 0, 0, 0, 0);

    hv_secondary_info.hcr = mrs(HCR_EL2);
    hv_secondary_info.hacr = mrs(HACR_EL2);
    hv_secondary_info.vtcr = mrs(VTCR_EL2);
    hv_secondary_info.vttbr = mrs(VTTBR_EL2);
    hv_secondary_info.mdcr = mrs(MDCR_EL2);
    hv_secondary_info.mdscr = mrs(MDSCR_EL1);
    hv_secondary_info.amx_ctl = mrs(SYS_IMP_APL_AMX_CTL_EL2);
    hv_secondary_info.apvmkeylo = mrs(SYS_IMP_APL_APVMKEYLO_EL2);
    hv_secondary_info.apvmkeyhi = mrs(SYS_IMP_APL_APVMKEYHI_EL2);
    hv_secondary_info.apsts = mrs(SYS_IMP_APL_APSTS_EL12);
    hv_secondary_info.actlr_el2 = mrs(ACTLR_EL2);
    hv_secondary_info.actlr_el1 = mrs(SYS_IMP_APL_ACTLR_EL12);
    hv_secondary_info.cnthctl = mrs(CNTHCTL_EL2);
    hv_secondary_info.sprr_config = mrs(SYS_IMP_APL_SPRR_CONFIG_EL1);
    hv_secondary_info.gxf_config = mrs(SYS_IMP_APL_GXF_CONFIG_EL1);

    hv_arm_tick();
    hv_pinned_cpu = -1;
    hv_want_cpu = -1;
    hv_cpus_in_guest = 1;

    hv_enter_guest(regs[0], regs[1], regs[2], regs[3], entry);

    __atomic_sub_fetch(&hv_cpus_in_guest, 1, __ATOMIC_ACQUIRE);
    spin_lock(&bhl);

    hv_wdt_stop();

    hv_should_exit = true;
    printf("HV: Exiting hypervisor (main CPU)\n");

    for (int i = 0; i < MAX_CPUS; i++) {
        if (hv_started_cpus[i]) {
            printf("HV: Waiting for CPU %d to exit\n", i);
            spin_unlock(&bhl);
            smp_wait(i);
            spin_lock(&bhl);
            hv_started_cpus[i] = false;
        }
    }

    printf("HV: All CPUs exited\n");
    spin_unlock(&bhl);
}

static void hv_init_secondary(struct hv_secondary_info_t *info)
{
    gxf_init();

    msr(VBAR_EL1, _hv_vectors_start);

    msr(HCR_EL2, info->hcr);
    msr(HACR_EL2, info->hacr);
    msr(VTCR_EL2, info->vtcr);
    msr(VTTBR_EL2, info->vttbr);
    msr(MDCR_EL2, info->mdcr);
    msr(MDSCR_EL1, info->mdscr);
    msr(SYS_IMP_APL_AMX_CTL_EL2, info->amx_ctl);
    msr(SYS_IMP_APL_APVMKEYLO_EL2, info->apvmkeylo);
    msr(SYS_IMP_APL_APVMKEYHI_EL2, info->apvmkeyhi);
    msr(SYS_IMP_APL_APSTS_EL12, info->apsts);
    msr(ACTLR_EL2, info->actlr_el2);
    msr(SYS_IMP_APL_ACTLR_EL12, info->actlr_el1);
    msr(CNTHCTL_EL2, info->cnthctl);
    msr(SYS_IMP_APL_SPRR_CONFIG_EL1, info->sprr_config);
    msr(SYS_IMP_APL_GXF_CONFIG_EL1, info->gxf_config);

    if (gxf_enabled())
        gl2_call(hv_set_gxf_vbar, 0, 0, 0, 0);

    hv_arm_tick();
}

static void hv_enter_secondary(void *entry, u64 regs[4])
{
    hv_enter_guest(regs[0], regs[1], regs[2], regs[3], entry);

    spin_lock(&bhl);

    hv_should_exit = true;
    printf("HV: Exiting from CPU %d\n", smp_id());

    __atomic_sub_fetch(&hv_cpus_in_guest, 1, __ATOMIC_ACQUIRE);

    spin_unlock(&bhl);
}

void hv_start_secondary(int cpu, void *entry, u64 regs[4])
{
    printf("HV: Initializing secondary %d\n", cpu);
    iodev_console_flush();

    mmu_init_secondary(cpu);
    iodev_console_flush();
    smp_call4(cpu, hv_init_secondary, (u64)&hv_secondary_info, 0, 0, 0);
    smp_wait(cpu);
    iodev_console_flush();

    printf("HV: Entering guest secondary %d at %p\n", cpu, entry);
    hv_started_cpus[cpu] = true;
    __atomic_add_fetch(&hv_cpus_in_guest, 1, __ATOMIC_ACQUIRE);

    iodev_console_flush();
    smp_call4(cpu, hv_enter_secondary, (u64)entry, (u64)regs, 0, 0);
}

void hv_rendezvous(void)
{
    if (!__atomic_load_n(&hv_cpus_in_guest, __ATOMIC_ACQUIRE))
        return;

    /* IPI all CPUs. This might result in spurious IPIs to the guest... */
    for (int i = 0; i < MAX_CPUS; i++) {
        if (i != smp_id() && hv_started_cpus[i]) {
            smp_send_ipi(i);
        }
    }
    while (__atomic_load_n(&hv_cpus_in_guest, __ATOMIC_ACQUIRE))
        ;
}

bool hv_switch_cpu(int cpu)
{
    if (cpu > MAX_CPUS || cpu < 0 || !hv_started_cpus[cpu]) {
        printf("HV: CPU #%d is inactive or invalid\n", cpu);
        return false;
    }
    printf("HV: switching to CPU #%d\n", cpu);
    hv_want_cpu = cpu;
    hv_rendezvous();
    return true;
}

void hv_pin_cpu(int cpu)
{
    hv_pinned_cpu = cpu;
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

void hv_maybe_exit(void)
{
    if (hv_should_exit) {
        hv_exit_guest();
    }
}

void hv_tick(struct exc_info *ctx)
{
    hv_wdt_pet();
    iodev_handle_events(uartproxy_iodev);
    if (iodev_can_read(uartproxy_iodev)) {
        if (hv_pinned_cpu == -1 || hv_pinned_cpu == smp_id())
            hv_exc_proxy(ctx, START_HV, HV_USER_INTERRUPT, NULL);
    }
    hv_vuart_poll();
}
