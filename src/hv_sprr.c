/* SPDX-License-Identifier: MIT */

#include "hv_sprr.h"
#include "cpu_regs.h"
#include "heapblock.h"
#include "hv.h"
#include "malloc.h"
#include "memory.h"
#include "smp.h"
#include "string.h"
#include "utils.h"

#define HV_SPRR_NO_ACCESS (~0ULL)

// only 16K granule is supported, no Rosetta under this emulation
#define SPRR_PAGE_SHIFT 14
#define SPRR_PT_ENTRIES 2048
#define SPRR_OA_MASK    GENMASK(47, SPRR_PAGE_SHIFT)

#define SPRR_IDX_PXN    BIT(0)
#define SPRR_IDX_UXN    BIT(1)
#define SPRR_IDX_AP_EL0 BIT(2)
#define SPRR_IDX_AP_RO  BIT(3)

static u8 sprr_perm_nibble(u64 perm, u32 index)
{
    return (perm >> (index * 4)) & 0xf;
}

#define SPRR_WP_N_BUCKETS     4096
#define SPRR_N_CACHED_SHADOWS 256

bool hv_sprr_active = false;

void hv_sprr_set_active(bool active)
{
    printf("HV: emulated SPRR/GXF %s\n", active ? "enabled" : "disabled");
    hv_sprr_active = active;
}

static struct hv_sprr_cpu hv_sprr_cpus[MAX_CPUS];
static struct hv_sprr_shadow sprr_shadows[SPRR_N_CACHED_SHADOWS];
static u32 sprr_lru_clock;

static struct hv_sprr_cpu *hv_sprr_this(void)
{
    return &hv_sprr_cpus[smp_id()];
}

static const u8 sprr_lvl_off[4] = {47, 36, 25, 14};

static int sprr_start_level(u32 va_bits)
{
    for (int i = 0; i < 3; i++)
        if (va_bits > sprr_lvl_off[i])
            return i;
    return 3;
}

static struct sprr_wp_page *sprr_wp_hash[SPRR_WP_N_BUCKETS];

static struct sprr_wp_page **sprr_wp_bucket(u64 ipa)
{
    return &sprr_wp_hash[(ipa >> SPRR_PAGE_SHIFT) & (SPRR_WP_N_BUCKETS - 1)];
}

static struct sprr_wp_page *sprr_wp_find(u64 ipa)
{
    ipa &= ~(u64)(SZ_16K - 1);
    for (struct sprr_wp_page *wp = *sprr_wp_bucket(ipa); wp; wp = wp->hnext)
        if (wp->ipa == ipa)
            return wp;
    return NULL;
}

// memalign(16K, 16K) adds 16 bytes dlmalloc tracking which then grabs 32K so we'd be
// wasting almost 50% of the allocated memory. Let's build our own silly allocator for the
// tables instead since we'll have a *LOT* of those.
#define SPRR_TABLE_SIZE   (SPRR_PT_ENTRIES * sizeof(u64))
#define SPRR_CHUNK_TABLES 128

struct sprr_chunk {
    struct sprr_chunk *next;
    u64 base, end;
};

static struct sprr_chunk *sprr_chunks;
static void *sprr_free_tables;

static u64 *sprr_pool_alloc(void)
{
    if (!sprr_free_tables) {
        u64 size = SPRR_CHUNK_TABLES * SPRR_TABLE_SIZE;
        u8 *mem = heapblock_alloc_aligned(size, SZ_16K);
        struct sprr_chunk *chunk = malloc(sizeof(*chunk));

        chunk->base = (u64)mem;
        chunk->end = (u64)mem + size;
        chunk->next = sprr_chunks;
        sprr_chunks = chunk;

        hv_map_hw_ro(chunk->base, chunk->base, size);

        for (u32 i = 0; i < SPRR_CHUNK_TABLES; i++) {
            void *t = mem + i * SPRR_TABLE_SIZE;
            *(void **)t = sprr_free_tables;
            sprr_free_tables = t;
        }
    }

    void *t = sprr_free_tables;
    sprr_free_tables = *(void **)t;
    return t;
}

static void sprr_pool_release(u64 *t)
{
    *(void **)t = sprr_free_tables;
    sprr_free_tables = t;
}

static void sprr_wp_track(struct exc_info *ctx, struct sprr_mirror *mirror)
{
    struct sprr_wp_page *wp = sprr_wp_find(mirror->ipa);

    if (!wp) {
        u64 page = mirror->ipa & ~(u64)(SZ_16K - 1);
        if (hv_pt_set_writable(page, false) < 0) {
            printf("hv_sprr: cannot write-protect guest PT page at IPA 0x%lx, its shadow cannot be "
                   "kept in sync\n",
                   page);
            hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
            return;
        }
        wp = malloc(sizeof(*wp));
        memset(wp, 0, sizeof(*wp));
        wp->ipa = page;
        wp->hnext = *sprr_wp_bucket(page);
        *sprr_wp_bucket(page) = wp;
    }

    mirror->hnext = wp->mirrors;
    wp->mirrors = mirror;
}

static void sprr_wp_untrack(struct sprr_mirror *mirror)
{
    struct sprr_wp_page *wp = sprr_wp_find(mirror->ipa);
    if (!wp)
        return;

    for (struct sprr_mirror **p = &wp->mirrors; *p; p = &(*p)->hnext) {
        if (*p == mirror) {
            *p = mirror->hnext;
            break;
        }
    }

    if (wp->mirrors)
        return;

    hv_pt_set_writable(wp->ipa, true);
    for (struct sprr_wp_page **p = sprr_wp_bucket(wp->ipa); *p; p = &(*p)->hnext) {
        if (*p == wp) {
            *p = wp->hnext;
            break;
        }
    }
    free(wp);
}

bool hv_sprr_is_pt_page(u64 ipa)
{
    return sprr_wp_find(ipa) != NULL;
}

bool hv_sprr_is_shadow_page(u64 ipa)
{
    for (struct sprr_chunk *chunk = sprr_chunks; chunk; chunk = chunk->next)
        if (ipa >= chunk->base && ipa < chunk->end)
            return true;

    return false;
}

static u64 sprr_ipa_to_pa(u64 ipa)
{
    return hv_pt_walk(ipa) & SPRR_OA_MASK;
}

static u64 *sprr_alloc_table(void)
{
    u64 *t = sprr_pool_alloc();

    memset64(t, 0, SPRR_PT_ENTRIES * sizeof(u64));
    return t;
}

static struct sprr_mirror *sprr_mirror_table(struct exc_info *ctx, struct hv_sprr_shadow *sh,
                                             u64 ipa, u8 level, u64 va_base, u32 nents);
static void sprr_mirror_entry(struct exc_info *ctx, struct sprr_mirror *mirror, u32 i, u64 pa);

static void sprr_mirror_free(struct sprr_mirror *mirror)
{
    struct sprr_mirror *next;
    for (struct sprr_mirror *c = mirror->children; c; c = next) {
        next = c->sibling;
        sprr_mirror_free(c);
    }
    sprr_wp_untrack(mirror);
    sprr_pool_release(mirror->el);
    sprr_pool_release(mirror->gl);
    free(mirror);
}

static void sprr_drop_child(struct sprr_mirror *mirror, u32 i)
{
    for (struct sprr_mirror **p = &mirror->children; *p; p = &(*p)->sibling) {
        if ((*p)->idx == i) {
            struct sprr_mirror *c = *p;
            *p = c->sibling;
            sprr_mirror_free(c);
            return;
        }
    }
}

#define SPRR_R BIT(2)
#define SPRR_W BIT(1)
#define SPRR_X BIT(0)

/* clang-format off */
static const u8 sprr_el_rwx[16] = {
    0,               SPRR_R | SPRR_X, SPRR_R,          SPRR_R | SPRR_W,
    0,               SPRR_R | SPRR_X, SPRR_R,          0,
    0,               SPRR_X,          SPRR_R,          SPRR_R | SPRR_W,
    0,               SPRR_R | SPRR_X, SPRR_R,          SPRR_R | SPRR_W,
};

static const u8 sprr_gl_rwx[16] = {
    0,               0,               0,               0,
    SPRR_R | SPRR_X, SPRR_R | SPRR_X, SPRR_R | SPRR_X, SPRR_R | SPRR_X,
    SPRR_R,          SPRR_R,          SPRR_R,          SPRR_R,
    SPRR_R | SPRR_W, SPRR_R | SPRR_W, SPRR_R | SPRR_W, SPRR_R | SPRR_W,
};
/* clang-format on */

// the value that cannot be expressed are over-granted: arbitrary decision since a missing access
// would be a fault the guest cannot handle but a missing fault might be used for e.g. copy-on-write
// and break as well. doesn't matter in practise because XNU never seems to use any of these.
static u64 sprr_leaf_bits(u8 k, u8 u)
{
    u64 bits = 0;

    if (!(k & SPRR_X))
        bits |= PTE_PXN;
    if (!(u & SPRR_X))
        bits |= PTE_UXN;
    if (u & SPRR_R)
        bits |= PTE_AP_EL0;
    if (!((k | u) & SPRR_W))
        bits |= PTE_AP_RO;

    return bits;
}

static void sprr_leaf_init(struct hv_sprr_shadow *sh)
{
    for (u32 guarded = 0; guarded < 2; guarded++) {
        const u8 *tbl = guarded ? sprr_gl_rwx : sprr_el_rwx;

        for (u32 index = 0; index < SPRR_N_INDICES; index++) {
            u8 k = tbl[sprr_perm_nibble(sh->perm_el1, index)];
            u8 u = tbl[sprr_perm_nibble(sh->perm_el0, index)];

            // no access from either kernel or userspace -> only way to express it is to just not
            // map it
            if (!k && !u) {
                sh->leaf[guarded][index] = HV_SPRR_NO_ACCESS;
                continue;
            }

            sh->leaf[guarded][index] = sprr_leaf_bits(k, u);
        }
    }
}

static void sprr_mirror_entry(struct exc_info *ctx, struct sprr_mirror *mirror, u32 i, u64 pa)
{
    struct hv_sprr_shadow *sh = mirror->owner;
    u64 d = read64(pa + i * sizeof(u64));

    if (mirror->level < 3 && (mirror->el[i] & PTE_VALID) &&
        FIELD_GET(PTE_TYPE, mirror->el[i]) == PTE_TABLE)
        sprr_drop_child(mirror, i);

    if (!(d & PTE_VALID)) {
        mirror->el[i] = mirror->gl[i] = 0;
        return;
    }

    if (mirror->level < 3 && FIELD_GET(PTE_TYPE, d) == PTE_TABLE) {
        u64 va = mirror->va_base + ((u64)i << sprr_lvl_off[mirror->level]);

        // without SPRR these restrict everything below the entry, with SPRR we have no idea what
        // they do. XNU does set them, so ignoring them potentially over-grants.
        if (d & PTE_TABLE_PERM)
            printf("hv_sprr: L%d[%d] (VA 0x%lx) table attrs 0x%lx ignored\n", mirror->level, i, va,
                   FIELD_GET(PTE_TABLE_PERM, d));

        if (!hv_pt_is_ram(d & SPRR_OA_MASK)) {
            printf("hv_sprr: L%d[%d] (VA 0x%lx) points at non-RAM IPA 0x%lx, leaving unmapped\n",
                   mirror->level, i, va, d & SPRR_OA_MASK);
            mirror->el[i] = mirror->gl[i] = 0;
            return;
        }
        struct sprr_mirror *c =
            sprr_mirror_table(ctx, sh, d & SPRR_OA_MASK, mirror->level + 1, va, SPRR_PT_ENTRIES);
        c->idx = i;
        c->sibling = mirror->children;
        mirror->children = c;
        mirror->el[i] = ((u64)c->el & SPRR_OA_MASK) | PTE_VALID | FIELD_PREP(PTE_TYPE, PTE_TABLE);
        mirror->gl[i] = ((u64)c->gl & SPRR_OA_MASK) | PTE_VALID | FIELD_PREP(PTE_TYPE, PTE_TABLE);
        return;
    }

    u32 index = ((d & PTE_AP_RO) ? SPRR_IDX_AP_RO : 0) | ((d & PTE_AP_EL0) ? SPRR_IDX_AP_EL0 : 0) |
                ((d & PTE_UXN) ? SPRR_IDX_UXN : 0) | ((d & PTE_PXN) ? SPRR_IDX_PXN : 0);
    u64 base = d & ~(u64)(PTE_AP_RO | PTE_AP_EL0 | PTE_PXN | PTE_UXN);
    u64 pel = sh->leaf[0][index];
    u64 pgl = sh->leaf[1][index];
    if (pel == HV_SPRR_NO_ACCESS)
        mirror->el[i] = 0;
    else
        mirror->el[i] = base | pel;

    if (pgl == HV_SPRR_NO_ACCESS)
        mirror->gl[i] = 0;
    else
        mirror->gl[i] = base | pgl;
}

static struct sprr_mirror *sprr_mirror_table(struct exc_info *ctx, struct hv_sprr_shadow *sh,
                                             u64 ipa, u8 level, u64 va_base, u32 nents)
{
    struct sprr_mirror *mirror = malloc(sizeof(*mirror));
    memset(mirror, 0, sizeof(*mirror));

    mirror->owner = sh;
    mirror->ipa = ipa;
    mirror->va_base = va_base;
    mirror->level = level;
    mirror->nents = nents;
    mirror->el = sprr_alloc_table();
    mirror->gl = sprr_alloc_table();
    sprr_wp_track(ctx, mirror);

    u64 pa = sprr_ipa_to_pa(ipa);
    for (u32 i = 0; i < nents; i++)
        sprr_mirror_entry(ctx, mirror, i, pa);

    return mirror;
}

// if a guest tries to edit its own pagetables from EL0/GL0 something is terribly wrong
void hv_sprr_pt_writer_check(struct exc_info *ctx, u64 ipa, u64 far)
{
    if (FIELD_GET(SPSR_M, ctx->spsr) != SPSR_M_EL0)
        return;

    printf("hv_sprr: EL0 write to a write-protected PT page: IPA 0x%lx VA 0x%lx PC 0x%lx "
           "(mirror outlived the page table)\n",
           ipa, far, ctx->elr);
    hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
}

void hv_sprr_pt_updated(struct exc_info *ctx, u64 ipa, u64 bytes)
{
    struct sprr_wp_page *wp = sprr_wp_find(ipa);
    if (!wp)
        return;

    u64 first = ipa & ~7UL, end = ipa + bytes;
    u64 pa = sprr_ipa_to_pa(wp->ipa);

    struct sprr_mirror *next;
    for (struct sprr_mirror *mirror = wp->mirrors; mirror; mirror = next) {
        next = mirror->hnext;
        for (u64 a = first; a < end; a += 8)
            if (a >= mirror->ipa && (a - mirror->ipa) / sizeof(u64) < mirror->nents)
                sprr_mirror_entry(ctx, mirror, (a - mirror->ipa) / sizeof(u64), pa);
    }

    // we must not do TLB maintenance here because XNU relies on running on TLBs only while
    // the actual PTEs have changed early when it retypes its pages RO. wait for XNU to issue
    // the TLB
}

static void sprr_write_hw_ttbr(int ttbr_idx, u64 val)
{
    if (ttbr_idx == 0)
        msr(SYS_TTBR0_EL12, val);
    else
        msr(SYS_TTBR1_EL12, val);
}

static void sprr_set_cur_shadow(struct hv_sprr_cpu *cpu, int ttbr_idx, struct hv_sprr_shadow *sh)
{
    if (cpu->cur[ttbr_idx] == sh)
        return;

    if (cpu->cur[ttbr_idx])
        cpu->cur[ttbr_idx]->active &= ~BIT(smp_id());
    if (sh)
        sh->active |= BIT(smp_id());

    cpu->cur[ttbr_idx] = sh;
}

static void hv_sprr_switch_tables(struct hv_sprr_cpu *cpu)
{
    if (!cpu->sprr_en)
        return;
    for (int i = 0; i < 2; i++) {
        struct hv_sprr_shadow *sh = cpu->cur[i];
        if (!sh)
            continue;
        u64 top_pa = (u64)(cpu->guarded ? sh->top->gl : sh->top->el);
        // the el/gl trees share the guest ASID but have different permissions while CPUs run in
        // different worlds -> disallow CnP
        sprr_write_hw_ttbr(i, (cpu->guest_ttbr[i] & ~(SPRR_OA_MASK | TTBR_CNP)) |
                                  (top_pa & SPRR_OA_MASK));
    }

    // the trees have different perms but the same ASID so we need to invalidate here
    sysop("dsb ishst");
    sysop("tlbi vmalle1");
    sysop("dsb nsh");
    sysop("isb");
}

static struct hv_sprr_shadow *sprr_get_shadow(struct exc_info *ctx, struct hv_sprr_cpu *cpu,
                                              int ttbr_idx, u64 guest_ttbr, u32 va_bits)
{
    struct hv_sprr_shadow *slot = NULL;

    if (va_bits < SPRR_PAGE_SHIFT || va_bits > 48 || (guest_ttbr & TTBR_BADDR & (SZ_16K - 1)) ||
        !hv_pt_is_ram(guest_ttbr & SPRR_OA_MASK)) {
        printf("hv_sprr: unsupported TTBR%d root 0x%lx (%d VA bits)\n", ttbr_idx, guest_ttbr,
               va_bits);
        hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
        return NULL;
    }

    for (int i = 0; i < SPRR_N_CACHED_SHADOWS; i++) {
        struct hv_sprr_shadow *sh = &sprr_shadows[i];
        if (!sh->guest_ttbr) {
            if (!slot || slot->guest_ttbr)
                slot = sh;
            continue;
        }
        if (sh->ttbr_idx == ttbr_idx && sh->va_bits == va_bits &&
            ((sh->guest_ttbr ^ guest_ttbr) & SPRR_OA_MASK) == 0 &&
            sh->perm_el0 == cpu->sprr_perm_el0 && sh->perm_el1 == cpu->sprr_perm_el1) {
            sh->lru = ++sprr_lru_clock;
            return sh;
        }
        if (sh->active)
            continue;
        if (!slot || (slot->guest_ttbr && sh->lru < slot->lru))
            slot = sh;
    }

    if (!slot) {
        printf("hv_sprr: shadow cache exhausted\n");
        hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
        return NULL;
    }

    if (slot->guest_ttbr)
        sprr_mirror_free(slot->top);

    int start = sprr_start_level(va_bits);
    slot->guest_ttbr = guest_ttbr;
    slot->va_bits = va_bits;
    slot->ttbr_idx = ttbr_idx;
    slot->perm_el0 = cpu->sprr_perm_el0;
    slot->perm_el1 = cpu->sprr_perm_el1;
    sprr_leaf_init(slot);
    slot->lru = ++sprr_lru_clock;
    slot->top =
        sprr_mirror_table(ctx, slot, guest_ttbr & SPRR_OA_MASK, start,
                          ttbr_idx ? 0UL - BIT(va_bits) : 0, 1u << (va_bits - sprr_lvl_off[start]));

    return slot;
}

static bool sprr_mmu_on(void)
{
    return mrs(SYS_SCTLR_EL12) & SCTLR_M;
}

static void sprr_load_shadow(struct exc_info *ctx, struct hv_sprr_cpu *cpu, int ttbr_idx)
{
    u64 tcr = mrs(SYS_TCR_EL12);
    u64 tg = ttbr_idx ? FIELD_GET(TCR_TG1, tcr) : FIELD_GET(TCR_TG0, tcr);
    u64 tsz = ttbr_idx ? FIELD_GET(TCR_T1SZ, tcr) : FIELD_GET(TCR_T0SZ, tcr);

    sprr_set_cur_shadow(cpu, ttbr_idx, NULL);
    if (tcr & (ttbr_idx ? TCR_EPD1 : TCR_EPD0))
        return;
    if (tg != (ttbr_idx ? TCR_TG1_16K : TCR_TG0_16K)) {
        printf("hv_sprr: unsupported TTBR%d granule in TCR 0x%lx\n", ttbr_idx, tcr);
        hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
        return;
    }
    sprr_set_cur_shadow(cpu, ttbr_idx,
                        sprr_get_shadow(ctx, cpu, ttbr_idx, cpu->guest_ttbr[ttbr_idx], 64 - tsz));
}

static void sprr_reload_shadows(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    u64 tcr = mrs(SYS_TCR_EL12);

    if (tcr & (TCR_HA | TCR_HD)) {
        printf("hv_sprr: TCR 0x%lx enabled HW AF/dirty updates\n", tcr);
        hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
    }

    for (int i = 0; i < 2; i++)
        sprr_load_shadow(ctx, cpu, i);
}

static void hv_sprr_build(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    if (!cpu->sprr_en)
        return;
    sprr_reload_shadows(ctx, cpu);
    hv_sprr_switch_tables(cpu);
}

