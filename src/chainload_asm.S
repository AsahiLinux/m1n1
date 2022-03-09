/* SPDX-License-Identifier: MIT */

.text

.globl _chainload_stub_start
.globl _chainload_stub_end
.type _chainload_stub_start, @function

_chainload_stub_start:
1:
    ldp x5, x6, [x1], #16
    stp x5, x6, [x2]
    dc cvau, x2
    ic ivau, x2
    add x2, x2, #16
    sub x3, x3, #16
    cbnz x3, 1b

    br x4
_chainload_stub_end:
