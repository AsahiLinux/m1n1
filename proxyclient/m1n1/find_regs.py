# SPDX-License-Identifier: MIT
import struct

from . import asm, sysreg
from .proxyutils import GuardedHeap

__all__ = ["dynamic_regs", "impdef_regs", "static_regs", "find_regs"]

def _all():
    for op1 in range(1 << 3):
        for CRn in (0b1011, 0b1111):
            for CRm in range(1 << 4):
                for op2 in range(1 << 3):
                    yield 3, op1, CRn, CRm, op2

dynamic_regs = [
    sysreg.CNTVCT_ALIAS_EL0,
    sysreg.CNTPCT_ALIAS_EL0,
]

impdef_regs = list(_all())
static_regs = [i for i in _all() if i not in dynamic_regs]

def find_regs(u, regs=None, block=1024, call=None, values=True):
    if regs is None:
        regs = impdef_regs

    p = u.proxy
    iface = u.iface

    data_len = 8 * block

    with GuardedHeap(u.heap) as heap:
        data_buffer = heap.malloc(data_len)

        template = asm.ARMAsm("""
            mov x2, x0
            mrs x2, s3_0_c0_c0_0
            str x2, [x1], #8
        """, 0x1000)

        mov, mrs, st = struct.unpack("3I", template.data)


        BAD = 0xacce5515abad1dea
        OOPS = 0xdeadc0dedeadc0de

        iregs = iter(regs)

        while True:
            insns = []
            bregs = []
            for i in iregs:
                op0, op1, CRn, CRm, op2 = enc = sysreg.sysreg_parse(i)
                bregs.append(enc)
                assert op0 == 3

                insns.extend((mov, mrs | (op1 << 16) | (CRn << 12) | (CRm << 8) | (op2 << 5), st))

                if len(bregs) >= block:
                    break

            if not bregs:
                break

            p.memset64(data_buffer, OOPS, data_len)
            u.exec(insns, BAD, data_buffer, call=call, silent=True, ignore_exceptions=True)
            data = iface.readmem(data_buffer, 8 * len(bregs))
            for reg, val in zip(bregs, struct.unpack(f"<{len(bregs)}Q", data)):
                if val == OOPS:
                    raise Exception(f"Failed to execute reg-finder code at {reg}")
                if val != BAD:
                    if values:
                        yield reg, val
                    else:
                        yield reg

if __name__ == "__main__":
    from m1n1.setup import *

    p.iodev_set_usage(IODEV.FB, 0)

    for reg, val in find_regs(u):
        print(f"{sysreg_name(reg)} ({', '.join(map(str, reg))}) = 0x{val:x}")

        try:
            u.msr(reg, val, silent=True)
        except:
            print(" - READONLY")
        try:
            u.mrs(reg, silent=True, call="el1")
        except:
            print(" - ### EL2 only ###")
        try:
            u.mrs(reg, silent=True, call="el0")
        except:
            pass
        else:
            print(" - *** EL0 accessible ***")
