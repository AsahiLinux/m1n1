# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

cyc_ovrd = False

code = u.malloc(0x1000)
c = asm.ARMAsm("""
    // enable timer interrupts
    msr CNTP_TVAL_EL0, x0
    mov x1, #1
    msr CNTP_CTL_EL0, x1

    mov x0, #1  // canary, not saved

    str x30, [sp, #-16]!
    stp x28, x29, [sp, #-16]!
    stp x26, x27, [sp, #-16]!
    stp x24, x25, [sp, #-16]!
    stp x22, x23, [sp, #-16]!
    stp x20, x21, [sp, #-16]!
    stp x18, x19, [sp, #-16]!
""" + ("""
    mrs x1, s3_5_c15_c5_0
    orr x1, x1, #(3L << 24)
    msr s3_5_c15_c5_0, x1
""" if cyc_ovrd else "") + """
    isb
    wfi
""" + ("""
    mrs x1, s3_5_c15_c5_0
    bic x1, x1, #(1L << 24)
    msr s3_5_c15_c5_0, x1
""" if cyc_ovrd else "") + """

    ldp x18, x19, [sp], #16
    ldp x20, x21, [sp], #16
    ldp x22, x23, [sp], #16
    ldp x24, x25, [sp], #16
    ldp x26, x27, [sp], #16
    ldp x28, x29, [sp], #16
    ldr x30, [sp], #16

    mov x1, #3
    msr CNTP_CTL_EL0, x1

    ret
""", code)
iface.writemem(code, c.data)
p.dc_cvau(code, len(c.data))
p.ic_ivau(code, len(c.data))

p.smp_start_secondaries()
freq = u.mrs(CNTFRQ_EL0)

for cpu in u.adt["/cpus"]:
    if cpu.state == "running":
        call=p.call
    else:
        if not p.smp_is_alive(cpu.cpu_id):
            print(f"cpu{cpu.cpu_id} is not alive, skipping")
            continue
        call=lambda addr, *args: p.smp_call_sync(cpu.cpu_id, addr & ~REGION_RX_EL1, *args)
    ret = call(code, round(freq / 100))
    print(f"cpu{cpu.cpu_id} persists x0: {ret}")
