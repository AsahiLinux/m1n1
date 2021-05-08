/* spDx-License-Identifier: MIT */

.align 11
.globl _hv_vectors_start
_hv_vectors_start:

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
    b _v_hv_sync
    .align 7
    b _v_hv_irq
    .align 7
    b _v_hv_fiq
    .align 7
    b _v_hv_serr
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

.globl _v_hv_sync
.type _v_hv_sync, @function
_v_hv_sync:
    msr pan, #0
    str x30, [sp, #-16]!
    bl _exc_entry
    bl hv_exc_sync

    b _exc_return

.globl _v_hv_irq
.type _v_hv_irq, @function
_v_hv_irq:
    msr pan, #0
    str x30, [sp, #-16]!
    bl _exc_entry
    bl hv_exc_irq

    b _exc_return

.globl _v_hv_fiq
.type _v_hv_fiq, @function
_v_hv_fiq:
    msr pan, #0
    str x30, [sp, #-16]!
    bl _exc_entry
    bl hv_exc_fiq

    b _exc_return

.globl _v_hv_serr
.type _v_hv_serr, @function
_v_hv_serr:
    msr pan, #0
    str x30, [sp, #-16]!
    bl _exc_entry
    bl hv_exc_serr

    b _exc_return

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

    mov x5, sp
    msr tpidr_el2, x5

    mrs x5, daif
    msr daifclr, 3
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
    mrs x5, tpidr_el2
    mov sp, x5

    ldr x18, [sp], #16
    ldp x19, x20, [sp], #16
    ldp x21, x22, [sp], #16
    ldp x23, x24, [sp], #16
    ldp x25, x26, [sp], #16
    ldp x27, x28, [sp], #16
    ldp x29, x30, [sp], #16

    ret
