/* SPDX-License-Identifier: MIT */

.text

.globl memcpy32
.type memcpy32, @function
memcpy32:
    ands    x2, x2, #~3
    beq     2f
1:  ldr     x3, [x1], #4
    str     w3, [x0], #4
    subs    x2, x2, #4
    bne     1b
2:    
    ret

.globl memset32
.type memset32, @function
memset32:
    ands    x2, x2, #~3
    beq     2f
1:  str     w1, [x0], #4
    subs    x2, x2, #4
    bne     1b
2:    
    ret

.globl memcpy16
.type memcpy16, @function
memcpy16:
    ands    x2, x2, #~1
    beq     2f
1:  ldrh    w3, [x1], #2
    strh    w3, [x0], #2
    subs    x2, x2, #2
    bne     1b
2:    
    ret

.globl memset16
.type memset16, @function
memset16:
    ands    x2, x2, #~1
    beq     2f
1:  strh    w1, [x0], #2
    subs    x2, x2, #2
    bne     1b
2:    
    ret

.globl memcpy8
.type memcpy8, @function
memcpy8:
    cmp     x2, #0
    beq     2f
1:  ldrb    w3, [x1], #1
    strb    w3, [x0], #1
    subs    x2, x2, #1
    bne     1b
2:    
    ret

.globl memset8
.type memset8, @function
memset8:
    cmp     x2, #0
    beq     2f
1:  strb    w1, [x0], #1
    subs    x2, x2, #1
    bne     1b
2:    
    ret
