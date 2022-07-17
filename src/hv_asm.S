/* spDx-License-Identifier: MIT */

#include "exception.h"

.align 11
.globl _hv_vectors_start
_hv_vectors_start:

    /* EL2 with SP_EL0 */
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

    /* EL2 with SP_EL2 */
    b _v_sp0_sync
    .align 7
    b _v_sp0_irq
    .align 7
    b _v_sp0_fiq
    .align 7
    b _v_sp0_serr
    .align 7

    /* EL1/0 64-bit */
    b _v_hv_sync
    .align 7
    b _v_hv_irq
    .align 7
    b _v_hv_fiq
    .align 7
    b _v_hv_serr
    .align 7

    /* EL1/0 32-bit */
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

.globl _hv_entry
.type _hv_entry, @function
_hv_entry:
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

    dsb sy
    isb

    mov x0, sp
    ret

.globl _hv_return
.type _hv_return, @function
_hv_return:
    ldp x0, x1, [sp], #16
    ldp x2, x3, [sp], #16
    ldp x4, x5, [sp], #16
    ldp x6, x7, [sp], #16
    ldp x8, x9, [sp], #16
    ldp x10, x11, [sp], #16
    ldp x12, x13, [sp], #16
    ldp x14, x15, [sp], #16
    ldp x16, x17, [sp], #16
    ldp x18, x19, [sp], #16
    ldp x20, x21, [sp], #16
    ldp x22, x23, [sp], #16
    ldp x24, x25, [sp], #16
    ldp x26, x27, [sp], #16
    ldp x28, x29, [sp], #16
    ldr x30, [sp], #16

    add sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)

    eret

.globl _v_hv_sync
.type _v_hv_sync, @function
_v_hv_sync:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _hv_entry
    bl hv_exc_sync

    b _hv_return

.globl _v_hv_irq
.type _v_hv_irq, @function
_v_hv_irq:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _hv_entry
    bl hv_exc_irq

    b _hv_return

.globl _v_hv_fiq
.type _v_hv_fiq, @function
_v_hv_fiq:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _hv_entry
    bl hv_exc_fiq

    b _hv_return

.globl _v_hv_serr
.type _v_hv_serr, @function
_v_hv_serr:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _hv_entry
    bl hv_exc_serr

    b _hv_return

.extern hv_saved_sp

.globl hv_enter_guest
.type hv_enter_guest, @function
hv_enter_guest:
    stp x29, x30, [sp, #-16]!
    stp x27, x28, [sp, #-16]!
    stp x25, x26, [sp, #-16]!
    stp x23, x24, [sp, #-16]!
    stp x21, x22, [sp, #-16]!
    stp x19, x20, [sp, #-16]!
    str x18, [sp, #-16]!

    mrs x7, tpidr_el2
    ldr x6, =hv_saved_sp
    mov x5, sp
    str x5, [x6, x7, LSL #3]

    mrs x5, daif
    mov x6, #5
    orr x5, x5, x6 // EL1h
    msr spsr_el2, x5

    msr elr_el2, x4
    mov x5, #0
    msr sp_el0, x5
    msr sp_el1, x5

    eret

.globl hv_exit_guest
.type hv_exit_guest, @function
hv_exit_guest:
    mrs x7, tpidr_el2
    ldr x6, =hv_saved_sp
    ldr x5, [x6, x7, LSL #3]
    mov sp, x5

    ldr x18, [sp], #16
    ldp x19, x20, [sp], #16
    ldp x21, x22, [sp], #16
    ldp x23, x24, [sp], #16
    ldp x25, x26, [sp], #16
    ldp x27, x28, [sp], #16
    ldp x29, x30, [sp], #16

    ret
