/* SPDX-License-Identifier: MIT */
#include "private.h"

int debug_printf(const char *fmt, ...);

static inline bool_t dart_validate_xnu_object(u64 obj, u32 *gapf_count_out,
                                               u32 *inst_count_out,
                                               u64 *state_out) {
    u32 mode, gapf_count, inst_count;
    u64 state;

    if (!is_kernel_va(obj))
        return 0;
    if (!guest_read32(obj + DART_OBJ_MODE_OFF, &mode) || mode != 2)
        return 0;
    if (!guest_read32(obj + DART_OBJ_GAPF_COUNT_OFF, &gapf_count))
        return 0;
    if (gapf_count == 0 || gapf_count > 128)
        return 0;
    if (!guest_read32(obj + DART_OBJ_INST_COUNT_OFF, &inst_count))
        return 0;
    if (inst_count == 0 || inst_count > 16)
        return 0;
    if (!guest_read64(obj + DART_OBJ_STATE_OFF, &state) || !is_kernel_va(state))
        return 0;

    *gapf_count_out = gapf_count;
    *inst_count_out = inst_count;
    *state_out = state;
    return 1;
}

static inline void dart_record_xnu_object(u32 table, u32 endpoint, u64 dart_id,
                                          u64 obj, u64 source,
                                          u32 gapf_count, u32 inst_count,
                                          u64 state) {
    u32 slot = DART_OBJ_CACHE_SLOTS;

    for (u32 i = 0; i < DART_OBJ_CACHE_SLOTS; i++) {
        if (g_state.dart_obj_cache_va[i] != 0 &&
            g_state.dart_obj_cache_id[i] == dart_id) {
            slot = i;
            break;
        }
    }
    if (slot == DART_OBJ_CACHE_SLOTS) {
        slot = (u32)(g_state.dart_obj_cache_idx & (DART_OBJ_CACHE_SLOTS - 1));
        g_state.dart_obj_cache_idx++;
    }

    g_state.dart_obj_cache_id[slot] = dart_id;
    g_state.dart_obj_cache_va[slot] = obj;
    g_state.dart_obj_last[0] = table;
    g_state.dart_obj_last[1] = endpoint;
    g_state.dart_obj_last[2] = dart_id;
    g_state.dart_obj_last[3] = obj;
    g_state.dart_obj_last[4] = source;
    g_state.dart_obj_last[5] = gapf_count;
    g_state.dart_obj_last[6] = inst_count;
    g_state.dart_obj_last[7] = state;
    for (u32 i = 0; i < 16; i++) {
        g_state.dart_obj_last_base_va[i] = 0;
        g_state.dart_obj_last_base_pa[i] = 0;
    }
    for (u32 i = 0; i < inst_count && i < 16; i++) {
        u64 mmio_va, mmio_pa;
        if (!guest_read64(state + 0x20UL + (u64)i * 0x70UL, &mmio_va))
            continue;
        g_state.dart_obj_last_base_va[i] = mmio_va;
        if (is_kernel_va(mmio_va) && guest_va_to_pa(mmio_va, 1, &mmio_pa)) {
            g_state.dart_obj_last_base_pa[i] = mmio_pa;
        } else if (mmio_va >= 0x100000000UL &&
                   (mmio_va & (DART_C_PAGE_SIZE - 1)) == 0) {
            g_state.dart_obj_last_base_pa[i] = mmio_va;
        }
    }
    g_state.dart_obj_cache_hits++;
}

static inline bool_t dart_try_candidate(u32 table, u32 endpoint, u64 dart_id,
                                        u64 candidate, u64 source) {
    u32 gapf_count, inst_count;
    u64 state;

    if (!dart_validate_xnu_object(candidate, &gapf_count, &inst_count, &state))
        return 0;
    dart_record_xnu_object(table, endpoint, dart_id, candidate, source,
                           gapf_count, inst_count, state);
    return 1;
}

void dart_cache_xnu_object_from_regs(u32 table, u32 endpoint,
                                                   u64 *regs) {
    u64 dart_id = regs[0];

    if (table != SPTM_TABLE_T8110_DART_XNU &&
        table != SPTM_TABLE_T8110_DART_SK &&
        table != SPTM_TABLE_GEN3_DART_XNU &&
        table != SPTM_TABLE_GEN3_DART_SK)
        return;

    /* Endpoint 6 (init) also needs the recovered AppleT8110DART object so
     * Python can import locked live TTBR roots without doing UART-backed
     * object/frame probing. Map/unmap endpoints still stay out of this path. */
    if (endpoint != 4 && endpoint != 5 && endpoint != 6)
        return;

    if (dart_try_candidate(table, endpoint, dart_id, regs[19], 0x19))
        return;

    u64 fp = regs[29];
    for (u32 depth = 0; depth < 16; depth++) {
        u64 saved_fp, saved_lr, candidate;

        if (!is_kernel_va(fp))
            break;
        if (!guest_read64(fp, &saved_fp) || !guest_read64(fp + 8, &saved_lr))
            break;

        if (guest_read64(fp - 8, &candidate) &&
            dart_try_candidate(table, endpoint, dart_id, candidate,
                               0x100000UL | ((u64)depth << 8) | 19))
            return;
        if (guest_read64(fp - 16, &candidate) &&
            dart_try_candidate(table, endpoint, dart_id, candidate,
                               0x100000UL | ((u64)depth << 8) | 20))
            return;
        if (guest_read64(fp - 24, &candidate) &&
            dart_try_candidate(table, endpoint, dart_id, candidate,
                               0x100000UL | ((u64)depth << 8) | 21))
            return;
        if (guest_read64(fp - 32, &candidate) &&
            dart_try_candidate(table, endpoint, dart_id, candidate,
                               0x100000UL | ((u64)depth << 8) | 22))
            return;

        if (saved_fp == fp)
            break;
        fp = saved_fp;
    }

    g_state.dart_obj_cache_misses++;
    g_state.dart_obj_last[0] = table;
    g_state.dart_obj_last[1] = endpoint;
    g_state.dart_obj_last[2] = dart_id;
    g_state.dart_obj_last[3] = 0;
    g_state.dart_obj_last[4] = 0;
    g_state.dart_obj_last[5] = 0;
    g_state.dart_obj_last[6] = 0;
    g_state.dart_obj_last[7] = 0;
}

static inline bool_t dart_c_looks_like_mmio(u64 pa) {
    return !is_kernel_va(pa) &&
           pa >= 0x100000000UL &&
           (pa & (DART_C_PAGE_SIZE - 1)) == 0;
}

static inline u32 dart_c_read32(u64 addr) {
    return *(volatile u32 *)addr;
}

static inline void dart_c_write32(u64 addr, u32 value) {
    *(volatile u32 *)addr = value;
}

static inline u64 dart_c_pte_from_pa(u64 paddr) {
    return (((paddr >> 14) & 0x0fffffffUL) << 10) | 1UL;
}

static inline u64 dart_c_pa_from_pte(u64 pte) {
    return ((pte >> 10) & 0x0fffffffUL) << 14;
}

static inline u32 dart_c_ttbr_from_pa(u64 paddr) {
    return (u32)((((paddr >> 14) << 2) & 0xfffffffcU) | DART_T8110_TTBR_VALID);
}

static inline u64 dart_c_pa_from_ttbr(u32 ttbr) {
    return (u64)((ttbr & 0xfffffffcU) >> 2) << 14;
}

static inline u32 dart_c_idx(u64 dva, u32 level) {
    u64 page = dva >> 14;
    if (level == 0) return (u32)((page >> 33) & 0x7ff);
    if (level == 1) return (u32)((page >> 22) & 0x7ff);
    if (level == 2) return (u32)((page >> 11) & 0x7ff);
    return (u32)(page & 0x7ff);
}

static inline u64 dart_c_effective_dva(struct dart_c_instance *inst, u32 sid,
                                       struct dart_c_sid_state *st, u64 dva) {
    (void)inst;
    (void)sid;
    (void)st;

    /*
     * The firmware validates the full DVA, but a non-FOUR_LEVELS stream starts
     * its TTBR root at the DVA[25:35] table. DVA[36:46] is not part of the page
     * table walk for that mode; root_level encodes that below.
     */
    return dva;
}

static inline u8 dart_c_root_level_from_tcr(u32 tcr) {
    return (tcr & DART_T8110_TCR_FOUR_LEVEL) ? 1 : 2;
}

static inline u32 dart_c_tcr_from_root_level(u8 root_level) {
    u32 tcr = DART_T8110_TCR_TRANSLATE_EN;
    if (root_level <= 1)
        tcr |= DART_T8110_TCR_FOUR_LEVEL;
    return tcr;
}

static inline void dart_c_clean64(u64 addr) {
    clean_pt_range_poc((volatile u64 *)addr, 8);
}

static inline u64 dart_c_leaf_pte(u64 paddr, u64 dva, u64 bytes, u64 bits) {
    u64 start = (dva & (DART_C_PAGE_SIZE - 1)) >> 2;
    u64 end = ((dva & (DART_C_PAGE_SIZE - 1)) + bytes - 1) >> 2;
    if (end > 0xfff)
        end = 0xfff;
    return dart_c_pte_from_pa(paddr) |
           (bits & 0xfUL) |
           (start << 52) |
           (end << 40);
}

static inline u64 dart_c_perm_bits(u64 flags) {
    /*
     * 26.6b2 SPTM no longer uses the older 4-bit reversal here. The valid bit
     * is supplied by dart_c_pte_from_pa(); only prot bits 0/1 contribute.
     */
    return ((flags << 1) & 0x4UL) | ((flags & 1UL) << 3);
}

static inline u64 dart_c_leaf_perm_bits(struct dart_c_instance *inst,
                                        u64 paddr, u64 flags) {
    (void)paddr;

    /*
     * 26.6 SPTM records relaxed-rw-protections and then consults an internal
     * frame-type policy table before changing PTE permission bits. Keep the
     * flag in state, but leave PTE permissions unchanged until that policy is
     * recovered instead of guessing a write-protect set.
     */
    (void)inst->relaxed_rw_protections;
    return dart_c_perm_bits(flags);
}

static inline bool_t dart_c_map_needs_tlbi(struct dart_c_instance *inst,
                                           u64 old_pte, u64 new_pte) {
    if (old_pte == new_pte)
        return 0;
    if (!inst->avoid_tlbi_in_map)
        return 1;
    return (old_pte & 1UL) != 0;
}

static inline u64 dart_c_validate_dva_range(u64 dva, u64 size) {
    if (!size)
        return SPTM_SUCCESS;
    if (size > 0x2000000UL)
        return DART_C_STATUS_VIOLATION;
    if (dva >> 42)
        return DART_C_STATUS_VIOLATION;
    if ((size - 1UL) > (((1UL << 42) - 1UL) - dva))
        return DART_C_STATUS_VIOLATION;

    u64 pages = ((dva & (DART_C_PAGE_SIZE - 1UL)) + size +
                 DART_C_PAGE_SIZE - 1UL) / DART_C_PAGE_SIZE;
    if (pages > 0x800UL)
        return DART_C_STATUS_VIOLATION;
    return SPTM_SUCCESS;
}

static inline struct dart_c_instance *dart_c_get(u64 dart_id) {
    u32 empty = DART_C_MAX_DARTS;

    for (u32 i = 0; i < DART_C_MAX_DARTS; i++) {
        if (g_state.dart.inst[i].used && g_state.dart.inst[i].dart_id == dart_id)
            return &g_state.dart.inst[i];
        if (!g_state.dart.inst[i].used && empty == DART_C_MAX_DARTS)
            empty = i;
    }

    if (empty == DART_C_MAX_DARTS)
        empty = (u32)(dart_id & (DART_C_MAX_DARTS - 1));

    struct dart_c_instance *inst = &g_state.dart.inst[empty];
    for (u32 i = 0; i < sizeof(*inst); i++)
        ((volatile u8 *)inst)[i] = 0;
    inst->dart_id = dart_id;
    inst->used = 1;
    return inst;
}

