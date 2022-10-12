/* SPDX-License-Identifier: MIT */

#include "exception.h"
#include "aic.h"
#include "aic_regs.h"
#include "cpu_regs.h"
#include "gxf.h"
#include "iodev.h"
#include "memory.h"
#include "uart.h"
#include "utils.h"

#define EL0_STACK_SIZE 0x4000

u8 el0_stack[EL0_STACK_SIZE] ALIGNED(64);
void *el0_stack_base = (void *)(u64)(&el0_stack[EL0_STACK_SIZE]);

extern char _vectors_start[0];
extern char _el1_vectors_start[0];

volatile enum exc_guard_t exc_guard = GUARD_OFF;
volatile int exc_count = 0;

void el0_ret(void);
void el1_ret(void);

static char *m_table[0x10] = {
    [0x00] = "EL0t", //
    [0x04] = "EL1t", //
    [0x05] = "EL1h", //
    [0x08] = "EL2t", //
    [0x09] = "EL2h", //
};

static char *gl_m_table[0x10] = {
    [0x00] = "GL0t", //
    [0x04] = "GL1t", //
    [0x05] = "GL1h", //
    [0x08] = "GL2t", //
    [0x09] = "GL2h", //
};

static char *ec_table[0x40] = {
    [0x00] = "unknown",
    [0x01] = "wf*",
    [0x03] = "c15 mcr/mrc",
    [0x04] = "c15 mcrr/mrrc",
    [0x05] = "c14 mcr/mrc",
    [0x06] = "ldc/stc",
    [0x07] = "FP off",
    [0x08] = "VMRS access",
    [0x09] = "PAC off",
    [0x0a] = "ld/st64b",
    [0x0c] = "c14 mrrc",
    [0x0d] = "branch target",
    [0x0e] = "illegal state",
    [0x11] = "svc in a32",
    [0x12] = "hvc in a32",
    [0x13] = "smc in a32",
    [0x15] = "svc in a64",
    [0x16] = "hvc in a64",
    [0x17] = "smc in a64",
    [0x18] = "other mcr/mrc/sys",
    [0x19] = "SVE off",
    [0x1a] = "eret",
    [0x1c] = "PAC failure",
    [0x20] = "instruction abort (lower)",
    [0x21] = "instruction abort (current)",
    [0x22] = "pc misaligned",
    [0x24] = "data abort (lower)",
    [0x25] = "data abort (current)",
    [0x26] = "sp misaligned",
    [0x28] = "FP exception (a32)",
    [0x2c] = "FP exception (a64)",
    [0x2f] = "SError",
    [0x30] = "BP (lower)",
    [0x31] = "BP (current)",
    [0x32] = "step (lower)",
    [0x33] = "step (current)",
    [0x34] = "watchpoint (lower)",
    [0x35] = "watchpoint (current)",
    [0x38] = "bkpt (a32)",
    [0x3a] = "vector catch (a32)",
    [0x3c] = "brk (a64)",
};

static const char *get_exception_source(u64 spsr)
{
    u64 aspsr = in_gl12() ? mrs(SYS_IMP_APL_ASPSR_GL1) : 0;
    const char *m_desc = NULL;

    if (aspsr & 1)
        m_desc = gl_m_table[spsr & 0xf];
    else
        m_desc = m_table[spsr & 0xf];

    if (!m_desc)
        m_desc = "?";

    return m_desc;
}

static const char *get_exception_level(void)
{
    u64 lvl = mrs(CurrentEL);

    if (in_gl12()) {
        if (lvl == 0x04)
            return "GL1";
        else if (lvl == 0x08)
            return "GL2";
    } else {
        if (lvl == 0x04)
            return "EL1";
        else if (lvl == 0x08)
            return "EL2";
    }

    return "?";
}

