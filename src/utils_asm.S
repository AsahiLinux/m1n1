/* SPDX-License-Identifier: MIT */

.text

.globl memcpy64
.type memcpy64, @function
memcpy64:
    ands    x2, x2, #~7
    beq     2f
1:  ldr     x3, [x1], #8
    str     x3, [x0], #8
    subs    x2, x2, #8
    bne     1b
2:
    ret

.globl memset64
.type memset64, @function
memset64:
    ands    x2, x2, #~7
    beq     2f
1:  str     x1, [x0], #8
    subs    x2, x2, #8
    bne     1b
2:
    ret

.globl memcpy32
.type memcpy32, @function
memcpy32:
    ands    x2, x2, #~3
    beq     2f
1:  ldr     w3, [x1], #4
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

.globl get_simd_state
.type get_simd_state, @function
get_simd_state:
    stp q0, q1, [x0], #32
    stp q2, q3, [x0], #32
    stp q4, q5, [x0], #32
    stp q6, q7, [x0], #32
    stp q8, q9, [x0], #32
    stp q10, q11, [x0], #32
    stp q12, q13, [x0], #32
    stp q14, q15, [x0], #32
    stp q16, q17, [x0], #32
    stp q18, q19, [x0], #32
    stp q20, q21, [x0], #32
    stp q22, q23, [x0], #32
    stp q24, q25, [x0], #32
    stp q26, q27, [x0], #32
    stp q28, q29, [x0], #32
    stp q30, q31, [x0], #32
    ret

.globl put_simd_state
.type put_simd_state, @function
put_simd_state:
    ldp q0, q1, [x0], #32
    ldp q2, q3, [x0], #32
    ldp q4, q5, [x0], #32
    ldp q6, q7, [x0], #32
    ldp q8, q9, [x0], #32
    ldp q10, q11, [x0], #32
    ldp q12, q13, [x0], #32
    ldp q14, q15, [x0], #32
    ldp q16, q17, [x0], #32
    ldp q18, q19, [x0], #32
    ldp q20, q21, [x0], #32
    ldp q22, q23, [x0], #32
    ldp q24, q25, [x0], #32
    ldp q26, q27, [x0], #32
    ldp q28, q29, [x0], #32
    ldp q30, q31, [x0], #32
    ret