static void hv_sprr_activate(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    cpu->guest_ttbr[0] = mrs(SYS_TTBR0_EL12);
    cpu->guest_ttbr[1] = mrs(SYS_TTBR1_EL12);

    hv_write_hcr(mrs(HCR_EL2) | HCR_TTLB);

    printf("hv_sprr[%d]: SPRR on: PERM_EL0 0x%lx PERM_EL1 0x%lx TTBR 0x%lx/0x%lx MMU %s\n",
           smp_id(), cpu->sprr_perm_el0, cpu->sprr_perm_el1, cpu->guest_ttbr[0], cpu->guest_ttbr[1],
           sprr_mmu_on() ? "on" : "off");

    if (sprr_mmu_on())
        hv_sprr_build(ctx, cpu);
}

static void sprr_release_shadows(struct hv_sprr_cpu *cpu)
{
    sprr_set_cur_shadow(cpu, 0, NULL);
    sprr_set_cur_shadow(cpu, 1, NULL);
}

static void hv_sprr_deactivate(struct hv_sprr_cpu *cpu)
{
    sprr_release_shadows(cpu);
    for (int i = 0; i < 2; i++)
        sprr_write_hw_ttbr(i, cpu->guest_ttbr[i]);

    hv_write_hcr(mrs(HCR_EL2) & ~HCR_TTLB);

    sysop("dsb ishst");
    sysop("tlbi vmalle1");
    sysop("dsb nsh");
    sysop("isb");
}

static void hv_sprr_rebuild(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    if (!cpu->sprr_en)
        return;
    if (sprr_mmu_on())
        hv_sprr_build(ctx, cpu);
}

static bool sprr_shadows_active(struct hv_sprr_cpu *cpu)
{
    return cpu->sprr_en && sprr_mmu_on();
}

static u64 sprr_read_ttbr(struct hv_sprr_cpu *cpu, int ttbr_idx)
{
    if (!sprr_shadows_active(cpu))
        return ttbr_idx ? mrs(SYS_TTBR1_EL12) : mrs(SYS_TTBR0_EL12);

    return cpu->guest_ttbr[ttbr_idx];
}

static void sprr_write_ttbr(struct exc_info *ctx, struct hv_sprr_cpu *cpu, int ttbr_idx, u64 val)
{
    cpu->guest_ttbr[ttbr_idx] = val;

    if (!sprr_shadows_active(cpu)) {
        sprr_write_hw_ttbr(ttbr_idx, val);
        return;
    }

    sprr_load_shadow(ctx, cpu, ttbr_idx);
    hv_sprr_switch_tables(cpu);
}

static void sprr_write_tcr(struct exc_info *ctx, struct hv_sprr_cpu *cpu, u64 val)
{
    u64 old = mrs(SYS_TCR_EL12);

    msr(SYS_TCR_EL12, val);
    if ((old ^ val) &
        (TCR_TG0 | TCR_TG1 | TCR_T0SZ | TCR_T1SZ | TCR_EPD0 | TCR_EPD1 | TCR_HA | TCR_HD))
        hv_sprr_rebuild(ctx, cpu);
}

static void sprr_write_sctlr(struct exc_info *ctx, struct hv_sprr_cpu *cpu, u64 val)
{
    // no idea what this would do together with SPRR so just disallow it
    if (val & SCTLR_WXN) {
        printf("hv_sprr: guest enabled SCTLR_EL1.WXN (0x%lx)\n", val);
        hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
    }

    // The shadow has to be installed before the guest's MMU goes live. hv_sprr_build is a
    // no-op with SPRR still off, in which case hv_sprr_activate builds instead.
    if ((val & SCTLR_M) && !sprr_mmu_on()) {
        printf("hv_sprr[%d]: guest MMU on: TCR 0x%lx TTBR 0x%lx/0x%lx SPRR %s\n", smp_id(),
               mrs(SYS_TCR_EL12), cpu->guest_ttbr[0], cpu->guest_ttbr[1],
               cpu->sprr_en ? "on" : "off");
        hv_sprr_build(ctx, cpu);
    }
    msr(SYS_SCTLR_EL12, val);
}

static void sprr_drop_asid(u64 asid)
{
    for (int i = 0; i < SPRR_N_CACHED_SHADOWS; i++) {
        struct hv_sprr_shadow *sh = &sprr_shadows[i];

        if (!sh->guest_ttbr || sh->active)
            continue;
        if (FIELD_GET(TTBR_ASID, sh->guest_ttbr) != asid)
            continue;

        sprr_mirror_free(sh->top);
        memset(sh, 0, sizeof(*sh));
    }
}