static inline struct dart_c_sid_state *dart_c_sid(struct dart_c_instance *inst,
                                                  u64 sid) {
    if (sid >= DART_C_MAX_SIDS)
        return (struct dart_c_sid_state *)0;
    struct dart_c_sid_state *st = &inst->sid[sid];
    st->valid = 1;
    return st;
}

static inline struct dart_c_sid_state *
dart_c_sid_lookup(struct dart_c_instance *inst, u64 sid) {
    if (sid >= DART_C_MAX_SIDS)
        return (struct dart_c_sid_state *)0;
    struct dart_c_sid_state *st = &inst->sid[sid];
    return st->valid ? st : (struct dart_c_sid_state *)0;
}

static inline bool_t dart_c_sid_exclave(struct dart_c_sid_state *st) {
    return st && st->exclave;
}

static inline bool_t dart_c_sid_translates(struct dart_c_sid_state *st) {
    return st && ((st->tcr & DART_T8110_TCR_TRANSLATE_EN) != 0);
}

static inline u32 dart_c_num_streams(u64 base) {
    u32 num = dart_c_read32(base + DART_T8110_PARAMS4) & 0x1ffU;
    if (num == 0 || num > DART_C_MAX_STREAMS)
        num = DART_C_MAX_STREAMS;
    return num;
}

static inline u32 dart_c_stream_words(u32 num) {
    return (num + 31U) >> 5;
}

static inline u64 dart_c_first_mmio_base(struct dart_c_instance *inst) {
    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        u64 base = inst->base_pa[i];
        if (dart_c_looks_like_mmio(base))
            return base;
    }
    return 0;
}

static inline u64 dart_c_pack_hw_sid_regs(struct dart_c_instance *inst,
                                          u32 sid) {
    u64 base = dart_c_first_mmio_base(inst);
    if (!base || sid >= DART_C_MAX_SIDS)
        return 0;
    return ((u64)dart_c_read32(base + DART_T8110_TCR + sid * 4) << 32) |
           dart_c_read32(base + DART_T8110_TTBR + sid * 4);
}

static inline u64 dart_c_pack_hw_stream_error(struct dart_c_instance *inst,
                                              u32 sid) {
    u64 base = dart_c_first_mmio_base(inst);
    if (!base)
        return 0;
    u32 stream_word = 0;
    u32 num = dart_c_num_streams(base);
    if (sid < num) {
        stream_word = dart_c_read32(base + DART_T8110_ENABLE_STREAMS +
                                    ((sid >> 5) * 4));
    }
    return ((u64)dart_c_read32(base + DART_T8110_ERROR) << 32) | stream_word;
}

static inline bool_t dart_c_base_needs_new_tlb_cmd(u64 base) {
    return (dart_c_read32(base + DART_T8110_PARAMS3) & 0xffffU) >= 0x0202U;
}

static inline u64 dart_c_tlb_raw_command(u64 base, u32 command) {
    dart_c_write32(base + DART_T8110_TLB_CMD, command);
    for (u32 i = 0; i < 100; i++) {
        u32 status = dart_c_read32(base + DART_T8110_TLB_CMD);
        if (!(status & DART_T8110_TLB_CMD_BUSY))
            return ((u64)status << 32);
    }
    return DART_C_ERR_TIMEOUT | ((u64)dart_c_read32(base + DART_T8110_TLB_CMD) << 32);
}

static inline u64 dart_c_tlb_command(u64 base, u32 op, u32 sid) {
    u32 command = ((op & 7U) << 8) | (sid & 0xffU);

    if (op == DART_T8110_TLB_OP_FLUSH_SID &&
        dart_c_base_needs_new_tlb_cmd(base))
        command |= DART_T8110_TLB_CMD_NEW_DART;

    return dart_c_tlb_raw_command(base, command);
}

static inline u64 dart_c_flush_sid_base(u64 base, u32 sid) {
    return dart_c_tlb_command(base, DART_T8110_TLB_OP_FLUSH_SID, sid);
}

static inline u64 dart_c_flush_sid_range_base(u64 base, u32 sid,
                                              u64 start_dva, u64 end_dva) {
    u32 start_page = (u32)((start_dva >> 14) & 0x0fffffffU);
    u32 end_page = (u32)((end_dva >> 14) & 0x0fffffffU);
    u32 command = DART_T8110_TLB_CMD_VA_RANGE |
                  DART_T8110_TLB_CMD_STT_FLUSH |
                  ((DART_T8110_TLB_OP_FLUSH_SID & 7U) << 8) |
                  (sid & 0xffU);

    if (dart_c_base_needs_new_tlb_cmd(base))
        command |= DART_T8110_TLB_CMD_NEW_DART;

    dart_c_write32(base + DART_T8110_TLB_START_DVA_PAGE, start_page << 2);
    __asm__ volatile("dsb sy" ::: "memory");
    dart_c_write32(base + DART_T8110_TLB_END_DVA_PAGE, end_page << 2);
    __asm__ volatile("dsb sy" ::: "memory");
    return dart_c_tlb_raw_command(base, command);
}

static inline void dart_c_clear_errors_base(u64 base) {
    u32 num = dart_c_num_streams(base);
    u32 words = dart_c_stream_words(num);
    u32 error = dart_c_read32(base + DART_T8110_ERROR);
    dart_c_write32(base + DART_T8110_ERROR, error);
    for (u32 i = 0; i < words; i++)
        dart_c_write32(base + DART_T8110_ERROR_STREAMS + i * 4, 0xffffffffU);
    dart_c_write32(base + DART_T8110_ERROR_MASK, 0xffffffffU);
}

static inline u32 dart_c_import_live_base(struct dart_c_instance *inst, u64 base,
                                          bool_t *preserve_out) {
    u32 num = dart_c_num_streams(base);
    if (num > DART_C_MAX_SIDS)
        num = DART_C_MAX_SIDS;

    u32 protect = dart_c_read32(base + DART_T8110_PROTECT);
    u32 protect_lock = dart_c_read32(base + DART_T8110_PROTECT_LOCK);
    bool_t preserve = ((protect | protect_lock) & DART_T8110_PROTECT_TTBR_TCR) ? 1 : 0;
    u32 enable_words[(DART_C_MAX_STREAMS + 31U) >> 5];
    u32 words = dart_c_stream_words(num);
    if (words > ((DART_C_MAX_STREAMS + 31U) >> 5))
        words = ((DART_C_MAX_STREAMS + 31U) >> 5);

    for (u32 i = 0; i < words; i++)
        enable_words[i] = dart_c_read32(base + DART_T8110_ENABLE_STREAMS + i * 4);

    for (u32 sid = 0; sid < num; sid++) {
        u32 tcr = dart_c_read32(base + DART_T8110_TCR + sid * 4);
        u32 ttbr = dart_c_read32(base + DART_T8110_TTBR + sid * 4);
        if (ttbr & DART_T8110_TTBR_VALID)
            preserve = 1;
        if (tcr & DART_T8110_TCR_REMAP_EN)
            preserve = 1;
        if ((tcr & DART_T8110_TCR_TRANSLATE_EN) && ttbr)
            preserve = 1;
    }

    *preserve_out = preserve;
    if (!preserve)
        return 0;

    inst->locked = 1;
    u32 imported = 0;
    for (u32 sid = 0; sid < num; sid++) {
        u32 tcr = dart_c_read32(base + DART_T8110_TCR + sid * 4);
        u32 ttbr = dart_c_read32(base + DART_T8110_TTBR + sid * 4);
        u32 word = (sid >> 5) < words ? enable_words[sid >> 5] : 0;
        u8 stream_enabled = (word & (1U << (sid & 31))) ? 1 : 0;
        if (!tcr && !ttbr && !stream_enabled)
            continue;
        if ((tcr & DART_T8110_TCR_TRANSLATE_EN) &&
            !(ttbr & DART_T8110_TTBR_VALID) && !ttbr) {
            /*
             * Several T8110-class DART register files contain non-reset-looking
             * stale values in unused SID slots at raw boot. Treating TE with a
             * non-valid TTBR as live state later replays a translated stream
             * with no root, which is not a coherent DART configuration.
             */
            if (!stream_enabled)
                continue;
        }

        struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
        if (dart_c_sid_exclave(st)) {
            if (stream_enabled)
                st->stream_enabled = 1;
            imported++;
            continue;
        }
        if (st && (st->tcr & (DART_T8110_TCR_REMAP_EN |
                              DART_T8110_TCR_BYPASS_DART |
                              DART_T8110_TCR_BYPASS_DAPF))) {
            imported++;
            continue;
        }
        if (st && st->root_valid && !(ttbr & DART_T8110_TTBR_VALID)) {
            if (stream_enabled)
                st->stream_enabled = 1;
            imported++;
            continue;
        }
        st = dart_c_sid(inst, sid);
        if (!st)
            continue;
        st->tcr = tcr;
        st->ttbr = ttbr;
        /*
         * SPTM keeps ADT initial streams as state and replays them during
         * finalize. A pre-finalize ENABLE_STREAMS read may still be clear, so
         * live import may set this bit but must not erase seeded state.
         */
        if (stream_enabled)
            st->stream_enabled = 1;
        st->translation_enabled = (tcr & DART_T8110_TCR_TRANSLATE_EN) ? 1 : 0;
        st->root_level = dart_c_root_level_from_tcr(tcr);
        if (ttbr & DART_T8110_TTBR_VALID) {
            st->root_valid = 1;
            st->root_pt_pa = dart_c_pa_from_ttbr(ttbr);
            st->raw_replay = 0;
        } else {
            st->root_valid = 0;
            st->root_pt_pa = 0;
            st->raw_replay =
                ((tcr & DART_T8110_TCR_TRANSLATE_EN) && ttbr) ? 1 : 0;
        }
        imported++;
    }

    inst->last[10] = imported;
    inst->last[11] = num;
    inst->last[12] = protect;
    inst->last[13] = protect_lock;
    g_state.dart.last[10] = imported;
    g_state.dart.last[11] = num;
    g_state.dart.last[12] = protect;
    g_state.dart.last[13] = protect_lock;
    return imported;
}

static inline bool_t dart_c_has_seeded_live_sid(struct dart_c_instance *inst) {
    for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++) {
        struct dart_c_sid_state *st = &inst->sid[sid];
        if (!st->valid)
            continue;
        if (st->ttbr || st->root_valid || st->stream_enabled)
            return 1;
        if (st->tcr && !(st->tcr & DART_T8110_TCR_REMAP_EN))
            return 1;
    }
    return 0;
}

static inline void dart_c_for_each_base_flush_sid(struct dart_c_instance *inst,
                                                  u32 sid) {
    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        if (dart_c_looks_like_mmio(inst->base_pa[i]))
            dart_c_flush_sid_base(inst->base_pa[i], sid);
    }
}

static inline void dart_c_for_each_base_flush_sid_range(struct dart_c_instance *inst,
                                                        u32 sid,
                                                        u64 start_dva,
                                                        u64 end_dva) {
    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        if (dart_c_looks_like_mmio(inst->base_pa[i]))
            dart_c_flush_sid_range_base(inst->base_pa[i], sid, start_dva,
                                        end_dva);
    }
}

static inline void dart_c_for_each_base_flush_map_change(struct dart_c_instance *inst,
                                                         u32 sid,
                                                         u64 start_dva,
                                                         u64 end_dva) {
    if (inst->flush_by_dva)
        dart_c_for_each_base_flush_sid_range(inst, sid, start_dva, end_dva);
    else
        dart_c_for_each_base_flush_sid(inst, sid);
}

static inline void dart_c_flush_known_sids_base(struct dart_c_instance *inst,
                                                u64 base) {
    u32 touched[DART_C_MAX_SIDS / 32];

    if (!dart_c_looks_like_mmio(base))
        return;

    for (u32 i = 0; i < DART_C_MAX_SIDS / 32; i++)
        touched[i] = 0;

    u32 num = dart_c_num_streams(base);
    if (num > DART_C_MAX_SIDS)
        num = DART_C_MAX_SIDS;
    u32 words = dart_c_stream_words(num);
    if (words > DART_C_MAX_SIDS / 32)
        words = DART_C_MAX_SIDS / 32;

    for (u32 word = 0; word < words; word++) {
        u32 enabled = dart_c_read32(base + DART_T8110_ENABLE_STREAMS +
                                    (u64)word * 4UL);
        touched[word] |= enabled;
    }

    for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++) {
        struct dart_c_sid_state *st = &inst->sid[sid];
        if (!st->valid && !st->root_valid && !st->stream_enabled &&
            !st->ttbr)
            continue;
        touched[sid >> 5] |= 1U << (sid & 31);
    }

    for (u32 sid = 0; sid < num; sid++)
        if (touched[sid >> 5] & (1U << (sid & 31)))
            dart_c_flush_sid_base(base, sid);
}

static inline void dart_c_add_base(struct dart_c_instance *inst, u64 base) {
    if (!dart_c_looks_like_mmio(base))
        return;
    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        if (inst->base_pa[i] == base)
            return;
    }
    if (inst->base_count < DART_C_MAX_BASES) {
        inst->base_pa[inst->base_count++] = base;
        /*
         * Real SPTM maps through an already-recovered DART object and flushes
         * after leaf updates. If our object recovery learns the MMIO base after
         * a software PTE update, catch the hardware up once the base is known.
         */
        dart_c_flush_known_sids_base(inst, base);
    }
}

static inline u64 dart_c_range_sid(struct dart_c_identity_range *range) {
    return range->sid & DART_C_RANGE_SID_MASK;
}

static inline u64 dart_c_range_flags(struct dart_c_identity_range *range) {
    return range->sid & ~DART_C_RANGE_SID_MASK;
}

static inline bool_t dart_c_range_matches_inst(struct dart_c_instance *inst,
                                               struct dart_c_identity_range *range) {
    for (u32 bi = 0; bi < inst->base_count && bi < DART_C_MAX_BASES; bi++) {
        if (inst->base_pa[bi] == range->base_pa)
            return 1;
    }
    return 0;
}

static inline bool_t dart_c_restore_boot_premap_page(struct dart_c_instance *inst,
                                                     u32 sid, u64 dva,
                                                     u64 slot) {
    u64 page = dva & ~(DART_C_PAGE_SIZE - 1UL);

    for (u32 ri = 0; ri < g_state.dart.identity_count &&
                     ri < DART_C_MAX_IDENTITY_RANGES; ri++) {
        struct dart_c_identity_range *range = &g_state.dart.identity[ri];
        u64 flags = dart_c_range_flags(range);
        u64 start, end;

        if (!(flags & DART_C_RANGE_FLAG_BOOT_PREMAP) ||
            (flags & DART_C_RANGE_FLAG_REMAP) ||
            !dart_c_range_matches_inst(inst, range) ||
            dart_c_range_sid(range) != sid ||
            range->end <= range->start)
            continue;

        start = range->start & ~(DART_C_PAGE_SIZE - 1UL);
        end = (range->end + DART_C_PAGE_SIZE - 1UL) &
              ~(DART_C_PAGE_SIZE - 1UL);
        if (page < start || page >= end)
            continue;

        *(volatile u64 *)slot =
            dart_c_leaf_pte(page, page, DART_C_PAGE_SIZE, 0);
        dart_c_clean64(slot);
        return 1;
    }

    return 0;
}

static inline void dart_c_program_sid_tcr_ttbr(struct dart_c_instance *inst,
                                               u32 sid, u32 tcr, u32 ttbr) {
    u32 writes = 0;
    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        u64 base = inst->base_pa[i];
        if (!dart_c_looks_like_mmio(base))
            continue;
        u64 tcr_reg = base + DART_T8110_TCR + sid * 4;
        u64 ttbr_reg = base + DART_T8110_TTBR + sid * 4;
        if (dart_c_read32(tcr_reg) != tcr) {
            dart_c_write32(tcr_reg, tcr);
            writes++;
        }
        if (dart_c_read32(ttbr_reg) != ttbr) {
            dart_c_write32(ttbr_reg, ttbr);
            writes++;
        }
    }
    if (writes) {
        __asm__ volatile("dsb sy" ::: "memory");
        dart_c_for_each_base_flush_sid(inst, sid);
    }
}

static inline void dart_c_configure_sid_remap(struct dart_c_instance *inst,
                                              u32 sid, u32 target) {
    struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
    if (!st)
        return;

    st->tcr = DART_T8110_TCR_REMAP_EN | DART_T8110_TCR_REMAP_TARGET(target);
    st->ttbr = 0;
    st->root_pt_pa = 0;
    st->root_valid = 0;
    st->root_level = 2;
    st->translation_enabled = 0;
    st->raw_replay = 0;
    dart_c_program_sid_tcr_ttbr(inst, sid, st->tcr, 0);
}

static inline u64 dart_c_walk_leaf_slot(struct dart_c_instance *inst, u32 sid,
                                        struct dart_c_sid_state *st, u64 dva,
                                        u64 *slot_out);
static inline u64 dart_c_ensure_leaf_table(struct dart_c_instance *inst, u32 sid,
                                           struct dart_c_sid_state *st, u64 dva,
                                           u64 *table_out, u64 *allocs_out,
                                           u64 *imports_out);

static inline bool_t dart_c_import_live_sid(struct dart_c_instance *inst, u32 sid) {
    if (sid >= DART_C_MAX_SIDS)
        return 0;

    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        u64 base = inst->base_pa[i];
        if (!dart_c_looks_like_mmio(base))
            continue;

        u32 tcr = dart_c_read32(base + DART_T8110_TCR + sid * 4);
        u32 ttbr = dart_c_read32(base + DART_T8110_TTBR + sid * 4);
        if (!(ttbr & DART_T8110_TTBR_VALID) &&
            !(ttbr && (tcr & DART_T8110_TCR_TRANSLATE_EN)))
            continue;

        struct dart_c_sid_state *st = dart_c_sid(inst, sid);
        if (!st)
            return 0;

        u32 enable_word = dart_c_read32(base + DART_T8110_ENABLE_STREAMS +
                                        ((sid >> 5) * 4));
        struct dart_c_sid_state *existing = dart_c_sid_lookup(inst, sid);
        if (dart_c_sid_exclave(existing)) {
            if (enable_word & (1U << (sid & 31)))
                existing->stream_enabled = 1;
            return 1;
        }

        st->tcr = tcr;
        st->ttbr = ttbr;
        st->valid = 1;
        st->root_level = dart_c_root_level_from_tcr(tcr);
        if (enable_word & (1U << (sid & 31)))
            st->stream_enabled = 1;
        st->translation_enabled = (tcr & DART_T8110_TCR_TRANSLATE_EN) ? 1 : 0;
        if (ttbr & DART_T8110_TTBR_VALID) {
            st->root_valid = 1;
            st->root_pt_pa = dart_c_pa_from_ttbr(ttbr);
            st->raw_replay = 0;
        } else {
            st->root_valid = 0;
            st->root_pt_pa = 0;
            st->raw_replay =
                ((tcr & DART_T8110_TCR_TRANSLATE_EN) && ttbr) ? 1 : 0;
        }
        inst->locked = 1;
        return 1;
    }

    return 0;
}

static inline bool_t dart_c_pt_region_page_referenced(u64 start, u64 end,
                                                       u64 pa) {
    start &= ~(DART_C_PAGE_SIZE - 1UL);
    end = (end + DART_C_PAGE_SIZE - 1UL) & ~(DART_C_PAGE_SIZE - 1UL);
    for (u64 table = start; table < end; table += DART_C_PAGE_SIZE) {
        volatile u64 *entries = (volatile u64 *)table;
        for (u32 i = 0; i < DART_C_TT_ENTRIES; i++) {
            u64 pte = entries[i];
            if ((pte & 1UL) && dart_c_pa_from_pte(pte) == pa)
                return 1;
        }
    }
    return 0;
}

static inline u64 dart_c_alloc_pt_region_table(struct dart_c_instance *inst,
                                               u32 sid,
                                               struct dart_c_sid_state *st) {
    if (!inst || !st)
        return 0;

    for (u32 ri = 0; ri < g_state.dart.identity_count &&
                     ri < DART_C_MAX_IDENTITY_RANGES; ri++) {
        struct dart_c_identity_range *range = &g_state.dart.identity[ri];
        u64 flags = dart_c_range_flags(range);
        if (!(flags & DART_C_RANGE_FLAG_PT_REGION) ||
            !dart_c_range_matches_inst(inst, range) ||
            dart_c_range_sid(range) != sid ||
            range->end <= range->start)
            continue;

        u64 scan_start = st->root_pt_pa;
        if (scan_start < range->start || scan_start >= range->end)
            scan_start = range->start;
        scan_start &= ~(DART_C_PAGE_SIZE - 1UL);

        u64 cur = (range->start + DART_C_PAGE_SIZE - 1UL) &
                  ~(DART_C_PAGE_SIZE - 1UL);
        u64 end = range->end & ~(DART_C_PAGE_SIZE - 1UL);
        while (cur < end) {
            if (cur == st->root_pt_pa ||
                dart_c_pt_region_page_referenced(scan_start, range->end, cur)) {
                cur += DART_C_PAGE_SIZE;
                continue;
            }

            volatile u64 *entries = (volatile u64 *)cur;
            for (u32 i = 0; i < DART_C_TT_ENTRIES; i++)
                entries[i] = 0;
            clean_range_poc((void *)cur, DART_C_PAGE_SIZE);
            sptm_coproc_cache_maint_range((const void *)cur, DART_C_PAGE_SIZE);
            g_state.dart.pt_pool_allocs++;
            return cur;
        }
    }

    g_state.dart.pt_pool_failures++;
    return 0;
}

static inline bool_t dart_c_pa_in_pt_region(struct dart_c_instance *inst,
                                            u32 sid, u64 pa) {
    pa &= ~(DART_C_PAGE_SIZE - 1UL);
    for (u32 ri = 0; ri < g_state.dart.identity_count &&
                     ri < DART_C_MAX_IDENTITY_RANGES; ri++) {
        struct dart_c_identity_range *range = &g_state.dart.identity[ri];
        u64 flags = dart_c_range_flags(range);
        if (!(flags & DART_C_RANGE_FLAG_PT_REGION) ||
            !dart_c_range_matches_inst(inst, range) ||
            dart_c_range_sid(range) != sid)
            continue;
        if (range->start <= pa && pa < range->end)
            return 1;
    }
    return 0;
}

static inline u64 dart_c_shadow_child_table_if_needed(
    struct dart_c_instance *inst, u32 sid, struct dart_c_sid_state *st,
    u64 pt_pa) {
    if (!inst || !st || !st->root_valid || !st->root_pt_pa)
        return pt_pa;

    if (dart_c_pa_in_pt_region(inst, sid, pt_pa))
        return pt_pa;

    u64 shadow = dart_c_alloc_pt_region_table(inst, sid, st);
    if (!shadow)
        return pt_pa;

    g_state.dart.last[8] = inst->dart_id;
    g_state.dart.last[9] = sid;
    g_state.dart.last[10] = pt_pa;
    g_state.dart.last[11] = shadow;
    g_state.dart.last[12] = 0x53484457UL; /* "SHDW" */
    return shadow;
}

static inline u32 dart_c_map_identity_range_page(struct dart_c_instance *inst,
                                                 u32 sid, u64 dva, u64 flags) {
    struct dart_c_sid_state *st = dart_c_sid(inst, sid);
    u64 table, slot;
    (void)flags;

    if (!st || !st->root_valid || !st->root_pt_pa)
        return 0;

    dva &= ~(DART_C_PAGE_SIZE - 1);

    if (dart_c_ensure_leaf_table(inst, sid, st, dva, &table, 0, 0))
        return 0;

    slot = table + (u64)dart_c_idx(dva, 3) * 8UL;
    *(volatile u64 *)slot = dart_c_leaf_pte(dva, dva, DART_C_PAGE_SIZE, 0);
    dart_c_clean64(slot);

    inst->last[8] = 0x44415046UL; /* "DAPF" */
    inst->last[9] = sid;
    inst->last[10] = dva;
    inst->last[11] = slot;
    inst->last[12] = 0;
    inst->last[13] = 0;
    g_state.dart.last[8] = inst->dart_id;
    g_state.dart.last[9] = sid;
    g_state.dart.last[10] = dva;
    g_state.dart.last[11] = slot;
    return 1;
}

static inline u32 dart_c_apply_identity_ranges(struct dart_c_instance *inst) {
    u32 pages = 0;

    for (u32 ri = 0; ri < g_state.dart.identity_count &&
                     ri < DART_C_MAX_IDENTITY_RANGES; ri++) {
        struct dart_c_identity_range *range = &g_state.dart.identity[ri];
        u64 flags = dart_c_range_flags(range);
        u64 sid = dart_c_range_sid(range);
        u64 flush_start = 0;
        u64 flush_end = 0;
        if (!(flags & DART_C_RANGE_FLAG_BOOT_PREMAP) ||
            (flags & DART_C_RANGE_FLAG_REMAP) ||
            !dart_c_range_matches_inst(inst, range) ||
            sid >= DART_C_MAX_SIDS ||
            range->end <= range->start)
            continue;

        u64 start = range->start & ~(DART_C_PAGE_SIZE - 1);
        u64 end = (range->end + DART_C_PAGE_SIZE - 1) &
                  ~(DART_C_PAGE_SIZE - 1);
        for (u64 dva = start; dva < end && pages < 4096; dva += DART_C_PAGE_SIZE) {
            if (dart_c_map_identity_range_page(inst, (u32)sid, dva, flags)) {
                if (!flush_end)
                    flush_start = dva;
                flush_end = dva + DART_C_PAGE_SIZE;
                pages++;
            }
        }

        if (flush_end > flush_start) {
            /*
             * These leaves are written by the emulator into persistent
             * bootloader-owned DART roots. Real t8110dart_map flushes hardware
             * by DVA range immediately after leaf updates; do the same for
             * bootstrap leaves so stale negative display translations cannot
             * survive until scanout.
             */
            dart_c_for_each_base_flush_map_change(inst, (u32)sid,
                                                  flush_start,
                                                  flush_end - 1UL);
        }
    }

    if (pages) {
        inst->last[14] = pages;
        g_state.dart.last[12] = pages;
        g_state.dart.last[13] = g_state.dart.identity_count;
    }
    return pages;
}

static inline u32 dart_c_apply_bootstrap_remaps(struct dart_c_instance *inst) {
    u32 count = 0;

    for (u32 ri = 0; ri < g_state.dart.identity_count &&
                     ri < DART_C_MAX_IDENTITY_RANGES; ri++) {
        struct dart_c_identity_range *range = &g_state.dart.identity[ri];
        if (!(dart_c_range_flags(range) & DART_C_RANGE_FLAG_REMAP))
            continue;
        if (!dart_c_range_matches_inst(inst, range))
            continue;

        u32 sid = (u32)dart_c_range_sid(range);
        u32 target = (u32)(range->start & DART_C_RANGE_SID_MASK);
        if (sid >= DART_C_MAX_SIDS || target >= DART_C_MAX_SIDS)
            continue;
        dart_c_configure_sid_remap(inst, sid, target);
        count++;
    }

    if (count) {
        inst->last[13] = 0x524d5444UL; /* "DTMR" */
        inst->last[14] = count;
        g_state.dart.last[13] = inst->dart_id;
        g_state.dart.last[14] = count;
    }
    return count;
}

static inline bool_t dart_c_import_object_details(struct dart_c_instance *inst,
                                                  u64 obj) {
    u32 gapf_count, inst_count;
    u64 state;

    if (!dart_validate_xnu_object(obj, &gapf_count, &inst_count, &state))
        return 0;

    inst->obj_va = obj;
    inst->state_va = state;
    for (u32 i = 0; i < inst_count && i < 16; i++) {
        u64 mmio_va, mmio_pa;
        if (!guest_read64(state + 0x20UL + (u64)i * 0x70UL, &mmio_va))
            continue;
        if (is_kernel_va(mmio_va) && guest_va_to_pa(mmio_va, 1, &mmio_pa))
            dart_c_add_base(inst, mmio_pa);
        else if (dart_c_looks_like_mmio(mmio_va))
            dart_c_add_base(inst, mmio_va);
    }
    return 1;
}

static inline void dart_c_import_cached_bases(struct dart_c_instance *inst) {
    if (g_state.dart_obj_last[2] == inst->dart_id &&
        g_state.dart_obj_last[3] != 0) {
        inst->obj_va = g_state.dart_obj_last[3];
        inst->state_va = g_state.dart_obj_last[7];
        for (u32 i = 0; i < 16; i++)
            dart_c_add_base(inst, g_state.dart_obj_last_base_pa[i]);
        return;
    }

    /*
     * Endpoint stack layouts differ enough that a later recovery attempt can
     * miss even though an earlier endpoint already validated this DART object.
     * Real SPTM keeps a per-DART state object; mirror that by falling back to
     * the per-ID cache instead of letting a transient miss erase live state.
     */
    for (u32 i = 0; i < DART_OBJ_CACHE_SLOTS; i++) {
        if (g_state.dart_obj_cache_id[i] == inst->dart_id &&
            g_state.dart_obj_cache_va[i] != 0 &&
            dart_c_import_object_details(inst, g_state.dart_obj_cache_va[i]))
            return;
    }
}

static inline u64 dart_c_walk_to_table(struct dart_c_instance *inst, u32 sid,
                                       struct dart_c_sid_state *st, u64 dva,
                                       u32 table_level, u64 *table_out,
                                       u32 *idx_out) {
    if (!st || !st->root_valid || !st->root_pt_pa)
        return DART_C_ERR_NO_TTBR;

    dva = dart_c_effective_dva(inst, sid, st, dva);

    if (table_level < st->root_level || table_level > 3)
        return DART_C_ERR_NO_TABLE;
    if (table_level == st->root_level) {
        *table_out = st->root_pt_pa;
        *idx_out = dart_c_idx(dva, table_level);
        return 0;
    }

    u64 table = st->root_pt_pa;
    for (u32 level = st->root_level; level < table_level; level++) {
        u32 idx = dart_c_idx(dva, level);
        u64 pte = *(volatile u64 *)(table + (u64)idx * 8UL);
        if (!(pte & 1UL))
            return DART_C_ERR_NO_TABLE;
        table = dart_c_pa_from_pte(pte);
    }
    *table_out = table;
    *idx_out = dart_c_idx(dva, table_level);
    return 0;
}

static inline u64 dart_c_walk_leaf_slot(struct dart_c_instance *inst, u32 sid,
                                        struct dart_c_sid_state *st, u64 dva,
                                        u64 *slot_out) {
    u64 table;
    u32 idx;
    u64 rc = dart_c_walk_to_table(inst, sid, st, dva, 3, &table, &idx);
    if (rc)
        return rc;
    *slot_out = table + (u64)idx * 8UL;
    return 0;
}

static inline u64 dart_c_ensure_leaf_table(struct dart_c_instance *inst, u32 sid,
                                           struct dart_c_sid_state *st, u64 dva,
                                           u64 *table_out, u64 *allocs_out,
                                           u64 *imports_out) {
    if (!st || !st->root_valid || !st->root_pt_pa)
        return DART_C_ERR_NO_TTBR;

    dva = dart_c_effective_dva(inst, sid, st, dva);

    u64 table = st->root_pt_pa;
    u64 allocs = 0;
    u64 imports = 0;

    for (u32 level = st->root_level; level < 3; level++) {
        u32 idx = dart_c_idx(dva, level);
        u64 slot = table + (u64)idx * 8UL;
        u64 pte = *(volatile u64 *)slot;
        if (pte & 1UL) {
            table = dart_c_pa_from_pte(pte);
            imports++;
            continue;
        }

        u64 child = dart_c_alloc_pt_region_table(inst, sid, st);
        if (!child)
            return DART_C_ERR_NO_TABLE;
        *(volatile u64 *)slot = dart_c_pte_from_pa(child);
        dart_c_clean64(slot);
        table = child;
        allocs++;
    }

    *table_out = table;
    if (allocs_out)
        *allocs_out = allocs;
    if (imports_out)
        *imports_out = imports;
    return 0;
}

static inline void dart_c_snapshot_leaf(struct dart_c_instance *inst, u64 sid,
                                        u64 dva, u64 *slot_out,
                                        u64 *pte_out) {
    *slot_out = 0;
    *pte_out = 0;
    struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
    if (!st)
        return;
    u64 slot;
    if (dart_c_walk_leaf_slot(inst, (u32)sid, st, dva, &slot))
        return;
    *slot_out = slot;
    *pte_out = *(volatile u64 *)slot;
}

static inline void dart_c_record_recent(struct dart_c_instance *inst,
                                        u32 table, u32 endpoint, u64 *regs,
                                        u64 rc, u64 sid, u64 before_slot,
                                        u64 before_pte, u64 after_slot,
                                        u64 after_pte) {
    u64 seq = ++g_state.dart.recent_idx;
    struct dart_c_recent_event *ev =
        &g_state.dart.recent[(seq - 1) & (DART_C_RECENT_SLOTS - 1)];

    ev->seq = seq;
    ev->table = table;
    ev->endpoint = endpoint;
    ev->dart_id = inst ? inst->dart_id : 0;
    ev->sid = sid;
    for (u32 i = 0; i < 6; i++)
        ev->regs[i] = regs[i];
    ev->before_slot = before_slot;
    ev->before_pte = before_pte;
    ev->after_slot = after_slot;
    ev->after_pte = after_pte;
    ev->rc = rc;
}

#define DART_C_SID0_TRACE_DVA         0x300704048UL
#define DART_C_SID0_REASON_DIRECT     (1UL << 0)
#define DART_C_SID0_REASON_GLOBAL     (1UL << 2)
#define DART_C_SID0_REASON_FLUSH      (1UL << 3)

static inline u64 dart_c_sid0_pack_tcr_ttbr(struct dart_c_sid_state *st) {
    if (!st)
        return 0;
    return ((u64)st->ttbr << 32) | st->tcr;
}

static inline u64 dart_c_sid0_pack_root_flags(struct dart_c_sid_state *st) {
    if (!st)
        return 0;
    return (st->root_pt_pa & 0x00ffffffffffffffUL) |
           ((u64)(st->valid & 1U) << 56) |
           ((u64)(st->root_valid & 1U) << 57) |
           ((u64)(st->root_level & 3U) << 58) |
           ((u64)(st->stream_enabled & 1U) << 60) |
           ((u64)(dart_c_sid_translates(st) & 1U) << 61) |
           ((u64)(st->raw_replay & 1U) << 62) |
           ((u64)(st->initial_stream_enabled & 1U) << 63);
}

