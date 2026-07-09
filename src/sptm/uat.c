/* SPDX-License-Identifier: MIT */
#include "private.h"

int debug_printf(const char *fmt, ...);

#define UAT_TTE_ADDR_MASK             0x000001fffffff000UL
#define UAT_PTE_ADDR_MASK             0x0000fffffffff000UL
#define UAT_TABLE_DESC                3UL
#define UAT_VALID_LEAF_BITS           0x0080000000000400UL
#define UAT_OPTIONS_INVALID_MASK      0xfff0fcf0UL
#define UAT_FW_OWNED_BIT             8UL
#define UAT_DEFAULT_VADDR_SHIFT       0x27UL
#define UAT_MAX_VA_PAGES             (1UL << 50)
#define UAT_STATE_ROOT0_OFF          0x08UL
#define UAT_STATE_ROOT1_OFF          0x10UL
#define UAT_STATE_CTX_ID_OFF         0x18UL
#define UAT_STATE_GUARD_OFF          0x1aUL
#define UAT_STATE_WORK0_OFF          0x20UL
#define UAT_STATE_WORK1_OFF          0x28UL
#define UAT_STATE_WORK2_OFF          0x30UL
#define UAT_STATE_WORK3_OFF          0x38UL
#define UAT_STATE_OPTIONS_OFF        0x40UL
#define UAT_STATE_FLUSH_LEVEL_OFF    0x44UL
#define UAT_STATE_MAP_SEGS_OFF        0x48UL
#define UAT_STATE_CTX_FLUSH_OFF      0x248UL
#define UAT_STATE_UNMAP_SEGS_OFF      0x250UL
#define UAT_SAPT_ALIAS_COUNT         12
#define UAT_SAPT_LAST_PA             13
#define UAT_SAPT_LAST_OLD            14
#define UAT_SAPT_LAST_NEW            15
#define UAT_HANDOFF_MAGIC            0x4b1d000000000002UL
#define UAT_HANDOFF_MAGIC_FW_OFF     0x8UL
#define UAT_HANDOFF_SLOT_BASE        0x20UL
#define UAT_HANDOFF_SLOT_STRIDE      0x18UL
#define UAT_HANDOFF_CUR_CTX_OFF      0x18UL
#define UAT_HANDOFF_READY_OFF        0x638UL
#define UAT_HANDOFF_DEAD_PREFIX      0xdead000000000000UL
#define UAT_HANDOFF_ADDR_MASK        0x0000ffffffffffffUL

static const u8 uat_attr_table[16] = {
    0, 8, 9, 10, 4, 1, 0xff, 0xff,
    5, 0xff, 2, 0xff, 6, 7, 0xff, 3,
};

static inline u8 uat_sapt_field_for_options(u64 options)
{
    switch (options & 3UL) {
    case 1:
        return 1;
    case 3:
        return 0;
    default:
        return 3;
    }
}

static inline bool_t uat_looks_like_pa(u64 pa)
{
    return !is_kernel_va(pa) && pa >= 0x100000000UL && pa < 0x20000000000UL;
}

static inline bool_t uat_resolve_data_pa(u64 ptr, bool_t write, u64 *pa_out)
{
    if (is_kernel_va(ptr))
        return guest_va_to_pa(ptr, write, pa_out);
    if (uat_looks_like_pa(ptr)) {
        *pa_out = ptr;
        return 1;
    }
    return 0;
}

static inline bool_t uat_read64_ptr(u64 ptr, u64 *out)
{
    u64 pa;
    if (!uat_resolve_data_pa(ptr, 0, &pa))
        return 0;
    *out = *(volatile u64 *)pa;
    return 1;
}

static inline void uat_clean_state_range_poc(u64 pa, u64 size)
{
    /*
     * AGX/uPPL observes UAT state objects as a coprocessor-visible protocol,
     * not as CPU-local data. The real SPTM runs in the hardware domain that
     * makes these stores visible before the guard changes; our EL2 emulator
     * must publish them explicitly to PoC plus the coprocessor cache path.
     */
    clean_pt_range_poc((volatile u64 *)pa, size);
}

static inline bool_t uat_sapt_byte_for_pa(u64 pa, u64 *byte_pa, u8 *shift)
{
    u64 base = g_state.uat.sapt_base;
    u64 entries = g_state.uat.sapt_entries;
    u64 dram_base = g_state.uat.sapt_dram_base;
    u64 dram_end = g_state.uat.sapt_dram_end;
    u64 page = pa & ~(UAT_C_PAGE_SIZE - 1UL);
    u64 offset;
    u64 index;

    if (!base || !entries || !dram_base || page < dram_base || page >= dram_end)
        return 0;

    offset = page - dram_base;
    index = offset >> 16;
    if (index >= entries)
        return 0;

    *byte_pa = base + index;
    *shift = (u8)((offset >> 13) & 6UL);
    return 1;
}

static inline void uat_sapt_set_page(u64 pa, u8 field, bool_t expect_released)
{
    u64 byte_pa;
    u8 shift;
    u8 mask;
    u8 old;
    u8 old_field;
    u8 new_value;

    if (!uat_sapt_byte_for_pa(pa, &byte_pa, &shift))
        return;

    mask = (u8)(3U << shift);
    old = *(volatile u8 *)byte_pa;
    old_field = (old >> shift) & 3U;
    if (expect_released && old_field != 3U) {
        g_state.uat.violations++;
        g_state.uat.last[UAT_SAPT_ALIAS_COUNT]++;
        g_state.uat.last[UAT_SAPT_LAST_PA] = pa & ~(UAT_C_PAGE_SIZE - 1UL);
        g_state.uat.last[UAT_SAPT_LAST_OLD] = old_field;
        g_state.uat.last[UAT_SAPT_LAST_NEW] = field & 3U;
    }

    new_value = (u8)((old & ~mask) | ((field & 3U) << shift));
    *(volatile u8 *)byte_pa = new_value;
    uat_clean_state_range_poc(byte_pa, 1);
}