#define TLBI(crm, op2)                                                                             \
    case SYSREG_ISS(sys_reg(1, 0, 8, crm, op2)):                                                   \
        __asm__ volatile("sys #0, c8, c" #crm ", #" #op2 ", %0" ::"r"(wval) : "memory");           \
        break;

static bool hv_sprr_handle_tlbi(u64 reg, u64 wval)
{
    // first just replay the instruction that was trapped
    switch (reg) {
        TLBI(1, 0) // VMALLE1OS
        TLBI(1, 1) // VAE1OS
        TLBI(1, 2) // ASIDE1OS
        TLBI(1, 3) // VAAE1OS
        TLBI(1, 5) // VALE1OS
        TLBI(1, 7) // VAALE1OS
        TLBI(2, 1) // RVAE1IS
        TLBI(2, 3) // RVAAE1IS
        TLBI(2, 5) // RVALE1IS
        TLBI(2, 7) // RVAALE1IS
        TLBI(3, 0) // VMALLE1IS
        TLBI(3, 1) // VAE1IS
        TLBI(3, 2) // ASIDE1IS
        TLBI(3, 3) // VAAE1IS
        TLBI(3, 5) // VALE1IS
        TLBI(3, 7) // VAALE1IS
        TLBI(5, 1) // RVAE1OS
        TLBI(5, 3) // RVAAE1OS
        TLBI(5, 5) // RVALE1OS
        TLBI(5, 7) // RVAALE1OS
        TLBI(6, 1) // RVAE1
        TLBI(6, 3) // RVAAE1
        TLBI(6, 5) // RVALE1
        TLBI(6, 7) // RVAALE1
        TLBI(7, 0) // VMALLE1
        TLBI(7, 1) // VAE1
        TLBI(7, 2) // ASIDE1
        TLBI(7, 3) // VAAE1
        TLBI(7, 5) // VALE1
        TLBI(7, 7) // VAALE1

        default:
            printf("hv_sprr: unhandled TLBI op0=1 op1=0 CRn=8 CRm=%ld op2=%ld\n",
                   FIELD_GET(ESR_ISS_MSR_CRm, reg), FIELD_GET(ESR_ISS_MSR_OP2, reg));
            return false;
    }

    // if XNU drops an ASID we must drop our shadow tables since it might just hand back
    // the memory to userspace soon
    switch (reg) {
        case SYSREG_ISS(sys_reg(1, 0, 8, 1, 2)): // ASIDE1OS
        case SYSREG_ISS(sys_reg(1, 0, 8, 3, 2)): // ASIDE1IS
        case SYSREG_ISS(sys_reg(1, 0, 8, 7, 2)): // ASIDE1
            sprr_drop_asid(FIELD_GET(TTBR_ASID, wval));
            break;
    }

    return true;
}

// called from hv_handle_msr which also tries to handle some TLBIs and used to skip those if true
bool hv_sprr_traps_tlbi(void)
{
    return hv_sprr_active && hv_sprr_this()->sprr_en;
}

bool hv_sprr_handle_msr(struct exc_info *ctx, u64 reg, u32 rt, bool is_read)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    if (!hv_sprr_active || !cpu->sprr_en)
        return false;

    ctx->regs[31] = 0;

    if (!is_read && FIELD_GET(ESR_ISS_MSR_OP0, reg) == 1 && FIELD_GET(ESR_ISS_MSR_CRn, reg) == 8)
        return hv_sprr_handle_tlbi(reg, ctx->regs[rt]);

    return false;
}

#define SWAP_HW(cpu, reg, field)                                                                   \
    do {                                                                                           \
        u64 _t = _mrs(sr_tkn(reg));                                                                \
        _msr(sr_tkn(reg), (cpu)->bank.field);                                                      \
        (cpu)->bank.field = _t;                                                                    \
    } while (0)

static void hv_sprr_world_swap(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    u64 sp = ctx->sp[1];
    ctx->sp[1] = cpu->bank.sp_el1;
    cpu->bank.sp_el1 = sp;

    SWAP_HW(cpu, SYS_VBAR_EL12, vbar);
    SWAP_HW(cpu, SYS_SPSR_EL12, spsr);
    SWAP_HW(cpu, SYS_ELR_EL12, elr);
    SWAP_HW(cpu, SYS_ESR_EL12, esr);
    SWAP_HW(cpu, SYS_FAR_EL12, far);
    SWAP_HW(cpu, SYS_AFSR1_EL12, afsr1);
}

static void hv_gxf_undef(struct exc_info *ctx)
{
    msr(SYS_ESR_EL12, 0x02000000UL);
    msr(SYS_SPSR_EL12, ctx->spsr);
    msr(SYS_ELR_EL12, ctx->elr - 4);

    ctx->elr = mrs(SYS_VBAR_EL12) + 0x400;
    ctx->spsr = (ctx->spsr | SPSR_D | SPSR_A | SPSR_I | SPSR_F) & ~SPSR_M;
    ctx->spsr |= FIELD_PREP(SPSR_M, SPSR_M_EL1H);
}

static bool hv_gxf_genter(struct exc_info *ctx, u8 imm, bool locked)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();
    u64 link_pstate = ctx->spsr;
    u64 link_pc = ctx->elr;

    if (FIELD_GET(SPSR_M, link_pstate) == SPSR_M_EL0) {
        hv_gxf_undef(ctx);
        return true;
    }

    // the only thing here that is not per-CPU state is the first-time printf below.
    if (!locked && !cpu->n_genter)
        return false;

    // genter from GL is weird but allowed ¯\_(ツ)_/¯
    bool from_guarded = cpu->guarded;

    if (!from_guarded)
        hv_sprr_world_swap(ctx, cpu);

    msr(SYS_VBAR_EL12, cpu->vbar_gl1);
    msr(SYS_SPSR_EL12, link_pstate);
    msr(SYS_ELR_EL12, link_pc);
    msr(SYS_ESR_EL12, HV_GXF_ESR_GENTER | FIELD_PREP(HV_HVC_GENTER_IMM, imm));
    cpu->elr_gl1 = link_pc;
    cpu->spsr_gl1 = link_pstate;
    if (from_guarded)
        cpu->aspsr_gl1 |= ASPSR_GUARDED;
    else
        cpu->aspsr_gl1 &= ~ASPSR_GUARDED;

    if (!cpu->n_genter++)
        printf("hv_sprr[%d]: first genter #%d from 0x%lx -> 0x%lx\n", smp_id(), imm, link_pc,
               cpu->gxf_enter);

    if (!from_guarded) {
        cpu->guarded = true;
        hv_sprr_switch_tables(cpu);
    }

    ctx->elr = cpu->gxf_enter;
    ctx->spsr = (link_pstate | SPSR_D | SPSR_A | SPSR_I | SPSR_F) & ~SPSR_M;
    // genter automatically sets SPSel = 1
    ctx->spsr |= FIELD_PREP(SPSR_M, SPSR_M_EL1H);
    return true;
}