static inline void dart_c_snapshot_sid0(struct dart_c_instance *inst, u64 dva,
                                        u64 *tcr_ttbr_out,
                                        u64 *root_flags_out,
                                        u64 *slot_out, u64 *pte_out) {
    struct dart_c_sid_state *st = dart_c_sid_lookup(inst, 0);
    *tcr_ttbr_out = dart_c_sid0_pack_tcr_ttbr(st);
    *root_flags_out = dart_c_sid0_pack_root_flags(st);
    dart_c_snapshot_leaf(inst, 0, dva, slot_out, pte_out);
}

static inline bool_t dart_c_sid0_trace_reason(struct dart_c_instance *inst,
                                              bool_t xnu_table,
                                              bool_t sk_table,
                                              u32 endpoint, u64 *regs,
                                              u64 *reason_out) {
    u64 reason = 0;
    (void)inst;

    if (sk_table) {
        if (endpoint == 0 && regs[1] == 0)
            reason = DART_C_SID0_REASON_DIRECT;
        if (endpoint == 1 || endpoint == 2 || endpoint == 3)
            reason = DART_C_SID0_REASON_GLOBAL;
    } else if (xnu_table) {
        switch (endpoint) {
            case 0:
            case 1:
            case 8:
            case 9:
            case 13:
                if (regs[1] == 0)
                    reason = DART_C_SID0_REASON_DIRECT;
                break;
            case 2:
            case 3:
                if (regs[1] == 0)
                    reason = DART_C_SID0_REASON_DIRECT;
                break;
            case 4:
            case 5:
            case 6:
                reason = DART_C_SID0_REASON_GLOBAL;
                break;
            case 7:
                if (regs[1] == 0)
                    reason = DART_C_SID0_REASON_FLUSH;
                break;
            case 11:
            case 16:
                reason = DART_C_SID0_REASON_FLUSH;
                break;
            default:
                break;
        }
    }

    *reason_out = reason;
    return reason != 0;
}

static inline void dart_c_record_sid0_trace(struct dart_c_instance *inst,
                                            u32 table, u32 endpoint, u64 *regs,
                                            u64 rc, u64 reason,
                                            u64 before_tcr_ttbr,
                                            u64 before_root_flags,
                                            u64 before_pte,
                                            u64 after_tcr_ttbr,
                                            u64 after_root_flags,
                                            u64 after_pte) {
    u64 seq = ++g_state.dart.sid0_trace_idx;
    struct dart_c_sid0_event *ev =
        &g_state.dart.sid0_trace[(seq - 1) & (DART_C_SID0_TRACE_SLOTS - 1)];

    ev->seq = seq;
    ev->meta = ((u64)(table & 0xffffU)) |
               ((u64)(endpoint & 0xffffU) << 16) |
               ((u64)((inst ? inst->dart_id : 0) & 0xffffU) << 32) |
               ((u64)(reason & 0xffffU) << 48);
    for (u32 i = 0; i < 4; i++)
        ev->regs[i] = regs[i];
    ev->before_tcr_ttbr = before_tcr_ttbr;
    ev->before_root_flags = before_root_flags;
    ev->before_pte = before_pte;
    ev->after_tcr_ttbr = after_tcr_ttbr;
    ev->after_root_flags = after_root_flags;
    ev->after_pte = after_pte;
    ev->rc = rc;
}

static inline u64 dart_c_ep0_install_table(struct dart_c_instance *inst, u64 *regs) {
    u64 sid = regs[1];
    u64 dva = regs[2];
    u32 level = (u32)regs[3];
    u64 pt_pa = regs[4];
    struct dart_c_sid_state *st = dart_c_sid(inst, sid);
    if (!st || (pt_pa & (DART_C_PAGE_SIZE - 1)) || level > 2)
        return DART_C_STATUS_VIOLATION;
    if (dart_c_sid_exclave(st))
        return DART_C_STATUS_VIOLATION;

    /*
     * Firmware map_table uses level 0 as the root install for FOUR_LEVELS
     * streams and level 1 as the root install for normal streams. Once a
     * level-0 root is installed, later level-1 and level-2 requests install
     * child tables below that root; they must not replace it.
     */
    bool_t root_install = (!st->root_valid || level < st->root_level);
    u32 root_install_level = (level == 0) ? 1U : 2U;

    g_state.dart.last[8] = sid;
    g_state.dart.last[9] = level;
    g_state.dart.last[10] = pt_pa;
    g_state.dart.last[11] = 0;
    g_state.dart.last[12] = 0;
    g_state.dart.last[13] = st->root_level;
    g_state.dart.last[14] = st->root_valid;
    g_state.dart.last[15] = st->root_pt_pa;

    if (root_install && level > 1)
        return DART_C_STATUS_VIOLATION;

    if (root_install && st->root_valid)
        dart_c_import_live_sid(inst, (u32)sid);

    if (root_install) {
        st->root_valid = 1;
        st->root_level = (u8)root_install_level;
        st->root_pt_pa = pt_pa;
        st->ttbr = dart_c_ttbr_from_pa(pt_pa);
        st->tcr = dart_c_tcr_from_root_level(st->root_level);
        st->raw_replay = 0;
        st->translation_enabled = 1;
        dart_c_program_sid_tcr_ttbr(inst, (u32)sid, st->tcr, st->ttbr);
        return SPTM_SUCCESS;
    }

    if (level < st->root_level || level > 2)
        return DART_C_STATUS_VIOLATION;

    u64 parent;
    u32 idx;
    u64 rc = dart_c_walk_to_table(inst, (u32)sid, st, dva, level,
                                  &parent, &idx);
    if (rc)
        return SPTM_SUCCESS; /* Adapter glue: missing imported parent state is non-fatal. */
    u64 live_pt_pa = dart_c_shadow_child_table_if_needed(
        inst, (u32)sid, st, pt_pa);
    *(volatile u64 *)(parent + (u64)idx * 8UL) = dart_c_pte_from_pa(live_pt_pa);
    dart_c_clean64(parent + (u64)idx * 8UL);
    g_state.dart.last[11] = parent;
    g_state.dart.last[12] = idx;
    g_state.dart.last[13] = st->root_level;
    g_state.dart.last[14] = st->root_valid;
    g_state.dart.last[15] = st->root_pt_pa;
    dart_c_for_each_base_flush_sid(inst, (u32)sid);
    return SPTM_SUCCESS;
}

static inline u64 dart_c_ep1_unmap_table(struct dart_c_instance *inst, u64 *regs) {
    u64 sid = regs[1];
    u64 dva = regs[2];
    u32 level = (u32)regs[3];
    struct dart_c_sid_state *st = dart_c_sid(inst, sid);
    if (!st)
        return DART_C_STATUS_VIOLATION;
    if (dart_c_sid_exclave(st))
        return DART_C_STATUS_VIOLATION;
    if (!st->root_valid)
        return SPTM_SUCCESS;

    if ((st->root_level == 1 && level == 0) ||
        (st->root_level == 2 && level == 1)) {
        st->root_valid = 0;
        st->root_pt_pa = 0;
        st->ttbr = 0;
        st->tcr &= ~DART_T8110_TCR_TRANSLATE_EN;
        st->translation_enabled = 0;
        st->raw_replay = 0;
        for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
            u64 base = inst->base_pa[i];
            if (dart_c_looks_like_mmio(base))
                dart_c_write32(base + DART_T8110_TTBR + sid * 4, 0);
        }
        dart_c_for_each_base_flush_sid(inst, (u32)sid);
        return SPTM_SUCCESS;
    }

    if (level < st->root_level || level > 2)
        return DART_C_STATUS_VIOLATION;

    u64 parent;
    u32 idx;
    u64 rc = dart_c_walk_to_table(inst, (u32)sid, st, dva, level,
                                  &parent, &idx);
    if (!rc) {
        *(volatile u64 *)(parent + (u64)idx * 8UL) = 0;
        dart_c_clean64(parent + (u64)idx * 8UL);
    }
    dart_c_for_each_base_flush_sid(inst, (u32)sid);
    return SPTM_SUCCESS;
}

static inline bool_t dart_c_is_txm_secure_channel_dva(u64 dva) {
    if (!g_state.txm.secure_chan_dva)
        return 0;
    return (dva & ~(DART_C_PAGE_SIZE - 1UL)) ==
           (g_state.txm.secure_chan_dva & ~(DART_C_PAGE_SIZE - 1UL));
}

static inline bool_t dart_c_is_txm_secure_channel_pa(u64 pa) {
    if (!pa)
        return 0;
    return ft_get_type(pa & ~(DART_C_PAGE_SIZE - 1UL)) ==
           TXM_SEP_SECURE_CHANNEL;
}

static inline bool_t dart_c_is_txm_secure_channel_dart(struct dart_c_instance *inst) {
    /*
     * txm-secure-channel-base is a /arm-io/dart-sep property. DCP and other
     * DARTs use the same high DVA numbering and can legitimately have ordinary
     * mappings at the same numeric DVA, so keep this reservation scoped to the
     * SEP DART that owns the property.
     */
    return inst && inst->dart_id == 3;
}

static inline bool_t dart_c_validate_txm_secure_channel_map(struct dart_c_instance *inst,
                                                            u64 dva, u64 pa) {
    if (!g_state.txm.secure_chan_dva)
        return 1;
    if (!dart_c_is_txm_secure_channel_dart(inst))
        return 1;

    /*
     * Real sptm_t8110dart_map treats /arm-io/dart-sep's
     * txm-secure-channel-base/size as a reserved DVA window. With that DT
     * state present, the reserve window may only map frame type 0x3d, and
     * frame type 0x3d may only be mapped inside that window.
     */
    return dart_c_is_txm_secure_channel_dva(dva) ==
           dart_c_is_txm_secure_channel_pa(pa);
}

static inline bool_t dart_c_leaf_slot_is_txm_secure_channel(u64 slot) {
    u64 pte = *(volatile u64 *)slot;
    if ((pte & 1UL) == 0)
        return 0;
    return ft_get_type(dart_c_pa_from_pte(pte)) == TXM_SEP_SECURE_CHANNEL;
}