static inline void uat_sapt_grant_page(u64 pa, u64 options)
{
    uat_sapt_set_page(pa, uat_sapt_field_for_options(options), 1);
}

static inline void uat_sapt_release_page(u64 pa)
{
    uat_sapt_set_page(pa, 3, 0);
}

static u64 uat_publish_fw_unmap_handoff(struct uat_c_root_state *root,
                                        u64 addr, u64 size)
{
    u64 handoff = g_state.uat.gfx_handoff_pa;
    u64 slot_pa;
    u32 slot_state;
    u32 cur_ctx;
    u8 ready;
    bool_t dead;

    if (root->ctx_id >= 0x41U)
        return 0;

    if (!uat_looks_like_pa(handoff) ||
        g_state.uat.gfx_handoff_size < UAT_HANDOFF_READY_OFF + 1UL) {
        g_state.uat.violations++;
        return 0;
    }

    slot_pa = handoff + UAT_HANDOFF_SLOT_BASE +
              (u64)root->ctx_id * UAT_HANDOFF_SLOT_STRIDE;
    slot_state = *(volatile u32 *)slot_pa;
    if (slot_state != 0) {
        g_state.uat.violations++;
        root->last[6] = slot_pa;
        root->last[7] = slot_state;
        return 0;
    }

    *(volatile u64 *)(slot_pa + 8) = addr;
    *(volatile u64 *)(slot_pa + 0x10) = size;

    cur_ctx = *(volatile u32 *)(handoff + UAT_HANDOFF_CUR_CTX_OFF);
    ready = *(volatile u8 *)(handoff + UAT_HANDOFF_READY_OFF);
    dead = (ready & 1U) != 0 ||
           (((root->type & 5U) != 0) && cur_ctx != (u32)root->ctx_id);

    if (dead) {
        addr = UAT_HANDOFF_DEAD_PREFIX | (addr & UAT_HANDOFF_ADDR_MASK);
        *(volatile u64 *)(slot_pa + 8) = addr;
        slot_state = 2;
    } else {
        slot_state = 1;
    }

    /*
     * Real SPTM writes addr/size first, publishes state last, then orders the
     * handoff with an outer-shareable barrier. In EL2 we also clean to PoC so
     * the AGX firmware and UAT hardware see the slot update.
     */
    *(volatile u32 *)slot_pa = slot_state;
    clean_pt_range_poc((volatile u64 *)slot_pa, UAT_HANDOFF_SLOT_STRIDE);
    __asm__ volatile("dsb sy" ::: "memory");

    root->last[6] = slot_pa;
    root->last[7] = ((u64)slot_state << 32) | ready;
    return dead ? 0 : 2;
}

static bool_t uat_handoff_magic_valid(struct uat_c_root_state *root)
{
    u64 handoff = g_state.uat.gfx_handoff_pa;
    u64 magic;

    if (root->ctx_id >= 0x41U)
        return 1;

    if (!uat_looks_like_pa(handoff) ||
        g_state.uat.gfx_handoff_size < UAT_HANDOFF_MAGIC_FW_OFF + 8UL) {
        g_state.uat.violations++;
        root->last[6] = handoff;
        root->last[7] = g_state.uat.gfx_handoff_size;
        return 0;
    }

    magic = *(volatile u64 *)(handoff + UAT_HANDOFF_MAGIC_FW_OFF);
    if (magic != UAT_HANDOFF_MAGIC) {
        g_state.uat.violations++;
        root->last[6] = handoff + UAT_HANDOFF_MAGIC_FW_OFF;
        root->last[7] = magic;
        return 0;
    }

    return 1;
}

static inline bool_t uat_write64_ptr(u64 ptr, u64 value)
{
    u64 pa;
    if (!uat_resolve_data_pa(ptr, 1, &pa))
        return 0;
    *(volatile u64 *)pa = value;
    uat_clean_state_range_poc(pa, 8);
    return 1;
}

static inline bool_t uat_read16_ptr(u64 ptr, u16 *out)
{
    u64 pa;
    if (!uat_resolve_data_pa(ptr, 0, &pa))
        return 0;
    *out = *(volatile u16 *)pa;
    return 1;
}

static inline bool_t uat_read8_ptr(u64 ptr, u8 *out)
{
    u64 pa;
    if (!uat_resolve_data_pa(ptr, 0, &pa))
        return 0;
    *out = *(volatile u8 *)pa;
    return 1;
}

static inline bool_t uat_write16_ptr(u64 ptr, u16 value)
{
    u64 pa;
    if (!uat_resolve_data_pa(ptr, 1, &pa))
        return 0;
    *(volatile u16 *)pa = value;
    uat_clean_state_range_poc(pa, 2);
    return 1;
}

static inline bool_t uat_write8_ptr(u64 ptr, u8 value)
{
    u64 pa;
    if (!uat_resolve_data_pa(ptr, 1, &pa))
        return 0;
    *(volatile u8 *)pa = value;
    uat_clean_state_range_poc(pa, 1);
    return 1;
}

static inline u8 uat_read8_pa_default(u64 pa, u8 def)
{
    if (!uat_looks_like_pa(pa))
        return def;
    return *(volatile u8 *)pa;
}

static inline u64 uat_default_l1_mask(u64 shift)
{
    if (shift <= 36)
        return 0;
    if (shift >= 47)
        return 0x7ff000000000UL;
    return (((1UL << (shift - 36)) - 1UL) << 36) & 0x7ff000000000UL;
}

static inline void uat_set_defaults(void)
{
    struct uat_c_state *st = &g_state.uat;

    if (!st->vaddr_shift)
        st->vaddr_shift = UAT_DEFAULT_VADDR_SHIFT;
    if (!st->l1_index_mask)
        st->l1_index_mask = uat_default_l1_mask(st->vaddr_shift);
    if (!st->segment_limit)
        st->segment_limit = 0x40;
    if (!st->mapping_limit)
        st->mapping_limit = 0x100;
    if (!st->state_object_size)
        st->state_object_size = st->segment_limit * 0x10 + 0x250;
    if (!st->gfx_shared_l2_pa)
        st->gfx_shared_l2_pa = st->gfx_shared_region_pa;
    if (!st->raw_gfx_shared_l2_pa)
        st->raw_gfx_shared_l2_pa = st->gfx_shared_l2_pa;
    st->enabled = 1;
}

