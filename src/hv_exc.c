/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "exception.h"
#include "smp.h"
#include "string.h"
#include "uart.h"
#include "uartproxy.h"

#define TIME_ACCOUNTING

extern spinlock_t bhl;

#define _SYSREG_ISS(_1, _2, op0, op1, CRn, CRm, op2)                                               \
    (((op0) << ESR_ISS_MSR_OP0_SHIFT) | ((op1) << ESR_ISS_MSR_OP1_SHIFT) |                         \
     ((CRn) << ESR_ISS_MSR_CRn_SHIFT) | ((CRm) << ESR_ISS_MSR_CRm_SHIFT) |                         \
     ((op2) << ESR_ISS_MSR_OP2_SHIFT))
#define SYSREG_ISS(...) _SYSREG_ISS(__VA_ARGS__)

#define PERCPU(x) pcpu[mrs(TPIDR_EL2)].x

struct hv_pcpu_data {
    u32 ipi_queued;
    u32 ipi_pending;
    u32 pmc_pending;
    u64 pmc_irq_mode;
    u64 exc_entry_pmcr0_cnt;
} ALIGNED(64);

struct hv_pcpu_data pcpu[MAX_CPUS];

void hv_exit_guest(void) __attribute__((noreturn));

static u64 stolen_time = 0;
static u64 exc_entry_time;

extern u32 hv_cpus_in_guest;
extern int hv_pinned_cpu;
extern int hv_want_cpu;

static bool time_stealing = true;

static void _hv_exc_proxy(struct exc_info *ctx, uartproxy_boot_reason_t reason, u32 type,
                          void *extra)
{
    int from_el = FIELD_GET(SPSR_M, ctx->spsr) >> 2;

    hv_wdt_breadcrumb('P');

    /*
     * Get all the CPUs into the HV before running the proxy, to make sure they all exit to
     * the guest with a consistent time offset.
     */
    if (time_stealing)
        hv_rendezvous();

    u64 entry_time = mrs(CNTPCT_EL0);

    ctx->elr_phys = hv_translate(ctx->elr, false, false, NULL);
    ctx->far_phys = hv_translate(ctx->far, false, false, NULL);
    ctx->sp_phys = hv_translate(from_el == 0 ? ctx->sp[0] : ctx->sp[1], false, false, NULL);
    ctx->extra = extra;

    struct uartproxy_msg_start start = {
        .reason = reason,
        .code = type,
        .info = ctx,
    };

    hv_wdt_suspend();
    int ret = uartproxy_run(&start);
    hv_wdt_resume();

    switch (ret) {
        case EXC_RET_HANDLED:
            hv_wdt_breadcrumb('p');
            if (time_stealing) {
                u64 lost = mrs(CNTPCT_EL0) - entry_time;
                stolen_time += lost;
            }
            break;
        case EXC_EXIT_GUEST:
            hv_rendezvous();
            spin_unlock(&bhl);
            hv_exit_guest(); // does not return
        default:
            printf("Guest exception not handled, rebooting.\n");
            print_regs(ctx->regs, 0);
            flush_and_reboot(); // does not return
    }
}

static void hv_maybe_switch_cpu(struct exc_info *ctx, uartproxy_boot_reason_t reason, u32 type,
                                void *extra)
{
    while (hv_want_cpu != -1) {
        if (hv_want_cpu == smp_id()) {
            hv_want_cpu = -1;
            _hv_exc_proxy(ctx, reason, type, extra);
        } else {
            // Unlock the HV so the target CPU can get into the proxy
            spin_unlock(&bhl);
            while (hv_want_cpu != -1)
                sysop("dmb sy");
            spin_lock(&bhl);
        }
    }
}

void hv_exc_proxy(struct exc_info *ctx, uartproxy_boot_reason_t reason, u32 type, void *extra)
{
    /*
     * Wait while another CPU is pinned or being switched to.
     * If a CPU switch is requested, handle it before actually handling the
     * exception. We still tell the host the real reason code, though.
     */
    while ((hv_pinned_cpu != -1 && hv_pinned_cpu != smp_id()) || hv_want_cpu != -1) {
        if (hv_want_cpu == smp_id()) {
            hv_want_cpu = -1;
            _hv_exc_proxy(ctx, reason, type, extra);
        } else {
            // Unlock the HV so the target CPU can get into the proxy
            spin_unlock(&bhl);
            while ((hv_pinned_cpu != -1 && hv_pinned_cpu != smp_id()) || hv_want_cpu != -1)
                sysop("dmb sy");
            spin_lock(&bhl);
        }
    }

    /* Handle the actual exception */
    _hv_exc_proxy(ctx, reason, type, extra);

    /*
     * If as part of handling this exception we want to switch CPUs, handle it without returning
     * to the guest.
     */
    hv_maybe_switch_cpu(ctx, reason, type, extra);
}

