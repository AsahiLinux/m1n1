/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "exception.h"
#include "string.h"
#include "uartproxy.h"

void hv_exit_guest(void) __attribute__((noreturn));

void hv_exc_proxy(u64 *regs, uartproxy_boot_reason_t reason, uartproxy_exc_code_t type, void *extra)
{
    int from_el = FIELD_GET(SPSR_M, mrs(SPSR_EL2)) >> 2;

    struct uartproxy_exc_info exc_info = {
        .spsr = mrs(SPSR_EL2),
        .elr = mrs(ELR_EL2),
        .esr = mrs(ESR_EL2),
        .far = mrs(FAR_EL2),
        .sp = {mrs(SP_EL0), mrs(SP_EL1), 0},
        .mpidr = mrs(MPIDR_EL1),
        .elr_phys = hv_translate(mrs(ELR_EL2), false, false),
        .far_phys = hv_translate(mrs(FAR_EL2), false, false),
        .sp_phys = hv_translate(from_el == 0 ? mrs(SP_EL0) : mrs(SP_EL1), false, false),
        .extra = extra,
    };
    memcpy(exc_info.regs, regs, sizeof(exc_info.regs));

    struct uartproxy_msg_start start = {
        .reason = reason,
        .code = type,
        .info = &exc_info,
    };

    int ret = uartproxy_run(&start);

    switch (ret) {
        case EXC_RET_STEP:
        case EXC_RET_HANDLED:
            memcpy(regs, exc_info.regs, sizeof(exc_info.regs));
            msr(SPSR_EL2, exc_info.spsr);
            msr(ELR_EL2, exc_info.elr);
            msr(SP_EL0, exc_info.sp[0]);
            msr(SP_EL1, exc_info.sp[1]);
            if (ret == EXC_RET_STEP) {
                msr(CNTV_TVAL_EL0, 256);
                msr(CNTV_CTL_EL0, 1);
            }
            return;
        case EXC_EXIT_GUEST:
            hv_exit_guest();
        default:
            printf("Guest exception not handled, rebooting.\n");
            print_regs(regs, 0);
            flush_and_reboot();
    }
}

void hv_exc_sync(u64 *regs)
{
    bool handled = false;
    u64 esr = mrs(ESR_EL2);
    u32 ec = FIELD_GET(ESR_EC, esr);

    switch (ec) {
        case ESR_EC_DABORT_LOWER:
            handled = hv_handle_dabort(regs);
            break;
    }

    if (handled)
        msr(ELR_EL2, mrs(ELR_EL2) + 4);
    else
        hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_SYNC, NULL);
}

void hv_exc_irq(u64 *regs)
{
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_IRQ, NULL);
}

void hv_exc_fiq(u64 *regs)
{
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_FIQ, NULL);
}

void hv_exc_serr(u64 *regs)
{
    hv_exc_proxy(regs, START_EXCEPTION_LOWER, EXC_SERROR, NULL);
}