static inline u64 uat_selector2_state_pa(void)
{
    if (g_state.uat.mode != 1)
        return 0;
    if (!uat_looks_like_pa(g_state.uat.selector2_pa) ||
        !uat_looks_like_pa(g_state.uat.selector2_root_pa)) {
        g_state.uat.violations++;
        return 0;
    }
    return g_state.uat.selector2_pa;
}

static inline u64 uat_selector9_papt_va(void)
{
    u64 pa = 0;

    if (!is_kernel_va(g_state.uat.selector9_pa) ||
        !g_state.uat.raw_gfx_shared_l2_pa ||
        !guest_va_to_pa(g_state.uat.selector9_pa, 0, &pa) ||
        (pa & UAT_PTE_ADDR_MASK) != (g_state.uat.raw_gfx_shared_l2_pa & UAT_PTE_ADDR_MASK)) {
        g_state.uat.violations++;
        return 0;
    }
    return g_state.uat.selector9_pa;
}

static inline void uat_refresh_state_object(struct uat_c_root_state *root)
{
    u64 value;

    if (uat_read64_ptr(root->handle + UAT_STATE_ROOT0_OFF, &value))
        root->root0_pa = value;
    if (uat_read64_ptr(root->handle + UAT_STATE_ROOT1_OFF, &value))
        root->root1_pa = value;
    if (uat_read16_ptr(root->handle + UAT_STATE_CTX_ID_OFF, &root->ctx_id) &&
        uat_read8_ptr(root->handle, &root->type))
        return;
}

static inline void uat_record(u32 endpoint, u64 *regs, u64 root_pa, u64 slot_pa,
                              u64 before, u64 after, u64 rc)
{
    struct uat_c_state *st = &g_state.uat;
    u64 idx = st->recent_idx & (UAT_C_RECENT_SLOTS - 1);
    struct uat_c_recent_event *ev = &st->recent[idx];

    ev->seq = st->recent_idx;
    ev->endpoint = endpoint;
    ev->handle = regs[0];
    for (u32 i = 0; i < 5; i++)
        ev->regs[i] = regs[i];
    ev->root_pa = root_pa;
    ev->slot_pa = slot_pa;
    ev->before = before;
    ev->after = after;
    ev->rc = rc;
    st->recent_idx++;
    st->last_rc = rc;
}

static struct uat_c_root_state *uat_find_state(u64 handle, bool_t alloc)
{
    struct uat_c_root_state *free_slot = (struct uat_c_root_state *)0;
    bool_t selector2_shadow;

    if (!handle)
        return (struct uat_c_root_state *)0;

    selector2_shadow = handle == g_state.uat.selector2_pa &&
                       uat_looks_like_pa(g_state.uat.selector2_pa) &&
                       uat_looks_like_pa(g_state.uat.selector2_root_pa);

    for (u32 i = 0; i < UAT_C_MAX_STATES; i++) {
        struct uat_c_root_state *slot = &g_state.uat.roots[i];
        if (slot->used && slot->handle == handle) {
            uat_refresh_state_object(slot);
            return slot;
        }
        if (!slot->used && free_slot == (struct uat_c_root_state *)0)
            free_slot = slot;
    }

    /*
     * Selector 2 returns a firmware-owned UAT state object seeded before any
     * table-7 init_state call. Real SPTM can use that object immediately for
     * map_table/map/unmap; mirror that by importing it into the shadow root
     * table on first use instead of treating map_table as a no-op success.
     */
    if ((!alloc && !selector2_shadow) || free_slot == (struct uat_c_root_state *)0)
        return (struct uat_c_root_state *)0;

    for (u32 i = 0; i < sizeof(*free_slot); i++)
        ((volatile u8 *)free_slot)[i] = 0;
    free_slot->used = 1;
    free_slot->handle = handle;
    free_slot->ctx_id = UAT_C_CTX_NONE;
    uat_refresh_state_object(free_slot);
    if (selector2_shadow) {
        if (!free_slot->root1_pa)
            free_slot->root1_pa = g_state.uat.selector2_root_pa;
        if (!free_slot->type)
            free_slot->type = uat_read8_pa_default(handle, 8);
    }
    return free_slot;
}

static inline u64 uat_root_for_va(struct uat_c_root_state *root, u64 va)
{
    u64 shift = g_state.uat.vaddr_shift ? g_state.uat.vaddr_shift :
                UAT_DEFAULT_VADDR_SHIFT;
    if (((va >> shift) & 1UL) && root->root1_pa)
        return root->root1_pa;
    return root->root0_pa;
}

static inline u64 uat_l1_idx(u64 va)
{
    u64 mask = g_state.uat.l1_index_mask;
    if (!mask)
        mask = uat_default_l1_mask(g_state.uat.vaddr_shift ?
                                   g_state.uat.vaddr_shift :
                                   UAT_DEFAULT_VADDR_SHIFT);
    if (mask)
        return (va & mask) >> 36;
    return (va >> 36) & 0x7ffUL;
}

static inline u64 uat_l2_idx(u64 va) { return (va >> 25) & 0x7ffUL; }
static inline u64 uat_l3_idx(u64 va) { return (va >> 14) & 0x7ffUL; }

