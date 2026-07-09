/* SPDX-License-Identifier: MIT */
#include "private.h"

int debug_printf(const char *fmt, ...);

#define USER_POINTER_BATCH_LIMIT       64U
#define USER_POINTER_OP_SIZE           0x18UL
#define USER_POINTER_VALUE_OFF         0x00UL

bool_t xnu_handle_table0(void *ctx, u32 endpoint, u64 *regs)
{
    if (endpoint < 64) g_state.ep_count[endpoint]++;

    switch (endpoint) {
        case SPTM_FN_MAP_PAGE: {
            /* (root_pa, va, new_pte) -> sptm_return_t */
            u64 root_pa = regs[0];
            u64 va      = regs[1];
            u64 new_pte = regs[2];
            u64 idx = 0;
            bool_t geom4k = root_uses_4k(root_pa, 3);
            u64 l3 = walk_to_l3(root_pa, va, &idx);
            if (l3 == 0) {
                regs[0] = SPTM_TABLE_NOT_PRESENT;
                g_state.fast_path_calls++; sev();
                return 1;
            }
            volatile u64 *slot = pt_slot_ptr(l3, idx);
            u64 existing = pt_read_slot_poc(slot);
            bool_t existing_valid = ((existing & 3) == 3);
            u64 arm_pte =
                t8140_cpu_pio_shadow_pte(xnu_pte_to_arm_geom(new_pte, geom4k),
                                         geom4k);
            u64 ptep_pa = l3 + idx * 8;
            u64 ptep_frame_pa = ptep_pa & FRAME_PAGE_MASK;
            u64 page_mask = geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK;
            u64 target_pa = new_pte & page_mask;
            u64 ptep_papt_va = 0;
            if (g_state.first_papt != 0 && ptep_pa >= g_state.vm_first_phys)
                ptep_papt_va = g_state.first_papt + (ptep_pa - g_state.vm_first_phys);
            g_state.last_map_page[0] = root_pa;
            g_state.last_map_page[1] = va;
            g_state.last_map_page[2] = l3;
            g_state.last_map_page[3] = idx;
            g_state.last_map_page[4] = ptep_pa;
            g_state.last_map_page[5] = ptep_papt_va;
            g_state.last_map_page[6] = existing;
            g_state.last_map_page[7] = new_pte;
            g_state.last_map_page[8] = arm_pte;
            g_state.last_map_page[9] = target_pa;
            g_state.last_map_page[10] = ft_get_type(target_pa);
            g_state.last_map_page[11] = ft_read_page_refcount(target_pa);
            g_state.last_map_page[12] = ft_read_table_refcount(ptep_frame_pa);
            g_state.last_map_page[13] = ft_idx_or_bad(ptep_frame_pa);
            /* AUDIT FIX #1: write sptm_map_page_output_t.
             * Then DC CVAU + DSB to make scratch visible to xnu's read. */
            if (g_state.scratch_pa != 0) {
                volatile u64 *out = scratch_for_current_cpu();
                out[0] = existing;
                out[1] = ptep_papt_va;
                __asm__ volatile(
                    "dc cvau, %0\n\t"
                    "dc cvau, %1\n\t"
                    "dsb ish\n\t"
                    : : "r"(&out[0]), "r"(&out[1]) : "memory");
            }
            /*
             * Existing same-PA mappings are upgraded in place. Different-PA
             * replacements must go back through XNU's remove/retry path so the
             * architecture's break-before-make sequence is preserved.
             */
            if (existing_valid && ((existing & page_mask) != (arm_pte & page_mask))) {
                regs[0] = SPTM_MAP_PADDR_CONFLICT;
                g_state.fast_path_calls++; sev();
                return 1;
            }
            *slot = arm_pte;
            clean_pt_slot_poc(slot);
            update_refcounts_for_leaf_pte_change(l3, existing, arm_pte, geom4k);
            maybe_map_t8140_pmgr_cpustart_window(root_pa, va, arm_pte,
                                                 geom4k, l3, idx);
            if (existing_valid)
                tlbi_vmalle1is();
            regs[0] = existing_valid ? SPTM_MAP_VALID : SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_MAP_TABLE: {
            /* (root_pa, va, target_level, new_tte) -> sptm_return_t */
            u64 root_pa      = regs[0];
            u64 va           = regs[1];
            u32 target_level = (u32)regs[2];
            u64 new_tte      = regs[3];
            u64 idx = 0;
            u64 parent = walk_to_level(root_pa, va, target_level, &idx);
            if (parent == 0) {
                regs[0] = SPTM_TABLE_NOT_PRESENT;
                g_state.fast_path_calls++; sev();
                return 1;
            }
            bool_t geom4k = root_uses_4k(root_pa, target_level);
            u64 base_idx = table_group_base_idx(idx, geom4k);
            u32 group_count = table_group_count(geom4k);
            volatile u64 *slot = pt_slot_ptr(parent, base_idx);
            u64 existing = 0;
            u64 arm_tte = xnu_tte_to_arm(new_tte);
            u64 child_pa = new_tte & ARM_TTE_TABLE_MASK;
            bool_t already_present = 0;
            for (u32 n = 0; n < group_count; n++) {
                u64 cur = pt_read_slot_poc(&slot[n]);
                if ((cur & 3) == 3) {
                    if (!already_present)
                        existing = cur;
                    already_present = 1;
                }
            }
            if (already_present) {
                g_state.last_map_table[0] = root_pa;
                g_state.last_map_table[1] = va;
                g_state.last_map_table[2] = target_level;
                g_state.last_map_table[3] = parent;
                g_state.last_map_table[4] = base_idx;
                g_state.last_map_table[5] = existing;
                g_state.last_map_table[6] = new_tte;
                g_state.last_map_table[7] = arm_tte;
                g_state.last_map_table[8] = child_pa & FRAME_PAGE_MASK;
                g_state.last_map_table[9] = ft_read_table_refcount(child_pa);
                regs[0] = SPTM_TABLE_ALREADY_PRESENT;
                g_state.fast_path_calls++; sev();
                return 1;
            }
            u64 desc_attrs = arm_tte & ~ARM_TTE_TABLE_MASK;
            for (u32 n = 0; n < group_count; n++) {
                u64 sub_pa = table_group_child_pa(child_pa, n, geom4k);
                slot[n] = desc_attrs | (sub_pa & ARM_TTE_TABLE_MASK);
            }
            clean_pt_range_poc(slot, (u64)group_count * 8);
            ft_inc_table_mapping_refcount(child_pa & FRAME_PAGE_MASK);
            g_state.last_map_table[0] = root_pa;
            g_state.last_map_table[1] = va;
            g_state.last_map_table[2] = target_level;
            g_state.last_map_table[3] = parent;
            g_state.last_map_table[4] = base_idx;
            g_state.last_map_table[5] = existing;
            g_state.last_map_table[6] = new_tte;
            g_state.last_map_table[7] = arm_tte;
            g_state.last_map_table[8] = child_pa & FRAME_PAGE_MASK;
            g_state.last_map_table[9] = ft_read_table_refcount(child_pa);
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UNMAP_TABLE: {
            /* (root_pa, va, target_level) -> void.
             * Clear the parent TTE and leave the child frame type/counts
             * alone. XNU drains leaf mappings first, queries the child table
             * count, then performs the retype itself. */
            u64 root_pa      = regs[0];
            u64 va           = regs[1];
            u32 target_level = (u32)regs[2];
            u64 idx = 0;
            u64 parent = walk_to_level(root_pa, va, target_level, &idx);
            u64 existing = 0;
            u64 freed_pa = 0;
            if (parent != 0) {
                bool_t geom4k = root_uses_4k(root_pa, target_level);
                u64 base_idx = table_group_base_idx(idx, geom4k);
                u32 group_count = table_group_count(geom4k);
                volatile u64 *slot = pt_slot_ptr(parent, base_idx);
                idx = base_idx;
                for (u32 n = 0; n < group_count; n++) {
                    u64 cur = pt_read_slot_poc(&slot[n]);
                    if (existing == 0 && (cur & 3) == 3)
                        existing = cur;
                    slot[n] = 0;
                }
                clean_pt_range_poc(slot, (u64)group_count * 8);
                if ((existing & 3) == 3) {
                    freed_pa = existing & FRAME_PAGE_MASK;
                    ft_dec_table_mapping_refcount(freed_pa);
                }
            }
            g_state.last_unmap_table[0] = root_pa;
            g_state.last_unmap_table[1] = va;
            g_state.last_unmap_table[2] = target_level;
            g_state.last_unmap_table[3] = parent;
            g_state.last_unmap_table[4] = idx;
            g_state.last_unmap_table[5] = existing;
            g_state.last_unmap_table[6] = freed_pa;
            g_state.last_unmap_table[7] = ft_get_type(freed_pa);
            g_state.last_unmap_table[8] = ft_read_table_refcount(freed_pa);
            g_state.last_unmap_table[9] = ft_idx_or_bad(freed_pa);
            tlbi_vmalle1is();
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_RETYPE: {
            /* (pa, current_type, new_type, options) -> sptm_return_t.
             * Real SPTM validates the old type and zeroes pages that become
             * page tables. We keep the functional side effects in C; violations
             * remain accepted in this permissive bringup model, but frame_table
             * is the single source of truth for XNU/libsptm direct reads. */
            u64 pa = regs[0];
            u8 current_type = (u8)regs[1];
            u8 nt = (u8)regs[2];
            u8 existing_type = ft_get_type(pa);
            bool_t was_alt_ptd = existing_type == XNU_PAGE_TABLE_ALT;
            bool_t will_alt_ptd = nt == XNU_PAGE_TABLE_ALT;
            bool_t alt_papt_attr_write = 0;
            u64 page_ref_before = ft_read_page_refcount(pa);
            u64 table_ref_before = ft_read_table_refcount(pa);
            u64 papt_ring_before = g_state.papt_update.ring_idx;
            u8 root_geom = ROOT_GEOM_UNKNOWN;
            u16 root_asid = 0;

            if (was_alt_ptd && !will_alt_ptd) {
                alt_papt_attr_write =
                    set_kernel_papt_cacheable_for_managed_pa(pa, 1,
                                                             sptm_ctx_elr(ctx));
                alt_ptd_set_el2_cacheable(pa, 1);
            } else if (!was_alt_ptd && will_alt_ptd) {
                alt_papt_attr_write =
                    set_kernel_papt_cacheable_for_managed_pa(pa, 0,
                                                             sptm_ctx_elr(ctx));
                alt_ptd_set_el2_cacheable(pa, 0);
            }

            if (is_pt_type(nt)) {
                zero_16k(pa);
                ft_write_u16(pa, FT_TABLE_MAPPING_REFCNT_OFF, 0);
                ft_write_u16(pa, FT_TABLE_NESTED_REFCNT_OFF, 0);
            }

            if (is_pt_type(existing_type) && !is_pt_type(nt)) {
                ft_write_u16(pa, FT_TABLE_MAPPING_REFCNT_OFF, 0);
                ft_write_u16(pa, FT_TABLE_NESTED_REFCNT_OFF, 0);
            }

            ft_set_type(pa, nt);
            if (was_alt_ptd || will_alt_ptd)
                sptm_coproc_cache_maint_data_page(pa);
            if (is_root_type(nt)) {
                root_geom = retype_params_attr_idx(regs[3]);
                root_asid = retype_params_asid(regs[3]);
                root_geom_set_meta(pa, root_geom, root_asid);
            }
            barrier();

            g_state.last_retype[0] = pa;
            g_state.last_retype[1] = current_type;
            g_state.last_retype[2] = nt;
            g_state.last_retype[3] = existing_type;
            g_state.last_retype[4] = ft_read_page_refcount(pa);
            g_state.last_retype[5] = ft_read_table_refcount(pa);
            g_state.last_retype[6] = ft_idx_or_bad(pa);
            g_state.last_retype[7] = (is_pt_type(existing_type) ? 1UL : 0UL) |
                                     (is_pt_type(nt) ? 2UL : 0UL) |
                                     ((u64)root_geom << 8) |
                                     ((u64)root_asid << 16) |
                                     ((u64)retype_params_flags(regs[3]) << 32);
            if (was_alt_ptd || will_alt_ptd) {
                u64 flags = (was_alt_ptd ? 1UL : 0UL) |
                            (will_alt_ptd ? 2UL : 0UL) |
                            (alt_papt_attr_write ? 4UL : 0UL) |
                            (is_pt_type(existing_type) ? 8UL : 0UL) |
                            (is_pt_type(nt) ? 16UL : 0UL);
                u64 sp0 = ctx ? *(volatile u64 *)((unsigned char *)ctx + 0x158) : 0;
                u64 sp1 = ctx ? *(volatile u64 *)((unsigned char *)ctx + 0x160) : 0;
                note_alt_ptd_retype(pa, sptm_ctx_elr(ctx), regs[30], regs[29],
                                    sp0, sp1, current_type, existing_type, nt,
                                    regs[3],
                                    page_ref_before, table_ref_before,
                                    ft_read_page_refcount(pa),
                                    ft_read_table_refcount(pa),
                                    ft_idx_or_bad(pa), papt_ring_before,
                                    flags);
            }

            if (alt_papt_attr_write)
                tlbi_vmalls12e1is();
            else if (is_pt_type(nt) || is_io_type(nt) ||
                is_pt_type(existing_type) || is_pt_type(current_type))
                tlbi_vmalle1is();

            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UPDATE_REGION: {
            u64 root_pa = regs[0];
            u64 start_va = regs[1];
            u32 num = (u32)(regs[2] & 0xffffffff);
            u64 templates_pa = regs[3];
            u64 options = regs[4];
            u64 mask = options & SPTM_UPDATE_MASK;
            bool_t geom4k = root_uses_4k(root_pa, 3);
            u64 page_size = geom4k ? PAGE_SIZE_4K_EMUL : PAGE_SIZE_GUEST_EMUL;
            volatile u64 *prev_out = scratch_for_current_cpu();
            u32 prev_count = 0;
            if (num > 2048) num = 2048;
            for (u32 i = 0; i < num; i++) {
                u64 va = start_va + (u64)i * page_size;
                u64 idx;
                u64 l3 = walk_to_l3(root_pa, va, &idx);
                u64 existing = 0;
                if (l3) {
                    volatile u64 *slot = pt_slot_ptr(l3, idx);
                    existing = pt_read_slot_poc(slot);
                    u64 tmpl = ((volatile u64 *)templates_pa)[i];
                    u64 arm_template =
                        xnu_pte_update_template_to_arm_geom(tmpl, geom4k);
                    u64 arm_pte =
                        t8140_cpu_pio_shadow_pte(
                            merge_pte_with_mask_geom(existing, arm_template,
                                                     mask, geom4k),
                            geom4k);
                    *slot = arm_pte;
                    clean_pt_slot_poc(slot);
                    update_refcounts_for_leaf_pte_change(l3, existing, arm_pte,
                                                         geom4k);
                    maybe_map_t8140_pmgr_cpustart_window(root_pa, va, arm_pte,
                                                         geom4k, l3, idx);
                }
                write_prev_pte(prev_out, &prev_count, existing);
            }
            if (prev_out) clean_range((void *)prev_out, (u64)prev_count * 8);
            if (!(options & 0x100))
                tlbi_vmalle1is();
            else
                barrier();
            regs[0] = (options & 0x100) ? SPTM_UPDATE_DELAYED_TLBI : SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UPDATE_DISJOINT: {
            u64 ops_pa = regs[1];
            u32 num = (u32)(regs[2] & 0xffffffff);
            u64 options = regs[3];
            u64 mask = options & SPTM_UPDATE_MASK;
            volatile u64 *prev_out = scratch_for_current_cpu();
            u32 prev_count = 0;
            if (num > 2048) num = 2048;
            for (u32 i = 0; i < num; i++) {
                volatile u64 *op = (volatile u64 *)(ops_pa + (u64)i * DISJOINT_OP_SIZE);
                u64 root_pa = op[0];
                u64 va = op[1];
                u64 tmpl = op[2];
                u64 idx;
                bool_t geom4k = root_uses_4k(root_pa, 3);
                u64 l3 = walk_to_l3(root_pa, va, &idx);
                u64 existing = 0;
                if (l3) {
                    volatile u64 *slot = pt_slot_ptr(l3, idx);
                    existing = pt_read_slot_poc(slot);
                    u64 arm_template =
                        xnu_pte_update_template_to_arm_geom(tmpl, geom4k);
                    u64 arm_pte =
                        t8140_cpu_pio_shadow_pte(
                            merge_pte_with_mask_geom(existing, arm_template,
                                                     mask, geom4k),
                            geom4k);
                    *slot = arm_pte;
                    clean_pt_slot_poc(slot);
                    update_refcounts_for_leaf_pte_change(l3, existing, arm_pte,
                                                         geom4k);
                    maybe_map_t8140_pmgr_cpustart_window(root_pa, va, arm_pte,
                                                         geom4k, l3, idx);
                }
                write_prev_pte(prev_out, &prev_count, existing);
            }
            if (prev_out) clean_range((void *)prev_out, (u64)prev_count * 8);
            if (!(options & 0x100))
                tlbi_vmalle1is();
            else
                barrier();
            regs[0] = (options & 0x100) ? SPTM_UPDATE_DELAYED_TLBI : SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UPDATE_DISJOINT_MULTIPAGE: {
            u64 ops_pa = regs[0];
            u32 num_entries = (u32)(regs[1] & 0xffffffff);
            volatile u64 *prev_out = scratch_for_current_cpu();
            u32 prev_count = 0;
            bool_t any_deferred = 0;
            bool_t any_papt_attr_write = 0;
            u32 i = 0;
            if (num_entries > 2048) num_entries = 2048;
            while (i < num_entries) {
                u64 base = ops_pa + (u64)i * DISJOINT_OP_SIZE;
                u64 paddr = *(volatile u64 *)base;
                u64 papt_template = *(volatile u64 *)(base + 8);
                u32 inner_n = *(volatile u32 *)(base + 16);
                u32 opts = *(volatile u32 *)(base + 20);
                u64 inner_root_pa = 0;
                u64 inner_va = 0;
                u64 inner_template = 0;
                i++;
                if (inner_n != 0 && i < num_entries) {
                    volatile u64 *first_inner =
                        (volatile u64 *)(ops_pa + (u64)i * DISJOINT_OP_SIZE);
                    inner_root_pa = first_inner[0];
                    inner_va = first_inner[1];
                    inner_template = first_inner[2];
                }
                if (opts & SPTM_UPDATE_DEFER_TLBI)
                    any_deferred = 1;
                if (update_kernel_papt_attrs(paddr, papt_template, opts,
                                             sptm_ctx_elr(ctx), inner_root_pa,
                                             inner_va, inner_template))
                    any_papt_attr_write = 1;
                for (u32 j = 0; j < inner_n && i < num_entries; j++, i++) {
                    volatile u64 *op = (volatile u64 *)(ops_pa + (u64)i * DISJOINT_OP_SIZE);
                    u64 root_pa = op[0];
                    u64 va = op[1];
                    u64 tmpl = op[2];
                    u64 idx;
                    bool_t geom4k = root_uses_4k(root_pa, 3);
                    u64 l3 = walk_to_l3(root_pa, va, &idx);
                    u64 existing = 0;
                    if (l3) {
                        volatile u64 *slot = pt_slot_ptr(l3, idx);
                        existing = pt_read_slot_poc(slot);
                        u64 arm_template =
                            xnu_pte_update_template_to_arm_geom(tmpl, geom4k);
                        u64 arm_pte =
                            t8140_cpu_pio_shadow_pte(
                                merge_pte_with_mask_geom(
                                    existing, arm_template,
                                    opts & SPTM_UPDATE_MASK, geom4k),
                                geom4k);
                        *slot = arm_pte;
                        clean_pt_slot_poc(slot);
                        update_refcounts_for_leaf_pte_change(l3, existing, arm_pte,
                                                             geom4k);
                        maybe_map_t8140_pmgr_cpustart_window(root_pa, va, arm_pte,
                                                             geom4k, l3, idx);
                    }
                    write_prev_pte(prev_out, &prev_count, existing);
                }
            }
            if (prev_out) clean_range((void *)prev_out, (u64)prev_count * 8);
            /*
             * Deferred TLBI covers the guest-requested VA updates. The PAPT
             * mirror is a private kernel alias we update on XNU's behalf, so
             * flush it here when its cacheability attributes changed.
             */
            if (any_papt_attr_write)
                tlbi_vmalls12e1is();
            else if (!any_deferred)
                tlbi_vmalle1is();
            else
                barrier();
            regs[0] = any_deferred ? SPTM_UPDATE_DELAYED_TLBI : SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UNMAP_DISJOINT: {
            u64 ops_pa = regs[1];
            u32 num = (u32)(regs[2] & 0xffffffff);
            volatile u64 *prev_out = scratch_for_current_cpu();
            u32 prev_count = 0;
            if (num > 2048) num = 2048;
            for (u32 i = 0; i < num; i++) {
                volatile u64 *op = (volatile u64 *)(ops_pa + (u64)i * DISJOINT_OP_SIZE);
                u64 root_pa = op[0];
                u64 va = op[1];
                u64 tmpl = op[2];
                u64 idx;
                bool_t geom4k = root_uses_4k(root_pa, 3);
                u64 l3 = walk_to_l3(root_pa, va, &idx);
                u64 existing = 0;
                if (l3) {
                    volatile u64 *slot = pt_slot_ptr(l3, idx);
                    existing = pt_read_slot_poc(slot);
                    /*
                     * Disjoint unmap receives an XNU template, but leaving
                     * template PA/attribute bits in an invalid slot can make
                     * XNU later interpret the entry as a corrupt compressed
                     * PTE.  Real pmap remove paths fault the slot; keep the
                     * old PTE only in the prev-PTE scratch output.
                     */
                    (void)tmpl;
                    *slot = 0;
                    clean_pt_slot_poc(slot);
                    update_refcounts_for_leaf_pte_change(l3, existing, 0, geom4k);
                }
                write_prev_pte(prev_out, &prev_count, existing);
            }
            if (prev_out) clean_range((void *)prev_out, (u64)prev_count * 8);
            tlbi_vmalle1is();
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_SWITCH_ROOT: {
            u64 root_pa = regs[0];
            if (ft_get_type(root_pa) == SPTM_KERNEL_ROOT_TABLE) {
                u64 ttbr = root_pa & TTBR_BADDR_MASK;
                __asm__ volatile("msr S3_5_C2_C0_1, %0" : : "r"(ttbr));
            } else {
                u64 asid = root_asid_lookup(root_pa);
                u64 ttbr = (root_pa & TTBR_BADDR_MASK) | (asid << TTBR_ASID_SHIFT);
                __asm__ volatile("msr S3_5_C2_C0_0, %0" : : "r"(ttbr));
            }
            tlbi_vmalle1is();
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_CONFIGURE_SHAREDREGION:
            ft_set_type(regs[0], XNU_SHARED_ROOT_TABLE);
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;

        case SPTM_FN_SET_SHARED_REGION:
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;

        case SPTM_FN_NEST_REGION: {
            u64 user_root = regs[0];
            u64 shared_root = regs[1];
            u64 start_va = regs[2];
            u32 page_count = (u32)(regs[3] & 0xffffffff);
            bool_t geom4k = root_uses_4k(user_root, 2);
            u64 page_size = geom4k ? PAGE_SIZE_4K_EMUL : PAGE_SIZE_GUEST_EMUL;
            u64 l2_coverage = (geom4k ? 0x200UL : 0x800UL) * page_size;
            u64 end_va = start_va + (u64)page_count * page_size;
            u64 va = start_va & ~(l2_coverage - 1);
            while (va < end_va) {
                u64 sidx = 0, uidx = 0;
                u64 sparent = walk_to_level(shared_root, va, 2, &sidx);
                u64 uparent = walk_to_level(user_root, va, 2, &uidx);
                if (sparent != 0 && uparent != 0 && sidx == uidx) {
                    volatile u64 *uslot = pt_slot_ptr(uparent, uidx);
                    u64 tte = pt_read_slot_poc(pt_slot_ptr(sparent, sidx));
                    if ((tte & 3) == 3) {
                        *uslot = tte;
                        clean_pt_slot_poc(uslot);
                    }
                }
                va += l2_coverage;
            }
            barrier();
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UNNEST_REGION: {
            u64 user_root = regs[0];
            u64 start_va = regs[2];
            u32 page_count = (u32)(regs[3] & 0xffffffff);
            bool_t geom4k = root_uses_4k(user_root, 2);
            u64 page_size = geom4k ? PAGE_SIZE_4K_EMUL : PAGE_SIZE_GUEST_EMUL;
            u64 l2_coverage = (geom4k ? 0x200UL : 0x800UL) * page_size;
            u64 end_va = start_va + (u64)page_count * page_size;
            u64 va = start_va & ~(l2_coverage - 1);
            while (va < end_va) {
                u64 idx = 0;
                u64 parent = walk_to_level(user_root, va, 2, &idx);
                if (parent != 0) {
                    volatile u64 *slot = pt_slot_ptr(parent, idx);
                    *slot = 0;
                    clean_pt_slot_poc(slot);
                }
                va += l2_coverage;
            }
            tlbi_vmalle1is();
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        /* C-only ack-success endpoints.
         *
         * Historical note: older m1n1 builds also added +4 to ELR for
         * handled HVCs, which double-advanced these non-trampoline call
         * sites and skipped one real instruction. Core m1n1 now leaves
         * handled HVC ELR alone, so resume should use ELR_EL2 directly. */
        case SPTM_FN_FIXUPS_COMPLETE:
        case SPTM_FN_CONFIGURE_ROOT:
        case SPTM_FN_SLIDE_REGION:
        case SPTM_FN_REG_WRITE:
        case SPTM_FN_SERIAL_DISABLE:
        case SPTM_FN_REGISTER_EXC_RETURN:
        case SPTM_FN_DISABLE_KERNEL_MODE_CPA2:
        case SPTM_FN_PROGRAM_IRGKEY:
        case SPTM_FN_REG_SNAPSHOT:
        case SPTM_FN_MAP_SK_DOMAIN:
        case SPTM_FN_HIB_BEGIN:
        case SPTM_FN_HIB_VERIFY_HASH_NON_WIRED:
        case SPTM_FN_HIB_FINALIZE_NON_WIRED:
        case SPTM_FN_GUEST_EXIT:
        {
            return finish_hvc_success(ctx, regs);
        }

        case SPTM_FN_GUEST_STAGE1_TLBOP:
            /*
             * Real SPTM decodes the requested guest S1 operation and issues a
             * scoped TLBI while running under the guest's stage-2 context. We
             * do not model nested guest contexts yet, but ACK-only is wrong:
             * callers use this endpoint specifically to retire stale S1
             * translations. A broadcast S1 invalidate is conservative and
             * preserves the architectural effect until the op decoder exists.
             */
            tlbi_vmalle1is();
            return finish_hvc_success(ctx, regs);

        case SPTM_FN_GUEST_STAGE2_TLBOP:
            /*
             * Same conservative treatment for guest stage-2 invalidates. The
             * exact firmware path can narrow this to IPA/range later.
             */
            tlbi_vmalls12e1is();
            return finish_hvc_success(ctx, regs);

        case SPTM_FN_REGISTER_CPU: {
            u64 phys = regs[0];
            u64 count = g_state.cpu_count;
            if (count > SPTM_MAX_CPUS_EMUL)
                count = SPTM_MAX_CPUS_EMUL;

            u64 slot = SPTM_MAX_CPUS_EMUL;
            for (u64 i = 0; i < count; i++) {
                if (cpu_phys_matches(g_state.cpu_phys_ids[i], phys)) {
                    slot = i;
                    break;
                }
            }

            if (slot == SPTM_MAX_CPUS_EMUL && count < SPTM_MAX_CPUS_EMUL) {
                slot = count;
                g_state.cpu_phys_ids[slot] = phys;
                g_state.cpu_count = count + 1;
            }

            g_state.cpu_last_mpidr = current_mpidr_phys();
            g_state.cpu_last_id = (slot == SPTM_MAX_CPUS_EMUL) ? 0 : slot;
            sptm_cpu_pio_note_registered(phys, g_state.cpu_last_id);
            return finish_hvc_success(ctx, regs);
        }

        case SPTM_FN_SURT_ALLOC:
        case SPTM_FN_SURT_FREE: {
            u64 surt_frame = regs[0];
            u64 surt_index = regs[1] & 0xff;
            u8 attr_idx = (u8)(regs[2] & 0xff);
            u64 slot_pa = surt_frame + surt_index * SURT_SUBPAGE_SIZE;
            volatile u64 *q = (volatile u64 *)slot_pa;
            for (u32 i = 0; i < (SURT_SUBPAGE_SIZE / 8); i++)
                q[i] = 0;
            clean_range_poc((void *)slot_pa, SURT_SUBPAGE_SIZE);
            if (endpoint == SPTM_FN_SURT_ALLOC)
                root_geom_set_meta(slot_pa, attr_idx, (u16)(regs[4] & 0xffff));
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_REG_READ:
        case SPTM_FN_SPTM_SYSCTL:
            regs[0] = 0;
            g_state.fast_path_calls++; sev();
            return 1;

        case SPTM_FN_SIGN_USER_POINTER:
        case SPTM_FN_AUTH_USER_POINTER:
            g_state.fast_path_calls++; sev();
            return 1;

        case SPTM_FN_BATCH_SIGN_USER_POINTER: {
            u64 ops_pa = regs[0];
            u32 ops_count = (u32)(regs[1] & 0xffffffff);
            volatile u64 *out = scratch_for_current_cpu();
            if (out) {
                if (ops_count > USER_POINTER_BATCH_LIMIT)
                    ops_count = USER_POINTER_BATCH_LIMIT;
                for (u32 i = 0; i < ops_count; i++) {
                    u64 op_pa = ops_pa + (u64)i * USER_POINTER_OP_SIZE;
                    out[i] = *(volatile u64 *)(op_pa +
                                               USER_POINTER_VALUE_OFF);
                }
                clean_range((void *)out, (u64)ops_count * 8);
            }
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_GUEST_VA_TO_IPA:
            regs[0] = UINT64_MAX_VALUE;
            g_state.fast_path_calls++; sev();
            return 1;

        case SPTM_FN_IOFILTER_PROTECTED_WRITE: {
            /*
             * No C model yet. Leave this unhandled so any future caller stops
             * at the missing endpoint instead of silently touching guarded
             * MMIO or reviving the removed Python fallback policy.
             */
            return 0;
        }

        case SPTM_FN_CONDEMN_LEAF_TABLE: {
            u64 root_pa = regs[0];
            u64 va = regs[1];
            u64 idx = 0;
            u64 parent = walk_to_level(root_pa, va, 2, &idx);
            if (parent == 0) {
                regs[0] = SPTM_TABLE_NOT_PRESENT;
            } else {
                volatile u64 *slot = pt_slot_ptr(parent, idx);
                u64 l2e = pt_read_slot_poc(slot);
                if ((l2e & 3) != 3 || (l2e & TTE_CONDEMNED_BIT))
                    regs[0] = SPTM_TABLE_NOT_PRESENT;
                else {
                    *slot = l2e | TTE_CONDEMNED_BIT;
                    clean_pt_slot_poc(slot);
                    regs[0] = SPTM_SUCCESS;
                }
            }
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_UNCONDEMN_LEAF_TABLE: {
            u64 root_pa = regs[0];
            u64 va = regs[1];
            u64 idx = 0;
            u64 parent = walk_to_level(root_pa, va, 2, &idx);
            if (parent != 0) {
                volatile u64 *slot = pt_slot_ptr(parent, idx);
                u64 l2e = pt_read_slot_poc(slot);
                *slot = l2e & ~TTE_CONDEMNED_BIT;
                clean_pt_slot_poc(slot);
            }
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_SERIAL_PUTC:
            /* Avoid per-character UART round trips. Panic diagnostics are
             * captured through XNU_PANIC_BEGIN and framebuffer/serial KDP. */
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;

        case SPTM_FN_LOCKDOWN:
            /* Our boot page tables already establish coarse kernel RX/RO/RW.
             * Real SPTM would lock CTRR and retype text pages. */
            regs[0] = SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;

        /* UNMAP_REGION (ep=7) — port to C, ATTEMPT 3 (subagent fix).
         *
         * ROOT CAUSE of prior 2 attempts: incorrectly applied the ELR-=4
         * workaround. That workaround is ONLY needed for HVCs at NON-
         * trampoline call sites (FIXUPS_COMPLETE etc.). UNMAP_REGION
         * goes through the SPTM trampoline at 0xbcee880 — same as
         * MAP_PAGE/MAP_TABLE/RETYPE — which has `hvc; retab; bti c`.
         * m1n1's auto +4 lands on `bti c` (benign NOP); ELR-=4 made it
         * land on `retab` instead, NOT a BTI landing pad → EC=0x1b BTI
         * fail → corrupt PC → panic 2-3 calls later.
         *
         * Plus: real SPTM `f6180 sptm_pte_finalize_unmap` decrements
         * the page-FTE refcount on each unmapped target. Mirror that. */
        case 7: {  /* SPTM_FN_UNMAP_REGION */
            u64 root_pa  = regs[0];
            u64 start_va = regs[1];
            u32 num      = (u32)(regs[2] & 0xffffffff);
            u64 options  = regs[3];
            bool_t geom4k = root_uses_4k(root_pa, 3);
            u64 page_size = geom4k ? PAGE_SIZE_4K_EMUL : PAGE_SIZE_GUEST_EMUL;
            volatile u64 *prev_out = scratch_for_current_cpu();
            u32 prev_count = 0;
            bool_t any_unmapped = 0;
            if (num > 2048) num = 2048;
            for (u32 i = 0; i < num; i++) {
                u64 va = start_va + (u64)i * page_size;
                u64 idx;
                u64 l3 = walk_to_l3(root_pa, va, &idx);
                u64 existing = 0;
                if (l3) {
                    volatile u64 *slot = pt_slot_ptr(l3, idx);
                    existing = pt_read_slot_poc(slot);
                    *slot = 0;
                    clean_pt_slot_poc(slot);
                    if ((existing & 3) == 3)
                        any_unmapped = 1;
                }
                write_prev_pte(prev_out, &prev_count, existing);
                update_refcounts_for_leaf_pte_change(l3, existing, 0, geom4k);
            }
            if (prev_out) clean_range((void *)prev_out, (u64)prev_count * 8);
            if (any_unmapped && !(options & 0x100))
                tlbi_vmalle1is();
            else
                barrier();
            regs[0] = (any_unmapped && (options & 0x100)) ?
                SPTM_UPDATE_DELAYED_TLBI : SPTM_SUCCESS;
            g_state.fast_path_calls++; sev();
            return 1;
        }

        case SPTM_FN_CPU_ID:
            regs[0] = cpu_id_for_phys(regs[0]);
            g_state.fast_path_calls++; sev();
            return 1;

        default:
            /* Unrecognized — host treats this as a hard diagnostic failure. */
            g_state.unknown_calls++;
            g_state.fallthrough_calls++;
            return 0;
    }
}