void exception_initialize(void)
{
    msr(VBAR_EL1, _vectors_start);

    // Clear FIQ sources
    msr(CNTP_CTL_EL0, 7L);
    msr(CNTV_CTL_EL0, 7L);
    if (in_el2()) {
        msr(CNTP_CTL_EL02, 7L);
        msr(CNTV_CTL_EL02, 7L);
    }
    reg_clr(SYS_IMP_APL_PMCR0, PMCR0_IACT | PMCR0_IMODE_MASK);
    reg_clr(SYS_IMP_APL_UPMCR0, UPMCR0_IMODE_MASK);
    msr(SYS_IMP_APL_IPI_SR_EL1, IPI_SR_PENDING);

    if (is_primary_core())
        msr(DAIF, 0 << 6); // Enable SError, IRQ and FIQ
    else
        msr(DAIF, 3 << 6); // Disable IRQ and FIQ

    if (in_el2()) {
        // Set up a sane HCR_EL2
        msr(HCR_EL2, (BIT(41) | // API
                      BIT(40) | // APK
                      BIT(37) | // TEA
                      BIT(34) | // E2H
                      BIT(31) | // RW
                      BIT(27) | // TGE
                      BIT(5) |  // AMO
                      BIT(4) |  // IMO
                      BIT(3));  // FMO
        );
        // Set up exception forwarding from EL1
        msr(VBAR_EL12, _el1_vectors_start);
        sysop("isb");
    }
}

void exception_shutdown(void)
{
    msr(DAIF, 7 << 6); // Disable SError, IRQ and FIQ
}

void print_regs(u64 *regs, int el12)
{
    bool in_gl;
    u64 sp = ((u64)(regs)) + 256;

    in_gl = in_gl12();

    u64 spsr = in_gl ? mrs(SYS_IMP_APL_SPSR_GL1) : (el12 ? mrs(SPSR_EL12) : mrs(SPSR_EL1));

    printf("Exception taken from %s\n", get_exception_source(spsr));
    printf("Running in %s\n", get_exception_level());
    printf("MPIDR: 0x%lx\n", mrs(MPIDR_EL1));
    printf("Registers: (@%p)\n", regs);
    printf("  x0-x3: %016lx %016lx %016lx %016lx\n", regs[0], regs[1], regs[2], regs[3]);
    printf("  x4-x7: %016lx %016lx %016lx %016lx\n", regs[4], regs[5], regs[6], regs[7]);
    printf(" x8-x11: %016lx %016lx %016lx %016lx\n", regs[8], regs[9], regs[10], regs[11]);
    printf("x12-x15: %016lx %016lx %016lx %016lx\n", regs[12], regs[13], regs[14], regs[15]);
    printf("x16-x19: %016lx %016lx %016lx %016lx\n", regs[16], regs[17], regs[18], regs[19]);
    printf("x20-x23: %016lx %016lx %016lx %016lx\n", regs[20], regs[21], regs[22], regs[23]);
    printf("x24-x27: %016lx %016lx %016lx %016lx\n", regs[24], regs[25], regs[26], regs[27]);
    printf("x28-x30: %016lx %016lx %016lx\n", regs[28], regs[29], regs[30]);

    u64 elr = in_gl ? mrs(SYS_IMP_APL_ELR_GL1) : (el12 ? mrs(ELR_EL12) : mrs(ELR_EL1));
    u64 esr = in_gl ? mrs(SYS_IMP_APL_ESR_GL1) : (el12 ? mrs(ESR_EL12) : mrs(ESR_EL1));
    u64 far = in_gl ? mrs(SYS_IMP_APL_FAR_GL1) : (el12 ? mrs(FAR_EL12) : mrs(FAR_EL1));

    printf("PC:       0x%lx (rel: 0x%lx)\n", elr, elr - (u64)_base);
    printf("SP:       0x%lx\n", sp);
    printf("SPSR:     0x%lx\n", spsr);
    if (in_gl12()) {
        printf("ASPSR:    0x%lx\n", mrs(SYS_IMP_APL_ASPSR_GL1));
    }
    printf("FAR:      0x%lx\n", far);

    const char *ec_desc = ec_table[(esr >> 26) & 0x3f];
    printf("ESR:      0x%lx (%s)\n", esr, ec_desc ? ec_desc : "?");

    u64 sts = mrs(SYS_IMP_APL_L2C_ERR_STS);
    printf("L2C_ERR_STS: 0x%lx\n", sts);
    printf("L2C_ERR_ADR: 0x%lx\n", mrs(SYS_IMP_APL_L2C_ERR_ADR));
    printf("L2C_ERR_INF: 0x%lx\n", mrs(SYS_IMP_APL_L2C_ERR_INF));
    msr(SYS_IMP_APL_L2C_ERR_STS, sts);

    if (is_ecore()) {
        printf("E_LSU_ERR_STS: 0x%lx\n", mrs(SYS_IMP_APL_E_LSU_ERR_STS));
        printf("E_FED_ERR_STS: 0x%lx\n", mrs(SYS_IMP_APL_E_FED_ERR_STS));
        printf("E_MMU_ERR_STS: 0x%lx\n", mrs(SYS_IMP_APL_E_MMU_ERR_STS));
    } else {
        printf("LSU_ERR_STS: 0x%lx\n", mrs(SYS_IMP_APL_LSU_ERR_STS));
        printf("FED_ERR_STS: 0x%lx\n", mrs(SYS_IMP_APL_FED_ERR_STS));
        printf("MMU_ERR_STS: 0x%lx\n", mrs(SYS_IMP_APL_MMU_ERR_STS));
    }
}

