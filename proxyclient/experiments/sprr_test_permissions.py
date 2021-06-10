#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from contextlib import contextmanager

from m1n1.setup import *
from m1n1.find_regs import *
from m1n1 import asm

p.smp_start_secondaries()

class ARMPageTable:
    PAGESIZE = 0x4000

    def __init__(self, memalign, free):
        self.memalign = memalign
        self.free = free

        self.l0 = self.memalign(self.PAGESIZE, self.PAGESIZE)
        self.l1 = [self.memalign(self.PAGESIZE, self.PAGESIZE), self.memalign(
            self.PAGESIZE, self.PAGESIZE)]
        self.l2 = {}

        p.write64(self.l0, self.make_table_pte(self.l1[0]))
        p.write64(self.l0+8, self.make_table_pte(self.l1[1]))

    def make_table_pte(self, addr):
        # table mapping, access bit set
        return addr | 0b11 | (1 << 10)

    def map_page(self, vaddr, paddr, access_bits):
        ap = (access_bits & 0b1100) >> 2
        pxn = (access_bits & 0b0010) >> 1
        uxn = (access_bits & 0b0001)

        # block mapping, access bit set
        pte = paddr | 0b01 | (1 << 10)

        # move access bits in place
        pte |= ap << 6
        pte |= pxn << 54
        pte |= uxn << 53

        l0_idx = (vaddr >> (25+11+11)) & 1
        l1_idx = (vaddr >> (25+11)) & 0x7ff
        l2_idx = (vaddr >> 25) & 0x7ff

        tbl = self.l2.get((l0_idx, l1_idx), None)
        if not tbl:
            tbl = self.memalign(self.PAGESIZE, self.PAGESIZE)
            self.l2[(l0_idx, l1_idx)] = tbl
            p.write64(self.l1[l0_idx] + 8*l1_idx, self.make_table_pte(tbl))

        p.write64(tbl + 8*l2_idx, pte)

    def map(self, vaddr, paddr, sz, access_bits):
        assert sz % 0x2000000 == 0
        assert vaddr % 0x2000000 == 0
        assert paddr % 0x2000000 == 0
        assert access_bits <= 0b1111

        while sz > 0:
            self.map_page(vaddr, paddr, access_bits)
            sz -= 0x2000000
            vaddr += 0x2000000
            paddr += 0x2000000


def build_and_write_code(heap, code):
    page = heap.memalign(0x4000, 0x4000)
    compiled = asm.ARMAsm(code, page).data
    iface.writemem(page, compiled)
    p.dc_cvau(page, len(compiled))
    p.ic_ivau(page, len(compiled))
    return page


def setup_exception_vectors(heap, gxf=False):
    if gxf:
        elr = "S3_6_C15_C10_6"
        eret = ".long 0x201400"
        indicator = 0xf2
    else:
        elr = "ELR_EL1"
        eret = "eret"
        indicator = 0xf0

    return build_and_write_code(heap, """
                .rept   16
                b 1f
                .align 7
                .endr

                1:
                // store that we failed
                mov x10, 0x{indicator:x}

                // move PC two instruction further and clear 0xf0 0000 0000 to
                // make sure we end up in the r-x mapping either way and don't
                // repeat the instruction that just faulted
                // we skip the second instruction since that one is used to
                // indicate success
                ldr x11, =0x0fffffffff
                mrs x12, {elr}
                add x12, x12, #8
                and x12, x12, x11
                msr {elr}, x12

                isb
                {eret}
        """.format(eret=eret, elr=elr, indicator=indicator))


print("Setting up..")
pagetable = ARMPageTable(u.memalign, u.free)
pagetable.map(0x800000000, 0x800000000, 0xc00000000, 0)
pagetable.map(0xf800000000, 0x800000000, 0xc00000000, 1)

el2_vectors = setup_exception_vectors(u.heap, gxf=False)
gl2_vectors = setup_exception_vectors(u.heap, gxf=True)

probe_page = build_and_write_code(u.heap, "mov x10, 0x80\nret\nret\nret\n")
probe_page_vaddr = probe_page | 0xf000000000