void hv_set_time_stealing(bool enabled, bool reset)
{
    time_stealing = enabled;
    if (reset)
        stolen_time = 0;
}

static void hv_update_fiq(void)
{
    u64 hcr = mrs(HCR_EL2);
    bool fiq_pending = false;

    if (mrs(CNTP_CTL_EL02) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        fiq_pending = true;
        reg_clr(SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_P);
    } else {
        reg_set(SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_P);
    }

    if (mrs(CNTV_CTL_EL02) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        fiq_pending = true;
        reg_clr(SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_V);
    } else {
        reg_set(SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_V);
    }

    fiq_pending |= PERCPU(ipi_pending) || PERCPU(pmc_pending);

    sysop("isb");

    if ((hcr & HCR_VF) && !fiq_pending) {
        hv_write_hcr(hcr & ~HCR_VF);
    } else if (!(hcr & HCR_VF) && fiq_pending) {
        hv_write_hcr(hcr | HCR_VF);
    }
}

#define SYSREG_MAP(sr, to)                                                                         \
    case SYSREG_ISS(sr):                                                                           \
        if (is_read)                                                                               \
            regs[rt] = _mrs(sr_tkn(to));                                                           \
        else                                                                                       \
            _msr(sr_tkn(to), regs[rt]);                                                            \
        return true;

#define SYSREG_PASS(sr)                                                                            \
    case SYSREG_ISS(sr):                                                                           \
        if (is_read)                                                                               \
            regs[rt] = _mrs(sr_tkn(sr));                                                           \
        else                                                                                       \
            _msr(sr_tkn(sr), regs[rt]);                                                            \
        return true;

