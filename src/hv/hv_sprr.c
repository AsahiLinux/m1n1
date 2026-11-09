/* SPDX-License-Identifier: GPL-2.0-or-later */

#include "hv_sprr.h"
#include "cpu_regs.h"
#include "hv.h"
#include "malloc.h"
#include "memory.h"
#include "smp.h"
#include "string.h"
#include "utils.h"
#include "xnuboot.h"

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

#define SPRR_VECTOR_VA          0xffffffffffffc000UL
#define SPRR_VECTOR_STRIDE      0x80
#define SPRR_VECTOR_TYPE        GENMASK(1, 0)
#define SPRR_VECTOR_TYPE_SYNC   0
#define SPRR_VECTOR_TYPE_IRQ    1
#define SPRR_VECTOR_TYPE_FIQ    2
#define SPRR_VECTOR_TYPE_SERROR 3
extern const u8 hv_sprr_vectors[SZ_16K];

static_assert(HV_VREG_MAX - 1 <= FIELD_GET(HV_HVC_SYSREG_VREG, HV_HVC_SYSREG_VREG),
              "Virtual register IDs must fit in the HVC immediate");

static struct hv_sprr_cpu hv_sprr_cpus[MAX_CPUS];
static struct hv_sprr_shadow sprr_shadows[SPRR_N_CACHED_SHADOWS];
static u32 sprr_lru_clock;

static struct hv_sprr_cpu *hv_sprr_this(void)
{
    return &hv_sprr_cpus[smp_id()];
}

static bool sprr_guarded(struct hv_sprr_cpu *cpu)
{
    return cpu->context != HV_SPRR_XNU;
}

/*
 * XNU and SPTM run at EL1/GL1 but we want to pretend they are actually running at
 * EL2/GL2. cL4 runs at EL1 which already looks like GL1 in SPSR so there's nothing
 * we need to change there.
 */
static u64 sprr_virtual_pstate(struct hv_sprr_cpu *cpu, u64 pstate)
{
    if (cpu->context == HV_SPRR_CL4)
        return pstate;

    switch (pstate & SPSR_M) {
        case SPSR_M_EL1T:
            return (pstate & ~SPSR_M) | SPSR_M_EL2T;
        case SPSR_M_EL1H:
            return (pstate & ~SPSR_M) | SPSR_M_EL2H;
        default:
            return pstate;
    }
}

static u64 sprr_physical_pstate(u64 pstate)
{
    switch (pstate & SPSR_M) {
        case SPSR_M_EL2T:
            return (pstate & ~SPSR_M) | SPSR_M_EL1T;
        case SPSR_M_EL2H:
            return (pstate & ~SPSR_M) | SPSR_M_EL1H;
        default:
            return pstate;
    }
}

static void sprr_prepare_cpu(struct hv_sprr_cpu *cpu)
{
    if (cpu->initialized)
        return;

    struct hv_sprr_mmu *mmu = cpu->mmu;
    mmu->sctlr = mrs(SYS_SCTLR_EL12);
    mmu->tcr = mrs(SYS_TCR_EL12);
    mmu->mair = mrs(SYS_MAIR_EL12);
    mmu->cpacr = mrs(CPACR_EL12);
    mmu->smcr = mrs(SYS_SMCR_EL12);
    mmu->cntkctl = mrs(CNTKCTL_EL12);
    mmu->guest_ttbr[0] = mrs(SYS_TTBR0_EL12);
    mmu->guest_ttbr[1] = mrs(SYS_TTBR1_EL12);
    cpu->initialized = true;
}

static u64 apple_timer_now(void)
{
    return mrs(SYS_IMP_APL_CNTVCT_ALIAS_EL0);
}

u64 *hv_sprr_mdscr(void)
{
    return &hv_sprr_this()->mmu->mdscr;
}

bool hv_sprr_timer_pending(void)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    if (hv_sptm_mode != SPTM_EMULATION)
        return false;
    if (!(cpu->shadow[HV_VREG_APL_CNTV_CTL_EL0] & CNTx_CTL_ENABLE))
        return false;
    if (cpu->shadow[HV_VREG_APL_CNTV_CTL_EL0] & CNTx_CTL_IMASK)
        return false;

    return (s64)(cpu->timer_deadline - apple_timer_now()) <= 0;
}

void hv_sprr_timer_arm(void)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    if (hv_sptm_mode != SPTM_EMULATION)
        return;
    if (!(cpu->shadow[HV_VREG_APL_CNTV_CTL_EL0] & CNTx_CTL_ENABLE))
        return;
    if (cpu->shadow[HV_VREG_APL_CNTV_CTL_EL0] & CNTx_CTL_IMASK)
        return;

    /* Check if the guest's timer has already expired */
    s64 apple_delta = cpu->timer_deadline - apple_timer_now();
    if (apple_delta <= 0) {
        hv_update_fiq();
        return;
    }

    /* Scale the guest's Apple timer (24 MHz on M4 Pro) to host timer ticks (1GHz on M4 Pro) */
    u64 host_ticks = DIV_ROUND_UP(apple_delta * mrs(CNTFRQ_EL0), mrs(SYS_IMP_APL_CNTFRQ_EL0));
    u64 host_now = mrs(CNTPCT_EL0);
    s64 host_remaining = mrs(CNTP_CVAL_EL0) - host_now;

    /* Make sure we don't postpone m1n1's timer */
    if (host_remaining <= 0)
        return;
    if (host_ticks >= (u64)host_remaining)
        return;
    msr(CNTP_CVAL_EL0, host_now + host_ticks);
    sysop("isb");
}

static const u8 sprr_protection_regs[] = {
    HV_VREG_CTRR_C_LWR_EL1,     HV_VREG_CTRR_C_UPR_EL1,     HV_VREG_CTRR_C_CTL_EL1,
    HV_VREG_CTRR_D_LWR_EL1,     HV_VREG_CTRR_D_UPR_EL1,     HV_VREG_CTRR_D_CTL_EL1,
    HV_VREG_CTXR_A_LWR_EL1,     HV_VREG_CTXR_A_UPR_EL1,     HV_VREG_CTXR_A_CTL_EL1,
    HV_VREG_CTXR_B_LWR_EL1,     HV_VREG_CTXR_B_UPR_EL1,     HV_VREG_CTXR_B_CTL_EL1,
    HV_VREG_CTXR_C_LWR_EL1,     HV_VREG_CTXR_C_UPR_EL1,     HV_VREG_CTXR_C_CTL_EL1,
    HV_VREG_CTXR_D_LWR_EL1,     HV_VREG_CTXR_D_UPR_EL1,     HV_VREG_CTXR_D_CTL_EL1,
    HV_VREG_CTRR_A_CTL_EL1,     HV_VREG_CTRR_B_CTL_EL1,     HV_VREG_ACC_CTRR_A_CTL_EL2,
    HV_VREG_ACC_CTRR_B_CTL_EL2, HV_VREG_ACC_CTRR_C_CTL_EL2, HV_VREG_ACC_CTRR_D_CTL_EL2,
    HV_VREG_ACC_CTXR_A_CTL_EL2, HV_VREG_ACC_CTXR_B_CTL_EL2, HV_VREG_ACC_CTXR_C_CTL_EL2,
    HV_VREG_ACC_CTXR_D_CTL_EL2,
};