static inline u64 dart_c_ep2_map_from_pa_list(struct dart_c_instance *inst,
                                              u64 *regs) {
    u64 sid = regs[1];
    u64 dva = regs[2];
    u64 scratch_pa = regs[3];
    u64 size = regs[4];
    u64 flags = regs[5];
    struct dart_c_sid_state *st = dart_c_sid(inst, sid);
    u64 first_old_pa = 0;
    u64 first_new_pa = 0;
    bool_t flush_sid = 0;
    if (dart_c_sid_exclave(st))
        return DART_C_STATUS_VIOLATION;
    if (!st || !size || (scratch_pa & 7UL))
        return SPTM_SUCCESS;
    u64 range_rc = dart_c_validate_dva_range(dva, size);
    if (range_rc)
        return range_rc;

    u64 pages = ((dva & (DART_C_PAGE_SIZE - 1)) + size + DART_C_PAGE_SIZE - 1) /
                DART_C_PAGE_SIZE;

    u64 cur = dva;
    u64 remaining = size;
    for (u64 i = 0; i < pages; i++) {
        u64 table, slot;
        u64 page_bytes = DART_C_PAGE_SIZE - (cur & (DART_C_PAGE_SIZE - 1));
        if (page_bytes > remaining)
            page_bytes = remaining;
        if (dart_c_ensure_leaf_table(inst, (u32)sid, st, cur, &table, 0, 0))
            break;
        slot = table + (u64)dart_c_idx(cur, 3) * 8UL;
        u64 scratch_slot = scratch_pa + i * 8UL;
        u64 old_pte = *(volatile u64 *)slot;
        u64 old_pa = (old_pte & 1UL) ? dart_c_pa_from_pte(old_pte) : 0;
        u64 new_pa = *(volatile u64 *)scratch_slot;
        if (i == 0) {
            first_old_pa = old_pa;
            first_new_pa = new_pa;
        }
        if (!dart_c_validate_txm_secure_channel_map(inst, cur, new_pa)) {
            inst->last[8] = 0x54584d56UL; /* "TXMV" */
            inst->last[9] = sid;
            inst->last[10] = cur;
            inst->last[11] = new_pa;
            inst->last[12] = ft_get_type(new_pa);
            inst->last[13] = old_pa;
            g_state.dart.last[8] = 0x54584d56UL;
            g_state.dart.last[9] = sid;
            g_state.dart.last[10] = cur;
            g_state.dart.last[11] = new_pa;
            g_state.dart.last[12] = ft_get_type(new_pa);
            g_state.dart.last[13] = old_pa;
            return DART_C_STATUS_VIOLATION;
        }
        /*
         * Real t8110dart_map copies the caller's PA-list page into SPTM-owned
         * scratch, consumes the new PAs from that copy, and keeps old PAs only
         * for internal release bookkeeping. Do not write old mappings back into
         * XNU's supplied PA-list page.
         */
        u64 new_pte = new_pa ?
            dart_c_leaf_pte(new_pa, cur, page_bytes,
                            dart_c_leaf_perm_bits(inst, new_pa, flags)) : 0;
        *(volatile u64 *)slot = new_pte;
        dart_c_clean64(slot);
        if (dart_c_map_needs_tlbi(inst, old_pte, new_pte))
            flush_sid = 1;
        remaining -= page_bytes;
        cur += page_bytes;
    }
    if (flush_sid) {
        u64 flush_start = dva & ~(DART_C_PAGE_SIZE - 1UL);
        u64 flush_end = (dva + size + DART_C_PAGE_SIZE - 1UL) &
                        ~(DART_C_PAGE_SIZE - 1UL);
        if (flush_end > flush_start)
            dart_c_for_each_base_flush_map_change(inst, (u32)sid,
                                                  flush_start,
                                                  flush_end - 1UL);
    }
    inst->last[8] = 0x4d41504cUL; /* "MAPL" */
    inst->last[9] = sid;
    inst->last[10] = dva;
    inst->last[11] = size;
    inst->last[12] = pages;
    inst->last[13] = first_old_pa;
    inst->last[14] = first_new_pa;
    inst->last[15] = flags;
    g_state.dart.last[8] = 0x4d41504cUL;
    g_state.dart.last[9] = first_old_pa;
    g_state.dart.last[10] = first_new_pa;
    g_state.dart.last[11] = pages;
    g_state.dart.last[12] = flags;
    return SPTM_SUCCESS;
}

static inline u64 dart_c_ep3_unmap_range(struct dart_c_instance *inst, u64 *regs,
                                         bool_t flush) {
    u64 sid = regs[1];
    u64 start = regs[2];
    u64 size_or_end = regs[3];
    u64 end = flush ? size_or_end : start + size_or_end;
    struct dart_c_sid_state *st = dart_c_sid(inst, sid);
    u64 unmapped = 0;
    if (dart_c_sid_exclave(st))
        return DART_C_STATUS_VIOLATION;
    if (!st || end < start)
        return SPTM_SUCCESS;
    if (!flush) {
        u64 range_rc = dart_c_validate_dva_range(start, size_or_end);
        if (range_rc)
            return range_rc;
    }
    start &= ~(DART_C_PAGE_SIZE - 1);
    end = (end + DART_C_PAGE_SIZE - 1) & ~(DART_C_PAGE_SIZE - 1);
    for (u64 dva = start; dva < end; dva += DART_C_PAGE_SIZE) {
        u64 slot;
        if (!dart_c_walk_leaf_slot(inst, (u32)sid, st, dva, &slot)) {
            if (dart_c_leaf_slot_is_txm_secure_channel(slot))
                return DART_C_STATUS_VIOLATION;
            if (!dart_c_restore_boot_premap_page(inst, (u32)sid, dva, slot)) {
                *(volatile u64 *)slot = 0;
                dart_c_clean64(slot);
            }
            unmapped++;
        }
    }
    if (end > start)
        dart_c_for_each_base_flush_map_change(inst, (u32)sid, start,
                                              end - 1UL);
    inst->last[8] = 0x554e4d50UL; /* "UNMP" */
    inst->last[9] = sid;
    inst->last[10] = start;
    inst->last[11] = end - start;
    inst->last[12] = unmapped;
    g_state.dart.last[8] = 0x554e4d50UL;
    g_state.dart.last[9] = sid;
    g_state.dart.last[10] = start;
    g_state.dart.last[11] = end;
    g_state.dart.last[12] = unmapped;
    return SPTM_SUCCESS;
}

static inline u64 dart_c_ep12_translate(struct dart_c_instance *inst, u64 *regs) {
    u64 sid = regs[1];
    u64 dva = regs[2];
    struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
    if (!st && sid < DART_C_MAX_SIDS && dart_c_import_live_sid(inst, (u32)sid))
        st = dart_c_sid_lookup(inst, sid);
    u64 slot;
    if (!st || dart_c_walk_leaf_slot(inst, (u32)sid, st, dva, &slot)) {
        regs[1] = 0;
        return SPTM_SUCCESS;
    }
    u64 pte = *(volatile u64 *)slot;
    regs[1] = (pte & 1UL) ? (dart_c_pa_from_pte(pte) | (dva & (DART_C_PAGE_SIZE - 1))) : 0;
    return SPTM_SUCCESS;
}

#define DART_DAPF_SLICE_STRIDE        0x40UL
#define DART_DAPF_CTRL                0x00UL
#define DART_DAPF_START_LO            0x08UL
#define DART_DAPF_START_HI            0x0cUL
#define DART_DAPF_END_LO              0x10UL
#define DART_DAPF_END_HI              0x14UL
#define DART_DAPF_WORD_BASE           0x20UL

static inline u32 dart_c_dapf_count(struct dart_c_instance *inst) {
    u32 count = inst->dapf.count;
    if (count > DART_C_MAX_DAPF_SLICES)
        count = DART_C_MAX_DAPF_SLICES;
    return count;
}

static inline u32 dart_c_dapf_word_count(struct dart_c_instance *inst) {
    u32 sid_count = inst->dapf.sid_count;
    if (sid_count == 0 || sid_count > DART_C_MAX_STREAMS)
        sid_count = DART_C_MAX_STREAMS;
    u32 words = (sid_count + 31U) >> 5;
    if (words == 0)
        words = 1;
    if (words > 8)
        words = 8;
    return words;
}

static inline u32 dart_c_program_dapf_power_up(struct dart_c_instance *inst) {
    u64 base = inst->dapf.base_pa;
    u32 count = dart_c_dapf_count(inst);
    u32 words = dart_c_dapf_word_count(inst);
    u32 writes = 0;

    if (!base || !count || !dart_c_looks_like_mmio(base))
        return 0;

    for (u32 i = 0; i < count; i++) {
        struct dart_c_dapf_slice *desc = &inst->dapf.slice[i];
        u64 off = base + (u64)i * DART_DAPF_SLICE_STRIDE;
        dart_c_write32(off + DART_DAPF_START_LO, (u32)desc->start);
        dart_c_write32(off + DART_DAPF_START_HI, (u32)(desc->start >> 32));
        dart_c_write32(off + DART_DAPF_END_LO, (u32)desc->end);
        dart_c_write32(off + DART_DAPF_END_HI, (u32)(desc->end >> 32));
        writes += 4;

        for (u32 word = 0; word < words; word++) {
            dart_c_write32(off + DART_DAPF_WORD_BASE + (u64)word * 4UL,
                           desc->words[word]);
            writes++;
        }

        dart_c_write32(off + DART_DAPF_CTRL, desc->ctrl);
        writes++;
    }

    __asm__ volatile("dsb sy" ::: "memory");
    return writes;
}

#define DART_PIOGW_PROT_BASE          0x1120UL
#define DART_PIOGW_PROT_STRIDE        0x20UL
#define DART_PIOGW_PROT_CTRL          0x00UL
#define DART_PIOGW_PROT_START_LO      0x04UL
#define DART_PIOGW_PROT_START_HI      0x08UL
#define DART_PIOGW_PROT_END_LO        0x0cUL
#define DART_PIOGW_PROT_END_HI        0x10UL

static inline u32 dart_c_piogw_desc_count(struct dart_c_instance *inst) {
    u32 count = inst->piogw_desc_count;
    if (count > DART_C_MAX_PIOGW_DESCS)
        count = DART_C_MAX_PIOGW_DESCS;
    return count;
}

static inline u32 dart_c_piogw_count(struct dart_c_instance *inst) {
    u32 count = inst->piogw_count;
    if (count > DART_C_MAX_PIOGW_RANGES)
        count = DART_C_MAX_PIOGW_RANGES;
    return count;
}

static inline u32 dart_c_program_piogw_power_up(struct dart_c_instance *inst) {
    u32 desc_count = dart_c_piogw_desc_count(inst);
    u32 piogw_count = dart_c_piogw_count(inst);
    u32 writes = 0;

    if (!piogw_count || !desc_count)
        return 0;

    for (u32 i = 0; i < piogw_count; i++) {
        u64 base = inst->piogw_base_pa[i];
        if (!dart_c_looks_like_mmio(base))
            continue;
        if (dart_c_read32(base + 0x10UL) != 0 ||
            dart_c_read32(base + 0x0cUL) != 0)
            continue;

        dart_c_write32(base + DART_PIOGW_PROT_BASE +
                       DART_PIOGW_PROT_START_LO, 0);
        dart_c_write32(base + DART_PIOGW_PROT_BASE +
                       DART_PIOGW_PROT_START_HI, 0);
        dart_c_write32(base + DART_PIOGW_PROT_BASE +
                       DART_PIOGW_PROT_END_LO, 0xffffffffU);
        dart_c_write32(base + DART_PIOGW_PROT_BASE +
                       DART_PIOGW_PROT_END_HI, 0xffffffffU);
        dart_c_write32(base + DART_PIOGW_PROT_BASE +
                       DART_PIOGW_PROT_CTRL, 3);
        writes += 5;

        for (u32 j = 0; j < desc_count; j++) {
            struct dart_c_piogw_desc *desc = &inst->piogw_desc[j];
            u32 slice = desc->slice;
            u64 addr = desc->addr;
            if (slice < 1 || slice > 9 || addr == 0)
                continue;
            u64 off = DART_PIOGW_PROT_BASE + (u64)slice * DART_PIOGW_PROT_STRIDE;
            dart_c_write32(base + off + DART_PIOGW_PROT_START_LO, (u32)addr);
            dart_c_write32(base + off + DART_PIOGW_PROT_START_HI,
                           (u32)(addr >> 32));
            dart_c_write32(base + off + DART_PIOGW_PROT_END_LO, (u32)(addr + 3));
            dart_c_write32(base + off + DART_PIOGW_PROT_END_HI,
                           (u32)((addr + 3) >> 32));
            dart_c_write32(base + off + DART_PIOGW_PROT_CTRL, 6);
            writes += 5;
        }

        dart_c_write32(base + 4UL, dart_c_read32(base + 4UL) | 1U);
        writes++;
    }

    return writes;
}

