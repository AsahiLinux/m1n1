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

    mov x0, x19
    mov x1, x20
    bl _start_c
    b .

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
    bl _cpu_reset_c
    b .

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
    mrs x0, CurrentEL
    cmp x0, #8
    beq 1f
    hvc #0
1:
    bl wdt_reboot
    b .

.pool