static bool hv_handle_msr(struct exc_info *ctx, u64 iss)
{
    u64 reg = iss & (ESR_ISS_MSR_OP0 | ESR_ISS_MSR_OP2 | ESR_ISS_MSR_OP1 | ESR_ISS_MSR_CRn |
                     ESR_ISS_MSR_CRm);
    u64 rt = FIELD_GET(ESR_ISS_MSR_Rt, iss);
    bool is_read = iss & ESR_ISS_MSR_DIR;

    u64 *regs = ctx->regs;

    regs[31] = 0;

    switch (reg) {
        /* Some kind of timer */
        SYSREG_PASS(sys_reg(3, 7, 15, 1, 1));
        SYSREG_PASS(sys_reg(3, 7, 15, 3, 1));
        /* Spammy stuff seen on t600x p-cores */
        SYSREG_PASS(sys_reg(3, 2, 15, 12, 0));
        SYSREG_PASS(sys_reg(3, 2, 15, 13, 0));
        SYSREG_PASS(sys_reg(3, 2, 15, 14, 0));
        SYSREG_PASS(sys_reg(3, 2, 15, 15, 0));
        SYSREG_PASS(sys_reg(3, 1, 15, 7, 0));
        SYSREG_PASS(sys_reg(3, 1, 15, 8, 0));
        SYSREG_PASS(sys_reg(3, 1, 15, 9, 0));
        SYSREG_PASS(sys_reg(3, 1, 15, 10, 0));
        /* Noisy traps */
        SYSREG_MAP(SYS_ACTLR_EL1, SYS_IMP_APL_ACTLR_EL12)
        SYSREG_PASS(SYS_IMP_APL_HID4)
        SYSREG_PASS(SYS_IMP_APL_EHID4)
        /* We don't normally trap hese, but if we do, they're noisy */
        SYSREG_PASS(SYS_IMP_APL_GXF_STATUS_EL1)
        SYSREG_PASS(SYS_IMP_APL_CNTVCT_ALIAS_EL0)
        SYSREG_PASS(SYS_IMP_APL_TPIDR_GL1)
        SYSREG_MAP(SYS_IMP_APL_SPSR_GL1, SYS_IMP_APL_SPSR_GL12)
        SYSREG_MAP(SYS_IMP_APL_ASPSR_GL1, SYS_IMP_APL_ASPSR_GL12)
        SYSREG_MAP(SYS_IMP_APL_ELR_GL1, SYS_IMP_APL_ELR_GL12)
        SYSREG_MAP(SYS_IMP_APL_ESR_GL1, SYS_IMP_APL_ESR_GL12)
        SYSREG_MAP(SYS_IMP_APL_SPRR_PERM_EL1, SYS_IMP_APL_SPRR_PERM_EL12)
        SYSREG_MAP(SYS_IMP_APL_APCTL_EL1, SYS_IMP_APL_APCTL_EL12)
        SYSREG_MAP(SYS_IMP_APL_AMX_CTL_EL1, SYS_IMP_APL_AMX_CTL_EL12)
        /* FIXME:Might be wrong */
        SYSREG_PASS(sys_reg(3, 4, 15, 1, 3))
        /* pass through PMU handling */
        SYSREG_PASS(SYS_IMP_APL_PMCR1)
        SYSREG_PASS(SYS_IMP_APL_PMCR2)
        SYSREG_PASS(SYS_IMP_APL_PMCR3)
        SYSREG_PASS(SYS_IMP_APL_PMCR4)
        SYSREG_PASS(SYS_IMP_APL_PMESR0)
        SYSREG_PASS(SYS_IMP_APL_PMESR1)
        SYSREG_PASS(SYS_IMP_APL_PMSR)
#ifndef DEBUG_PMU_IRQ
        SYSREG_PASS(SYS_IMP_APL_PMC0)
#endif
        SYSREG_PASS(SYS_IMP_APL_PMC1)
        SYSREG_PASS(SYS_IMP_APL_PMC2)
        SYSREG_PASS(SYS_IMP_APL_PMC3)
        SYSREG_PASS(SYS_IMP_APL_PMC4)
        SYSREG_PASS(SYS_IMP_APL_PMC5)
        SYSREG_PASS(SYS_IMP_APL_PMC6)
        SYSREG_PASS(SYS_IMP_APL_PMC7)
        SYSREG_PASS(SYS_IMP_APL_PMC8)
        SYSREG_PASS(SYS_IMP_APL_PMC9)

        /* Outer Sharable TLB maintenance instructions */
        SYSREG_PASS(sys_reg(1, 0, 8, 1, 0)) // TLBI VMALLE1OS
        SYSREG_PASS(sys_reg(1, 0, 8, 1, 1)) // TLBI VAE1OS
        SYSREG_PASS(sys_reg(1, 0, 8, 1, 2)) // TLBI ASIDE1OS
        SYSREG_PASS(sys_reg(1, 0, 8, 5, 1)) // TLBI RVAE1OS

        /*
         * Handle this one here because m1n1/Linux (will) use it for explicit cpuidle.
         * We can pass it through; going into deep sleep doesn't break the HV since we
         * don't do any wfis that assume otherwise in m1n1. However, don't het macOS
         * disable WFI ret (when going into systemwide sleep), since that breaks things.
         */
        case SYSREG_ISS(SYS_IMP_APL_CYC_OVRD):
            if (is_read) {
                regs[rt] = mrs(SYS_IMP_APL_CYC_OVRD);
            } else {
                msr(SYS_IMP_APL_CYC_OVRD, regs[rt] & ~CYC_OVRD_DISABLE_WFI_RET);
                if (regs[rt] & CYC_OVRD_DISABLE_WFI_RET)
                    printf("msr(SYS_IMP_APL_CYC_OVRD, 0x%08lx): Filtered WFI RET disable\n",
                           regs[rt]);
            }
            return true;
            /* clang-format off */

        /* IPI handling */
        SYSREG_PASS(SYS_IMP_APL_IPI_CR_EL1)
        /* clang-format on */
        case SYSREG_ISS(SYS_IMP_APL_IPI_RR_LOCAL_EL1): {
            assert(!is_read);
            u64 mpidr = (regs[rt] & 0xff) | (mrs(MPIDR_EL1) & 0xffff00);
            msr(SYS_IMP_APL_IPI_RR_LOCAL_EL1, regs[rt]);
            for (int i = 0; i < MAX_CPUS; i++)
                if (mpidr == smp_get_mpidr(i))
                    pcpu[i].ipi_queued = true;
            return true;
        }
        case SYSREG_ISS(SYS_IMP_APL_IPI_RR_GLOBAL_EL1):
            assert(!is_read);
            u64 mpidr = (regs[rt] & 0xff) | ((regs[rt] & 0xff0000) >> 8);
            msr(SYS_IMP_APL_IPI_RR_GLOBAL_EL1, regs[rt]);
            for (int i = 0; i < MAX_CPUS; i++) {
                if (mpidr == (smp_get_mpidr(i) & 0xffff))
                    pcpu[i].ipi_queued = true;
            }
            return true;
        case SYSREG_ISS(SYS_IMP_APL_IPI_SR_EL1):
            if (is_read)
                regs[rt] = PERCPU(ipi_pending) ? IPI_SR_PENDING : 0;
            else if (regs[rt] & IPI_SR_PENDING)
                PERCPU(ipi_pending) = false;
            return true;
        /* shadow the interrupt mode and state flag */
        case SYSREG_ISS(SYS_IMP_APL_PMCR0):
            if (is_read) {
                u64 val = (mrs(SYS_IMP_APL_PMCR0) & ~PMCR0_IMODE_MASK) | PERCPU(pmc_irq_mode);
                regs[rt] =
                    val | (PERCPU(pmc_pending) ? PMCR0_IACT : 0) | PERCPU(exc_entry_pmcr0_cnt);
            } else {
                PERCPU(pmc_pending) = !!(regs[rt] & PMCR0_IACT);
                PERCPU(pmc_irq_mode) = regs[rt] & PMCR0_IMODE_MASK;
                PERCPU(exc_entry_pmcr0_cnt) = regs[rt] & PMCR0_CNT_MASK;
                msr(SYS_IMP_APL_PMCR0, regs[rt] & ~PERCPU(exc_entry_pmcr0_cnt));
            }
            return true;
#ifdef DEBUG_PMU_IRQ
        case SYSREG_ISS(SYS_IMP_APL_PMC0):
            if (is_read) {
                regs[rt] = mrs(SYS_IMP_APL_PMC0);
            } else {
                msr(SYS_IMP_APL_PMC0, regs[rt]);
                printf("msr(SYS_IMP_APL_PMC0, 0x%04lx_%08lx)\n", regs[rt] >> 32,
                       regs[rt] & 0xFFFFFFFF);
            }
            return true;
#endif
        /* M1RACLES reg, handle here due to silly 12.0 "mitigation" */
        case SYSREG_ISS(sys_reg(3, 5, 15, 10, 1)):
            if (is_read)
                regs[rt] = 0;
            return true;
    }

    return false;
}