static inline u32 dart_c_program_piogw_power_down(struct dart_c_instance *inst) {
    u32 desc_count = dart_c_piogw_desc_count(inst);
    u32 piogw_count = dart_c_piogw_count(inst);
    u32 writes = 0;

    if (!piogw_count || !desc_count)
        return 0;

    for (u32 i = 0; i < piogw_count; i++) {
        u64 base = inst->piogw_base_pa[i];
        if (!dart_c_looks_like_mmio(base))
            continue;
        if (dart_c_read32(base + 0x10UL) != 0 ||
            dart_c_read32(base + 0x0cUL) != 0)
            continue;

        for (u32 j = 0; j < desc_count; j++) {
            struct dart_c_piogw_desc *desc = &inst->piogw_desc[j];
            u32 slice = desc->slice;
            if (slice < 1 || slice > 9)
                continue;
            u64 off = DART_PIOGW_PROT_BASE + (u64)slice * DART_PIOGW_PROT_STRIDE;
            dart_c_write32(base + off + DART_PIOGW_PROT_CTRL, 0);
            writes++;
        }
    }

    return writes;
}

static inline u32 dart_c_snapshot_live_streams(struct dart_c_instance *inst) {
    u32 seen = 0;

    for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++) {
        struct dart_c_sid_state *st = &inst->sid[sid];
        if (st->valid)
            st->stream_enabled = 0;
    }

    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        u64 base = inst->base_pa[i];
        if (!dart_c_looks_like_mmio(base))
            continue;
        u32 num = dart_c_num_streams(base);
        if (num > DART_C_MAX_SIDS)
            num = DART_C_MAX_SIDS;
        u32 words = dart_c_stream_words(num);
        for (u32 word = 0; word < words; word++) {
            u32 bits = dart_c_read32(base + DART_T8110_ENABLE_STREAMS + word * 4);
            while (bits) {
                u32 bit = __builtin_ctz(bits);
                u32 sid = word * 32 + bit;
                bits &= bits - 1;
                if (sid >= num)
                    continue;
                struct dart_c_sid_state *st = dart_c_sid(inst, sid);
                if (st)
                    st->stream_enabled = 1;
                seen++;
            }
        }
    }

    return seen;
}

static inline u32 dart_c_disable_translated_streams(struct dart_c_instance *inst) {
    u32 writes = 0;

    for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++) {
        struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
        if (dart_c_sid_exclave(st) || !dart_c_sid_translates(st))
            continue;
        for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
            u64 base = inst->base_pa[i];
            if (!dart_c_looks_like_mmio(base))
                continue;
            dart_c_write32(base + DART_T8110_DISABLE_STREAMS +
                           ((sid >> 5) * 4), 1U << (sid & 31));
            writes++;
        }
    }

    return writes;
}

static inline u32 dart_c_finalize_replay(struct dart_c_instance *inst) {
    u32 writes = 0;
    u32 touched[DART_C_MAX_SIDS / 32];

    for (u32 i = 0; i < DART_C_MAX_SIDS / 32; i++)
        touched[i] = 0;

    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
        u64 base = inst->base_pa[i];
        if (!dart_c_looks_like_mmio(base))
            continue;

        for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++) {
            struct dart_c_sid_state *st = &inst->sid[sid];
            if (!st->valid)
                continue;
            bool_t replay_regs =
                !dart_c_sid_exclave(st) &&
                (st->root_valid || st->raw_replay ||
                 (st->tcr & (DART_T8110_TCR_REMAP_EN |
                             DART_T8110_TCR_BYPASS_DART |
                             DART_T8110_TCR_BYPASS_DAPF)));
            if (replay_regs) {
                u64 tcr_reg = base + DART_T8110_TCR + sid * 4;
                u64 ttbr_reg = base + DART_T8110_TTBR + sid * 4;
                touched[sid >> 5] |= 1U << (sid & 31);
                if (dart_c_read32(tcr_reg) != st->tcr) {
                    dart_c_write32(tcr_reg, st->tcr);
                    writes++;
                }
                if (dart_c_read32(ttbr_reg) != st->ttbr) {
                    dart_c_write32(ttbr_reg, st->ttbr);
                    writes++;
                }
            }
        }

        u32 num = dart_c_num_streams(base);
        if (num > DART_C_MAX_SIDS)
            num = DART_C_MAX_SIDS;
        u32 words = dart_c_stream_words(num);
        for (u32 word = 0; word < words; word++) {
            u32 bits = 0;
            for (u32 bit = 0; bit < 32; bit++) {
                u32 sid = word * 32 + bit;
                if (sid >= num)
                    break;
                struct dart_c_sid_state *st = &inst->sid[sid];
                if (st->valid &&
                    (st->stream_enabled || st->initial_stream_enabled)) {
                    bits |= 1U << bit;
                    touched[sid >> 5] |= 1U << (sid & 31);
                }
            }
            dart_c_write32(base + DART_T8110_ENABLE_STREAMS + word * 4, bits);
            writes++;
        }
    }

    /*
     * Persistent display/DCP roots can contain valid leaves before any map call
     * touches them in this boot. Once finalize replays that root or enables a
     * stream, force the hardware translation cache to forget older negative
     * entries before firmware starts reading through the DART.
     */
    __asm__ volatile("dsb sy" ::: "memory");
    for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++)
        if (touched[sid >> 5] & (1U << (sid & 31)))
            dart_c_for_each_base_flush_sid(inst, sid);

    return writes;
}

static inline u32 dart_c_count_raw_replay_state(struct dart_c_instance *inst) {
    u32 count = 0;

    for (u32 sid = 0; sid < DART_C_MAX_SIDS; sid++) {
        struct dart_c_sid_state *st = &inst->sid[sid];
        if (st->valid && st->raw_replay)
            count++;
    }

    return count;
}

static inline u32 dart_c_xnu_clock_protection(struct dart_c_instance *inst,
                                              bool_t enable) {
    u64 obj = inst->obj_va;
    u32 gapf_count, inst_count;
    u64 state;

    if (!dart_validate_xnu_object(obj, &gapf_count, &inst_count, &state)) {
        dart_c_import_cached_bases(inst);
        obj = inst->obj_va;
    }
    if (!dart_validate_xnu_object(obj, &gapf_count, &inst_count, &state))
        return 0;
    inst->state_va = state;

    u32 writes = 0;
    for (u32 gapf_i = 0; gapf_i < gapf_count; gapf_i++) {
        u64 base_va;
        if (!guest_read64(obj + 0x17d0UL + (u64)gapf_i * 0x18UL, &base_va))
            continue;
        if (!is_kernel_va(base_va))
            continue;

        for (u32 inst_i = 0; inst_i < inst_count; inst_i++) {
            u32 slice_idx;
            u64 entry = obj + 0x14f8UL + (u64)inst_i * 0x70UL +
                        (u64)gapf_i * 4UL;
            if (!guest_read32(entry, &slice_idx) || slice_idx > 0x3ffU)
                continue;

            u64 reg_va = base_va + 0x100UL + (u64)slice_idx * 0x40UL;
            u64 reg_pa;
            if (!guest_va_to_pa(reg_va, 1, &reg_pa))
                continue;

            u32 old = dart_c_read32(reg_pa);
            u32 new_value = enable ? (old | 0x10U) : (old & ~0x10U);
            dart_c_write32(reg_pa, new_value);
            writes++;
        }
    }

    inst->clock_protection = enable ? (writes != 0) : 0;
    inst->last[8] = enable;
    inst->last[9] = writes;
    g_state.dart.last[8] = enable;
    g_state.dart.last[9] = writes;
    return writes;
}