static bool hv_gxf_gexit(struct exc_info *ctx, bool locked)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();
    static bool warned_nested;

    if (!cpu->guarded)
        return false;

    if (!locked && (!cpu->n_gexit || ((cpu->aspsr_gl1 & ASPSR_GUARDED) && !warned_nested)))
        return false;

    u64 ret_pc = cpu->elr_gl1;
    u64 ret_pstate = cpu->spsr_gl1;

    if (!cpu->n_gexit++)
        printf("hv_sprr[%d]: first gexit -> 0x%lx (ASPSR 0x%lx)\n", smp_id(), ret_pc,
               cpu->aspsr_gl1);

    if ((cpu->aspsr_gl1 & ASPSR_GUARDED) && !warned_nested) {
        warned_nested = true;
        printf("hv_sprr[%d]: gexit #%ld keeps the world (ASPSR 0x%lx), SP_EL1 stays 0x%lx\n",
               smp_id(), cpu->n_gexit, cpu->aspsr_gl1, ctx->sp[1]);
    }

    if (!(cpu->aspsr_gl1 & ASPSR_GUARDED)) {
        hv_sprr_world_swap(ctx, cpu);
        cpu->guarded = false;
        hv_sprr_switch_tables(cpu);
    }

    ctx->elr = ret_pc;
    ctx->spsr = ret_pstate;
    return true;
}

#define GL1_BANKED(hwreg, field)                                                                   \
    if (is_read)                                                                                   \
        rval = cpu->guarded ? _mrs(sr_tkn(hwreg)) : cpu->bank.field;                               \
    else if (cpu->guarded)                                                                         \
        _msr(sr_tkn(hwreg), wval);                                                                 \
    else                                                                                           \
        cpu->bank.field = wval;