static void hv_exc_entry(struct exc_info *ctx)
{
    ctx->spsr = hv_get_spsr();
    ctx->elr = hv_get_elr();
    ctx->esr = hv_get_esr();
    ctx->far = hv_get_far();
    ctx->afsr1 = hv_get_afsr1();
    ctx->sp[0] = mrs(SP_EL0);
    ctx->sp[1] = mrs(SP_EL1);
    ctx->sp[2] = (u64)ctx;
    ctx->cpu_id = smp_id();
    ctx->mpidr = mrs(MPIDR_EL1);

    sysop("isb");

    // Enable SErrors in the HV, but only if not already pending
    if (!(mrs(ISR_EL1) & 0x100))
        sysop("msr daifclr, 4");

    __atomic_sub_fetch(&hv_cpus_in_guest, 1, __ATOMIC_ACQUIRE);
    spin_lock(&bhl);
    hv_wdt_breadcrumb('X');
    exc_entry_time = mrs(CNTPCT_EL0);
    /* disable PMU counters in the hypervisor */
    u64 pmcr0 = mrs(SYS_IMP_APL_PMCR0);
    PERCPU(exc_entry_pmcr0_cnt) = pmcr0 & PMCR0_CNT_MASK;
    msr(SYS_IMP_APL_PMCR0, pmcr0 & ~PMCR0_CNT_MASK);
}

static void hv_exc_exit(struct exc_info *ctx)
{
    hv_wdt_breadcrumb('x');
    hv_update_fiq();
    /* reenable PMU counters */
    reg_set(SYS_IMP_APL_PMCR0, PERCPU(exc_entry_pmcr0_cnt));
    msr(CNTVOFF_EL2, stolen_time);
    spin_unlock(&bhl);
    __atomic_add_fetch(&hv_cpus_in_guest, 1, __ATOMIC_ACQUIRE);

    hv_set_spsr(ctx->spsr);
    hv_set_elr(ctx->elr);
    msr(SP_EL0, ctx->sp[0]);
    msr(SP_EL1, ctx->sp[1]);
}