bool_t dart_handle_table(u32 table, u32 endpoint, u64 *regs) {
    bool_t t8110_xnu = table == SPTM_TABLE_T8110_DART_XNU;
    bool_t t8110_sk = table == SPTM_TABLE_T8110_DART_SK;
    bool_t gen3_xnu = table == SPTM_TABLE_GEN3_DART_XNU;
    bool_t gen3_sk = table == SPTM_TABLE_GEN3_DART_SK;
    bool_t xnu_table = t8110_xnu || gen3_xnu;
    bool_t sk_table = t8110_sk || gen3_sk;

    if (!xnu_table && !sk_table)
        return 0;

    struct dart_c_instance *inst = dart_c_get(regs[0]);
    if (!inst)
        return 0;

    g_state.dart.enabled = 1;
    g_state.dart.total_calls++;
    inst->total_calls++;
    if (endpoint < DART_C_MAX_ENDPOINTS) {
        inst->ep_count[endpoint]++;
    }
    g_state.dart.last[0] = table;
    g_state.dart.last[1] = endpoint;
    g_state.dart.last[2] = regs[0];
    g_state.dart.last[3] = regs[1];
    g_state.dart.last[4] = regs[2];
    g_state.dart.last[5] = regs[3];
    for (u32 i = 0; i < 16; i++)
        inst->last[i] = (i < 8) ? regs[i] : 0;

    u64 rc = SPTM_SUCCESS;
    bool_t record_dart_lifetime = 0;
    u64 record_sid = 0;
    u64 record_dva = 0;
    u64 before_slot = 0;
    u64 before_pte = 0;
    u64 after_slot = 0;
    u64 after_pte = 0;
    bool_t record_sid0_trace = 0;
    u64 sid0_reason = 0;
    u64 sid0_before_tcr_ttbr = 0;
    u64 sid0_before_root_flags = 0;
    u64 sid0_before_slot = 0;
    u64 sid0_before_pte = 0;
    u64 sid0_after_tcr_ttbr = 0;
    u64 sid0_after_root_flags = 0;
    u64 sid0_after_slot = 0;
    u64 sid0_after_pte = 0;

    if (xnu_table && (endpoint == 2 || endpoint == 3)) {
        record_dart_lifetime = 1;
        record_sid = regs[1];
        record_dva = regs[2];
        if (record_dart_lifetime)
            dart_c_snapshot_leaf(inst, record_sid, record_dva,
                                 &before_slot, &before_pte);
    } else if (xnu_table &&
               (endpoint == 0 || endpoint == 1 ||
                endpoint == 4 || endpoint == 5 || endpoint == 6 ||
                endpoint == 7 || endpoint == 8 || endpoint == 9 ||
                endpoint == 10 || endpoint == 11 || endpoint == 16)) {
        record_dart_lifetime = 1;
        record_sid = (endpoint == 7 || endpoint == 8 || endpoint == 14) ?
                     regs[1] : 0;
        record_dva = regs[2];
        if (endpoint == 0 || endpoint == 1) {
            dart_c_snapshot_leaf(inst, record_sid, record_dva,
                                 &before_slot, &before_pte);
        } else {
            before_slot = dart_c_pack_hw_sid_regs(inst, (u32)record_sid);
            before_pte = dart_c_pack_hw_stream_error(inst, (u32)record_sid);
        }
    }

    record_sid0_trace = dart_c_sid0_trace_reason(inst, xnu_table, sk_table,
                                                 endpoint, regs, &sid0_reason);
    if (record_sid0_trace) {
        dart_c_snapshot_sid0(inst, DART_C_SID0_TRACE_DVA,
                             &sid0_before_tcr_ttbr,
                             &sid0_before_root_flags,
                             &sid0_before_slot,
                             &sid0_before_pte);
    }

    if (sk_table) {
        switch (endpoint) {
            case 0:
                rc = dart_c_ep3_unmap_range(inst, regs, 1);
                break;
            case 1:
                inst->locked = 0;
                rc = SPTM_SUCCESS;
                break;
            case 2:
                inst->clock_protection++;
                rc = SPTM_SUCCESS;
                break;
            case 3:
                regs[1] = inst->clock_protection;
                rc = SPTM_SUCCESS;
                break;
            default:
                rc = SPTM_SUCCESS;
                break;
        }
    } else {
        if (endpoint == 4 || endpoint == 5 || endpoint == 6) {
            dart_cache_xnu_object_from_regs(table, endpoint, regs);
            dart_c_import_cached_bases(inst);
        }
        if (endpoint == 6 && dart_c_looks_like_mmio(regs[1]))
            dart_c_add_base(inst, regs[1]);

        switch (endpoint) {
            case 0:
                rc = dart_c_ep0_install_table(inst, regs);
                if (rc == SPTM_SUCCESS)
                    dart_c_apply_identity_ranges(inst);
                break;
            case 1:
                rc = dart_c_ep1_unmap_table(inst, regs);
                break;
            case 2:
                rc = dart_c_ep2_map_from_pa_list(inst, regs);
                break;
            case 3:
                rc = dart_c_ep3_unmap_range(inst, regs, 0);
                break;
            case 4:
                if (t8110_xnu || gen3_xnu) {
                    u32 stream_seen = dart_c_snapshot_live_streams(inst);
                    u32 stream_disables = dart_c_disable_translated_streams(inst);
                    u32 piogw_writes = dart_c_program_piogw_power_down(inst);
                    inst->init_state = 1;
                    dart_c_xnu_clock_protection(inst, 0);
                    inst->last[13] = stream_seen;
                    inst->last[14] = stream_disables;
                    inst->last[15] = piogw_writes;
                    g_state.dart.last[13] = stream_seen;
                    g_state.dart.last[14] = stream_disables;
                    g_state.dart.last[15] = piogw_writes;
                } else {
                    inst->last[8] = 0x494f4354UL; /* "IOCT" */
                    inst->last[9] = endpoint;
                }
                rc = SPTM_SUCCESS;
                break;
            case 5: {
                u32 piogw_writes = dart_c_program_piogw_power_up(inst);
                u32 dapf_writes = dart_c_program_dapf_power_up(inst);
                u32 raw_replay_sids = dart_c_count_raw_replay_state(inst);
                inst->init_state = 2;
                inst->locked = 1;
                dart_c_apply_bootstrap_remaps(inst);
                dart_c_apply_identity_ranges(inst);
                u32 replay_writes = dart_c_finalize_replay(inst);
                dart_c_xnu_clock_protection(inst, 1);
                inst->last[10] = raw_replay_sids;
                inst->last[11] = replay_writes;
                inst->last[14] = dapf_writes;
                inst->last[15] = piogw_writes;
                g_state.dart.last[10] = raw_replay_sids;
                g_state.dart.last[11] = replay_writes;
                g_state.dart.last[14] = dapf_writes;
                g_state.dart.last[15] = piogw_writes;
                rc = SPTM_SUCCESS;
                break;
            }
            case 6: {
                inst->init_state = 1;
                u32 preserved = 0;
                u32 reset = 0;
                u32 imported = 0;
                for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
                    u64 base = inst->base_pa[i];
                    if (!dart_c_looks_like_mmio(base))
                        continue;
                    bool_t preserve = 0;
                    imported += dart_c_import_live_base(inst, base, &preserve);
                    if (!preserve && dart_c_has_seeded_live_sid(inst))
                        preserve = 1;
                    if (preserve) {
                        /*
                         * Bootloader-owned display/AOP/DCP DARTs can have
                         * protected TTBR/TCR registers. On those DARTs, resetting
                         * TCR/TTBR is ineffective, but enabling every stream is
                         * very effective and can expose stale DMA as a real XNU
                         * DART panic. Preserve the live root and only clear stale
                         * interrupt state.
                         */
                        dart_c_clear_errors_base(base);
                        preserved++;
                        continue;
                    }
                    dart_c_clear_errors_base(base);
                    reset++;
                }
                inst->last[10] = imported;
                inst->last[11] = preserved;
                inst->last[12] = reset;
                g_state.dart.last[10] = imported;
                g_state.dart.last[11] = preserved;
                g_state.dart.last[12] = reset;
                dart_c_apply_bootstrap_remaps(inst);
                dart_c_apply_identity_ranges(inst);
                rc = SPTM_SUCCESS;
                break;
            }
            case 7: {
                u32 sid = (u32)regs[1];
                struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
                if (!st || dart_c_sid_exclave(st)) {
                    rc = DART_C_STATUS_VIOLATION;
                    break;
                }
                if (dart_c_sid_translates(st)) {
                    st->stream_enabled = 0;
                    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
                        u64 base = inst->base_pa[i];
                        if (!dart_c_looks_like_mmio(base))
                            continue;
                        dart_c_write32(base + DART_T8110_DISABLE_STREAMS +
                                       ((sid >> 5) * 4), 1U << (sid & 31));
                    }
                }
                rc = SPTM_SUCCESS;
                break;
            }
            case 8: {
                u32 sid = (u32)regs[1];
                struct dart_c_sid_state *st = dart_c_sid_lookup(inst, sid);
                if (!st || dart_c_sid_exclave(st)) {
                    rc = DART_C_STATUS_VIOLATION;
                    break;
                }
                if (dart_c_sid_translates(st)) {
                    st->stream_enabled = 1;
                    for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
                        u64 base = inst->base_pa[i];
                        if (!dart_c_looks_like_mmio(base))
                            continue;
                        dart_c_write32(base + DART_T8110_ENABLE_STREAMS +
                                       ((sid >> 5) * 4), 1U << (sid & 31));
                    }
                    __asm__ volatile("dsb sy" ::: "memory");
                    dart_c_for_each_base_flush_sid(inst, sid);
                }
                rc = SPTM_SUCCESS;
                break;
            }
            case 9: {
                u32 instance = (u32)regs[1];
                u32 mask = (u32)regs[2] & 0x7fffU;
                if (instance >= inst->base_count ||
                    instance >= DART_C_MAX_BASES ||
                    !dart_c_looks_like_mmio(inst->base_pa[instance]) ||
                    !mask || (mask & (mask - 1U))) {
                    rc = DART_C_STATUS_VIOLATION;
                    break;
                }
                dart_c_write32(inst->base_pa[instance] + DART_T8110_ERROR, mask);
                inst->last[8] = 0x45525243UL; /* "ERRC" */
                inst->last[9] = instance;
                inst->last[10] = mask;
                rc = SPTM_SUCCESS;
                break;
            }
            case 10: {
                u32 instance = (u32)regs[1];
                u32 mask = (u32)regs[2] & 0x777U;
                if (instance >= inst->base_count ||
                    instance >= DART_C_MAX_BASES ||
                    !dart_c_looks_like_mmio(inst->base_pa[instance])) {
                    rc = DART_C_STATUS_VIOLATION;
                    break;
                }
                if (mask)
                    dart_c_write32(inst->base_pa[instance] +
                                   DART_T8110_ERROR_MASK, mask);
                inst->last[8] = 0x4552524dUL; /* "ERRM" */
                inst->last[9] = instance;
                inst->last[10] = mask;
                rc = SPTM_SUCCESS;
                break;
            }
            case 11:
                for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++) {
                    u64 base = inst->base_pa[i];
                    if (!dart_c_looks_like_mmio(base))
                        continue;
                    dart_c_clear_errors_base(base);
                }
                rc = SPTM_SUCCESS;
                break;
            case 12: {
                u32 instance = (u32)regs[1];
                if (instance >= inst->base_count ||
                    instance >= DART_C_MAX_BASES ||
                    !dart_c_looks_like_mmio(inst->base_pa[instance])) {
                    rc = DART_C_STATUS_VIOLATION;
                    break;
                }
                u32 command = (((u32)regs[3] & 0xfU) << 4) |
                              (((u32)regs[2] & 0x3fffU) << 8) |
                              ((u32)regs[4] & 7U);
                u64 base = inst->base_pa[instance];
                dart_c_write32(base + DART_T8110_TLB_CMD, command);
                for (u32 poll = 0; poll < 100; poll++) {
                    if (!(dart_c_read32(base + DART_T8110_TLB_CMD) &
                          DART_T8110_TLB_CMD_BUSY))
                        break;
                }
                regs[1] = dart_c_read32(base + 0x88UL);
                regs[2] = dart_c_read32(base + 0x90UL);
                inst->last[8] = 0x544c4243UL; /* "TLBC" */
                inst->last[9] = instance;
                inst->last[10] = command;
                break;
            }
            case 13:
                inst->last[8] = 0x41504653UL; /* "APFS" */
                inst->last[9] = regs[1];
                inst->last[10] = regs[2];
                rc = SPTM_SUCCESS;
                break;
            case 14: {
                struct dart_c_sid_state *st = dart_c_sid_lookup(inst, regs[1]);
                regs[1] = st ? st->status : 0;
                rc = SPTM_SUCCESS;
                break;
            }
            case 15: {
                inst->last[8] = 0x494f4354UL; /* "IOCT" */
                inst->last[9] = endpoint;
                inst->last[10] = regs[1];
                inst->last[11] = regs[2];
                rc = SPTM_SUCCESS;
                break;
            }
            case 16:
                for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++)
                    if (dart_c_looks_like_mmio(inst->base_pa[i]))
                        dart_c_clear_errors_base(inst->base_pa[i]);
                rc = SPTM_SUCCESS;
                break;
            case 17:
                rc = DART_C_STATUS_VIOLATION;
                break;
            case 18:
                for (u32 i = 0; i < inst->base_count && i < DART_C_MAX_BASES; i++)
                    if (dart_c_looks_like_mmio(inst->base_pa[i]))
                        dart_c_clear_errors_base(inst->base_pa[i]);
                inst->last[8] = 0x45525252UL; /* "ERRR" */
                inst->last[9] = endpoint;
                rc = SPTM_SUCCESS;
                break;
            default:
                rc = DART_C_STATUS_VIOLATION;
                break;
        }
    }

    if (record_dart_lifetime) {
        if (endpoint == 0 || endpoint == 1 || endpoint == 2 || endpoint == 3) {
            dart_c_snapshot_leaf(inst, record_sid, record_dva,
                                 &after_slot, &after_pte);
        } else {
            after_slot = dart_c_pack_hw_sid_regs(inst, (u32)record_sid);
            after_pte = dart_c_pack_hw_stream_error(inst, (u32)record_sid);
        }
        dart_c_record_recent(inst, table, endpoint, regs, rc, record_sid,
                             before_slot, before_pte, after_slot, after_pte);
    }
    if (record_sid0_trace) {
        dart_c_snapshot_sid0(inst, DART_C_SID0_TRACE_DVA,
                             &sid0_after_tcr_ttbr,
                             &sid0_after_root_flags,
                             &sid0_after_slot,
                             &sid0_after_pte);
        bool_t changed =
            sid0_before_tcr_ttbr != sid0_after_tcr_ttbr ||
            sid0_before_root_flags != sid0_after_root_flags ||
            sid0_before_slot != sid0_after_slot ||
            sid0_before_pte != sid0_after_pte;
        if (changed || !(sid0_reason & DART_C_SID0_REASON_FLUSH)) {
            dart_c_record_sid0_trace(inst, table, endpoint, regs, rc, sid0_reason,
                                     sid0_before_tcr_ttbr,
                                     sid0_before_root_flags,
                                     sid0_before_pte,
                                     sid0_after_tcr_ttbr,
                                     sid0_after_root_flags,
                                     sid0_after_pte);
        }
    }

    if (rc == DART_C_STATUS_VIOLATION) {
        g_state.dart.violations++;
        inst->violations++;
    } else {
        g_state.dart.fast_path_calls++;
        inst->fast_path_calls++;
    }
    g_state.dart.last[6] = rc;
    g_state.dart.last[7] = inst->base_count;
    regs[0] = rc;
    sev();
    return 1;
}