static bool hv_sprr_emulate_sysreg(struct exc_info *ctx, u32 vreg, bool is_read, u32 rt,
                                   bool locked)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    ctx->regs[31] = 0;
    u64 wval = ctx->regs[rt];
    u64 rval = 0;

    switch (vreg) {
        case HV_VREG_SPRR_CONFIG_EL1:
            if (is_read) {
                rval = cpu->sprr_config;
            } else {
                if (!locked)
                    return false;
                bool en = wval & SPRR_CONFIG_EN;
                bool was_en = cpu->sprr_en;
                cpu->sprr_config = wval;
                cpu->sprr_en = en;
                if (en && !was_en)
                    hv_sprr_activate(ctx, cpu);
                else if (!en && was_en)
                    hv_sprr_deactivate(cpu);
            }
            break;
        case HV_VREG_GXF_CONFIG_EL1:
            if (is_read)
                rval = cpu->gxf_en ? GXF_CONFIG_EN : 0;
            else {
                if (!locked)
                    return false;
                if ((wval & GXF_CONFIG_EN) && !cpu->gxf_en)
                    printf("hv_sprr[%d]: GXF on: enter 0x%lx abort 0x%lx vbar_gl1 0x%lx\n",
                           smp_id(), cpu->gxf_enter, cpu->gxf_abort, cpu->vbar_gl1);
                cpu->gxf_en = wval & GXF_CONFIG_EN;
            }
            break;
        case HV_VREG_GXF_STATUS_EL1:
            if (is_read)
                rval = cpu->guarded ? GXF_STATUS_GUARDED : 0;
            break;
        case HV_VREG_GXF_ENTER_EL1:
            if (is_read)
                rval = cpu->gxf_enter;
            else
                cpu->gxf_enter = wval;
            break;
        case HV_VREG_GXF_ABORT_EL1:
            if (is_read)
                rval = cpu->gxf_abort;
            else
                cpu->gxf_abort = wval;
            break;
        // XNU rewrites these with the value they already hold on all the time but we only care
        // if it writes a new value which would change the way we need to shadow perms
        case HV_VREG_SPRR_PERM_EL0:
            if (is_read) {
                rval = cpu->sprr_perm_el0;
            } else if (wval != cpu->sprr_perm_el0) {
                if (!locked)
                    return false;
                printf("hv_sprr[%d]: SPRR_PERM_EL0 0x%lx -> 0x%lx\n", smp_id(), cpu->sprr_perm_el0,
                       wval);
                cpu->sprr_perm_el0 = wval;
                hv_sprr_rebuild(ctx, cpu);
            }
            break;
        case HV_VREG_SPRR_PERM_EL1:
            if (is_read) {
                rval = cpu->sprr_perm_el1;
            } else if (wval != cpu->sprr_perm_el1) {
                if (!locked)
                    return false;
                printf("hv_sprr[%d]: SPRR_PERM_EL1 0x%lx -> 0x%lx\n", smp_id(), cpu->sprr_perm_el1,
                       wval);
                cpu->sprr_perm_el1 = wval;
                hv_sprr_rebuild(ctx, cpu);
            }
            break;
        case HV_VREG_TPIDR_GL1:
            if (is_read)
                rval = cpu->tpidr_gl1;
            else
                cpu->tpidr_gl1 = wval;
            break;
        case HV_VREG_VBAR_GL1:
            if (is_read) {
                rval = cpu->guarded ? mrs(SYS_VBAR_EL12) : cpu->bank.vbar;
            } else {
                cpu->vbar_gl1 = wval;
                if (cpu->guarded)
                    msr(SYS_VBAR_EL12, wval);
                else
                    cpu->bank.vbar = wval;
            }
            break;
        case HV_VREG_ASPSR_GL1:
            if (is_read)
                rval = cpu->aspsr_gl1;
            else
                cpu->aspsr_gl1 = wval;
            break;
        case HV_VREG_ASPSR_EL1:
            if (is_read)
                rval = cpu->aspsr_el1;
            else
                cpu->aspsr_el1 = wval;
            break;
        // no idea what this is, so just replay any stored value back
        case HV_VREG_SPRR_UMPRR_EL1:
            if (is_read)
                rval = cpu->sprr_umprr;
            else
                cpu->sprr_umprr = wval;
            break;
        case HV_VREG_SPSR_GL1:
            GL1_BANKED(SYS_SPSR_EL12, spsr);
            if (!is_read && cpu->guarded)
                cpu->spsr_gl1 = wval;
            break;
        case HV_VREG_ELR_GL1:
            GL1_BANKED(SYS_ELR_EL12, elr);
            if (!is_read && cpu->guarded)
                cpu->elr_gl1 = wval;
            break;
        case HV_VREG_TTBR0_EL1:
        case HV_VREG_TTBR1_EL1: {
            int ttbr_idx = vreg == HV_VREG_TTBR1_EL1;
            if (is_read) {
                rval = sprr_read_ttbr(cpu, ttbr_idx);
            } else {
                if (!locked)
                    return false;
                sprr_write_ttbr(ctx, cpu, ttbr_idx, wval);
            }
            break;
        }
        case HV_VREG_TCR_EL1:
            if (is_read) {
                rval = mrs(SYS_TCR_EL12);
            } else {
                if (!locked)
                    return false;
                sprr_write_tcr(ctx, cpu, wval);
            }
            break;
        case HV_VREG_SCTLR_EL1:
            if (is_read) {
                rval = mrs(SYS_SCTLR_EL12);
            } else {
                if (!locked)
                    return false;
                sprr_write_sctlr(ctx, cpu, wval);
            }
            break;
        case HV_VREG_ESR_GL1:
            GL1_BANKED(SYS_ESR_EL12, esr);
            break;
        case HV_VREG_FAR_GL1:
            GL1_BANKED(SYS_FAR_EL12, far);
            break;
        case HV_VREG_AFSR1_GL1:
            GL1_BANKED(SYS_AFSR1_EL12, afsr1);
            break;
        default:
            if (locked)
                printf("hv_sprr: unknown vreg %d\n", vreg);
            return false;
    }

    if (is_read)
        ctx->regs[rt] = rval;
    return true;
}

bool hv_hvc_dispatch_unlocked(struct exc_info *ctx, u16 imm)
{
    if (!hv_sprr_active)
        return false;

    if (imm & HV_HVC_SYSREG_FLAG)
        return hv_sprr_emulate_sysreg(ctx, FIELD_GET(HV_HVC_SYSREG_VREG, imm),
                                      imm & HV_HVC_SYSREG_DIR, FIELD_GET(HV_HVC_SYSREG_RT, imm),
                                      false);

    if ((imm & HV_HVC_GENTER_MASK) == HV_HVC_GENTER_BASE) {
        if (!hv_gxf_genter(ctx, FIELD_GET(HV_HVC_GENTER_IMM, imm), false))
            return false;
    } else if (imm == HV_HVC_GEXIT) {
        if (!hv_gxf_gexit(ctx, false))
            return false;
    } else {
        return false;
    }

    hv_set_spsr(ctx->spsr);
    hv_set_elr(ctx->elr);
    msr(SP_EL1, ctx->sp[1]);
    return true;
}

bool hv_hvc_dispatch(struct exc_info *ctx, u16 imm)
{
    if (!hv_sprr_active)
        return false;

    if (imm & HV_HVC_SYSREG_FLAG)
        return hv_sprr_emulate_sysreg(ctx, FIELD_GET(HV_HVC_SYSREG_VREG, imm),
                                      imm & HV_HVC_SYSREG_DIR, FIELD_GET(HV_HVC_SYSREG_RT, imm),
                                      true);

    if ((imm & HV_HVC_GENTER_MASK) == HV_HVC_GENTER_BASE)
        return hv_gxf_genter(ctx, FIELD_GET(HV_HVC_GENTER_IMM, imm), true);

    if (imm == HV_HVC_GEXIT)
        return hv_gxf_gexit(ctx, true);

    return false;
}