static bool_t uat_walk_slot(u64 root_pa, u64 va, u32 level,
                            u64 *slot_pa_out, u64 *before_out)
{
    volatile u64 *l1;
    volatile u64 *l2;
    u64 l1e, l2e;
    u64 slot_pa;

    if (!uat_looks_like_pa(root_pa))
        return 0;

    if (level == 1) {
        slot_pa = root_pa + uat_l1_idx(va) * 8;
        *slot_pa_out = slot_pa;
        *before_out = *(volatile u64 *)slot_pa;
        return 1;
    }

    l1 = (volatile u64 *)root_pa;
    l1e = l1[uat_l1_idx(va)];
    if ((l1e & 3UL) != UAT_TABLE_DESC)
        return 0;

    if (level == 2) {
        slot_pa = (l1e & UAT_TTE_ADDR_MASK) + uat_l2_idx(va) * 8;
        *slot_pa_out = slot_pa;
        *before_out = *(volatile u64 *)slot_pa;
        return 1;
    }

    l2 = (volatile u64 *)(l1e & UAT_TTE_ADDR_MASK);
    l2e = l2[uat_l2_idx(va)];
    if ((l2e & 3UL) != UAT_TABLE_DESC)
        return 0;

    slot_pa = (l2e & UAT_TTE_ADDR_MASK) + uat_l3_idx(va) * 8;
    *slot_pa_out = slot_pa;
    *before_out = *(volatile u64 *)slot_pa;
    return 1;
}

static inline void uat_write_slot(u64 slot_pa, u64 value)
{
    *(volatile u64 *)slot_pa = value;
    clean_pt_range_poc((volatile u64 *)slot_pa, 8);
}

static inline void uat_publish_mapped_data_page(struct uat_c_root_state *root,
                                                u64 pa)
{
    u64 page = pa & ARM_PTE_PAGE_MASK;
    u64 idx;

    /*
     * Real SPTM's UAT map path performs per-mapped-frame side effects in
     * addition to installing the leaf PTE. The important correctness effect for
     * this emulator is that data the AGX firmware will read is pushed through
     * the coprocessor-visible cache path, not just the 8-byte UAT PTE slot.
     *
     * Some UAT operations carry low/sentinel/non-DRAM values through the same
     * segment format. Do not run data-cache maintenance on those addresses:
     * EL2 can fault on e.g. PA 0 before XNU even boots.
     */
    if (!uat_looks_like_pa(page) || !ft_get_idx(page, &idx)) {
        root->last[6] = 0;
        root->last[7] = page;
        return;
    }

    sptm_coproc_cache_maint_data_page(page);
    uat_write8_ptr(root->handle + UAT_STATE_FLUSH_LEVEL_OFF, 1);
    root->last[6]++;
    root->last[7] = page;
}

static inline void uat_tlbi_ctx_if_bound(struct uat_c_root_state *root)
{
    (void)root;
}

static inline u64 uat_leaf_pte(struct uat_c_root_state *root, u64 pa, u64 options)
{
    u64 idx = ((options >> 8) & 2UL) |
              ((options & 3UL) << 2) |
              ((options >> 8) & 1UL);
    u64 attr = uat_attr_table[idx & 0xf];
    u64 perm = 3UL;
    u64 os_ng = ((root->type & 10U) != 0) ? 0 : 0x800UL;

    if (attr == 0xff)
        attr = 0;
    if (options & 8UL)
        perm = 0xbUL;
    if (options & 4UL)
        perm = 7UL;

    return os_ng |
           ((attr & 3UL) << 53) |
           (pa & UAT_PTE_ADDR_MASK) |
           perm |
           (((attr >> 2) & 3UL) << 6) |
           UAT_VALID_LEAF_BITS;
}

static bool_t uat_read_segment(u64 seglist_pa, u64 index, u64 *first, u64 *pages)
{
    u64 base = seglist_pa + index * 0x10UL;
    return uat_read64_ptr(base, first) &&
           uat_read64_ptr(base + 8, pages);
}

static bool_t uat_copy_segments_to_state(struct uat_c_root_state *root,
                                         u64 dst_off, u64 seglist_pa,
                                         u64 num_segs)
{
    u64 state_size = g_state.uat.state_object_size ?
                     g_state.uat.state_object_size :
                     ((g_state.uat.segment_limit ? g_state.uat.segment_limit : 0x40) *
                      0x10UL + 0x250UL);

    if (dst_off + num_segs * 0x10UL > state_size)
        return 0;

    for (u64 i = 0; i < num_segs; i++) {
        u64 first, pages;
        if (!uat_read_segment(seglist_pa, i, &first, &pages) ||
            !uat_write64_ptr(root->handle + dst_off + i * 0x10UL, first) ||
            !uat_write64_ptr(root->handle + dst_off + i * 0x10UL + 8, pages))
            return 0;
    }
    return 1;
}

static inline void uat_write_state_header(struct uat_c_root_state *root)
{
    u64 handle = root->handle;

    uat_write64_ptr(handle + UAT_STATE_ROOT0_OFF, root->root0_pa);
    uat_write64_ptr(handle + UAT_STATE_ROOT1_OFF, root->root1_pa);
    uat_write16_ptr(handle + UAT_STATE_CTX_ID_OFF, root->ctx_id);
}

static inline void uat_release_state_guard(struct uat_c_root_state *root, u8 guard)
{
    uat_write8_ptr(root->handle + UAT_STATE_GUARD_OFF, guard);
}

static inline void uat_write_idle_state(struct uat_c_root_state *root)
{
    uat_write_state_header(root);
    uat_release_state_guard(root, 2);
}

static void uat_write_map_state(struct uat_c_root_state *root, u8 guard)
{
    u64 handle = root->handle;

    uat_write_state_header(root);
    uat_write64_ptr(handle + UAT_STATE_WORK0_OFF, root->current_va);
    uat_write64_ptr(handle + UAT_STATE_WORK1_OFF, root->num_segs);
    uat_write64_ptr(handle + UAT_STATE_WORK2_OFF, root->current_seg);
    uat_write64_ptr(handle + UAT_STATE_WORK3_OFF, root->seg_offset);
    uat_write64_ptr(handle + UAT_STATE_OPTIONS_OFF, root->options);
    /*
     * BUG FIX 2026-07-05: do NOT write CTX_FLUSH_OFF (0x248) here. The map
     * seglist copy lives at MAP_SEGS_OFF (0x48); entry 32's first_pa is at
     * 0x48 + 32*0x10 = 0x248 == CTX_FLUSH_OFF. For any map with >=33 segments
     * this 0-write clobbered the 33rd segment's PA to 0 right after the copy,
     * which our old zero-leaf branch then turned into a UAT hole -> GPU FW data
     * abort at the corresponding VA (0xfffffc20c0130000). Real SPTM's map-begin
     * writes no such field; this write was spurious (CTX_FLUSH_OFF is write-only
     * in our emulator, never read).
     */
    uat_release_state_guard(root, guard);
}

