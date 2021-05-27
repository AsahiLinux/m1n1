/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "exception.h"
#include "string.h"
#include "uart.h"
#include "uartproxy.h"

#define _SYSREG_ISS(_1, _2, op0, op1, CRn, CRm, op2)                                               \
    (((op0) << ESR_ISS_MSR_OP0_SHIFT) | ((op1) << ESR_ISS_MSR_OP1_SHIFT) |                         \
     ((CRn) << ESR_ISS_MSR_CRn_SHIFT) | ((CRm) << ESR_ISS_MSR_CRm_SHIFT) |                         \
     ((op2) << ESR_ISS_MSR_OP2_SHIFT))
#define SYSREG_ISS(...) _SYSREG_ISS(__VA_ARGS__)

bool ipi_pending = false;

void hv_exit_guest(void) __attribute__((noreturn));

void hv_exc_proxy(u64 *regs, uartproxy_boot_reason_t reason, uartproxy_exc_code_t type, void *extra)
{
    int from_el = FIELD_GET(SPSR_M, hv_get_spsr()) >> 2;

    hv_wdt_breadcrumb('P');

    struct uartproxy_exc_info exc_info = {
        .spsr = hv_get_spsr(),
        .elr = hv_get_elr(),
        .esr = hv_get_esr(),
        .far = hv_get_far(),
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
        case EXC_RET_STEP:
        case EXC_RET_HANDLED:
            memcpy(regs, exc_info.regs, sizeof(exc_info.regs));
            hv_set_spsr(exc_info.spsr);
            hv_set_elr(exc_info.elr);
            msr(SP_EL0, exc_info.sp[0]);
            msr(SP_EL1, exc_info.sp[1]);
            if (ret == EXC_RET_STEP) {
                msr(CNTV_TVAL_EL0, 100);
                msr(CNTV_CTL_EL0, CNTx_CTL_ENABLE);
            }
            hv_wdt_breadcrumb('p');
            return;
        case EXC_EXIT_GUEST:
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
        reg_clr(SYS_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_P);
    } else {
        reg_set(SYS_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_P);
    }

    if (mrs(CNTV_CTL_EL02) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        fiq_pending = true;
        reg_clr(SYS_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_V);
    } else {
        reg_set(SYS_VM_TMR_FIQ_ENA_EL2, VM_TMR_FIQ_ENA_ENA_V);
    }

    fiq_pending |= ipi_pending;

    sysop("isb");

    if ((hcr & HCR_VF) && !fiq_pending) {
        hv_write_hcr(hcr & ~HCR_VF);
    } else if (!(hcr & HCR_VF) && fiq_pending) {
        hv_write_hcr(hcr | HCR_VF);
    }
}

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
        /* IPI handling */
        SYSREG_PASS(SYS_IPI_RR_LOCAL_EL1)
        SYSREG_PASS(SYS_IPI_RR_GLOBAL_EL1)
        SYSREG_PASS(SYS_IPI_CR_EL1)
        case SYSREG_ISS(SYS_IPI_SR_EL1):
            if (is_read)
                regs[rt] = ipi_pending ? IPI_SR_PENDING : 0;
            else if (regs[rt] & IPI_SR_PENDING)
                ipi_pending = false;
            return true;
    }

    return false;
}

static void hv_exc_exit(u64 *regs)
{
    hv_wdt_breadcrumb('x');
    if (iodev_can_read(uartproxy_iodev))
        hv_exc_proxy(regs, START_HV, HV_USER_INTERRUPT, NULL);
    hv_update_fiq();
}

void hv_exc_sync(u64 *regs)
{
    hv_wdt_breadcrumb('S');
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
                    handled = hv_handle_msr(regs, mrs(AFSR1_EL1));
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
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_IRQ, NULL);
    hv_exc_exit(regs);
    hv_wdt_breadcrumb('i');
}

void hv_exc_fiq(u64 *regs)
{
    hv_wdt_breadcrumb('F');
    if (mrs(CNTP_CTL_EL0) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        msr(CNTP_CTL_EL0, CNTx_CTL_ISTATUS | CNTx_CTL_IMASK | CNTx_CTL_ENABLE);
        hv_tick();
        hv_arm_tick();
    }

    if (mrs(CNTV_CTL_EL0) == (CNTx_CTL_ISTATUS | CNTx_CTL_ENABLE)) {
        msr(CNTV_CTL_EL0, CNTx_CTL_ISTATUS | CNTx_CTL_IMASK | CNTx_CTL_ENABLE);
        hv_exc_proxy(regs, START_HV, HV_VTIMER, NULL);
    }

    u64 reg = mrs(SYS_IMP_APL_PMCR0);
    if ((reg & (PMCR0_IMODE_MASK | PMCR0_IACT)) == (PMCR0_IMODE_FIQ | PMCR0_IACT)) {
        printf("[FIQ] PMC IRQ, masking");
        reg_clr(SYS_IMP_APL_PMCR0, PMCR0_IACT | PMCR0_IMODE_MASK);
        hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_FIQ, NULL);
    }

    reg = mrs(SYS_IMP_APL_UPMCR0);
    if ((reg & UPMCR0_IMODE_MASK) == UPMCR0_IMODE_FIQ && (mrs(SYS_IMP_APL_UPMSR) & UPMSR_IACT)) {
        printf("[FIQ] UPMC IRQ, masking");
        reg_clr(SYS_IMP_APL_UPMCR0, UPMCR0_IMODE_MASK);
        hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_FIQ, NULL);
    }

    if (mrs(SYS_IPI_SR_EL1) & IPI_SR_PENDING) {
        ipi_pending = true;
        msr(SYS_IPI_SR_EL1, IPI_SR_PENDING);
        sysop("isb");
    }

    // Handles guest timers
    hv_exc_exit(regs);
    hv_wdt_breadcrumb('f');
}

void hv_exc_serr(u64 *regs)
{
    hv_wdt_breadcrumb('E');
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_SERROR, NULL);
    hv_exc_exit(regs);
    hv_wdt_breadcrumb('e');
}
