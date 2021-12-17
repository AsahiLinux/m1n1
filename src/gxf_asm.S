/* SPDX-License-Identifier: MIT */

#include "gxf.h"
#include "cpu_regs.h"
#include "exception.h"

#define genter .long 0x00201420
#define gexit .long 0x00201400

.global _gxf_init
.type _gxf_init, @function
_gxf_init:
    str x30, [sp, #-16]!
    mov x5, x0
    mov x6, x1
    mov x0, 1
    msr SYS_IMP_APL_SPRR_CONFIG_EL1, x0
    isb
    msr SYS_IMP_APL_GXF_CONFIG_EL1, x0
    isb
    ldr x0, =_gxf_setup
    msr SYS_IMP_APL_GXF_ENTER_EL1, x0
    isb
    genter
    msr SYS_IMP_APL_GXF_CONFIG_EL1, xzr
    isb
    msr SYS_IMP_APL_SPRR_CONFIG_EL1, xzr
    isb
    ldr x30, [sp], #16
    ret

.globl gxf_enter
.type gxf_enter, @function
gxf_enter:
    genter
    ret

_gxf_setup:
    mov sp, x5
    ldr x1, =_gxf_vectors
    ldr x2, =_gxf_exc_sync
    ldr x3, =_gxf_entry
    msr SYS_IMP_APL_VBAR_GL1, x1
    msr SYS_IMP_APL_GXF_ABORT_EL1, x2
    msr SYS_IMP_APL_GXF_ENTER_EL1, x3

    mrs x4, CurrentEL
    cmp x4, #8
    bne 1f

    msr SYS_IMP_APL_SP_GL12, x6
    msr SYS_IMP_APL_VBAR_GL12, x1
    msr SYS_IMP_APL_GXF_ABORT_EL12, x2
    msr SYS_IMP_APL_GXF_ENTER_EL12, x3

1:
    isb
    gexit

_gxf_entry:
    stp x29, x30, [sp, #-16]!
    stp x23, x24, [sp, #-16]!
    stp x21, x22, [sp, #-16]!
    stp x19, x20, [sp, #-16]!

    // these registers would be overwritten by each exception happening in GL1/2
    // but we need them to gexit correctly again
    mrs x20, SYS_IMP_APL_SPSR_GL1
    mrs x21, SYS_IMP_APL_ASPSR_GL1
    mrs x22, SYS_IMP_APL_ESR_GL1
    mrs x23, SYS_IMP_APL_ELR_GL1
    mrs x24, SYS_IMP_APL_FAR_GL1

    mov x5, x0
    mov x0, x1
    mov x1, x2
    mov x2, x3
    mov x3, x4

    blr x5

    msr SYS_IMP_APL_SPSR_GL1, x20
    msr SYS_IMP_APL_ASPSR_GL1, x21
    msr SYS_IMP_APL_ESR_GL1, x22
    msr SYS_IMP_APL_ELR_GL1, x23
    msr SYS_IMP_APL_FAR_GL1, x24

    ldp x19, x20, [sp], #16
    ldp x21, x22, [sp], #16
    ldp x23, x24, [sp], #16
    ldp x29, x30, [sp], #16

    isb
    gexit

.align 11
_gxf_vectors:
    mov x9, '0'
    b _gxf_exc_unk
    .align 7
    mov x9, '1'
    b _gxf_exc_unk
    .align 7
    mov x9, '2'
    b _gxf_exc_unk
    .align 7
    mov x9, '3'
    b _gxf_exc_unk
    .align 7
    b _gxf_exc_sync
    .align 7
    mov x9, '5'
    b _gxf_exc_unk
    .align 7
    mov x9, '6'
    b _gxf_exc_unk
    .align 7
    b _gxf_serr
    .align 7
    b _gxf_exc_sync
    .align 7
    mov x9, '9'
    b _gxf_exc_unk
    .align 7
    mov x9, 'a'
    b _gxf_exc_unk
    .align 7
    b _gxf_serr
    .align 7
    mov x9, 'c'
    b _gxf_exc_unk
    .align 7
    mov x9, 'd'
    b _gxf_exc_unk
    .align 7
    mov x9, 'e'
    b _gxf_exc_unk
    .align 7
    mov x9, 'f'
    b _gxf_exc_unk
    .align 7

_gxf_exc_sync:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _gxf_exc_entry
    bl exc_sync
    b _gxf_exc_return

_gxf_serr:
    msr pan, #0
    sub sp, sp, #(SIZEOF_EXC_INFO - 32 * 8)
    str x30, [sp, #-16]!
    bl _gxf_exc_entry
    bl exc_serr
    b _gxf_exc_return

_gxf_exc_entry:
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

    mrs x1, SYS_IMP_APL_SPSR_GL1
    msr SPSR_EL1, x1
    mrs x1, SYS_IMP_APL_ELR_GL1
    msr ELR_EL1, x1
    mrs x1, SYS_IMP_APL_ESR_GL1
    msr ESR_EL1, x1
    mrs x1, SYS_IMP_APL_FAR_GL1
    msr FAR_EL1, x1

    ret

_gxf_exc_return:
    mrs x0, SPSR_EL1
    msr SYS_IMP_APL_SPSR_GL1, x0
    mrs x0, ELR_EL1
    msr SYS_IMP_APL_ELR_GL1, x0

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

    isb

    gexit

_gxf_exc_unk:
    msr pan, #0
    mov w0, 0xd /* '\r', clang compat */
    bl debug_putc
    mov w0, '\n'
    bl debug_putc
    mov w0, '!'
    bl debug_putc
    mov w0, 'G'
    bl debug_putc
    mov w0, 'L'
    bl debug_putc
    mov w0, 'E'
    bl debug_putc
    mov w0, 'X'
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