static void uat_write_prepare_fw_unmap_state(struct uat_c_root_state *root,
                                             u8 guard, u64 changed)
{
    u64 handle = root->handle;

    uat_write_state_header(root);
    uat_write64_ptr(handle + UAT_STATE_WORK0_OFF, root->current_va);
    uat_write64_ptr(handle + UAT_STATE_WORK1_OFF, root->current_seg);
    uat_write64_ptr(handle + UAT_STATE_WORK2_OFF, root->num_segs);
    uat_write64_ptr(handle + UAT_STATE_WORK3_OFF, changed ? 1 : 0);
    uat_release_state_guard(root, guard);
}

static void uat_write_unmap_state(struct uat_c_root_state *root, u8 guard,
                                  u64 op_state)
{
    u64 handle = root->handle;

    uat_write_state_header(root);
    uat_write64_ptr(handle + UAT_STATE_WORK0_OFF, op_state);
    uat_write64_ptr(handle + UAT_STATE_WORK1_OFF, root->num_segs);
    uat_write64_ptr(handle + UAT_STATE_WORK2_OFF, root->current_seg);
    uat_write64_ptr(handle + UAT_STATE_WORK3_OFF, root->seg_offset);
    uat_write64_ptr(handle + UAT_STATE_OPTIONS_OFF, root->options);
    uat_release_state_guard(root, guard);
}

static u64 uat_map_pending(struct uat_c_root_state *root)
{
    u64 limit = g_state.uat.mapping_limit ? g_state.uat.mapping_limit : 0x100;
    u64 mapped = 0;

    while (root->current_seg < root->num_segs) {
        u64 first, pages;
        if (!uat_read_segment(root->seglist_pa, root->current_seg, &first, &pages)) {
            g_state.uat.violations++;
            root->state = 0;
            return 0;
        }

        while (root->seg_offset < pages) {
            u64 pa = first + root->seg_offset * UAT_C_PAGE_SIZE;
            u64 va = root->current_va;
            u64 root_pa = uat_root_for_va(root, va);
            u64 slot_pa = 0, before = 0, pte;

            if (!uat_walk_slot(root_pa, va, 3, &slot_pa, &before)) {
                g_state.uat.violations++;
                root->last[0] = root_pa;
                root->last[1] = va;
                root->last[2] = pa;
                root->last[3] = 3;
                root->state = 0;
                uat_write_idle_state(root);
                return 0;
            }

            pte = uat_leaf_pte(root, pa, root->options);
            if (before & 1UL) {
                g_state.uat.violations++;
                root->last[0] = root_pa;
                root->last[1] = va;
                root->last[2] = pa;
                root->last[3] = slot_pa;
                root->last[4] = before;
                root->last[5] = pte;
                root->state = 0;
                uat_write_map_state(root, 2);
                return 0;
            }
            if (!uat_looks_like_pa(pa)) {
                /*
                 * XNU can describe holes in GPU queue VA space with a zero
                 * backing address. Treat those as invalid leaves. Turning PA 0
                 * into a valid GPU translation makes AGX read physical low
                 * memory and trips SAPT at e.g. PA 0x600.
                 */
                uat_write_slot(slot_pa, 0);
                root->last[0] = root_pa;
                root->last[1] = va;
                root->last[2] = pa;
                root->last[3] = slot_pa;
                root->last[4] = before;
                root->last[5] = 0;
                root->last[6]++;
                root->last[7] = pa;

                root->current_va += UAT_C_PAGE_SIZE;
                root->seg_offset++;
                mapped++;
                if (mapped >= limit) {
                    uat_tlbi_ctx_if_bound(root);
                    root->state = 3;
                    uat_write_map_state(root, 3);
                    return 1;
                }
                continue;
            }
            uat_write_slot(slot_pa, pte);
            uat_sapt_grant_page(pa, root->options);
            uat_publish_mapped_data_page(root, pa);

            root->last[0] = root_pa;
            root->last[1] = va;
            root->last[2] = pa;
            root->last[3] = slot_pa;
            root->last[4] = before;
            root->last[5] = pte;

            root->current_va += UAT_C_PAGE_SIZE;
            root->seg_offset++;
            mapped++;
            if (mapped >= limit) {
                uat_tlbi_ctx_if_bound(root);
                root->state = 3;
                uat_write_map_state(root, 3);
                return 1;
            }
        }

        root->current_seg++;
        root->seg_offset = 0;
    }

    root->state = 0;
    uat_tlbi_ctx_if_bound(root);
    uat_write_map_state(root, 2);
    return 0;
}

static inline bool_t uat_fw_unmap_leaf_qualifies(u64 pte)
{
    u32 perm_bits = ((u32)(pte >> 4)) & 0xcU;
    u32 attr_hi = (u32)(pte >> 53);
    u32 attr_code = perm_bits | (attr_hi & 3U);

    if ((pte & 0x1cUL) != 0)
        return 0;
    return (perm_bits | (attr_hi & 2U)) == 2U ||
           (attr_code >= 5U && attr_code < 8U);
}

