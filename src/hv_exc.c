/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "exception.h"
#include "smp.h"
#include "string.h"
#include "uart.h"
#include "uartproxy.h"

extern spinlock_t bhl;

#define _SYSREG_ISS(_1, _2, op0, op1, CRn, CRm, op2)                                               \
    (((op0) << ESR_ISS_MSR_OP0_SHIFT) | ((op1) << ESR_ISS_MSR_OP1_SHIFT) |                         \
     ((CRn) << ESR_ISS_MSR_CRn_SHIFT) | ((CRm) << ESR_ISS_MSR_CRm_SHIFT) |                         \
     ((op2) << ESR_ISS_MSR_OP2_SHIFT))
#define SYSREG_ISS(...) _SYSREG_ISS(__VA_ARGS__)

bool ipi_pending = false;
bool pmc_pending = false;
u64 pmc_irq_mode = 0;
static u64 exc_entry_pmcr0_cnt;

void hv_exit_guest(void) __attribute__((noreturn));

static u64 stolen_time = 0;
static u64 exc_entry_time;

void hv_exc_proxy(u64 *regs, uartproxy_boot_reason_t reason, uartproxy_exc_code_t type, void *extra)
{
    int from_el = FIELD_GET(SPSR_M, hv_get_spsr()) >> 2;

    hv_wdt_breadcrumb('P');

    struct uartproxy_exc_info exc_info = {
        .cpu_id = smp_id(),
        .spsr = hv_get_spsr(),
        .elr = hv_get_elr(),
        .esr = hv_get_esr(),
        .far = hv_get_far(),
        .afsr1 = hv_get_afsr1(),
        .sp = {mrs(SP_EL0), mrs(SP_EL1), 0},
        .mpidr = mrs(MPIDR_EL1),
        .elr_phys = hv_translate(hv_get_elr(), false, false),
        .far_phys = hv_translate(hv_get_far(), false, false),
        .sp_phys = hv_translate(from_el == 0 ? mrs(SP_EL0) : mrs(SP_EL1), false, false),
        .extra = extra,
    };
    memcpy(exc_info.regs, regs, sizeof(exc_info.regs));

    struct uartproxy_msg_start start = {
        .reason = reason,
        .code = type,
        .info = &exc_info,
    };

    hv_wdt_suspend();
    int ret = uartproxy_run(&start);
    hv_wdt_resume();

    switch (ret) {
        case EXC_RET_HANDLED:
            memcpy(regs, exc_info.regs, sizeof(exc_info.regs));
            hv_set_spsr(exc_info.spsr);
            hv_set_elr(exc_info.elr);
            msr(SP_EL0, exc_info.sp[0]);
            msr(SP_EL1, exc_info.sp[1]);
            hv_wdt_breadcrumb('p');
            return;
        case EXC_EXIT_GUEST:
            spin_unlock(&bhl);
            hv_exit_guest();
        default:
            printf("Guest exception not handled, rebooting.\n");
            print_regs(regs, 0);
            flush_and_reboot();
    }
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

    fiq_pending |= ipi_pending || pmc_pending;

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

static bool hv_handle_msr(u64 *regs, u64 iss)
{
    u64 reg = iss & (ESR_ISS_MSR_OP0 | ESR_ISS_MSR_OP2 | ESR_ISS_MSR_OP1 | ESR_ISS_MSR_CRn |
                     ESR_ISS_MSR_CRm);
    u64 rt = FIELD_GET(ESR_ISS_MSR_Rt, iss);
    bool is_read = iss & ESR_ISS_MSR_DIR;

    regs[31] = 0;

    switch (reg) {
        /* Some kind of timer */
        SYSREG_PASS(sys_reg(3, 7, 15, 1, 1));
        /* Noisy traps */
        SYSREG_MAP(SYS_ACTLR_EL1, SYS_IMP_APL_ACTLR_EL12)
        SYSREG_PASS(SYS_IMP_APL_HID4)
        SYSREG_PASS(SYS_IMP_APL_EHID4)
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
        /* IPI handling */
        SYSREG_PASS(SYS_IMP_APL_IPI_RR_LOCAL_EL1)
        SYSREG_PASS(SYS_IMP_APL_IPI_RR_GLOBAL_EL1)
        SYSREG_PASS(SYS_IMP_APL_IPI_CR_EL1)
        case SYSREG_ISS(SYS_IMP_APL_IPI_SR_EL1):
            if (is_read)
                regs[rt] = ipi_pending ? IPI_SR_PENDING : 0;
            else if (regs[rt] & IPI_SR_PENDING)
                ipi_pending = false;
            return true;
        /* shadow the interrupt mode and state flag */
        case SYSREG_ISS(SYS_IMP_APL_PMCR0):
            if (is_read) {
                u64 val = (mrs(SYS_IMP_APL_PMCR0) & ~PMCR0_IMODE_MASK) | pmc_irq_mode;
                regs[rt] = val | (pmc_pending ? PMCR0_IACT : 0) | exc_entry_pmcr0_cnt;
            } else {
                pmc_pending = !!(regs[rt] & PMCR0_IACT);
                pmc_irq_mode = regs[rt] & PMCR0_IMODE_MASK;
                exc_entry_pmcr0_cnt = regs[rt] & PMCR0_CNT_MASK;
                msr(SYS_IMP_APL_PMCR0, regs[rt] & ~exc_entry_pmcr0_cnt);
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

static void hv_exc_entry(u64 *regs)
{
    UNUSED(regs);
    spin_lock(&bhl);
    hv_wdt_breadcrumb('X');
    exc_entry_time = mrs(CNTPCT_EL0);
    /* disable PMU counters in the hypervisor */
    u64 pmcr0 = mrs(SYS_IMP_APL_PMCR0);
    exc_entry_pmcr0_cnt = pmcr0 & PMCR0_CNT_MASK;
    msr(SYS_IMP_APL_PMCR0, pmcr0 & ~PMCR0_CNT_MASK);
}

static void hv_exc_exit(u64 *regs)
{
    UNUSED(regs);
    hv_wdt_breadcrumb('x');
    hv_update_fiq();
    /* reenabale PMU counters */
    reg_set(SYS_IMP_APL_PMCR0, exc_entry_pmcr0_cnt);
    u64 lost = mrs(CNTPCT_EL0) - exc_entry_time;
    if (lost > 8)
        stolen_time += lost - 8;
    msr(CNTVOFF_EL2, stolen_time);
    spin_unlock(&bhl);
}

void hv_exc_sync(u64 *regs)
{
    hv_wdt_breadcrumb('S');
    hv_exc_entry(regs);
    bool handled = false;
    u64 esr = hv_get_esr();
    u32 ec = FIELD_GET(ESR_EC, esr);

    switch (ec) {
        case ESR_EC_DABORT_LOWER:
            hv_wdt_breadcrumb('D');
            handled = hv_handle_dabort(regs);
            break;
        case ESR_EC_MSR:
            hv_wdt_breadcrumb('M');
            handled = hv_handle_msr(regs, FIELD_GET(ESR_ISS, esr));
            break;
        case ESR_EC_IMPDEF:
            hv_wdt_breadcrumb('A');
            switch (FIELD_GET(ESR_ISS, esr)) {
                case ESR_ISS_IMPDEF_MSR:
                    handled = hv_handle_msr(regs, hv_get_afsr1());
                    break;
            }
            break;
    }

    if (handled) {
        hv_wdt_breadcrumb('+');
        hv_set_elr(hv_get_elr() + 4);
    } else {
        hv_wdt_breadcrumb('-');
        hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_SYNC, NULL);
    }

    hv_exc_exit(regs);
    hv_wdt_breadcrumb('s');
}

void hv_exc_irq(u64 *regs)
{
    hv_wdt_breadcrumb('I');
    hv_exc_entry(regs);
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_IRQ, NULL);
    hv_exc_exit(regs);
    hv_wdt_breadcrumb('i');
}

void hv_exc_fiq(u64 *regs)
{
    hv_wdt_breadcrumb('F');
    hv_exc_entry(regs);
    if (mrs(CNTP_CTL_EL0) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        msr(CNTP_CTL_EL0, CNTx_CTL_ISTATUS | CNTx_CTL_IMASK | CNTx_CTL_ENABLE);
        hv_tick(regs);
        hv_arm_tick();
    }

    if (mrs(CNTV_CTL_EL0) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        msr(CNTV_CTL_EL0, CNTx_CTL_ISTATUS | CNTx_CTL_IMASK | CNTx_CTL_ENABLE);
        hv_exc_proxy(regs, START_HV, HV_VTIMER, NULL);
    }

    u64 reg = mrs(SYS_IMP_APL_PMCR0);
    if ((reg & (PMCR0_IMODE_MASK | PMCR0_IACT)) == (PMCR0_IMODE_FIQ | PMCR0_IACT)) {
#ifdef DEBUG_PMU_IRQ
        printf("[FIQ] PMC IRQ, masking and delivering to the guest\n");
#endif
        reg_clr(SYS_IMP_APL_PMCR0, PMCR0_IACT | PMCR0_IMODE_MASK);
        pmc_pending = true;
    }

    reg = mrs(SYS_IMP_APL_UPMCR0);
    if ((reg & UPMCR0_IMODE_MASK) == UPMCR0_IMODE_FIQ && (mrs(SYS_IMP_APL_UPMSR) & UPMSR_IACT)) {
        printf("[FIQ] UPMC IRQ, masking");
        reg_clr(SYS_IMP_APL_UPMCR0, UPMCR0_IMODE_MASK);
        hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_FIQ, NULL);
    }

    if (mrs(SYS_IMP_APL_IPI_SR_EL1) & IPI_SR_PENDING) {
        ipi_pending = true;
        msr(SYS_IMP_APL_IPI_SR_EL1, IPI_SR_PENDING);
        sysop("isb");
    }

    // Handles guest timers
    hv_exc_exit(regs);
    hv_wdt_breadcrumb('f');
}

void hv_exc_serr(u64 *regs)
{
    hv_wdt_breadcrumb('E');
    hv_exc_entry(regs);
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_SERROR, NULL);
    hv_exc_exit(regs);
    hv_wdt_breadcrumb('e');
}
