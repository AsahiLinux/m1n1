from setup import *
import asm

code_len = 12 * 16 * 8 + 4
data_len = 8 * 16 * 8

u.msr(HACR_EL2, 0)

u.msr(HCR_EL2, u.mrs(HCR_EL2) & ~(1<<20))
u.inst(0xd5033fdf) # isb

ACTLR_DEFAULT = 0xc00
ACTLR_AFP = 1 << 5
u.msr(ACTLR_EL1, ACTLR_DEFAULT | ACTLR_AFP)

code_buffer = p.malloc(code_len)
data_buffer = p.malloc(data_len)

template = asm.ARMAsm("""
    mov x2, x0
    mrs x2, s3_0_c0_c0_0
    str x2, [x1], #8
    ret
""", code_buffer)

mov, mrs, st, ret = struct.unpack("4I", template.data)

data = []

BAD = 0xacce5515abad1dea

def test():
    for op1 in range(1 << 3):
        for CRn in (0b1011, 0b1111):
            mrs0 = mrs | (op1 << 16) | (CRn << 12)
            insns = []
            for CRm in range(1 << 4):
                for op2 in range(1 << 3):
                    insns.extend((mov, mrs0 | (CRm << 8) | (op2 << 5), st))
            insns.append(ret)
            iface.writemem(code_buffer, struct.pack("<385I", *insns))
            p.dc_cvau(code_buffer, code_len)
            p.ic_ivau(code_buffer, code_len)

            p.set_exc_guard(p.GUARD_SILENT | p.GUARD_SKIP)
            p.el1_call(code_buffer, BAD, data_buffer)
            cnt = p.get_exc_count()

            data = iface.readmem(data_buffer, data_len)
            d = struct.unpack("<128Q", data)
            i = 0
            for CRm in range(1 << 4):
                for op2 in range(1 << 3):
                    v = d[i]
                    if v != BAD:
                        yield (op1, CRn, CRm, op2)
                    i += 1

baseline = set(test())

for bit in range(64):
    print()
    print ("## HACR_EL2[%d]" % bit)
    u.msr(HACR_EL2, 1<<bit)
    u.inst(0xd5033fdf) # isb

    new = set(test())

    added = new - baseline
    removed = baseline - new

    if added:
        print("Untraps:")
        for op1, CRn, CRm, op2 in sorted(added):
            print("s3_%d_c%d_c%d_%d (3, %d, %d, %d, %d)" % (
                    op1, CRn, CRm, op2, op1, CRn, CRm, op2))

    if removed:
        print("Traps:")
        for op1, CRn, CRm, op2 in sorted(removed):
            print("s3_%d_c%d_c%d_%d (3, %d, %d, %d, %d)" % (
                    op1, CRn, CRm, op2, op1, CRn, CRm, op2))

p.set_exc_guard(p.GUARD_OFF)