static u64 uat_prepare_fw_unmap_pending(struct uat_c_root_state *root)
{
    u64 limit = g_state.uat.mapping_limit ? g_state.uat.mapping_limit : 0x100;
    u64 walked = 0;
    u64 changed = root->options & 1UL;

    if (!uat_handoff_magic_valid(root)) {
        root->state = 0;
        root->options = 0;
        uat_write_prepare_fw_unmap_state(root, 2, changed);
        return 0;
    }

    while (root->current_seg < root->num_segs) {
        u64 cur = root->current_va + root->current_seg * UAT_C_PAGE_SIZE;
        u64 root_pa = uat_root_for_va(root, cur);
        u64 slot_pa = 0, before = 0, after = 0;

        if (!uat_walk_slot(root_pa, cur, 3, &slot_pa, &before)) {
            g_state.uat.violations++;
            root->last[0] = root_pa;
            root->last[1] = cur;
            root->last[2] = slot_pa;
            root->last[3] = before;
            root->state = 0;
            root->options = 0;
            uat_write_prepare_fw_unmap_state(root, 2, changed);
            return 0;
        }

        after = before;
        if ((before & 3UL) == 3UL && uat_fw_unmap_leaf_qualifies(before)) {
            after = before | UAT_FW_OWNED_BIT;
            uat_write_slot(slot_pa, after);
            changed = 1;
        }

        root->last[0] = root_pa;
        root->last[1] = cur;
        root->last[2] = slot_pa;
        root->last[3] = before;
        root->last[4] = after;
        root->last[5] = changed;

        root->current_seg++;
        walked++;
        if (root->current_seg != root->num_segs && walked >= limit) {
            root->state = 4;
            root->options = changed;
            uat_write_prepare_fw_unmap_state(root, 4, changed);
            return 1;
        }
    }

    root->state = 0;
    root->options = 0;
    uat_write_prepare_fw_unmap_state(root, 2, changed);
    if (!changed)
        return 0;

    __asm__ volatile("dsb oshst" ::: "memory");
    tlbi_vmalle1os();
    return uat_publish_fw_unmap_handoff(root, root->current_va,
                                        root->num_segs * UAT_C_PAGE_SIZE);
}

static u64 uat_unmap_pending(struct uat_c_root_state *root)
{
    u64 limit = g_state.uat.mapping_limit ? g_state.uat.mapping_limit : 0x100;
    u64 unmapped = 0;

    while (root->current_seg < root->num_segs) {
        u64 va, pages;
        if (!uat_read_segment(root->seglist_pa, root->current_seg, &va, &pages)) {
            g_state.uat.violations++;
            root->state = 0;
            uat_write_unmap_state(root, 2, 0);
            return 0;
        }

        while (root->seg_offset < pages) {
            u64 cur = va + root->seg_offset * UAT_C_PAGE_SIZE;
            u64 root_pa = uat_root_for_va(root, cur);
            u64 slot_pa = 0, before = 0;

            if (!uat_walk_slot(root_pa, cur, 3, &slot_pa, &before) ||
                !(before & 1UL)) {
                g_state.uat.violations++;
                root->last[0] = root_pa;
                root->last[1] = cur;
                root->last[2] = slot_pa;
                root->last[3] = before;
                root->state = 0;
                uat_write_unmap_state(root, 2, 0);
                return 0;
            }
            uat_sapt_release_page(before & UAT_PTE_ADDR_MASK);
            uat_write_slot(slot_pa, 0);

            root->last[0] = root_pa;
            root->last[1] = cur;
            root->last[2] = slot_pa;
            root->last[3] = before;

            root->seg_offset++;
            unmapped++;
            if (unmapped >= limit) {
                root->state = 5;
                uat_write_unmap_state(root, 5, 1);
                tlbi_vmalle1os();
                return 1;
            }
        }

        root->current_seg++;
        root->seg_offset = 0;
    }

    root->state = 0;
    uat_write_unmap_state(root, 2, 0);
    tlbi_vmalle1os();
    return 0;
}

static u64 uat_unmap_segments(struct uat_c_root_state *root, u64 seglist_pa,
                              u64 num_segs)
{
    if (num_segs == 0 ||
        num_segs > (g_state.uat.segment_limit ? g_state.uat.segment_limit : 0x40) ||
        !uat_copy_segments_to_state(root, UAT_STATE_UNMAP_SEGS_OFF,
                                    seglist_pa, num_segs)) {
        g_state.uat.violations++;
        return 0;
    }

    root->seglist_pa = root->handle + UAT_STATE_UNMAP_SEGS_OFF;
    root->num_segs = num_segs;
    root->current_seg = 0;
    root->seg_offset = 0;
    root->options = 0;
    root->state = 5;
    uat_write_unmap_state(root, 5, 1);
    return uat_unmap_pending(root);
}

static u64 uat_ep_init(u64 *regs)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 1);
    u64 root1 = 0xffffffffUL;

    if (root == (struct uat_c_root_state *)0) {
        g_state.uat.violations++;
        return 0;
    }

    root->type = uat_read8_pa_default(root->handle, 0);
    if ((root->type & 5U) == 0) {
        if (uat_looks_like_pa(regs[2]))
            root->type = 4;
        else if (regs[2] == 0xffffffffUL)
            root->type = 1;
        if (root->type & 5U)
            uat_write8_ptr(root->handle, root->type);
    }
    if ((root->type & 5U) == 0 ||
        !uat_looks_like_pa(regs[1]) ||
        (root->root0_pa != 0 && root->root0_pa != 0xffffffffUL) ||
        (root->type == 1 && regs[2] != 0xffffffffUL) ||
        (root->type == 4 && !uat_looks_like_pa(regs[2]))) {
        g_state.uat.violations++;
        return 0;
    }

    if (root->type == 4) {
        if (root->root1_pa != 0 && root->root1_pa != 0xffffffffUL) {
            g_state.uat.violations++;
            return 0;
        }
        root1 = regs[2];
    }

    root->root0_pa = regs[1];
    root->root1_pa = root1;
    root->ctx_id = UAT_C_CTX_NONE;
    root->state = 0;
    uat_write_idle_state(root);
    return 0;
}

static u64 uat_ep_destroy(u64 *regs)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    if (root == (struct uat_c_root_state *)0)
        return 0;
    if (root->ctx_id != UAT_C_CTX_NONE) {
        g_state.uat.violations++;
        return 0;
    }
    for (u32 i = 0; i < sizeof(*root); i++)
        ((volatile u8 *)root)[i] = 0;
    tlbi_vmalle1os();
    return 0;
}

