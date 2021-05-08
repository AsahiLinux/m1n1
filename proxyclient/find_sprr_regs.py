from setup import *
import asm

p.iodev_set_usage(IODEV.FB, 0)

code_len = 12 * 16 * 8 + 4
data_len = 8 * 16 * 8

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


def find_regs(call=None):
    if not call:
        call = p.call
    regs = set()
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

            p.set_exc_guard(GUARD.SILENT | GUARD.SKIP)
            call(code_buffer, BAD, data_buffer)
            cnt = p.get_exc_count()

            data = iface.readmem(data_buffer, data_len)
            d = struct.unpack("<128Q", data)
            i = 0
            for CRm in range(1 << 4):
                for op2 in range(1 << 3):
                    v = d[i]
                    if v != BAD:
                        regs.add((3, op1, CRn, CRm, op2))
                    i += 1

    return regs

p.set_exc_guard(GUARD.SILENT | GUARD.SKIP)
all_regs = set()
with u.mmu_disabled():
    for reg in [(3, 6, 15, 1, 0), (3, 6, 15, 1, 2)]: # , (3, 6, 15, 1, 4)]: 

        old_regs = find_regs()
        u.msr(reg, 1)
        new_regs = find_regs()

        all_regs = all_regs.union(new_regs)

        diff_regs = new_regs - old_regs

        print(reg)
        for r in sorted(diff_regs):
            print("  %s --> %lx" % (list(r), u.mrs(r)))


    #u.msr((3, 6, 15, 1, 4), 0)
    u.msr((3, 6, 15, 1, 2), 0)
    u.msr((3, 6, 15, 1, 0), 0)

gxf_regs = find_regs(call=p.gl2_call)

print("GL2")
for r in sorted(gxf_regs - all_regs):
    print("  %s -> %lx" % (list(r), u.mrs(r, call=p.gl2_call)))


gxf_regs = find_regs(call=p.gl1_call)

print("GL1")
for r in sorted(gxf_regs - all_regs):
    print("  %s -> %lx" % (list(r), u.mrs(r, call=p.gl1_call)))