void hv_exc_sync(struct exc_info *ctx)
{
    hv_wdt_breadcrumb('S');
    hv_exc_entry(ctx);
    bool handled = false;
    u32 ec = FIELD_GET(ESR_EC, ctx->esr);

    switch (ec) {
        case ESR_EC_DABORT_LOWER:
            hv_wdt_breadcrumb('D');
            handled = hv_handle_dabort(ctx);
            break;
        case ESR_EC_MSR:
            hv_wdt_breadcrumb('M');
            handled = hv_handle_msr(ctx, FIELD_GET(ESR_ISS, ctx->esr));
            break;
        case ESR_EC_IMPDEF:
            hv_wdt_breadcrumb('A');
            switch (FIELD_GET(ESR_ISS, ctx->esr)) {
                case ESR_ISS_IMPDEF_MSR:
                    handled = hv_handle_msr(ctx, ctx->afsr1);
                    break;
            }
            break;
    }

    if (handled) {
        hv_wdt_breadcrumb('+');
        ctx->elr += 4;
    } else {
        hv_wdt_breadcrumb('-');
        // VM code can forward a nested SError exception here
        if (FIELD_GET(ESR_EC, ctx->esr) == ESR_EC_SERROR)
            hv_exc_proxy(ctx, START_EXCEPTION_LOWER, EXC_SERROR, NULL);
        else
            hv_exc_proxy(ctx, START_EXCEPTION_LOWER, EXC_SYNC, NULL);
    }

    hv_exc_exit(ctx);
    hv_wdt_breadcrumb('s');
}

void hv_exc_irq(struct exc_info *ctx)
{
    hv_wdt_breadcrumb('I');
    hv_exc_entry(ctx);
    hv_exc_proxy(ctx, START_EXCEPTION_LOWER, EXC_IRQ, NULL);
    hv_exc_exit(ctx);
    hv_wdt_breadcrumb('i');
}

void hv_exc_fiq(struct exc_info *ctx)
{
    bool tick = false;

    hv_maybe_exit();

    if (mrs(CNTP_CTL_EL0) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        msr(CNTP_CTL_EL0, CNTx_CTL_ISTATUS | CNTx_CTL_IMASK | CNTx_CTL_ENABLE);
        tick = true;
    }

    int interruptible_cpu = hv_pinned_cpu;
    if (interruptible_cpu == -1)
        interruptible_cpu = 0;

    if (smp_id() != interruptible_cpu && !(mrs(ISR_EL1) & 0x40) && hv_want_cpu == -1) {
        // Non-interruptible CPU and it was just a timer tick (or spurious), so just update FIQs
        hv_update_fiq();
        hv_arm_tick();
        return;
    }

    // Slow (single threaded) path
    hv_wdt_breadcrumb('F');
    hv_exc_entry(ctx);

    // Only poll for HV events in the interruptible CPU
    if (tick) {
        if (smp_id() == interruptible_cpu)
            hv_tick(ctx);
        hv_arm_tick();
    }

    if (mrs(CNTV_CTL_EL0) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        msr(CNTV_CTL_EL0, CNTx_CTL_ISTATUS | CNTx_CTL_IMASK | CNTx_CTL_ENABLE);
        hv_exc_proxy(ctx, START_HV, HV_VTIMER, NULL);
    }

    u64 reg = mrs(SYS_IMP_APL_PMCR0);
    if ((reg & (PMCR0_IMODE_MASK | PMCR0_IACT)) == (PMCR0_IMODE_FIQ | PMCR0_IACT)) {
#ifdef DEBUG_PMU_IRQ
        printf("[FIQ] PMC IRQ, masking and delivering to the guest\n");
#endif
        reg_clr(SYS_IMP_APL_PMCR0, PMCR0_IACT | PMCR0_IMODE_MASK);
        PERCPU(pmc_pending) = true;
    }

    reg = mrs(SYS_IMP_APL_UPMCR0);
    if ((reg & UPMCR0_IMODE_MASK) == UPMCR0_IMODE_FIQ && (mrs(SYS_IMP_APL_UPMSR) & UPMSR_IACT)) {
        printf("[FIQ] UPMC IRQ, masking");
        reg_clr(SYS_IMP_APL_UPMCR0, UPMCR0_IMODE_MASK);
        hv_exc_proxy(ctx, START_EXCEPTION_LOWER, EXC_FIQ, NULL);
    }

    if (mrs(SYS_IMP_APL_IPI_SR_EL1) & IPI_SR_PENDING) {
        if (PERCPU(ipi_queued)) {
            PERCPU(ipi_pending) = true;
            PERCPU(ipi_queued) = false;
        }
        msr(SYS_IMP_APL_IPI_SR_EL1, IPI_SR_PENDING);
        sysop("isb");
    }

    hv_maybe_switch_cpu(ctx, START_HV, HV_CPU_SWITCH, NULL);

    // Handles guest timers
    hv_exc_exit(ctx);
    hv_wdt_breadcrumb('f');
}

void hv_exc_serr(struct exc_info *ctx)
{
    hv_wdt_breadcrumb('E');
    hv_exc_entry(ctx);
    hv_exc_proxy(ctx, START_EXCEPTION_LOWER, EXC_SERROR, NULL);
    hv_exc_exit(ctx);
    hv_wdt_breadcrumb('e');
}