static u64 uat_ep_map_table(u64 *regs, u64 *root_out, u64 *slot_out,
                            u64 *before_out, u64 *after_out)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    u64 va = regs[1];
    u32 level = (u32)regs[2];
    u64 table_pa = regs[3];
    u64 root_pa, slot_pa = 0, before = 0, after = 0;

    if (root == (struct uat_c_root_state *)0 || (level != 1 && level != 2) ||
        !uat_looks_like_pa(table_pa)) {
        g_state.uat.violations++;
        return 0;
    }

    root_pa = uat_root_for_va(root, va);
    if (!uat_walk_slot(root_pa, va, level, &slot_pa, &before)) {
        g_state.uat.violations++;
        return 0;
    }
    after = (table_pa & UAT_TTE_ADDR_MASK) | UAT_TABLE_DESC;
    if (before != 0) {
        g_state.uat.violations++;
        root->last[0] = root_pa;
        root->last[1] = va;
        root->last[2] = level;
        root->last[3] = slot_pa;
        root->last[4] = before;
        root->last[5] = after;
        *root_out = root_pa;
        *slot_out = slot_pa;
        *before_out = before;
        *after_out = after;
        return 0;
    }
    uat_write_slot(slot_pa, after);

    root->last[0] = root_pa;
    root->last[1] = va;
    root->last[2] = level;
    root->last[3] = slot_pa;
    root->last[4] = before;
    root->last[5] = after;
    *root_out = root_pa;
    *slot_out = slot_pa;
    *before_out = before;
    *after_out = after;
    return 0;
}

static u64 uat_ep_unmap_table(u64 *regs, u64 *root_out, u64 *slot_out,
                              u64 *before_out)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    u64 va = regs[1];
    u32 level = (u32)regs[2];
    u64 root_pa, slot_pa = 0, before = 0;

    if (root == (struct uat_c_root_state *)0 || (level != 1 && level != 2)) {
        g_state.uat.violations++;
        return 0;
    }

    root_pa = uat_root_for_va(root, va);
    if (!uat_walk_slot(root_pa, va, level, &slot_pa, &before)) {
        g_state.uat.violations++;
        return 0;
    }
    if ((before & 3UL) != UAT_TABLE_DESC) {
        g_state.uat.violations++;
        *root_out = root_pa;
        *slot_out = slot_pa;
        *before_out = before;
        return 0;
    }
    uat_write_slot(slot_pa, 0);
    tlbi_vmalle1os();

    root->last[0] = root_pa;
    root->last[1] = va;
    root->last[2] = level;
    root->last[3] = slot_pa;
    root->last[4] = before;
    *root_out = root_pa;
    *slot_out = slot_pa;
    *before_out = before;
    return 0;
}

static u64 uat_ep_map_begin(u64 *regs)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    u64 segs_pa = regs[2];
    u64 num_segs = regs[3];
    u64 options = regs[4];
    u64 idx = ((options >> 8) & 2UL) |
              ((options & 3UL) << 2) |
              ((options >> 8) & 1UL);

    if (root == (struct uat_c_root_state *)0 ||
        num_segs == 0 ||
        num_segs > (g_state.uat.segment_limit ? g_state.uat.segment_limit : 0x40) ||
        (options & UAT_OPTIONS_INVALID_MASK) ||
        uat_attr_table[idx & 0xf] == 0xff) {
        g_state.uat.violations++;
        if (root == (struct uat_c_root_state *)0)
            return 0;
    }
    if (!uat_copy_segments_to_state(root, UAT_STATE_MAP_SEGS_OFF,
                                    segs_pa, num_segs)) {
        g_state.uat.violations++;
        return 0;
    }

    root->current_va = regs[1];
    root->seglist_pa = root->handle + UAT_STATE_MAP_SEGS_OFF;
    root->num_segs = num_segs;
    root->current_seg = 0;
    root->seg_offset = 0;
    root->options = options;
    root->state = 3;
    uat_write8_ptr(root->handle + UAT_STATE_FLUSH_LEVEL_OFF, 0);
    uat_write_map_state(root, 3);
    return uat_map_pending(root);
}

static u64 uat_ep_prepare_fw_unmap_begin(u64 *regs)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    u64 va = regs[1];
    u64 pages = regs[2];

    if (root == (struct uat_c_root_state *)0 ||
        (va & (UAT_C_PAGE_SIZE - 1)) != 0 ||
        pages == 0 || pages >= UAT_MAX_VA_PAGES) {
        g_state.uat.violations++;
        return 0;
    }

    if (!uat_handoff_magic_valid(root))
        return 0;

    root->current_va = va;
    root->current_seg = 0;
    root->num_segs = pages;
    root->seg_offset = 0;
    root->options = 0;
    root->state = 4;
    uat_write_prepare_fw_unmap_state(root, 4, 0);
    return uat_prepare_fw_unmap_pending(root);
}

static u64 uat_ep_set_ctx_id(u64 *regs)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    u64 ctx = regs[1];
    u64 base, root1;
    u64 ttbr0, ttbr1;

    if (root == (struct uat_c_root_state *)0 || ctx >= 64 ||
        root->ctx_id != UAT_C_CTX_NONE ||
        !g_state.uat.gpu_region_pa) {
        g_state.uat.violations++;
        return 0;
    }

    root1 = root->root1_pa;
    base = g_state.uat.gpu_region_pa + ctx * 16UL;
    if ((root->type & 0xeU) == 0 ||
        !uat_looks_like_pa(root->root0_pa) || !uat_looks_like_pa(root1) ||
        *(volatile u64 *)base != 0 || *(volatile u64 *)(base + 8) != 0) {
        g_state.uat.violations++;
        return 0;
    }
    ttbr0 = (root->root0_pa & 0x3ffffffc000UL) |
            ((ctx & 0x7fffUL) << 48) | 1UL;
    ttbr1 = (root1 & 0x3ffffffc000UL) |
            ((ctx & 0xffffUL) << 48) | 1UL;

    uat_write_slot(base, ttbr0);
    uat_write_slot(base + 8, ttbr1);
    root->ctx_id = (u16)ctx;
    uat_write_idle_state(root);
    tlbi_vmalle1os();
    return 0;
}

