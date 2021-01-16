/* SPDX-License-Identifier: MIT */

#include "uart.h"
#include "utils.h"

extern char _vectors_start[0];

void exception_initialize(void)
{
    printf("Initializing exceptions...\n");

    msr(vbar_el2, _vectors_start);
}

void print_regs(u64 *regs)
{
    u64 sp = ((u64)(regs)) + 256;

    printf("Running in EL%d\n", mrs(CurrentEL) >> 2);
    printf("Registers: (@%p)\n", regs);
    printf("  x0-x3: %016lx %016lx %016lx %016lx\n", regs[0], regs[1], regs[2],
           regs[3]);
    printf("  x4-x7: %016lx %016lx %016lx %016lx\n", regs[4], regs[5], regs[6],
           regs[7]);
    printf(" x8-x11: %016lx %016lx %016lx %016lx\n", regs[8], regs[9], regs[10],
           regs[11]);
    printf("x12-x15: %016lx %016lx %016lx %016lx\n", regs[12], regs[13],
           regs[14], regs[15]);
    printf("x16-x19: %016lx %016lx %016lx %016lx\n", regs[16], regs[17],
           regs[18], regs[19]);
    printf("x20-x23: %016lx %016lx %016lx %016lx\n", regs[20], regs[21],
           regs[22], regs[23]);
    printf("x24-x27: %016lx %016lx %016lx %016lx\n", regs[24], regs[25],
           regs[26], regs[27]);
    printf("x28-x30: %016lx %016lx %016lx\n", regs[28], regs[29], regs[30]);

    u64 elr = mrs(elr_el2);

    printf("PC:       0x%lx (rel: 0x%lx)\n", elr, elr - (u64)_base);
    printf("SPSEL:    0x%lx\n", mrs(spsel));
    printf("SP:       0x%lx\n", sp);
    printf("SPSR_EL2: 0x%x\n", mrs(spsr_el2));
}

void exc_sync(u64 *regs)
{
    uart_puts("Exception: SYNC");

    print_regs(regs);
    reboot();
}

void exc_irq(u64 *regs)
{
    uart_puts("Exception: IRQ");

    u32 reason = read32(0x23b102004);

    printf(" type: %d num: %d\n", reason >> 16, reason & 0xffff);

    // print_regs(regs);
}

void exc_fiq(u64 *regs)
{
    uart_puts("Exception: FIQ");

    u32 timer_ctl = mrs(CNTP_CTL_EL0);

    if (timer_ctl == 0x5) {
        uart_puts("  timer IRQ, masking");
        msr(CNTP_CTL_EL0, 7L);
    }

    // print_regs(regs);
}

void exc_serr(u64 *regs)
{
    printf("Exception: SError\n");

    print_regs(regs);
    reboot();
}
