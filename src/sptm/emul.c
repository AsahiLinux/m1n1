/* SPDX-License-Identifier: MIT */
/*
 * DO NOT MERGE: tainted SPTM endpoint emulator imported from the bringup tree.
 *
 * This is intentionally isolated under src/sptm while we separate the clean
 * hypervisor plumbing from the reverse-engineered SPTM behavior. The old tree
 * built this as a hot-loaded C object; this branch links it directly into the
 * streamed stage2 hypervisor so endpoint state has one C source of truth.
 */

#include "emul.h"
#include "private.h"

#include "../memory.h"
#include "../utils.h"
#include "../xnuboot.h"

int debug_printf(const char *fmt, ...);

/* The single state instance exported for Python-side boot seeding. Keep this
 * 1MiB even though struct sptm_emul_state is smaller: a few emulated SPTM
 * devices use the tail as private scratch, matching the old bringup layout. */
u8 g_sptm_state[0x100000] __attribute__((aligned(0x4000)));

bool_t sptm_handler(void *ctx) {
    /* ctx points at struct exc_info. regs[] is at offset 0. */
    u64 *regs = (u64 *)((unsigned char *)ctx + REGS_OFFSET);
    u64 esr = *(u64 *)((unsigned char *)ctx + ESR_OFFSET);
    u64 *ctx_spsr_ptr = (u64 *)((unsigned char *)ctx + 0x100);

    /* XNU's kernel-mode invariant is DAIF.D == 1.  Most SPTM calls are
     * direct in-kernel HVCs, so returning with the trapped SPSR unchanged can
     * propagate a transient D-clear state until ml_set_interrupts_enabled()
     * panics with "debug exceptions enabled in kernel mode".  Enforce only D
     * here; do not touch A/I/F, since the timer/FIQ path depends on preserving
     * XNU's interrupt mask state exactly. */
    *ctx_spsr_ptr |= 0x200;

    /* DEBUG: snapshot ALL guest GP regs at trap entry — BEFORE any C
     * code can touch them. Lets us bisect register-clobber bugs
     * introduced by new C handlers. Cheap (31 u64 stores). */
    {
        u64 idx = g_state.sptm_in_idx & 0x7f;
        for (int r = 0; r < 31; r++) {
            g_state.sptm_in_regs[idx][r] = regs[r];
        }
        g_state.sptm_in_idx = (g_state.sptm_in_idx + 1) & 0x7f;
    }

    /* ---------------------------------------------------------------
     * SPRR sysreg fast-path. EL1's vbar slot 0 has been patched to
     * HVC #0, so when xnu (e.g. _pmap_ro_zone_memcpy_internal in
     * libT8140) writes SPRR_PERM_EL1 from EL1, the UNDEF lands here.
     * SPRR is GL2-gated and m1n1 EL2 cannot complete the write — we
     * soft-cache it. Without this fast path each trap pays a UART
     * round-trip (~hundreds of ms × thousands of RO-zone init writes).
     *
     * Detect by inspecting the trapping instruction at ELR_EL12. If
     * it's any MSR/MRS to S3_6_C15_C1_x (op1=6, CRn=15, CRm=1):
     *   - MSR: cache write value (no actual sysreg touch)
     *   - MRS: return cached/seeded value into Rt
     * Then advance ELR_EL12 by 4 by setting ctx->elr to elr12+4 and
     * let m1n1 ERET past xnu's vector handler back to user code at
     * elr12+4.
     * --------------------------------------------------------------- */
    if (g_state.kc_vmin != 0) {
        u64 esr12, elr12, spsr12, elr2;
        /* ESR_EL12 = S3_5_C5_C2_0; ELR_EL12 = S3_5_C4_C0_1; SPSR_EL12 = S3_5_C4_C0_0 */
        __asm__ volatile("mrs %0, S3_5_C5_C2_0" : "=r"(esr12));
        __asm__ volatile("mrs %0, S3_5_C4_C0_1" : "=r"(elr12));
        __asm__ volatile("mrs %0, S3_5_C4_C0_0" : "=r"(spsr12));
        __asm__ volatile("mrs %0, elr_el2"      : "=r"(elr2));
        u32 ec12 = (u32)((esr12 >> 26) & 0x3f);
        /* CRITICAL: distinguish vector-induced HVC (real SPRR sysreg trap)
         * from in-kernel HVC dispatch (e.g. SPTM trampoline calls
         * `hvc #0` directly with x16=selector). For the latter, ELR_EL12
         * and ESR_EL12 are STALE from the prior EL1 vector entry — they
         * retain the LAST real SPRR trap's state. If we don't filter,
         * we mis-fast-path SPTM HVCs as if they were SPRR sysreg traps,
         * ERET-ing to a random PC inside pmap_ro_zone. ELR_EL2 is always
         * fresh: for vector-induced traps it points at the patched HVC
         * inside vbar_el1; for in-kernel HVCs it points at the dispatch
         * site in xnu code (outside vbar_el1).
         *
         * vbar_el1 in the current 26.5 setup = 0xfffffe000b388000 (vector table is
         * 0x800 bytes). Only treat as SPRR if ELR_EL2 falls in this range. */
        bool_t in_vbar = (elr2 >= 0xfffffe000b388000UL &&
                          elr2 <  0xfffffe000b388800UL);
        if (ec12 == 0 && in_vbar &&
            elr12 >= g_state.kc_vmin && elr12 < g_state.kc_vmax) {
            u64 insn_pa = g_state.kc_guest_base + (elr12 - g_state.kc_vmin);
            /* DEFENSIVE GUARD (2026-05-09): ensure insn_pa is a low PA, not a
             * high VA. Symptom: m1n1 takes EL2 sync exception with FAR in
             * 0xfffffe000c282xxx range when reading insn at "insn_pa" — that's
             * a guest VA, not a PA, so EL2 stage-1 doesn't have it mapped.
             * Cause: elr12 can be stale/bogus from a previous EL1 vector entry
             * (the in_vbar+ec12==0 filter isn't perfect across all paths), so
             * the computed insn_pa can land outside our PA range. Guard:
             *   - insn_pa must NOT have any high-VA bits set (PAs are < 4 TB)
             *   - insn_pa must be >= kc_guest_base (no arith underflow)
             *   - insn_pa must be < kc_guest_base + kc_size (kept in bounds)
             * On failure: return unhandled so the host can stop with full
             * diagnostics instead of crashing EL2. */
            u64 kc_size_va = g_state.kc_vmax - g_state.kc_vmin;
            bool_t insn_pa_ok = (insn_pa >= g_state.kc_guest_base) &&
                                ((insn_pa - g_state.kc_guest_base) < kc_size_va) &&
                                ((insn_pa & 0xfffffe0000000000UL) == 0);
            if (!insn_pa_ok) {
                g_state.fallthrough_calls++;
                return 0;  /* unsafe insn_pa — hard-fail in host diagnostics */
            }
            u32 insn = *(volatile u32 *)insn_pa;
            /* MSR S3_6_C15_C1_x, xN  →  0xd51ef1 ?? */
            /* MRS xN, S3_6_C15_C1_x  →  0xd53ef1 ?? */
            u32 base = insn & 0xffffff00u;
            if (base == 0xd51ef100u || base == 0xd53ef100u) {
                u32 is_read = (insn >> 21) & 1;
                u32 op2 = (insn >> 5) & 7;
                u32 Rt  = insn & 0x1f;
                if (is_read) {
                    u64 val;
                    if (op2 == 6)      val = g_state.sprr_perm_el1_cache;
                    else if (op2 == 5) val = g_state.sprr_perm_el0_cache;
                    else if (op2 == 0) val = g_state.sprr_config_el1_cache;
                    else               val = 0;
                    if (Rt < 31) regs[Rt] = val;
                } else {
                    u64 val = (Rt < 31) ? regs[Rt] : 0;
                    if (op2 == 6)      g_state.sprr_perm_el1_cache = val;
                    else if (op2 == 5) g_state.sprr_perm_el0_cache = val;
                    else if (op2 == 0) g_state.sprr_config_el1_cache = val;
                }
                /* If we're inside pmap_ro_zone_memcpy_internal, capture
                 * its args into the ring buffer. By the time the first
                 * SPRR MSR fires (~+0x90 from function start), the
                 * prologue has stashed args into x19..x24 — they're
                 * stable for the rest of the call. Records: (elr, x22,
                 * x24, x23, x20, x19) = (pc, zid, va, offset, src, size). */
                if (g_state.pmap_rzm_lo != 0 &&
                    elr12 >= g_state.pmap_rzm_lo &&
                    elr12 <  g_state.pmap_rzm_hi) {
                    u64 idx = g_state.pmap_rzm_idx & 0x7f;
                    g_state.pmap_rzm_ring[idx][0] = elr12;
                    g_state.pmap_rzm_ring[idx][1] = regs[22];  /* zid */
                    g_state.pmap_rzm_ring[idx][2] = regs[24];  /* va */
                    g_state.pmap_rzm_ring[idx][3] = regs[23];  /* offset */
                    g_state.pmap_rzm_ring[idx][4] = regs[20];  /* new_data */
                    g_state.pmap_rzm_ring[idx][5] = regs[19];  /* new_data_size */
                    /* Also capture full register snapshot in parallel ring.
                     * Helps tell whether it's args that are wrong or the whole
                     * machine state that's corrupted. */
                    for (int r = 0; r < 31; r++) {
                        g_state.pmap_rzm_full[idx][r] = regs[r];
                    }
                    g_state.pmap_rzm_full[idx][31] = spsr12;
                    g_state.pmap_rzm_full[idx][32] = elr12;
                    g_state.pmap_rzm_idx = (g_state.pmap_rzm_idx + 1) & 0x7f;
                    g_state.pmap_rzm_count++;
                }

                /* Skip xnu's vector handler entirely. ctx->elr currently
                 * points at the HVC in vbar_el1; redirect ERET straight to
                 * elr12+4, the original post-fault instruction boundary.
                 *
                 * CRITICAL: also restore ctx->spsr from SPSR_EL12. Without
                 * this, m1n1 ERETs with SPSR_EL2 which is EL1h (the vector
                 * handler's mode after entry), NOT the EL1t/EL1h state the
                 * function was actually running in. Result: SPSel switches
                 * mid-function, ldp/retab use the wrong stack — guaranteed
                 * PAC failure on signed-return functions. We mask DAIF for
                 * good measure (matches the Python EL1 vector handler). */
                u64 *ctx_elr  = (u64 *)((unsigned char *)ctx + 0x108);
                *ctx_elr  = elr12 + 4;
                /* Only mask DAIF.D (bit 9) to avoid xnu's
                 * "debug exceptions enabled in kernel mode" panic in
                 * ml_set_interrupts_enabled_with_debug. Preserve
                 * DAIF.I so vIRQ injection can actually fire. */
                *ctx_spsr_ptr = spsr12 | 0x200;
                g_state.sprr_fast_count++;
                g_state.fast_path_calls++;
                sev();
                return 1;
            }
        }
    }

    u64 x16      = regs[16];
    if (!is_dispatch_hvc(esr, x16)) {
        u64 elr;
        __asm__ volatile("mrs %0, elr_el2" : "=r"(elr));
        if ((esr & ESR_ISS_MASK) == SPTM_GENTER_DISPATCH_CALL &&
            (elr == XNU_265_GENTER_NODISPATCH_RET_PC ||
             elr == XNU_266_GENTER_NODISPATCH_RET_PC)) {
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++;
            sev();
            return 1;
        }
        g_state.fallthrough_calls++;
        return 0;
    }
    u32 domain   = (u32)((x16 >> 48) & 0xff);
    u32 table    = (u32)((x16 >> 32) & 0xff);
    u32 endpoint = (u32)(x16 & 0xffffffff);

    if (domain == TXM_DOMAIN && table == TXM_TABLE_XNU) {
        if (txm_handle_selector(endpoint, x16, regs))
            return 1;
        g_state.fallthrough_calls++;
        return 0;
    }

    /* Only handle domain=0 (SPTM/XNU) here. Other domains have different
     * endpoint numbering and must never be decoded as XNU_BOOTSTRAP calls. */
    if (domain != 0) {
        g_state.fallthrough_calls++;
        return 0;
    }

    g_state.total_calls++;
    g_state.last_x16     = x16;
    g_state.last_endpoint = endpoint;
    /* Record into ring buffer (last 128 calls). Also read ESR_EL2 + ELR_EL2
     * so we can distinguish SPTM HVC #0 from vector-trap HVC #0xFEEx and
     * see which xnu code issued the HVC. */
    {
        u64 idx = g_state.ring_idx & 0x7f;
        u64 esr, elr;
        __asm__ volatile("mrs %0, esr_el2" : "=r"(esr));
        __asm__ volatile("mrs %0, elr_el2" : "=r"(elr));
        g_state.ring[idx][0] = x16;
        g_state.ring[idx][1] = regs[0];
        g_state.ring[idx][2] = regs[1];
        g_state.ring[idx][3] = regs[2];
        g_state.ring[idx][4] = regs[3];
        g_state.ring[idx][5] = esr;
        g_state.ring[idx][6] = elr;
        g_state.ring[idx][7] = regs[30];  /* x30 = LR = caller of trampoline */
        g_state.ring_idx = (g_state.ring_idx + 1) & 0x7f;
    }

    /* Do not force periodic Python fall-throughs. UART round trips are too
     * expensive for boot progress; visibility comes from the shared rings and
     * explicit panic/watchdog dumps. */

    if (table == SPTM_TABLE_NVME) {
        if (nvme_handle_table6(endpoint, regs))
            return 1;
        g_state.fallthrough_calls++;
        return 0;
    }

    if (table == SPTM_TABLE_T8110_DART_XNU ||
        table == SPTM_TABLE_T8110_DART_SK ||
        table == SPTM_TABLE_GEN3_DART_XNU ||
        table == SPTM_TABLE_GEN3_DART_SK) {
        if (dart_handle_table(table, endpoint, regs))
            return 1;
        g_state.fallthrough_calls++;
        return 0;
    }

    if (table == SPTM_TABLE_SART) {
        if (sart_handle_table5(endpoint, regs))
            return 1;
        g_state.fallthrough_calls++;
        return 0;
    }

    if (table == SPTM_TABLE_UAT) {
        if (uat_handle_table7(endpoint, regs))
            return 1;
        g_state.fallthrough_calls++;
        return 0;
    }

    if (table == SPTM_TABLE_CPUTRACE) {
        /* CPUTRACE is a diagnostic/performance facility, not a boot-critical
         * memory-management endpoint.  The firmware exposes 13 known selectors
         * on this table; acknowledge them here instead of forcing a UART
         * round-trip to the removed Python fallback.  regs[0]=0 is both the
         * normal success code and the conservative "unsupported/no carveout"
         * answer for query-shaped helpers. */
        if (endpoint <= 12) {
            return finish_hvc_success(ctx, regs);
        }
        g_state.fallthrough_calls++;
        return 0;
    }

    if (compat_void_non_xnu_table(table)) {
        return finish_hvc_success(ctx, regs);
    }

    /* Fast-path the XNU_BOOTSTRAP table. Other non-XNU tables still fall
     * through to host, except NVMe table 6 above which is intentionally in C
     * to avoid Python/C split state on the ANS boot path. */
    if (table != SPTM_TABLE_XNU_BOOTSTRAP) {
        dart_cache_xnu_object_from_regs(table, endpoint, regs);
        g_state.fallthrough_calls++;
        return 0;  /* not handled */
    }


    return xnu_handle_table0(ctx, endpoint, regs);
}

extern void *hv_hvc_handler;

void sptm_emul_init(void)
{
    hv_hvc_handler = (void *)sptm_handler;

    /*
     * Map the RW_EL0 RAM alias Normal-NC. The emulator places the coprocessor /
     * IOMMU page tables it manages in this alias, and they must be uncached so
     * m1n1 does not allocate AMCC SLC directory tags on pages that AMCC/PMP
     * agents later read non-coherently (otherwise: UNEXP_RT_HIT_DIR -> panic).
     * This lives here, not in memory.c, so upstream memory.c stays generic and
     * carries no SPTM layout knowledge.
     */
    u64 ram_base = ALIGN_DOWN(cur_boot_args.phys_base, BIT(32));
    u64 ram_size = ALIGN_DOWN(cur_boot_args.mem_size + cur_boot_args.phys_base - ram_base,
                              get_page_size());
    mmu_add_mapping(ram_base | REGION_RW_EL0, ram_base, ram_size, MAIR_IDX_NORMAL_NC, PERM_RW_EL0);
}