static u64 uat_ep_remove_ctx_id(u64 *regs)
{
    struct uat_c_root_state *root = uat_find_state(regs[0], 0);
    if (root == (struct uat_c_root_state *)0)
        return 0;
    if (root->ctx_id == UAT_C_CTX_NONE) {
        g_state.uat.violations++;
        return 0;
    }
    if (root->ctx_id != UAT_C_CTX_NONE && g_state.uat.gpu_region_pa) {
        u64 base = g_state.uat.gpu_region_pa + (u64)root->ctx_id * 16UL;
        uat_write_slot(base, *(volatile u64 *)base & ~1UL);
        uat_write_slot(base + 8, *(volatile u64 *)(base + 8) & ~1UL);
    }
    root->ctx_id = UAT_C_CTX_NONE;
    uat_write_idle_state(root);
    tlbi_vmalle1os();
    return 0;
}

static u64 uat_ep_get_info(u64 *regs)
{
    u64 selector = regs[0];

    switch (selector) {
    case 0:
        return g_state.uat.mode;
    case 1:
        if (g_state.uat.mode == 0)
            return uat_looks_like_pa(g_state.uat.selector2_pa) ?
                   g_state.uat.selector2_pa : 0;
        return 0;
    case 2:
        return uat_selector2_state_pa();
    case 3:
        return g_state.uat.vaddr_shift ? g_state.uat.vaddr_shift :
               UAT_DEFAULT_VADDR_SHIFT;
    case 4:
        return g_state.uat.l1_index_mask ? g_state.uat.l1_index_mask :
               uat_default_l1_mask(g_state.uat.vaddr_shift ?
                                    g_state.uat.vaddr_shift :
                                    UAT_DEFAULT_VADDR_SHIFT);
    case 5:
        return g_state.uat.segment_limit ? g_state.uat.segment_limit : 0x40;
    case 6:
        return 0x1000000000UL;
    case 7:
        return 0x7000000000UL;
    case 8:
        return g_state.uat.state_object_size ? g_state.uat.state_object_size :
               ((g_state.uat.segment_limit ? g_state.uat.segment_limit : 0x40) *
                0x10UL + 0x250UL);
    case 9:
        return uat_selector9_papt_va();
    default:
        g_state.uat.violations++;
        return 0;
    }
}

bool_t uat_handle_table7(u32 endpoint, u64 *regs)
{
    u64 rc = 0;
    u64 root_pa = 0, slot_pa = 0, before = 0, after = 0;
    u64 saved_regs[5];
    struct uat_c_root_state *root;

    if (endpoint >= UAT_C_MAX_ENDPOINTS) {
        g_state.uat.fallthrough_calls++;
        return 0;
    }

    uat_set_defaults();
    g_state.uat.total_calls++;
    g_state.uat.ep_count[endpoint]++;
    for (u32 i = 0; i < 5; i++) {
        saved_regs[i] = regs[i];
        g_state.uat.last[i] = regs[i];
    }
    g_state.uat.last[5] = endpoint;

    switch (endpoint) {
    case UAT_FN_INIT_STATE:
        rc = uat_ep_init(regs);
        break;
    case UAT_FN_DESTROY_STATE:
        rc = uat_ep_destroy(regs);
        break;
    case UAT_FN_MAP_TABLE:
        rc = uat_ep_map_table(regs, &root_pa, &slot_pa, &before, &after);
        break;
    case UAT_FN_UNMAP_TABLE:
        rc = uat_ep_unmap_table(regs, &root_pa, &slot_pa, &before);
        after = 0;
        break;
    case UAT_FN_MAP_BEGIN:
        rc = uat_ep_map_begin(regs);
        break;
    case UAT_FN_MAP_CONTINUE:
        root = uat_find_state(regs[0], 0);
        rc = root ? uat_map_pending(root) : 0;
        if (!root)
            g_state.uat.violations++;
        break;
    case UAT_FN_PREP_FW_UNMAP_BEGIN:
        rc = uat_ep_prepare_fw_unmap_begin(regs);
        root = uat_find_state(saved_regs[0], 0);
        if (root) {
            root_pa = root->last[0];
            slot_pa = root->last[2];
            before = root->last[3];
            after = root->last[4];
        }
        break;
    case UAT_FN_PREP_FW_UNMAP_CONTINUE:
        root = uat_find_state(regs[0], 0);
        if (root && root->state == 4) {
            rc = uat_prepare_fw_unmap_pending(root);
            root_pa = root->last[0];
            slot_pa = root->last[2];
            before = root->last[3];
            after = root->last[4];
        } else {
            g_state.uat.violations++;
        }
        break;
    case UAT_FN_UNMAP_BEGIN:
        root = uat_find_state(regs[0], 0);
        if (root)
            rc = uat_unmap_segments(root, regs[1], regs[2]);
        else
            g_state.uat.violations++;
        break;
    case UAT_FN_UNMAP_CONTINUE:
        root = uat_find_state(regs[0], 0);
        rc = root ? uat_unmap_pending(root) : 0;
        if (!root)
            g_state.uat.violations++;
        break;
    case UAT_FN_SET_CTX_ID:
        rc = uat_ep_set_ctx_id(regs);
        break;
    case UAT_FN_REMOVE_CTX_ID:
        rc = uat_ep_remove_ctx_id(regs);
        break;
    case UAT_FN_GET_INFO:
        rc = uat_ep_get_info(regs);
        break;
    default:
        g_state.uat.fallthrough_calls++;
        return 0;
    }

    regs[0] = rc;
    g_state.uat.fast_path_calls++;
    g_state.fast_path_calls++;
    uat_record(endpoint, saved_regs, root_pa, slot_pa, before, after, rc);
    sev();
    return 1;
}
