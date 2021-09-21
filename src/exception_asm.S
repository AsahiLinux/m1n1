/* SPDX-License-Identifier: MIT */

#include "exception.h"
#include "memory.h"

.globl exc_sync
.globl exc_irq
.globl exc_fiq
.globl exc_serr
.globl _vectors_start
.globl el0_stack

.globl _v_sp0_sync
.type _v_sp0_sync, @function
_v_sp0_sync:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _exc_entry
    bl exc_sync

    b _exc_return

.globl _v_sp0_irq
.type _v_sp0_irq, @function
_v_sp0_irq:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _exc_entry
    bl exc_irq

    b _exc_return

.globl _v_sp0_fiq
.type _v_sp0_fiq, @function
_v_sp0_fiq:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _exc_entry
    bl exc_fiq

    b _exc_return

.globl _v_sp0_serr
.type _v_sp0_serr, @function
_v_sp0_serr:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _exc_entry
    bl exc_serr

    b _exc_return

.globl _exc_entry
.type _exc_entry, @function
_exc_entry:
    stp x28, x29, [sp, #-16]!
    stp x26, x27, [sp, #-16]!
    stp x24, x25, [sp, #-16]!
    stp x22, x23, [sp, #-16]!
    stp x20, x21, [sp, #-16]!
    stp x18, x19, [sp, #-16]!
    stp x16, x17, [sp, #-16]!
    stp x14, x15, [sp, #-16]!
    stp x12, x13, [sp, #-16]!
    stp x10, x11, [sp, #-16]!
    stp x8, x9, [sp, #-16]!
    stp x6, x7, [sp, #-16]!
    stp x4, x5, [sp, #-16]!
    stp x2, x3, [sp, #-16]!
    stp x0, x1, [sp, #-16]!

    mov x0, sp
    ret

.globl _exc_return
.type _exc_return, @function
_exc_return:
    ldp x0, x1, [sp], #16
    ldp x2, x3, [sp], #16
    ldp x4, x5, [sp], #16
    ldp x6, x7, [sp], #16
    ldp x8, x9, [sp], #16
    ldp x10, x11, [sp], #16
    ldp x12, x13, [sp], #16
    ldp x14, x15, [sp], #16
    ldp x16, x17, [sp], #16
    ldr x18, [sp], #8
    add sp, sp, #88
    ldr x30, [sp], #16

    add sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)

    eret

.globl el0_call
.type el0_call, @function
el0_call:
    str x30, [sp, #-16]!

    // Disable EL1
    mrs x5, hcr_el2
    orr x5, x5, #(1 << 27)
    msr hcr_el2, x5
    isb

    mrs x5, daif
    msr daifclr, 3
    msr spsr_el1, x5

    ldr x5, =_el0_thunk
    msr elr_el1, x5

    mov x5, #REGION_RWX_EL0
    orr x0, x0, x5

    ldr x5, =el0_stack_base
    ldr x5, [x5]
    mov x6, #REGION_RW_EL0
    orr x5, x5, x6
    msr spsel, #0
    mov sp, x5

    eret

_el0_thunk:
    mov x5, x0
    mov x0, x1
    mov x1, x2
    mov x2, x3
    mov x3, x4

    blr x5

    brk 0
    .long 0

.globl el0_ret
.type el0_ret, @function
el0_ret:
    ldr x30, [sp], #16
    ret

.globl el1_call
.type el1_call, @function
el1_call:
    str x30, [sp, #-16]!

    // Enable EL1, but only if not already done.
    // this check is here because writes to hcr_el2 are only possible from GL2
    // if that mode has been enabled
    mrs x5, hcr_el2
    bic x6, x5, #(1 << 27)
    cmp x5, x6
    beq 1f
    msr hcr_el2, x6
    isb

    1: mrs x5, daif
    msr daifclr, 3
    mov x6, #5
    orr x5, x5, x6 // EL1h
    msr spsr_el2, x5

    ldr x5, =_el1_thunk
    msr elr_el2, x5

    ldr x5, =el0_stack_base
    ldr x5, [x5]
    msr sp_el1, x5

    eret

_el1_thunk:
    mov x5, x0
    mov x0, x1
    mov x1, x2
    mov x2, x3
    mov x3, x4

    blr x5

    hvc 0
    .long 0

.globl el1_ret
.type el1_ret, @function
el1_ret:
    ldr x30, [sp], #16
    ret

.align 11
.globl _el1_vectors_start
_el1_vectors_start:
    hvc 0x10
    .align 7
    hvc 0x11
    .align 7
    hvc 0x12
    .align 7
    hvc 0x13
    .align 7

    hvc 0x14
    .align 7
    hvc 0x15
    .align 7
    hvc 0x16
    .align 7
    hvc 0x17
    .align 7

    hvc 0x18
    .align 7
    hvc 0x19
    .align 7
    hvc 0x1a
    .align 7
    hvc 0x1b
    .align 7

    hvc 0x1c
    .align 7
    hvc 0x1d
    .align 7
    hvc 0x1e
    .align 7
    hvc 0x1f