static void sprr_init_cpu(int i)
{
    struct hv_sprr_cpu *cpu = &hv_sprr_cpus[i];

    cpu->mmu = &cpu->mmu_el20;
    cpu->mmu_el20.apctl = APCTL_ENABLE_EL1;
    cpu->timer_deadline = 0;
    memset(cpu->shadow, 0, sizeof(cpu->shadow));

    /* SPTM either panics or gets stuck in a polling loop if any bit here isn't set */
    cpu->shadow[HV_VREG_HCR_EL2] = HCR_RW | HCR_E2H | HCR_APK | HCR_API;
    cpu->shadow[HV_VREG_APSTS_EL1] = 1;

    /* SPTM expects CTRR to be enabled and locked */
    cpu->shadow[HV_VREG_CTRR_A_CTL_EL1] = 0x8000000000000001;
    cpu->shadow[HV_VREG_CTRR_B_CTL_EL1] = 0x8000000000000001;
    cpu->shadow[HV_VREG_ACC_CTRR_A_CTL_EL2] = 0x8000000000000001;
    cpu->shadow[HV_VREG_ACC_CTRR_B_CTL_EL2] = 0x8000000000000001;
    cpu->shadow[HV_VREG_ACC_CTRR_C_CTL_EL2] = 0x8000000000000001;
    cpu->shadow[HV_VREG_ACC_CTRR_D_CTL_EL2] = 0x8000000000000001;

    /*
     * This is another set of CTRR registers and presumably these values mean
     * at least enabled and locked as well. SPTM will panic if it finds anything
     * different in here.
     */
    cpu->shadow[HV_VREG_ACC_CTXR_A_CTL_EL2] = 0xc000000000aa019a;
    cpu->shadow[HV_VREG_ACC_CTXR_B_CTL_EL2] = 0xc0000000009a02aa;
    cpu->shadow[HV_VREG_ACC_CTXR_C_CTL_EL2] = 0xc000000000aa026a;
    cpu->shadow[HV_VREG_ACC_CTXR_D_CTL_EL2] = 0xc000000000aa02a9;
}

void hv_sprr_init_secondary(int cpu)
{
    for (u32 i = 0; i < ARRAY_SIZE(sprr_protection_regs); i++)
        hv_sprr_cpus[cpu].shadow[sprr_protection_regs[i]] =
            hv_sprr_cpus[boot_cpu_idx].shadow[sprr_protection_regs[i]];
}

#define SCTRL_PAC_BITS (SCTLR_EnIA | SCTLR_EnIB | SCTLR_EnDA | SCTLR_EnDB)

static void sprr_update_pac(u64 pstate)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    if (hv_sptm_mode != SPTM_EMULATION)
        return;

    u64 enable = 0;
    if ((pstate & SPSR_M) == SPSR_M_EL0)
        enable = APCTL_ENABLE_EL0;
    else
        enable = APCTL_ENABLE_EL1;

    /*
     * On real hardware, APCTL enables an additional key for the selected exception level.
     * Since we can't emulate that we just enable all keys in SCTRL which looks the same
     * to the guest since the keys are opaque anyway and all that matters is that some key
     * is used and that PAC is enabled.
     */
    u64 pac = cpu->mmu->sctlr & SCTRL_PAC_BITS;
    if ((cpu->mmu->apctl & APCTL_APPLE_MODE) && (cpu->mmu->apctl & enable))
        pac |= SCTRL_PAC_BITS;

    u64 sctlr = mrs(SYS_SCTLR_EL12);
    sctlr &= ~SCTRL_PAC_BITS;
    sctlr |= pac;
    msr(SYS_SCTLR_EL12, sctlr);
    sysop("isb");
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
static u64 sprr_pool_base, sprr_pool_top;

void hv_sprr_set_pool(u64 base, u64 size)
{
    sprr_pool_base = base;
    sprr_pool_top = base + size;
}

