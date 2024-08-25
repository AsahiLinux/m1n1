/* SPDX-License-Identifier: MIT */

#include "soc.h"

#define UTRSTAT 0x010
#define UTXH 0x020

.extern _start_c
.extern _stack_bot
.extern _v_sp0_sync
.extern _v_sp0_irq
.extern _v_sp0_fiq
.extern _v_sp0_serr
.extern _reset_stack
.extern _cpu_reset_c
.extern wdt_reboot

.section .init, "ax"

.align 11
.globl _vectors_start
_vectors_start:

    mov x9, '0'
    b cpu_reset
    .align 7
    mov x9, '1'
    b exc_unk
    .align 7
    mov x9, '2'
    b exc_unk
    .align 7
    mov x9, '3'
    b exc_unk
    .align 7
    b _v_sp0_sync
    .align 7
    b _v_sp0_irq
    .align 7
    b _v_sp0_fiq
    .align 7
    b _v_sp0_serr
    .align 7
    b _v_sp0_sync
    .align 7
    b _v_sp0_irq
    .align 7
    b _v_sp0_fiq
    .align 7
    b _v_sp0_serr
    .align 7
    mov x9, 'p'
    b exc_unk
    .align 7
    mov x9, 'q'
    b exc_unk
    .align 7
    mov x9, 'r'
    b exc_unk
    .align 7
    mov x9, 's'
    b exc_unk
    .align 7

.globl _start
.type _start, @function
_start:
    mov x19, x0

    mov w0, 'm'
    bl debug_putc

    adrp x1, _stack_bot
    mov sp, x1

    mov w0, '1'
    bl debug_putc

    ldr x2, [sp, #-8]

    mov w0, 'n'
    bl debug_putc

    adrp x0, _base
    mov x20, x0
    adrp x1, _rela_start
    add x1, x1, :lo12:_rela_start
    adrp x2, _rela_end
    add x2, x2, :lo12:_rela_end
    bl apply_rela

    mov w0, '1'
    bl debug_putc
    mov w0, 0xd /* '\r', clang compat */
    bl debug_putc
    mov w0, '\n'
    bl debug_putc
    bl pan_fixup

    mrs x8, CurrentEL
    cmp x8, #0xc
    beq start_el3

    mov x0, x19
    mov x1, x20
    bl _start_c
    b .

start_el3:
    bl exception_initialize
    adrp x8, _stack_bot_el3
    mov sp, x8
    mov x0, x19
    mov x1, x20
    msr tpidr_el3, xzr
    adrp x6, _stack_bot
    adr x7, _start_c
    b el3_eret_to_el1

.globl exc_unk
.type exc_unk, @function
exc_unk:
    mov w0, 0xd /* '\r', clang compat */
    bl debug_putc
    mov w0, '\n'
    bl debug_putc
    mov w0, '!'
    bl debug_putc
    mov w0, 'E'
    bl debug_putc
    mov w0, 'x'
    bl debug_putc
    mov w0, 'C'
    bl debug_putc
    mov w0, ':'
    bl debug_putc
    mov w0, w9
    bl debug_putc
    mov w0, '!'
    bl debug_putc
    mov w0, 0xd /* '\r', clang compat */
    bl debug_putc
    mov w0, '\n'
    bl debug_putc
    b reboot

.globl cpu_reset
.type cpu_reset, @function
cpu_reset:
    mov w0, 'O'
    bl debug_putc

    adrp x1, _reset_stack
    add x1, x1, :lo12:_reset_stack
    ldr x1, [x1]
    mov sp, x1

    ldr x2, [sp, #-8]

    mov w0, 'K'
    bl debug_putc

    mov x0, sp

    mrs x8, CurrentEL
    cmp x8, #0xc
    beq cpu_reset_el3

    bl _cpu_reset_c
    b .

cpu_reset_el3:
    bl _cpu_reset_c
    adrp x6, _reset_stack_el1
    add x6, x6, :lo12:_reset_stack_el1
    ldr x6, [x6]
    mov x0, x6
    adr x7, _cpu_reset_c

el3_eret_to_el1:
    adr x8, _vectors_start
    msr sctlr_el1, xzr

    mrs x8, scr_el3
    orr x8, x8, #(1<<10) // EL1 execution state is AArch64
    orr x8, x8, #(1<<0)  // EL1 is non-secure
    msr scr_el3, x8
    msr elr_el3, x7 // Set EL1 entry point
    mov x8, #0x5 // EL1h
    msr spsr_el3, x8

    msr sp_el1, x6 // Set EL1 stack pointer

    eret

.globl debug_putc
.type debug_putc, @function
debug_putc:
#ifdef EARLY_UART_BASE
    ldr x1, =EARLY_UART_BASE

1:
    ldr w2, [x1, UTRSTAT]
    tst w2, #2
    beq 1b
    str w0, [x1, UTXH]
#endif
    ret

.globl reboot
.type reboot, @function
reboot:
    mrs x8, id_aa64pfr0_el1
    tst w8, 0xf00
    beq 1f
    mrs x0, CurrentEL
    cmp x0, #8
    beq 1f
    hvc #0
1:
    bl wdt_reboot
    b .

.pool
