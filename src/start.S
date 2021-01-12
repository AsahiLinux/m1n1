/* SPDX-License-Identifier: MIT */

#define UART_BASE 0x235200000
#define UTRSTAT 0x010
#define UTXH 0x020

.extern _start_c
.extern _stack_bot

.section .init, "ax"

.globl _start
.type _start, @function
_start:
    mov x9, x0

    mov w0, 'm'
    bl debug_putc
    
    mov w0, '1'
    bl debug_putc

    adrp x1, _stack_bot
    mov sp, x1
    
    mov w0, 'n'
    bl debug_putc

    adrp x0, _base
    mov x10, x0
    adrp x1, _rela_start
    add x1, x1, :lo12:_rela_start
    adrp x2, _rela_end
    add x2, x2, :lo12:_rela_end
    bl apply_rela

    mov w0, '1'
    bl debug_putc
    mov w0, '\r'
    bl debug_putc
    mov w0, '\n'
    bl debug_putc
    
    mov x0, x9
    mov x1, x10
    bl _start_c
    b .

.globl debug_putc
.type debug_putc, @function
debug_putc:
    ldr x1, =UART_BASE

1:
    ldr w2, [x1, UTRSTAT]
    tst w2, #2
    beq 1b
    str w0, [x1, UTXH]
    ret

    .pool