static u64 *sprr_pool_alloc(void)
{
    if (!sprr_free_tables) {
        u64 size = SPRR_CHUNK_TABLES * SPRR_TABLE_SIZE;
        if (sprr_pool_top - sprr_pool_base < size)
            panic("hv_sprr: shadow pool exhausted");
        sprr_pool_top -= size;
        u8 *mem = (u8 *)sprr_pool_top;
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

#define SPRR_COMMPAGE_VA            0x0000000fffffc000UL
#define SPRR_COMMPAGE_USER_TIMEBASE 0x90
#define SPRR_COMMPAGE_CONT_HWCLOCK  0x91
#define SPRR_COMMPAGE_xPRR_MODE     0x10c
static struct {
    u64 ipa;
    u8 *data;
} sprr_commpage;

bool hv_sprr_is_commpage(u64 ipa)
{
    if (hv_sptm_mode != SPTM_EMULATION)
        return false;
    if (!sprr_commpage.data)
        return false;
    if (sprr_commpage.ipa != ALIGN_DOWN(ipa, SZ_16K))
        return false;
    return true;
}

void hv_sprr_commpage_updated(u64 ipa, u64 bytes)
{
    u64 off = ipa - sprr_commpage.ipa;
    u64 end = off + bytes;
    u64 value[4] = {0};

    if (bytes > sizeof(value))
        panic("hv_sprr: unsupported commpage store size");
    memcpy(value, (void *)(sprr_ipa_to_pa(sprr_commpage.ipa) + off), bytes);

    if (off <= SPRR_COMMPAGE_USER_TIMEBASE && SPRR_COMMPAGE_USER_TIMEBASE < end)
        ((u8 *)value)[SPRR_COMMPAGE_USER_TIMEBASE - off] = 0;
    if (off <= SPRR_COMMPAGE_CONT_HWCLOCK && SPRR_COMMPAGE_CONT_HWCLOCK < end)
        ((u8 *)value)[SPRR_COMMPAGE_CONT_HWCLOCK - off] = 0;
    if (off <= SPRR_COMMPAGE_xPRR_MODE && SPRR_COMMPAGE_xPRR_MODE < end)
        ((u8 *)value)[SPRR_COMMPAGE_xPRR_MODE - off] = 0;

    u64 dst = (u64)sprr_commpage.data + off;
    switch (bytes) {
        case 1:
            write8(dst, (u8)value[0]);
            break;
        case 2:
            write16(dst, (u16)value[0]);
            break;
        case 4:
            write32(dst, (u32)value[0]);
            break;
        case 8:
            write64(dst, value[0]);
            break;
        default:
            memcpy((void *)dst, value, bytes);
            break;
    }
}

static u64 sprr_commpage_map(u8 level, u64 descriptor)
{
    u64 ipa = descriptor & SPRR_OA_MASK;

    if (level != 3)
        panic("hv_sprr: commpage not at level 3");
    if (sprr_commpage.data && sprr_commpage.ipa != ipa)
        panic("hv_sprr: commpage IPA changed from 0x%lx to 0x%lx", sprr_commpage.ipa, ipa);

    if (!sprr_commpage.data) {
        sprr_commpage.ipa = ipa;
        u8 *data = (u8 *)sprr_alloc_table(); /* not actually a table but just a SZ_16K page */
        if (hv_pt_set_writable(ipa, false) < 0)
            panic("hv_sprr: can't protect commpage");

        memcpy(data, (void *)sprr_ipa_to_pa(ipa), SZ_16K);
        data[SPRR_COMMPAGE_USER_TIMEBASE] = 0;
        data[SPRR_COMMPAGE_CONT_HWCLOCK] = 0;
        data[SPRR_COMMPAGE_xPRR_MODE] = 0;

        sprr_commpage.data = data;
    }

    return (descriptor & ~SPRR_OA_MASK) | (u64)sprr_commpage.data;
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

static void sprr_shadow_free(struct hv_sprr_shadow *sh)
{
    sprr_mirror_free(sh->top);

    for (int i = 0; i < 4; i++)
        if (sh->vector_tables[i])
            sprr_pool_release(sh->vector_tables[i]);

    memset(sh, 0, sizeof(*sh));
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

static bool pte_contains_vector_page(struct sprr_mirror *mirror, u64 va)
{
    struct hv_sprr_shadow *sh = mirror->owner;

    /* We only need the vector page for TTBR1 / the kernel's address space */
    if (sh->ttbr_idx != 1)
        return false;

    /* Check if this entry (which may a table) covers the target address for our vector page */
    if (va != ALIGN_DOWN(SPRR_VECTOR_VA, BIT(sprr_lvl_off[mirror->level])))
        return false;

    return true;
}

static u64 sprr_vector_entry(struct hv_sprr_shadow *sh, u8 level)
{
    if (level < 3) {
        u64 **table = &sh->vector_tables[level + 1];
        if (!*table)
            *table = sprr_alloc_table();
        u32 index = (SPRR_VECTOR_VA >> sprr_lvl_off[level + 1]) & (SPRR_PT_ENTRIES - 1);
        (*table)[index] = sprr_vector_entry(sh, level + 1);
        return (u64)*table | PTE_VALID | PTE_TYPE;
    }

    u64 mair = sh->mair;
    for (int attr = 0; attr < 8; attr++) {
        u8 value = mair >> (8 * attr);
        if (value == 0xff) /* Normal Memory, Write-back, XS=0, usually at attr = 0 */
            return (u64)hv_sprr_vectors | PTE_VALID | PTE_TYPE | PTE_ACCESS | PTE_AP_RO | PTE_UXN |
                   PTE_SH_IS | PTE_MAIR_IDX(attr);
    }

    panic("hv_sprr: no normal-memory MAIR slot for vector page");
}

static void sprr_mirror_entry(struct exc_info *ctx, struct sprr_mirror *mirror, u32 i, u64 pa)
{
    struct hv_sprr_shadow *sh = mirror->owner;
    u64 d = read64(pa + i * sizeof(u64));
    u64 va = mirror->va_base + ((u64)i << sprr_lvl_off[mirror->level]);

    if (pte_contains_vector_page(mirror, va) && (d & PTE_VALID) && mirror->level == 3)
        panic("hv_sprr: guest mapping collides with exception vector VA 0x%lx", SPRR_VECTOR_VA);

    if (mirror->level < 3 && (mirror->el[i] & PTE_VALID) &&
        FIELD_GET(PTE_TYPE, mirror->el[i]) == PTE_TABLE)
        sprr_drop_child(mirror, i);

    if (!(d & PTE_VALID)) {
        u64 entry = 0;

        /*
         * Inject a page with custom exception vectors if this entry covers the target address.
         * sprr_vector_entry will build the required tables if we're not already at the last level.
         */
        if (pte_contains_vector_page(mirror, va))
            entry = sprr_vector_entry(sh, mirror->level);

        mirror->el[i] = mirror->gl[i] = entry;
        return;
    }

    if (mirror->level < 3 && FIELD_GET(PTE_TYPE, d) == PTE_TABLE) {
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
    else {
        u64 descriptor = base | pel;
        if (!sh->el10 && sh->ttbr_idx == 0 &&
            va == ALIGN_DOWN(SPRR_COMMPAGE_VA, BIT(sprr_lvl_off[mirror->level])))
            descriptor = sprr_commpage_map(mirror->level, descriptor);
        mirror->el[i] = descriptor;
    }

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
    if (!cpu->mmu->sprr_en)
        return;
    for (int i = 0; i < 2; i++) {
        struct hv_sprr_shadow *sh = cpu->cur[i];
        if (!sh)
            continue;
        u64 top_pa = (u64)(sprr_guarded(cpu) ? sh->top->gl : sh->top->el);
        // the el/gl trees share the guest ASID but have different permissions while CPUs run in
        // different worlds -> disallow CnP
        sprr_write_hw_ttbr(i, (cpu->mmu->guest_ttbr[i] & ~(SPRR_OA_MASK | TTBR_CNP)) |
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
    u64 mair = cpu->mmu->mair;
    bool el10 = cpu->mmu == &cpu->mmu_el10;
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
            sh->perm_el0 == cpu->mmu->sprr_perm_el0 && sh->perm_el1 == cpu->mmu->sprr_perm_el1 &&
            sh->mair == mair && sh->el10 == el10) {
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
        sprr_shadow_free(slot);

    int start = sprr_start_level(va_bits);
    slot->guest_ttbr = guest_ttbr;
    slot->va_bits = va_bits;
    slot->ttbr_idx = ttbr_idx;
    slot->perm_el0 = cpu->mmu->sprr_perm_el0;
    slot->perm_el1 = cpu->mmu->sprr_perm_el1;
    slot->mair = mair;
    slot->el10 = el10;
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

static void sprr_update_vbar(struct hv_sprr_cpu *cpu)
{
    u64 vbar;

    if (cpu->mmu->sprr_en) {
        if (sprr_mmu_on())
            vbar = SPRR_VECTOR_VA;
        else
            vbar = (u64)hv_sprr_vectors;
    } else {
        /*
         * We can't easily inject a page if we don't own the guest's pagetables.
         * Without SPRR we have to be in XNU context here.
         */
        vbar = cpu->exc[HV_SPRR_XNU].vbar;
    }
    msr(SYS_VBAR_EL12, vbar);
}

static void sprr_load_shadow(struct exc_info *ctx, struct hv_sprr_cpu *cpu, int ttbr_idx)
{
    u64 tcr = cpu->mmu->tcr;
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
    sprr_set_cur_shadow(
        cpu, ttbr_idx,
        sprr_get_shadow(ctx, cpu, ttbr_idx, cpu->mmu->guest_ttbr[ttbr_idx], 64 - tsz));
}

static void sprr_reload_shadows(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    u64 tcr = cpu->mmu->tcr;

    if (tcr & (TCR_HA | TCR_HD)) {
        printf("hv_sprr: TCR 0x%lx enabled HW AF/dirty updates\n", tcr);
        hv_exc_proxy(ctx, START_HV, HV_PANIC, NULL);
    }

    for (int i = 0; i < 2; i++)
        sprr_load_shadow(ctx, cpu, i);
}

static void hv_sprr_build(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    if (!cpu->mmu->sprr_en)
        return;
    sprr_reload_shadows(ctx, cpu);
    hv_sprr_switch_tables(cpu);
}

static void hv_sprr_activate(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    if (sprr_guarded(cpu))
        panic("hv_sprr: enabling SPRR in guarded mode is unsupported");

    cpu->mmu->mair = mrs(SYS_MAIR_EL12);
    cpu->mmu->tcr = mrs(SYS_TCR_EL12);
    cpu->mmu->guest_ttbr[0] = mrs(SYS_TTBR0_EL12);
    cpu->mmu->guest_ttbr[1] = mrs(SYS_TTBR1_EL12);

    hv_write_hcr(mrs(HCR_EL2) | HCR_TTLB);

    if (sprr_mmu_on())
        hv_sprr_build(ctx, cpu);

    /*
     * Start trapping all exception entries and returns now that SPRR is on and we're now
     * able to inject a page to the guest to forward all exceptions to EL2. We need to update
     * our shadows of the exception register here since these will now be used instead of the
     * real hardware ones.
     * Note that we must be in HV_SPRR_XNU here since that's the only unguarded context
     */
    cpu->exc[HV_SPRR_XNU].spsr = sprr_virtual_pstate(cpu, mrs(SYS_SPSR_EL12));
    cpu->exc[HV_SPRR_XNU].elr = mrs(SYS_ELR_EL12);
    cpu->exc[HV_SPRR_XNU].esr = mrs(SYS_ESR_EL12);
    cpu->exc[HV_SPRR_XNU].far = mrs(SYS_FAR_EL12);
    cpu->exc[HV_SPRR_XNU].afsr1 = mrs(SYS_AFSR1_EL12);
    sprr_update_vbar(cpu);
    msr(SYS_HFGITR_EL2, mrs(SYS_HFGITR_EL2) | HFGITR_ERET);
    sysop("isb");
}

static void sprr_release_shadows(struct hv_sprr_cpu *cpu)
{
    sprr_set_cur_shadow(cpu, 0, NULL);
    sprr_set_cur_shadow(cpu, 1, NULL);
}

static void hv_sprr_deactivate(struct hv_sprr_cpu *cpu)
{
    if (sprr_guarded(cpu))
        panic("hv_sprr: disabling SPRR in guarded mode is unsupported");

    sprr_release_shadows(cpu);
    for (int i = 0; i < 2; i++)
        sprr_write_hw_ttbr(i, cpu->mmu->guest_ttbr[i]);

    hv_write_hcr(mrs(HCR_EL2) & ~HCR_TTLB);

    sysop("dsb ishst");
    sysop("tlbi vmalle1");
    sysop("dsb nsh");
    sysop("isb");

    /*
     * After SPRR is disabled we no longer trap exception entry/return and the guest starts
     * using the real hardware registers again
     * Note that we must be in HV_SPRR_XNU here since that's the only unguarded context
     */
    msr(SYS_SPSR_EL12, sprr_physical_pstate(cpu->exc[HV_SPRR_XNU].spsr));
    msr(SYS_ELR_EL12, cpu->exc[HV_SPRR_XNU].elr);
    msr(SYS_ESR_EL12, cpu->exc[HV_SPRR_XNU].esr);
    msr(SYS_FAR_EL12, cpu->exc[HV_SPRR_XNU].far);
    msr(SYS_AFSR1_EL12, cpu->exc[HV_SPRR_XNU].afsr1);
    sprr_update_vbar(cpu);
    msr(SYS_HFGITR_EL2, mrs(SYS_HFGITR_EL2) & ~HFGITR_ERET);
    sysop("isb");
}

static void hv_sprr_rebuild(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    if (!cpu->mmu->sprr_en)
        return;
    if (sprr_mmu_on()) {
        hv_sprr_build(ctx, cpu);
        sprr_update_vbar(cpu);
    }
}

static bool sprr_shadows_active(struct hv_sprr_cpu *cpu)
{
    return cpu->mmu->sprr_en && sprr_mmu_on();
}

static void sprr_write_ttbr(struct exc_info *ctx, struct hv_sprr_cpu *cpu, int ttbr_idx, u64 val)
{
    if (!sprr_shadows_active(cpu)) {
        sprr_write_hw_ttbr(ttbr_idx, val);
        return;
    }

    sprr_load_shadow(ctx, cpu, ttbr_idx);
    hv_sprr_switch_tables(cpu);
    sprr_update_vbar(cpu);
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
    if ((val & SCTLR_M) && !sprr_mmu_on())
        hv_sprr_build(ctx, cpu);

    msr(SYS_SCTLR_EL12, val);
    sprr_update_pac(ctx->spsr);
    sprr_update_vbar(cpu);
}

static void sprr_drop_asid(u64 asid)
{
    for (int i = 0; i < SPRR_N_CACHED_SHADOWS; i++) {
        struct hv_sprr_shadow *sh = &sprr_shadows[i];

        if (!sh->guest_ttbr || sh->active)
            continue;
        if (FIELD_GET(TTBR_ASID, sh->guest_ttbr) != asid)
            continue;

        sprr_shadow_free(sh);
    }
}

static bool hv_sprr_gxf_tlbi(void)
{
    sysop("dsb sy");
    sysop("tlbi vmalls12e1os");
    sysop("dsb sy");
    sysop("isb");

    return true;
}

#define TLBI(crm, op2)                                                                             \
    case SYSREG_ISS(sys_reg(1, 0, 8, crm, op2)):                                                   \
        __asm__ volatile("sys #0, c8, c" #crm ", #" #op2 ", %0" ::"r"(wval) : "memory");           \
        break;                                                                                     \
    case SYSREG_ISS(sys_reg(1, 0, 9, crm, op2)): /* FEAT_XS nXS variant */                         \
        __asm__ volatile("sys #0, c9, c" #crm ", #" #op2 ", %0" ::"r"(wval) : "memory");           \
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
            printf("hv_sprr: unhandled TLBI op0=1 op1=%ld CRn=%ld CRm=%ld op2=%ld\n",
                   FIELD_GET(ESR_ISS_MSR_OP1, reg), FIELD_GET(ESR_ISS_MSR_CRn, reg),
                   FIELD_GET(ESR_ISS_MSR_CRm, reg), FIELD_GET(ESR_ISS_MSR_OP2, reg));
            return false;
    }

    // if XNU drops an ASID we must drop our shadow tables since it might just hand back
    // the memory to userspace soon
    switch (reg) {
        case SYSREG_ISS(sys_reg(1, 0, 8, 1, 2)): // ASIDE1OS
        case SYSREG_ISS(sys_reg(1, 0, 8, 3, 2)): // ASIDE1IS
        case SYSREG_ISS(sys_reg(1, 0, 8, 7, 2)): // ASIDE1
        case SYSREG_ISS(sys_reg(1, 0, 9, 1, 2)): // ASIDE1OSNXS
        case SYSREG_ISS(sys_reg(1, 0, 9, 3, 2)): // ASIDE1ISNXS
        case SYSREG_ISS(sys_reg(1, 0, 9, 7, 2)): // ASIDE1NXS
            sprr_drop_asid(FIELD_GET(TTBR_ASID, wval));
            break;
    }

    return true;
}

// called from hv_handle_msr which also tries to handle some TLBIs and used to skip those if true
bool hv_sprr_traps_tlbi(void)
{
    return hv_sptm_mode == SPTM_EMULATION && hv_sprr_this()->mmu->sprr_en;
}

bool hv_sprr_handle_msr(struct exc_info *ctx, u64 reg, u32 rt, bool is_read)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    if (hv_sptm_mode != SPTM_EMULATION || !cpu->mmu->sprr_en)
        return false;

    ctx->regs[31] = 0;

    u64 crn = FIELD_GET(ESR_ISS_MSR_CRn, reg);
    if (!is_read && FIELD_GET(ESR_ISS_MSR_OP0, reg) == 1 &&
        (crn == 8 || crn == 9)) /* 8 = standard , 9 = nXS */
        return hv_sprr_handle_tlbi(reg, ctx->regs[rt]);

    return false;
}

static void sprr_save_keys(struct hv_sprr_mmu *mmu)
{
    mmu->pac_keys[0] = mrs(APIAKEYLO_EL1);
    mmu->pac_keys[1] = mrs(APIAKEYHI_EL1);
    mmu->pac_keys[2] = mrs(APIBKEYLO_EL1);
    mmu->pac_keys[3] = mrs(APIBKEYHI_EL1);
    mmu->pac_keys[4] = mrs(APDAKEYLO_EL1);
    mmu->pac_keys[5] = mrs(APDAKEYHI_EL1);
    mmu->pac_keys[6] = mrs(APDBKEYLO_EL1);
    mmu->pac_keys[7] = mrs(APDBKEYHI_EL1);
    mmu->pac_keys[8] = mrs(APGAKEYLO_EL1);
    mmu->pac_keys[9] = mrs(APGAKEYHI_EL1);
}

static void sprr_restore_keys(struct hv_sprr_mmu *mmu)
{
    msr(APIAKEYLO_EL1, mmu->pac_keys[0]);
    msr(APIAKEYHI_EL1, mmu->pac_keys[1]);
    msr(APIBKEYLO_EL1, mmu->pac_keys[2]);
    msr(APIBKEYHI_EL1, mmu->pac_keys[3]);
    msr(APDAKEYLO_EL1, mmu->pac_keys[4]);
    msr(APDAKEYHI_EL1, mmu->pac_keys[5]);
    msr(APDBKEYLO_EL1, mmu->pac_keys[6]);
    msr(APDBKEYHI_EL1, mmu->pac_keys[7]);
    msr(APGAKEYLO_EL1, mmu->pac_keys[8]);
    msr(APGAKEYHI_EL1, mmu->pac_keys[9]);
}

static void sprr_switch_mmu(struct exc_info *ctx, struct hv_sprr_cpu *cpu, struct hv_sprr_mmu *mmu)
{
    sprr_save_keys(cpu->mmu);
    sprr_release_shadows(cpu);
    cpu->mmu = mmu;

    msr(SYS_TCR_EL12, mmu->tcr);
    msr(SYS_MAIR_EL12, mmu->mair);
    msr(CPACR_EL12, mmu->cpacr);
    msr(SYS_SMCR_EL12, mmu->smcr);
    msr(CNTKCTL_EL12, mmu->cntkctl);
    sprr_restore_keys(mmu);

    for (int i = 0; i < 2; i++)
        sprr_write_hw_ttbr(i, mmu->guest_ttbr[i]);
    if (mmu->sprr_en && (mmu->sctlr & SCTLR_M))
        hv_sprr_build(ctx, cpu);
    msr(SYS_SCTLR_EL12, mmu->sctlr);

    sprr_update_pac(ctx->spsr);
    sprr_update_vbar(cpu);
    reg_mask(SYS_HFGITR_EL2, HFGITR_ERET, mmu->sprr_en ? HFGITR_ERET : 0);

    hv_write_hcr((mrs(HCR_EL2) & ~HCR_TTLB) | (mmu->sprr_en ? HCR_TTLB : 0));

    sysop("dsb ishst");
    sysop("tlbi vmalle1");
    sysop("dsb nsh");
    sysop("isb");
}

static void hv_sprr_switch_world(struct exc_info *ctx, struct hv_sprr_cpu *cpu,
                                 enum hv_sprr_context context)
{
    struct hv_sprr_exc_regs *from = &cpu->exc[cpu->context];
    struct hv_sprr_exc_regs *to = &cpu->exc[context];

    from->sp = ctx->sp[1];
    ctx->sp[1] = to->sp;
    cpu->context = context;

    struct hv_sprr_mmu *mmu = context == HV_SPRR_CL4 ? &cpu->mmu_el10 : &cpu->mmu_el20;
    if (cpu->mmu != mmu) {
        if (context == HV_SPRR_CL4) {
            cpu->tpidr_el2 = mrs(TPIDR_EL1);
            msr(TPIDR_EL1, cpu->tpidr_el1);
        } else {
            cpu->tpidr_el1 = mrs(TPIDR_EL1);
            msr(TPIDR_EL1, cpu->tpidr_el2);
        }
        sprr_switch_mmu(ctx, cpu, mmu);
    } else {
        hv_sprr_switch_tables(cpu);
    }
}

static void hv_gxf_genter(struct exc_info *ctx, u8 imm)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();
    u64 link_pstate = sprr_virtual_pstate(cpu, ctx->spsr);
    u64 link_pc = ctx->elr;

    // genter from GL is weird but allowed ¯\_(ツ)_/¯
    bool from_guarded = sprr_guarded(cpu);

    cpu->exc[HV_SPRR_SPTM].spsr = link_pstate;
    cpu->exc[HV_SPRR_SPTM].elr = link_pc;
    cpu->exc[HV_SPRR_SPTM].esr = HV_GXF_ESR_GENTER | FIELD_PREP(HV_HVC_GENTER_IMM, imm);
    if (from_guarded)
        cpu->exc[HV_SPRR_SPTM].aspsr |= ASPSR_GUARDED;
    else
        cpu->exc[HV_SPRR_SPTM].aspsr &= ~ASPSR_GUARDED;

    if (!from_guarded)
        hv_sprr_switch_world(ctx, cpu, HV_SPRR_SPTM);

    ctx->elr = cpu->gxf_enter;
    ctx->spsr = (link_pstate | SPSR_D | SPSR_A | SPSR_I | SPSR_F) & ~SPSR_M;
    // genter automatically sets SPSel = 1
    ctx->spsr |= FIELD_PREP(SPSR_M, SPSR_M_EL1H);
    sprr_update_pac(ctx->spsr);
}

static bool hv_gxf_gexit(struct exc_info *ctx)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    if (cpu->context != HV_SPRR_SPTM)
        return false;

    u64 ret_pc = cpu->exc[HV_SPRR_SPTM].elr;
    u64 ret_pstate = cpu->exc[HV_SPRR_SPTM].spsr;

    if (!(cpu->exc[HV_SPRR_SPTM].aspsr & ASPSR_GUARDED))
        hv_sprr_switch_world(ctx, cpu, HV_SPRR_XNU);

    ctx->elr = ret_pc;
    ctx->spsr = sprr_physical_pstate(ret_pstate);
    sprr_update_pac(ctx->spsr);
    return true;
}

/*
 * When SPRR is disabled we use the real hardware registers because we can't easily inject the
 * page redirecting all exceptions via hvc to EL2.
 */
#define VREG_EL1_BANKED(vreg_id, hwreg, field)                                                     \
    case vreg_id:                                                                                  \
        if (cpu->mmu->sprr_en) {                                                                   \
            if (is_read)                                                                           \
                rval = cpu->exc[HV_SPRR_XNU].field;                                                \
            else                                                                                   \
                cpu->exc[HV_SPRR_XNU].field = wval;                                                \
        } else if (is_read) {                                                                      \
            rval = _mrs(sr_tkn(hwreg));                                                            \
        } else {                                                                                   \
            _msr(sr_tkn(hwreg), wval);                                                             \
        }                                                                                          \
        break

#define VREG_EL2_BANKED(name, field)                                                               \
    case HV_VREG_##name##_EL2:                                                                     \
        VREG_EL1_BANKED(HV_VREG_##name##_EL1, SYS_##name##_EL12, field)

#define VREG_MASKED_ALIAS(vreg_id, shadow_id, mask)                                                \
    case vreg_id:                                                                                  \
        if (is_read)                                                                               \
            rval = cpu->shadow[shadow_id];                                                         \
        else                                                                                       \
            cpu->shadow[shadow_id] = wval & (mask);                                                \
        break

#define VREG_MASKED(vreg_id, mask) VREG_MASKED_ALIAS(vreg_id, vreg_id, mask)

#define VREG_STORED(vreg_id, field)                                                                \
    case vreg_id:                                                                                  \
        if (is_read)                                                                               \
            rval = cpu->field;                                                                     \
        else                                                                                       \
            cpu->field = wval;                                                                     \
        break

#define VREG_EL10_KEY(name, index)                                                                 \
    case HV_VREG_##name##_EL12:                                                                    \
        if (is_read)                                                                               \
            rval = cpu->mmu_el10.pac_keys[index];                                                  \
        else {                                                                                     \
            cpu->mmu_el10.pac_keys[index] = wval;                                                  \
            if (cpu->mmu == &cpu->mmu_el10)                                                        \
                msr(name##_EL1, wval);                                                             \
        }                                                                                          \
        break

#define MMU_REG(active_reg, el10_reg, field)                                                       \
    case HV_VREG_##el10_reg:                                                                       \
        mmu = &cpu->mmu_el10;                                                                      \
        reg = &mmu->field;                                                                         \
        break;                                                                                     \
    case HV_VREG_##active_reg:                                                                     \
        reg = &mmu->field;                                                                         \
        break

enum mmu_sysreg_result {
    MMU_SYSREG_UNHANDLED = 0,
    MMU_SYSREG_RETRY_LOCKED = 1,
    MMU_SYSREG_HANDLED = 2,
};
static enum mmu_sysreg_result hv_sprr_emulate_mmu_sysreg(struct exc_info *ctx,
                                                         struct hv_sprr_cpu *cpu, u32 vreg,
                                                         bool is_read, u32 rt, bool locked)
{
    struct hv_sprr_mmu *mmu = cpu->mmu;
    u64 *reg;
    switch (vreg) {
        MMU_REG(TTBR0_EL1, TTBR0_EL12, guest_ttbr[0]);
        MMU_REG(TTBR1_EL1, TTBR1_EL12, guest_ttbr[1]);
        MMU_REG(TCR_EL1, TCR_EL12, tcr);
        MMU_REG(SCTLR_EL1, SCTLR_EL12, sctlr);
        MMU_REG(MAIR_EL1, MAIR_EL12, mair);
        MMU_REG(CPACR_EL1, CPACR_EL12, cpacr);
        MMU_REG(SMCR_EL1, SMCR_EL12, smcr);
        MMU_REG(CNTKCTL_EL1, CNTKCTL_EL12, cntkctl);
        MMU_REG(APCTL_EL1, APCTL_EL12, apctl);
        MMU_REG(SPRR_CONFIG_EL1, SPRR_CONFIG_EL12, sprr_config);
        MMU_REG(GXF_CONFIG_EL1, GXF_CONFIG_EL12, gxf_config);
        MMU_REG(SPRR_PERM_EL0, SPRR_UPERM_EL02, sprr_perm_el0);
        MMU_REG(SPRR_PERM_EL1, SPRR_PPERM_EL12, sprr_perm_el1);
        MMU_REG(SPRR_AMRANGE_EL1, SPRR_AMRANGE_EL12, sprr_amrange);
        MMU_REG(SPRR_UMPRR_EL1, SPRR_UMPRR_EL12, sprr_umprr);
        MMU_REG(SPRR_PMPRR_EL1, SPRR_PMPRR_EL12, sprr_pmprr);
        MMU_REG(SPRR_PPERM_SH1_EL1, SPRR_PPERM_SH1_EL12, sprr_pperm_sh1);
        MMU_REG(SPRR_PPERM_SH2_EL1, SPRR_PPERM_SH2_EL12, sprr_pperm_sh2);
        MMU_REG(SPRR_PPERM_SH3_EL1, SPRR_PPERM_SH3_EL12, sprr_pperm_sh3);
        MMU_REG(SPRR_UPERM_SH1_EL1, SPRR_UPERM_SH1_EL12, sprr_uperm_sh1);
        MMU_REG(SPRR_UPERM_SH2_EL1, SPRR_UPERM_SH2_EL12, sprr_uperm_sh2);
        MMU_REG(SPRR_UPERM_SH3_EL1, SPRR_UPERM_SH3_EL12, sprr_uperm_sh3);
        case HV_VREG_SMCR_EL2:
            mmu = &cpu->mmu_el20;
            reg = &mmu->smcr;
            break;
        case HV_VREG_CPTR_EL2:
            mmu = &cpu->mmu_el20;
            reg = &mmu->cpacr;
            break;
        default:
            return MMU_SYSREG_UNHANDLED;
    }

    if (is_read) {
        ctx->regs[rt] = *reg;
        return MMU_SYSREG_HANDLED;
    }
    u64 old = *reg;
    u64 val = ctx->regs[rt];
    /*
     * XNU rewrites these with the value they already hold on all the time but we only care
     * if it writes a new value which would change the way we need to shadow perms.
     */
    if (old == val && (vreg == HV_VREG_SPRR_PERM_EL0 || vreg == HV_VREG_SPRR_UPERM_EL02 ||
                       vreg == HV_VREG_SPRR_PERM_EL1 || vreg == HV_VREG_SPRR_PPERM_EL12))
        return MMU_SYSREG_HANDLED;
    if (!locked)
        return MMU_SYSREG_RETRY_LOCKED;

    *reg = val;
    if (vreg == HV_VREG_SPRR_CONFIG_EL1 || vreg == HV_VREG_SPRR_CONFIG_EL12)
        mmu->sprr_en = val & SPRR_CONFIG_EN;
    if (mmu != cpu->mmu)
        return MMU_SYSREG_HANDLED;

    switch (vreg) {
        case HV_VREG_TTBR0_EL1:
        case HV_VREG_TTBR0_EL12:
            sprr_write_ttbr(ctx, cpu, 0, val);
            break;
        case HV_VREG_TTBR1_EL1:
        case HV_VREG_TTBR1_EL12:
            sprr_write_ttbr(ctx, cpu, 1, val);
            break;
        case HV_VREG_TCR_EL1:
        case HV_VREG_TCR_EL12:
            sprr_write_tcr(ctx, cpu, val);
            break;
        case HV_VREG_SCTLR_EL1:
        case HV_VREG_SCTLR_EL12:
            sprr_write_sctlr(ctx, cpu, val);
            break;
        case HV_VREG_MAIR_EL1:
        case HV_VREG_MAIR_EL12:
            msr(SYS_MAIR_EL12, val);
            hv_sprr_rebuild(ctx, cpu);
            break;
        case HV_VREG_CPACR_EL1:
        case HV_VREG_CPACR_EL12:
        case HV_VREG_CPTR_EL2:
            msr(CPACR_EL12, val);
            break;
        case HV_VREG_SMCR_EL1:
        case HV_VREG_SMCR_EL12:
        case HV_VREG_SMCR_EL2:
            msr(SYS_SMCR_EL12, val);
            break;
        case HV_VREG_CNTKCTL_EL1:
        case HV_VREG_CNTKCTL_EL12:
            msr(CNTKCTL_EL12, val);
            break;
        case HV_VREG_APCTL_EL1:
        case HV_VREG_APCTL_EL12:
            sprr_update_pac(ctx->spsr);
            break;
        case HV_VREG_SPRR_CONFIG_EL1:
        case HV_VREG_SPRR_CONFIG_EL12:
            if (!(old & SPRR_CONFIG_EN) && mmu->sprr_en)
                hv_sprr_activate(ctx, cpu);
            else if ((old & SPRR_CONFIG_EN) && !mmu->sprr_en)
                hv_sprr_deactivate(cpu);
            break;
        case HV_VREG_SPRR_PERM_EL0:
        case HV_VREG_SPRR_UPERM_EL02:
        case HV_VREG_SPRR_PERM_EL1:
        case HV_VREG_SPRR_PPERM_EL12:
            if (old != val)
                hv_sprr_rebuild(ctx, cpu);
            break;
    }
    return MMU_SYSREG_HANDLED;
}

static bool hv_sprr_emulate_sysreg(struct exc_info *ctx, u32 vreg, bool is_read, u32 rt,
                                   bool locked)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();

    ctx->regs[31] = 0;
    u64 wval = ctx->regs[rt];
    u64 rval = 0;
    enum mmu_sysreg_result result = hv_sprr_emulate_mmu_sysreg(ctx, cpu, vreg, is_read, rt, locked);
    switch (result) {
        case MMU_SYSREG_HANDLED:
            return true;
        case MMU_SYSREG_RETRY_LOCKED:
            return false;
        case MMU_SYSREG_UNHANDLED:
            break;
    }

    enum hv_sprr_context guarded_context = HV_SPRR_SPTM;
    switch (cpu->context) {
        case HV_SPRR_XNU:
        case HV_SPRR_SPTM:
            /*
             * XNU can't access guarded registers but it's easier to just map them to SPTM here
             * than rewriting all the code below
             */
            guarded_context = HV_SPRR_SPTM;
            break;
        case HV_SPRR_CL4:
            guarded_context = HV_SPRR_CL4;
            break;
    }

    switch (vreg) {
        VREG_MASKED_ALIAS(HV_VREG_ACTLR_EL12, HV_VREG_ACTLR_EL12_PRE, ~0ULL);
        VREG_EL10_KEY(APIAKEYLO, 0);
        VREG_EL10_KEY(APIAKEYHI, 1);
        VREG_EL10_KEY(APIBKEYLO, 2);
        VREG_EL10_KEY(APIBKEYHI, 3);
        VREG_EL10_KEY(APDAKEYLO, 4);
        VREG_EL10_KEY(APDAKEYHI, 5);
        VREG_EL10_KEY(APDBKEYLO, 6);
        VREG_EL10_KEY(APDBKEYHI, 7);
        VREG_EL10_KEY(APGAKEYLO, 8);
        VREG_EL10_KEY(APGAKEYHI, 9);
        VREG_STORED(HV_VREG_GXF_ENTER_EL1, gxf_enter);
        VREG_STORED(HV_VREG_GXF_ABORT_EL1, gxf_abort);
        VREG_STORED(HV_VREG_TPIDR_GL1, tpidr_gl1);
        VREG_STORED(HV_VREG_ASPSR_GL1, exc[guarded_context].aspsr);
        /* ASPSR_EL1 always describes unguarded exception state and must thus belong to XNU */
        VREG_STORED(HV_VREG_ASPSR_EL1, exc[HV_SPRR_XNU].aspsr);
        VREG_STORED(HV_VREG_VBAR_GL1, exc[guarded_context].vbar);
        VREG_STORED(HV_VREG_ELR_GL1, exc[guarded_context].elr);
        VREG_STORED(HV_VREG_SPSR_GL1, exc[guarded_context].spsr);
        VREG_STORED(HV_VREG_ESR_GL1, exc[guarded_context].esr);
        VREG_STORED(HV_VREG_FAR_GL1, exc[guarded_context].far);
        VREG_STORED(HV_VREG_AFSR1_GL1, exc[guarded_context].afsr1);
        /* GL12 is used by SPTM to modify cL4's registers */
        VREG_STORED(HV_VREG_VBAR_GL12, exc[HV_SPRR_CL4].vbar);
        VREG_STORED(HV_VREG_SP_GL12, exc[HV_SPRR_CL4].sp);
        VREG_STORED(HV_VREG_SPSR_GL12, exc[HV_SPRR_CL4].spsr);
        VREG_STORED(HV_VREG_ELR_GL12, exc[HV_SPRR_CL4].elr);
        VREG_STORED(HV_VREG_ASPSR_GL12, exc[HV_SPRR_CL4].aspsr);
        VREG_STORED(HV_VREG_ESR_GL12, exc[HV_SPRR_CL4].esr);
        /*
         * GL2 should never be written by cL4 running in GL1 but we don't model access permissions
         * like this correctly
         */
        VREG_STORED(HV_VREG_AFSR1_GL2, exc[HV_SPRR_SPTM].afsr1);
        VREG_STORED(HV_VREG_SP_EL1, sp_el1);
        VREG_EL2_BANKED(ELR, elr);
        VREG_EL2_BANKED(ESR, esr);
        VREG_EL2_BANKED(FAR, far);
        VREG_EL1_BANKED(HV_VREG_AFSR1_EL1, SYS_AFSR1_EL12, afsr1);

        /*
         * SPTM writes the end address, then reads it back and checks if the lower bits are
         * cleared. It accesses the _EL12 variants but doesn't validate them but we might need
         * that once we add support for "secure kernel".
         */
        VREG_MASKED(HV_VREG_CTRR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_D_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_C_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_C_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_D_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTRR_D_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_A_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_A_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_B_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_B_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_D_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_A_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_A_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_B_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_B_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_C_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_C_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_D_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_VREG_CTXR_D_UPR_EL12, ~0xfffULL);

        /*
         * It seems that XNU reads from _EL2 varient of the following registers while
         * SPTM writes the _EL1 varient of these registers. On real hardware, this would
         * refer to the same registers since HCR.E2H (always set on Apple Silcon) is set.
         * We don't emulate this correctly, but for now, this hack works.
         */
        VREG_MASKED_ALIAS(HV_VREG_CTRR_D_LWR_EL2, HV_VREG_CTRR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_CTRR_D_UPR_EL2, HV_VREG_CTRR_D_UPR_EL1, ~0xfffULL);

        /*
         * This is a bit of hack to make SPTM happy since it also checks the per-cluster
         * variants against the same values the per-core ones have after it wrote those. Just
         * mirror the per-cluster register even though it's not quite clear what happens on real
         * hardware.
         */
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTRR_C_LWR_EL2, HV_VREG_CTRR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTRR_C_UPR_EL2, HV_VREG_CTRR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTRR_D_LWR_EL2, HV_VREG_CTRR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTRR_D_UPR_EL2, HV_VREG_CTRR_D_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_A_LWR_EL2, HV_VREG_CTXR_A_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_A_UPR_EL2, HV_VREG_CTXR_A_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_B_LWR_EL2, HV_VREG_CTXR_B_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_B_UPR_EL2, HV_VREG_CTXR_B_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_C_LWR_EL2, HV_VREG_CTXR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_C_UPR_EL2, HV_VREG_CTXR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_D_LWR_EL2, HV_VREG_CTXR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_VREG_ACC_CTXR_D_UPR_EL2, HV_VREG_CTXR_D_UPR_EL1, ~0xfffULL);

        case HV_VREG_SPSR_EL1:
        case HV_VREG_SPSR_EL2:
            if (cpu->mmu->sprr_en) {
                if (is_read)
                    rval = cpu->exc[HV_SPRR_XNU].spsr;
                else
                    cpu->exc[HV_SPRR_XNU].spsr = wval;
            } else if (is_read) {
                rval = sprr_virtual_pstate(cpu, mrs(SYS_SPSR_EL12));
            } else {
                msr(SYS_SPSR_EL12, sprr_physical_pstate(wval));
            }
            break;

        case HV_VREG_CURRENTEL:
            rval = sprr_virtual_pstate(cpu, ctx->spsr) & 0xc;
            break;
        case HV_VREG_GXF_STATUS_EL1:
            if (is_read)
                rval = sprr_guarded(cpu) ? GXF_STATUS_GUARDED : 0;
            break;
        case HV_VREG_VBAR_EL1:
            if (is_read) {
                rval = cpu->exc[HV_SPRR_XNU].vbar;
            } else {
                cpu->exc[HV_SPRR_XNU].vbar = wval;
                if (!cpu->mmu->sprr_en)
                    sprr_update_vbar(cpu);
            }
            break;
        case HV_VREG_PMCR0_EL1:
            if (is_read) {
                rval = hv_pmcr0_read();
            } else {
                hv_pmcr0_write(wval);
                hv_update_fiq();
            }
            break;
        case HV_VREG_APL_CNTV_CTL_EL0:
            if (is_read) {
                rval = cpu->shadow[HV_VREG_APL_CNTV_CTL_EL0];
                if ((rval & CNTx_CTL_ENABLE) && (s64)(cpu->timer_deadline - apple_timer_now()) <= 0)
                    rval |= CNTx_CTL_ISTATUS;
            } else {
                cpu->shadow[vreg] = wval & (CNTx_CTL_ENABLE | CNTx_CTL_IMASK);
                hv_update_fiq();
                hv_sprr_timer_arm();
            }
            break;
        case HV_VREG_APL_CNTV_TVAL_EL0:
            if (is_read) {
                rval = (u32)(cpu->timer_deadline - apple_timer_now());
            } else {
                cpu->timer_deadline = apple_timer_now() + (s32)wval;
                hv_update_fiq();
                hv_sprr_timer_arm();
            }
            break;

        case HV_VREG_TAGOFFSET_EL2:
            if (!is_read)
                return false;
            rval = mrs(SYS_IMP_APL_TAGOFFSET_EL2);
            break;

        default:
            if (vreg >= HV_VREG_MAX)
                panic("hv_sprr: unknown vreg %d", vreg);
            if (is_read)
                rval = cpu->shadow[vreg];
            else
                cpu->shadow[vreg] = wval;
            break;
    }

    if (is_read)
        ctx->regs[rt] = rval;
    return true;
}

bool hv_sprr_handle_eret(struct exc_info *ctx, bool locked)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();
    struct hv_sprr_exc_regs *regs = &cpu->exc[cpu->context];

    if (hv_sptm_mode != SPTM_EMULATION)
        return false;
    if (!cpu->mmu->sprr_en)
        return false;
    if (FIELD_GET(ESR_ISS, ctx->esr) != 0)
        return false;

    enum hv_sprr_context context = cpu->context;
    u64 mode = regs->spsr & SPSR_M;
    bool el2_mode = mode == SPSR_M_EL2T || mode == SPSR_M_EL2H;
    bool el1_mode = mode == SPSR_M_EL1T || mode == SPSR_M_EL1H;
    switch (cpu->context) {
        case HV_SPRR_XNU:
            if (mode != SPSR_M_EL0 && !el2_mode)
                return false;
            break;
        case HV_SPRR_SPTM:
            if (mode != SPSR_M_EL0 && !el2_mode && !el1_mode)
                return false;
            break;
        case HV_SPRR_CL4:
            if (mode != SPSR_M_EL0 && !el1_mode)
                return false;
            break;
    }

    /* CL4 is the only virtual EL1 context we support returning to from SPTM. */
    if (context == HV_SPRR_SPTM && el1_mode) {
        if (!locked)
            return false;
        context = HV_SPRR_CL4;
    }

    ctx->elr = regs->elr;
    ctx->spsr = sprr_physical_pstate(regs->spsr);

    if (context != cpu->context)
        hv_sprr_switch_world(ctx, cpu, context);

    sprr_update_pac(ctx->spsr);
    hv_set_elr(ctx->elr);
    hv_set_spsr(ctx->spsr);
    msr(SP_EL1, ctx->sp[1]);
    return true;
}

static void sprr_cl4_hvc(struct exc_info *ctx, struct hv_sprr_cpu *cpu)
{
    struct hv_sprr_exc_regs *regs = &cpu->exc[HV_SPRR_SPTM];
    regs->spsr = ctx->spsr;
    regs->elr = ctx->elr;
    regs->esr = ctx->esr;
    regs->aspsr |= ASPSR_GUARDED;
    ctx->spsr &= ~(SPSR_M | SPSR_SS | SPSR_IL | SPSR_BTYPE | SPSR_UAO | SPSR_SSBS);
    ctx->spsr |= SPSR_M_EL1H | SPSR_D | SPSR_A | SPSR_I | SPSR_F;
    if (cpu->mmu_el20.sctlr & SCTLR_DSSBS)
        ctx->spsr |= SPSR_SSBS;
    if (FIELD_GET(ID_AA64PFR1_MTE, mrs(SYS_ID_AA64PFR1_EL1)) >= ID_AA64PFR1_MTE2)
        ctx->spsr |= SPSR_TCO;
    hv_sprr_switch_world(ctx, cpu, HV_SPRR_SPTM);
    ctx->elr = regs->vbar + 0x400;
}

static void hv_sprr_vector_enter(struct exc_info *ctx, u16 imm)
{
    struct hv_sprr_cpu *cpu = hv_sprr_this();
    struct hv_sprr_exc_regs *regs = &cpu->exc[cpu->context];
    unsigned slot = FIELD_GET(HV_HVC_VECTOR_SLOT, imm);
    unsigned type = FIELD_GET(SPRR_VECTOR_TYPE, slot);
    u64 offset = slot * SPRR_VECTOR_STRIDE;

    regs->elr = mrs(SYS_ELR_EL12);
    regs->spsr = sprr_virtual_pstate(cpu, mrs(SYS_SPSR_EL12));
    switch (type) {
        case SPRR_VECTOR_TYPE_SERROR:
            regs->esr = mrs(SYS_ESR_EL12);
            break;
        case SPRR_VECTOR_TYPE_SYNC:
            regs->esr = mrs(SYS_ESR_EL12);
            switch (FIELD_GET(ESR_EC, regs->esr)) {
                case ESR_EC_IABORT_LOWER:
                case ESR_EC_IABORT:
                case ESR_EC_DABORT_LOWER:
                case ESR_EC_DABORT:
                case ESR_EC_PC_ALIGN:
                case ESR_EC_WATCH_LOWER:
                case ESR_EC_WATCH:
                    regs->far = mrs(SYS_FAR_EL12);
                    break;
                case ESR_EC_IMPDEF:
                    regs->far = mrs(SYS_FAR_EL12);
                    regs->afsr1 = mrs(SYS_AFSR1_EL12);
                    break;
            }
            break;
        case SPRR_VECTOR_TYPE_IRQ:
        case SPRR_VECTOR_TYPE_FIQ:
            /* These don't have ESR or anything, just forward them */
            break;
    }

    if (sprr_guarded(cpu))
        regs->aspsr |= ASPSR_GUARDED;
    ctx->elr = regs->vbar + offset;

    sprr_update_pac(ctx->spsr);
    hv_set_elr(ctx->elr);
}

bool hv_hvc_dispatch_unlocked(struct exc_info *ctx, u16 imm)
{
    if (hv_sptm_mode != SPTM_EMULATION)
        return false;

    sprr_prepare_cpu(hv_sprr_this());

    if ((imm & HV_HVC_VECTOR_MASK) == HV_HVC_VECTOR_BASE) {
        hv_sprr_vector_enter(ctx, imm);
        return true;
    }

    if (imm & HV_HVC_SYSREG_FLAG)
        return hv_sprr_emulate_sysreg(ctx, FIELD_GET(HV_HVC_SYSREG_VREG, imm),
                                      imm & HV_HVC_SYSREG_DIR, FIELD_GET(HV_HVC_SYSREG_RT, imm),
                                      false);

    if ((imm & HV_HVC_GENTER_MASK) == HV_HVC_GENTER_BASE) {
        if (hv_sprr_this()->context == HV_SPRR_CL4)
            return false;
        hv_gxf_genter(ctx, FIELD_GET(HV_HVC_GENTER_IMM, imm));
    } else if (imm == HV_HVC_GEXIT) {
        if (!hv_gxf_gexit(ctx))
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
    if (hv_sptm_mode != SPTM_EMULATION)
        return false;

    struct hv_sprr_cpu *cpu = hv_sprr_this();
    if (imm == 0 && cpu->context == HV_SPRR_CL4) {
        if ((cpu->shadow[HV_VREG_HCR_EL2] & (HCR_E2H | HCR_TGE | HCR_VM)) != HCR_E2H)
            return false;
        sprr_cl4_hvc(ctx, cpu);
        return true;
    }

    if (imm == HV_HVC_GXF_TLBI_ALL || (imm & HV_HVC_GXF_TLBI_MASK) == HV_HVC_GXF_TLBI_ARG ||
        (imm & HV_HVC_GXF_TLBI_ARG2_MASK) == HV_HVC_GXF_TLBI_ARG2)
        return hv_sprr_gxf_tlbi();

    if (imm == HV_HVC_TLBI_ALLE1OSNXS) {
        sysop("tlbi alle1osnxs");
        return true;
    }

    if (imm & HV_HVC_SYSREG_FLAG)
        return hv_sprr_emulate_sysreg(ctx, FIELD_GET(HV_HVC_SYSREG_VREG, imm),
                                      imm & HV_HVC_SYSREG_DIR, FIELD_GET(HV_HVC_SYSREG_RT, imm),
                                      true);

    return false;
}

void hv_sprr_init(void)
{
    if (hv_sptm_mode != SPTM_EMULATION)
        return;
    for (int i = 0; i < MAX_CPUS; i++)
        sprr_init_cpu(i);
    if (hv_map_hw_ro((u64)hv_sprr_vectors, (u64)hv_sprr_vectors, SZ_16K) < 0)
        panic("hv_sprr: cannot map vector page");
}
