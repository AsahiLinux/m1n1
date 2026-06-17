#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

code = u.malloc(0x1000)
c = asm.ARMAsm("""
test_wfi:
    // enable timer interrupts
    msr CNTV_TVAL_EL0, x0
    mov x1, #1
    msr CNTV_CTL_EL0, x1

    mov x0, #1  // canary, not saved

    str x30, [sp, #-16]!
    stp x28, x29, [sp, #-16]!
    stp x26, x27, [sp, #-16]!
    stp x24, x25, [sp, #-16]!
    stp x22, x23, [sp, #-16]!
    stp x20, x21, [sp, #-16]!
    stp x18, x19, [sp, #-16]!

    isb
    wfi

    ldp x18, x19, [sp], #16
    ldp x20, x21, [sp], #16
    ldp x22, x23, [sp], #16
    ldp x24, x25, [sp], #16
    ldp x26, x27, [sp], #16
    ldp x28, x29, [sp], #16
    ldr x30, [sp], #16

    mov x1, #3
    msr CNTV_CTL_EL0, x1

    ret

test_wfit:
    // enable timer interrupts
    msr CNTV_TVAL_EL0, x0
    mov x2, #1
    msr CNTV_CTL_EL0, x2

    mov x0, #1  // canary, not saved

    str x30, [sp, #-16]!
    stp x28, x29, [sp, #-16]!
    stp x26, x27, [sp, #-16]!
    stp x24, x25, [sp, #-16]!
    stp x22, x23, [sp, #-16]!
    stp x20, x21, [sp, #-16]!
    stp x18, x19, [sp, #-16]!

    isb
    msr s0_3_c1_c0_1, x1 // encoding of wfit x1

    ldp x18, x19, [sp], #16
    ldp x20, x21, [sp], #16
    ldp x22, x23, [sp], #16
    ldp x24, x25, [sp], #16
    ldp x26, x27, [sp], #16
    ldp x28, x29, [sp], #16
    ldr x30, [sp], #16

    mov x1, #3
    msr CNTV_CTL_EL0, x1

    ret
""", code)
iface.writemem(code, c.data)
p.dc_cvau(code, len(c.data))
p.ic_ivau(code, len(c.data))

p.smp_start_secondaries()
freq = u.mrs(CNTFRQ_EL0)

# el -> cpu_id -> call_fn
cpu_call_el={
    2: {},
    1: {},
}
for cpu in u.adt["/cpus"]:
    if cpu.state == "running":
        cpu_call_el[2][cpu.cpu_id] = p.call
        cpu_call_el[1][cpu.cpu_id] = p.el1_call
    else:
        if not p.smp_is_alive(cpu.cpu_id):
            print(f"cpu{cpu.cpu_id} is not alive, skipping")
            continue
        cpu_call_el[2][cpu.cpu_id] = lambda addr, *args: p.smp_call_sync(cpu.cpu_id, addr & ~REGION_RX_EL1, *args)
        cpu_call_el[1][cpu.cpu_id] = lambda addr, *args: p.smp_call_sync_el1(cpu.cpu_id, addr, *args)

for el, cpu_call in cpu_call_el.items():
    print(f"Testing whether wfi persists x0 (el{el})")
    for cpu_id, call in cpu_call.items():
        ret = call(c.test_wfi, round(freq / 100))
        print(f"cpu{cpu_id}: {ret}")
for el, cpu_call in cpu_call_el.items():
    print(f"Testing whether wfit persists x0 after interrupt (el{el})")
    for cpu_id, call in cpu_call.items():
        ret = call(c.test_wfit, round(freq / 100), (1<<64)-1)
        print(f"cpu{cpu_id}: {ret}")
for el, cpu_call in cpu_call_el.items():
    print(f"Testing whether wfit persists x0 after timeout (el{el})")
    for cpu_id, call in cpu_call.items():
        ret = call(c.test_wfit, (1<<64)-1, round(freq / 100))
        print(f"cpu{cpu_id}: {ret}")