void exc_sync(u64 *regs)
{
    u32 insn;
    int el12 = 0;
    bool in_gl = in_gl12();

    u64 spsr = in_gl ? mrs(SYS_IMP_APL_SPSR_GL1) : mrs(SPSR_EL1);
    u64 esr = in_gl ? mrs(SYS_IMP_APL_ESR_GL1) : mrs(ESR_EL1);
    u64 elr = in_gl ? mrs(SYS_IMP_APL_ELR_GL1) : mrs(ELR_EL1);

    if ((spsr & 0xf) == 0 && ((esr >> 26) & 0x3f) == 0x3c) {
        // On clean EL0 return, let the normal exception return
        // path take us back to the return thunk.
        msr(SPSR_EL1, 0x09); // EL2h
        msr(ELR_EL1, el0_ret);
        return;
    }

    if (in_el2() && !in_gl12() && (spsr & 0xf) == 5 && ((esr >> 26) & 0x3f) == 0x16) {
        // Hypercall
        u32 imm = mrs(ESR_EL2) & 0xffff;
        switch (imm) {
            case 0:
                // On clean EL1 return, let the normal exception return
                // path take us back to the return thunk.
                msr(SPSR_EL2, 0x09); // EL2h
                msr(ELR_EL2, el1_ret);
                return;
            case 0x10 ... 0x1f:
                if (!(exc_guard & GUARD_SILENT))
                    printf("EL1 Exception: 0x%x\n", imm);
                // Short-circuit the hypercall and handle the EL1 exception
                el12 = 1;
                msr(SPSR_EL2, mrs(SPSR_EL12));
                msr(ELR_EL2, mrs(ELR_EL12));
                break;
            default:
                printf("Unknown HVC: 0x%x\n", imm);
                break;
        }
    } else {
        if (!(exc_guard & GUARD_SILENT))
            printf("Exception: SYNC\n");
    }

    sysop("isb");
    sysop("dsb sy");

    if (!(exc_guard & GUARD_SILENT))
        print_regs(regs, el12);

    u64 l2c_err_sts = mrs(SYS_IMP_APL_L2C_ERR_STS);
    msr(SYS_IMP_APL_L2C_ERR_STS, l2c_err_sts); // Clear the L2C_ERR flag bits

    switch (exc_guard & GUARD_TYPE_MASK) {
        case GUARD_SKIP:
            elr += 4;
            break;
        case GUARD_MARK:
            // Assuming this is a load or store, dest reg is in low bits
            insn = read32(elr);
            regs[insn & 0x1f] = 0xacce5515abad1dea;
            elr += 4;
            break;
        case GUARD_RETURN:
            regs[0] = 0xacce5515abad1dea;
            elr = regs[30];
            exc_guard = GUARD_OFF;
            break;
        case GUARD_OFF:
        default:
            printf("Unhandled exception, rebooting...\n");
            flush_and_reboot();
    }

    exc_count++;

    if (!(exc_guard & GUARD_SILENT))
        printf("Recovering from exception (ELR=0x%lx)\n", elr);
    if (in_gl)
        msr(SYS_IMP_APL_ELR_GL1, elr);
    else
        msr(ELR_EL1, elr);

    sysop("isb");
    sysop("dsb sy");
}