code_page = build_and_write_code(u.heap, """
            #define SPRR_PERM_EL0  S3_6_C15_C1_5
            #define SPRR_PERM_EL1  S3_6_C15_C1_6
            #define SPRR_PERM_EL2  S3_6_C15_C1_7

            #define GXF_CONFIG_EL2 s3_6_c15_c1_2
            #define GXF_ENTER_EL2 s3_6_c15_c8_1
            #define GXF_ABORT_EL2 s3_6_c15_c8_2

            #define MPIDR_GL2 S3_6_C15_C10_1
            #define VBAR_GL2 S3_6_C15_C10_2
            #define SPSR_GL2 S3_6_C15_C10_3
            #define ELR_GL2 S3_6_C15_C10_6
            #define FAR_GL2 S3_6_C15_C10_7

            #define genter .long 0x00201420
            #define gexit .long 0x201400

            // just store everything since i'm too lazy to think about
            // register assignments
            str x30, [sp, #-16]!
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

            mov x20, x0  // store SPRR value for later
            mov x21, 0   // clear result

            // setup exception vectors
            ldr x0, =0x{vectors:x}
            msr VBAR_EL2, x0
            isb

            // prepare MMU
            ldr x0, =0x0400ff
            msr MAIR_EL1, x0
            ldr x0, =0x27510b510
            msr TCR_EL1, x0
            ldr x0, =0x{ttbr:x}
            msr TTBR0_EL2, x0

            // enable SPPR
            mov x0, 1
            msr s3_6_c15_c1_0, x0
            msr s3_6_c15_c1_3, xzr
            isb

            // clear all SPPR registers
            // (note that reads from/writes to EL1 will be redirected to EL2 anyway)
            ldr x0, =0
            msr SPRR_PERM_EL0, x0
            msr SPRR_PERM_EL1, x0
            msr SPRR_PERM_EL2, x0
            msr s3_6_c15_c1_3, x0

            // setup SPPR_EL2
            msr SPRR_PERM_EL2, x20
            isb
            dsb ishst
            tlbi vmalle1is
            dsb ish
            isb


            msr s3_6_c15_c1_3, xzr
            isb

            // enable MMU
            ldr x1, =0x1005
            mrs x0, SCTLR_EL1
            mov x3, x0
            orr x0, x0, x1
            msr SCTLR_EL1, x0
            isb

            // configure and enable GXF
            mov x0, 1
            msr GXF_CONFIG_EL2, x0
            isb
            ldr x0, =gxf_entry
            msr GXF_ENTER_EL2, x0
            ldr x0, =gxf_abort
            msr GXF_ABORT_EL2, x0
            isb

            // test GXF access
            genter

            // test execute access
            ldr x1, =0x{probe_page:x}
            mov x10, 0
            blr x1
            lsl x21, x21, #8
            orr x21, x21, x10

            // test read access
            ldr x1, =0x{probe_page:x}
            mov x10, 0
            ldr x1, [x1]
            mov x10, 0x80
            lsl x21, x21, #8
            orr x21, x21, x10

            // test write access
            ldr x1, =0x{probe_page:x}
            add x1, x1, 0x20
            mov x10, 0
            str x1, [x1]
            mov x10, 0x80
            lsl x21, x21, #8
            orr x21, x21, x10

            // disable MMU again
            dsb ish
            isb
            msr SCTLR_EL1, x3
            isb

            mov x0, 0
            msr GXF_CONFIG_EL2, x0
            msr s3_6_c15_c1_0, x0

            mov x0, x21

            // restore everything except for x0
            add sp, sp, #8
            ldr x1, [sp], #8
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

            ret


            gxf_entry:
                    // setup GL exception vectors
                    ldr x0, =0x{gxf_vectors:x}
                    msr VBAR_GL2, x0
                    isb

                    // we might double fault -> store state here
                    mrs x14, S3_6_C15_C10_3
                    mrs x15, S3_6_C15_C10_4
                    mrs x16, S3_6_C15_C10_5
                    mrs x17, ELR_GL2
                    mrs x18, FAR_GL2

                    // test execute access
                    ldr x1, =0x{probe_page:x}
                    mov x10, 0
                    blr x1
                    lsl x21, x21, #8
                    orr x21, x21, x10

                    // test read access
                    ldr x1, =0x{probe_page:x}
                    mov x10, 0
                    ldr x1, [x1]
                    mov x10, 0x80
                    lsl x21, x21, #8
                    orr x21, x21, x10

                    // test write access
                    ldr x1, =0x{probe_page:x}
                    add x1, x1, #0x20
                    mov x10, 0
                    str x1, [x1]
                    mov x10, 0x80
                    lsl x21, x21, #8
                    orr x21, x21, x10

                    // restore state in case we faulted in here
                    msr S3_6_C15_C10_3, x14
                    msr S3_6_C15_C10_4, x15
                    msr S3_6_C15_C10_5, x16
                    msr ELR_GL2, x17
                    msr FAR_GL2, x18

                    isb
                    gexit

            gxf_abort:
                    // store that we failed
                    mov x10, 0xf1

                    // move PC two instruction further and clear 0xf0 0000 0000 to
                    // make sure we end up in the r-x mapping either way and don't
                    // repeat the instruction that just faulted
                    // we skip the second instruction since that one is used to
                    // indicate success
                    ldr x11, =0x0fffffffff
                    mrs x12, ELR_GL2
                    add x12, x12, #8
                    and x12, x12, x11
                    msr ELR_GL2, x12

                    isb
                    gexit
    """.format(ttbr=pagetable.l0, vectors=el2_vectors, probe_page=probe_page_vaddr, gxf_vectors=gl2_vectors))

print("Running code now...")
for i in range(0x10):
    sprr_val = 0x5 | ((i & 0xf) << 4)
    ret = p.smp_call_sync(1, code_page, sprr_val)

    glret = ret >> 24
    glx = 'x' if (glret >> 16) & 0xff == 0x80 else '-'
    glr = 'r' if (glret >> 8) & 0xff == 0x80 else '-'
    glw = 'w' if glret & 0xff == 0x80 else '-'

    x = 'x' if (ret >> 16) & 0xff == 0x80 else '-'
    r = 'r' if (ret >> 8) & 0xff == 0x80 else '-'
    w = 'w' if ret & 0xff == 0x80 else '-'

    print("SPRR: {0:04b} result: {1:x} GL: {2}{3}{4} EL: {5}{6}{7}".format(
        i, ret, glr, glw, glx, r, w, x))