void exc_irq(u64 *regs)
{
    u32 reason = aic_ack();

    printf("Exception: IRQ (from %s) die: %lu type: %lu num: %lu mpidr: %lx\n",
           get_exception_source(0), FIELD_GET(AIC_EVENT_DIE, reason),
           FIELD_GET(AIC_EVENT_TYPE, reason), FIELD_GET(AIC_EVENT_NUM, reason), mrs(MPIDR_EL1));

    UNUSED(regs);
    // print_regs(regs);
}

void exc_fiq(u64 *regs)
{
    printf("Exception: FIQ (from %s)\n", get_exception_source(0));

    u64 reg = mrs(CNTP_CTL_EL0);
    if (reg == 0x5) {
        printf("  PHYS timer IRQ, masking\n");
        msr(CNTP_CTL_EL0, 7L);
    }

    reg = mrs(CNTV_CTL_EL0);
    if (reg == 0x5) {
        printf("  VIRT timer IRQ, masking\n");
        msr(CNTV_CTL_EL0, 7L);
    }

    if (in_el2()) {
        reg = mrs(CNTP_CTL_EL02);
        if (reg == 0x5) {
            printf("  PHYS EL02 timer IRQ, masking\n");
            msr(CNTP_CTL_EL02, 7L);
        }
        reg = mrs(CNTV_CTL_EL02);
        if (reg == 0x5) {
            printf("  VIRT EL02 timer IRQ, masking\n");
            msr(CNTV_CTL_EL02, 7L);
        }
    }

    reg = mrs(SYS_IMP_APL_PMCR0);
    if ((reg & (PMCR0_IMODE_MASK | PMCR0_IACT)) == (PMCR0_IMODE_FIQ | PMCR0_IACT)) {
        printf("  PMC IRQ, masking\n");
        reg_clr(SYS_IMP_APL_PMCR0, PMCR0_IACT | PMCR0_IMODE_MASK);
    }
    reg = mrs(SYS_IMP_APL_UPMCR0);
    if ((reg & UPMCR0_IMODE_MASK) == UPMCR0_IMODE_FIQ && (mrs(SYS_IMP_APL_UPMSR) & UPMSR_IACT)) {
        printf("  UPMC IRQ, masking\n");
        reg_clr(SYS_IMP_APL_UPMCR0, UPMCR0_IMODE_MASK);
    }

    if (mrs(SYS_IMP_APL_IPI_SR_EL1) & IPI_SR_PENDING) {
        printf("  Fast IPI IRQ, clearing\n");
        msr(SYS_IMP_APL_IPI_SR_EL1, IPI_SR_PENDING);
    }

    UNUSED(regs);
    // print_regs(regs);
}

void exc_serr(u64 *regs)
{
    if (!(exc_guard & GUARD_SILENT))
        printf("Exception: SError\n");

    sysop("dsb sy");
    sysop("isb");

    if (!(exc_guard & GUARD_SILENT))
        print_regs(regs, 0);

    if ((exc_guard & GUARD_TYPE_MASK) == GUARD_OFF) {
        printf("Unhandled exception, rebooting...\n");
        flush_and_reboot();
    }

    exc_count++;

    sysop("dsb sy");
    sysop("isb");
}
