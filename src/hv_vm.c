/* SPDX-License-Identifier: MIT */

// #define DEBUG

#include "hv.h"
#include "assert.h"
#include "cpu_regs.h"
#include "exception.h"
#include "iodev.h"
#include "malloc.h"
#include "smp.h"
#include "string.h"
#include "types.h"
#include "uartproxy.h"
#include "utils.h"

#define PAGE_SIZE       0x4000
#define CACHE_LINE_SIZE 64
#define CACHE_LINE_LOG2 6

#define PTE_ACCESS            BIT(10)
#define PTE_SH_NS             (0b11L << 8)
#define PTE_S2AP_RW           (0b11L << 6)
#define PTE_MEMATTR_UNCHANGED (0b1111L << 2)

#define PTE_ATTRIBUTES (PTE_ACCESS | PTE_SH_NS | PTE_S2AP_RW | PTE_MEMATTR_UNCHANGED)

#define PTE_LOWER_ATTRIBUTES GENMASK(13, 2)

#define PTE_VALID BIT(0)
#define PTE_TYPE  BIT(1)
#define PTE_BLOCK 0
#define PTE_TABLE 1
#define PTE_PAGE  1

#define VADDR_L4_INDEX_BITS 12
#define VADDR_L3_INDEX_BITS 11
#define VADDR_L2_INDEX_BITS 11
#define VADDR_L1_INDEX_BITS 8

#define VADDR_L4_OFFSET_BITS 2
#define VADDR_L3_OFFSET_BITS 14
#define VADDR_L2_OFFSET_BITS 25
#define VADDR_L1_OFFSET_BITS 36

#define VADDR_L2_ALIGN_MASK GENMASK(VADDR_L2_OFFSET_BITS - 1, VADDR_L3_OFFSET_BITS)
#define VADDR_L3_ALIGN_MASK GENMASK(VADDR_L3_OFFSET_BITS - 1, VADDR_L4_OFFSET_BITS)
#define PTE_TARGET_MASK     GENMASK(49, VADDR_L3_OFFSET_BITS)
#define PTE_TARGET_MASK_L4  GENMASK(49, VADDR_L4_OFFSET_BITS)

#define ENTRIES_PER_L1_TABLE BIT(VADDR_L1_INDEX_BITS)
#define ENTRIES_PER_L2_TABLE BIT(VADDR_L2_INDEX_BITS)
#define ENTRIES_PER_L3_TABLE BIT(VADDR_L3_INDEX_BITS)
#define ENTRIES_PER_L4_TABLE BIT(VADDR_L4_INDEX_BITS)

#define SPTE_TRACE_READ    BIT(63)
#define SPTE_TRACE_WRITE   BIT(62)
#define SPTE_TRACE_UNBUF   BIT(61)
#define SPTE_TYPE          GENMASK(52, 50)
#define SPTE_MAP           0
#define SPTE_HOOK          1
#define SPTE_PROXY_HOOK_R  2
#define SPTE_PROXY_HOOK_W  3
#define SPTE_PROXY_HOOK_RW 4

#define IS_HW(pte) ((pte) && pte & PTE_VALID)
#define IS_SW(pte) ((pte) && !(pte & PTE_VALID))

#define L1_IS_TABLE(pte) ((pte) && FIELD_GET(PTE_TYPE, pte) == PTE_TABLE)

#define L2_IS_TABLE(pte)     ((pte) && FIELD_GET(PTE_TYPE, pte) == PTE_TABLE)
#define L2_IS_NOT_TABLE(pte) ((pte) && !L2_IS_TABLE(pte))
#define L2_IS_HW_BLOCK(pte)  (IS_HW(pte) && FIELD_GET(PTE_TYPE, pte) == PTE_BLOCK)
#define L2_IS_SW_BLOCK(pte)                                                                        \
    (IS_SW(pte) && FIELD_GET(PTE_TYPE, pte) == PTE_BLOCK && FIELD_GET(SPTE_TYPE, pte) == SPTE_MAP)
#define L3_IS_TABLE(pte)     (IS_SW(pte) && FIELD_GET(PTE_TYPE, pte) == PTE_TABLE)
#define L3_IS_NOT_TABLE(pte) ((pte) && !L3_IS_TABLE(pte))
#define L3_IS_HW_BLOCK(pte)  (IS_HW(pte) && FIELD_GET(PTE_TYPE, pte) == PTE_PAGE)
#define L3_IS_SW_BLOCK(pte)                                                                        \
    (IS_SW(pte) && FIELD_GET(PTE_TYPE, pte) == PTE_BLOCK && FIELD_GET(SPTE_TYPE, pte) == SPTE_MAP)

uint64_t vaddr_bits;

/*
 * We use 16KB page tables for stage 2 translation, and a 64GB (36-bit) guest
 * PA size, which results in the following virtual address space:
 *
 * [L2 index]  [L3 index] [page offset]
 *  11 bits     11 bits    14 bits
 *
 * 32MB L2 mappings look like this:
 * [L2 index]  [page offset]
 *  11 bits     25 bits
 *
 * We implement sub-page granularity mappings for software MMIO hooks, which behave
 * as an additional page table level used only by software. This works like this:
 *
 * [L2 index]  [L3 index] [L4 index]  [Word offset]
 *  11 bits     11 bits    12 bits     2 bits
 *
 * Thus, L4 sub-page tables are twice the size.
 *
 * We use invalid mappings (PTE_VALID == 0) to represent mmiotrace descriptors, but
 * otherwise the page table format is the same. The PTE_TYPE bit is weird, as 0 means
 * block but 1 means both table (at L<3) and page (at L3). For mmiotrace, this is
 * pushed to L4.
 *
 * On SoCs with more than 36-bit PA sizes there is an additional L1 translation level,
 * but no blocks or software mappings are allowed there. This level can have up to 8 bits
 * at this time.
 */

static u64 *hv_Ltop;

void hv_pt_init(void)
{
    const uint64_t pa_bits[] = {32, 36, 40, 42, 44, 48, 52};
    uint64_t pa_range = FIELD_GET(ID_AA64MMFR0_PARange, mrs(ID_AA64MMFR0_EL1));

    vaddr_bits = min(44, pa_bits[pa_range]);

    printf("HV: Initializing for %ld-bit PA range\n", vaddr_bits);

    hv_Ltop = memalign(PAGE_SIZE, sizeof(u64) * ENTRIES_PER_L2_TABLE);
    memset(hv_Ltop, 0, sizeof(u64) * ENTRIES_PER_L2_TABLE);

    u64 sl0 = vaddr_bits > 36 ? 2 : 1;

    msr(VTCR_EL2, FIELD_PREP(VTCR_PS, pa_range) |              // Full PA size
                      FIELD_PREP(VTCR_TG0, 2) |                // 16KB page size
                      FIELD_PREP(VTCR_SH0, 3) |                // PTWs Inner Sharable
                      FIELD_PREP(VTCR_ORGN0, 1) |              // PTWs Cacheable
                      FIELD_PREP(VTCR_IRGN0, 1) |              // PTWs Cacheable
                      FIELD_PREP(VTCR_SL0, sl0) |              // Start level
                      FIELD_PREP(VTCR_T0SZ, 64 - vaddr_bits)); // Translation region == PA

    msr(VTTBR_EL2, hv_Ltop);
}

static u64 *hv_pt_get_l2(u64 from)
{
    u64 l1idx = from >> VADDR_L1_OFFSET_BITS;

    if (vaddr_bits <= 36) {
        assert(l1idx == 0);
        return hv_Ltop;
    }

    u64 l1d = hv_Ltop[l1idx];

    if (L1_IS_TABLE(l1d))
        return (u64 *)(l1d & PTE_TARGET_MASK);

    u64 *l2 = (u64 *)memalign(PAGE_SIZE, ENTRIES_PER_L2_TABLE * sizeof(u64));
    memset64(l2, 0, ENTRIES_PER_L2_TABLE * sizeof(u64));

    l1d = ((u64)l2) | FIELD_PREP(PTE_TYPE, PTE_TABLE) | PTE_VALID;
    hv_Ltop[l1idx] = l1d;
    return l2;
}

static void hv_pt_free_l3(u64 *l3)
{
    if (!l3)
        return;

    for (u64 idx = 0; idx < ENTRIES_PER_L3_TABLE; idx++)
        if (IS_SW(l3[idx]) && FIELD_GET(PTE_TYPE, l3[idx]) == PTE_TABLE)
            free((void *)(l3[idx] & PTE_TARGET_MASK));
    free(l3);
}

static void hv_pt_map_l2(u64 from, u64 to, u64 size, u64 incr)
{
    assert((from & MASK(VADDR_L2_OFFSET_BITS)) == 0);
    assert(IS_SW(to) || (to & PTE_TARGET_MASK & MASK(VADDR_L2_OFFSET_BITS)) == 0);
    assert((size & MASK(VADDR_L2_OFFSET_BITS)) == 0);

    to |= FIELD_PREP(PTE_TYPE, PTE_BLOCK);

    for (; size; size -= BIT(VADDR_L2_OFFSET_BITS)) {
        u64 *l2 = hv_pt_get_l2(from);
        u64 idx = (from >> VADDR_L2_OFFSET_BITS) & MASK(VADDR_L2_INDEX_BITS);

        if (L2_IS_TABLE(l2[idx]))
            hv_pt_free_l3((u64 *)(l2[idx] & PTE_TARGET_MASK));

        l2[idx] = to;
        from += BIT(VADDR_L2_OFFSET_BITS);
        to += incr * BIT(VADDR_L2_OFFSET_BITS);
    }
}

static u64 *hv_pt_get_l3(u64 from)
{
    u64 *l2 = hv_pt_get_l2(from);
    u64 l2idx = (from >> VADDR_L2_OFFSET_BITS) & MASK(VADDR_L2_INDEX_BITS);
    u64 l2d = l2[l2idx];

    if (L2_IS_TABLE(l2d))
        return (u64 *)(l2d & PTE_TARGET_MASK);

    u64 *l3 = (u64 *)memalign(PAGE_SIZE, ENTRIES_PER_L3_TABLE * sizeof(u64));
    if (l2d) {
        u64 incr = 0;
        u64 l3d = l2d;
        if (IS_HW(l2d)) {
            l3d &= ~PTE_TYPE;
            l3d |= FIELD_PREP(PTE_TYPE, PTE_PAGE);
            incr = BIT(VADDR_L3_OFFSET_BITS);
        } else if (IS_SW(l2d) && FIELD_GET(SPTE_TYPE, l3d) == SPTE_MAP) {
            incr = BIT(VADDR_L3_OFFSET_BITS);
        }
        for (u64 idx = 0; idx < ENTRIES_PER_L3_TABLE; idx++, l3d += incr)
            l3[idx] = l3d;
    } else {
        memset64(l3, 0, ENTRIES_PER_L3_TABLE * sizeof(u64));
    }

    l2d = ((u64)l3) | FIELD_PREP(PTE_TYPE, PTE_TABLE) | PTE_VALID;
    l2[l2idx] = l2d;
    return l3;
}

static void hv_pt_map_l3(u64 from, u64 to, u64 size, u64 incr)
{
    assert((from & MASK(VADDR_L3_OFFSET_BITS)) == 0);
    assert(IS_SW(to) || (to & PTE_TARGET_MASK & MASK(VADDR_L3_OFFSET_BITS)) == 0);
    assert((size & MASK(VADDR_L3_OFFSET_BITS)) == 0);

    if (IS_HW(to))
        to |= FIELD_PREP(PTE_TYPE, PTE_PAGE);
    else
        to |= FIELD_PREP(PTE_TYPE, PTE_BLOCK);

    for (; size; size -= BIT(VADDR_L3_OFFSET_BITS)) {
        u64 idx = (from >> VADDR_L3_OFFSET_BITS) & MASK(VADDR_L3_INDEX_BITS);
        u64 *l3 = hv_pt_get_l3(from);

        if (L3_IS_TABLE(l3[idx]))
            free((void *)(l3[idx] & PTE_TARGET_MASK));

        l3[idx] = to;
        from += BIT(VADDR_L3_OFFSET_BITS);
        to += incr * BIT(VADDR_L3_OFFSET_BITS);
    }
}

static u64 *hv_pt_get_l4(u64 from)
{
    u64 *l3 = hv_pt_get_l3(from);
    u64 l3idx = (from >> VADDR_L3_OFFSET_BITS) & MASK(VADDR_L3_INDEX_BITS);
    u64 l3d = l3[l3idx];

    if (L3_IS_TABLE(l3d)) {
        return (u64 *)(l3d & PTE_TARGET_MASK);
    }

    if (IS_HW(l3d)) {
        assert(FIELD_GET(PTE_TYPE, l3d) == PTE_PAGE);
        l3d &= PTE_TARGET_MASK;
        l3d |= FIELD_PREP(PTE_TYPE, PTE_BLOCK) | FIELD_PREP(SPTE_TYPE, SPTE_MAP);
    }

    u64 *l4 = (u64 *)memalign(PAGE_SIZE, ENTRIES_PER_L4_TABLE * sizeof(u64));
    if (l3d) {
        u64 incr = 0;
        u64 l4d = l3d;
        l4d &= ~PTE_TYPE;
        l4d |= FIELD_PREP(PTE_TYPE, PTE_PAGE);
        if (FIELD_GET(SPTE_TYPE, l4d) == SPTE_MAP)
            incr = BIT(VADDR_L4_OFFSET_BITS);
        for (u64 idx = 0; idx < ENTRIES_PER_L4_TABLE; idx++, l4d += incr)
            l4[idx] = l4d;
    } else {
        memset64(l4, 0, ENTRIES_PER_L4_TABLE * sizeof(u64));
    }

    l3d = ((u64)l4) | FIELD_PREP(PTE_TYPE, PTE_TABLE);
    l3[l3idx] = l3d;
    return l4;
}

static void hv_pt_map_l4(u64 from, u64 to, u64 size, u64 incr)
{
    assert((from & MASK(VADDR_L4_OFFSET_BITS)) == 0);
    assert((size & MASK(VADDR_L4_OFFSET_BITS)) == 0);

    assert(!IS_HW(to));

    if (IS_SW(to))
        to |= FIELD_PREP(PTE_TYPE, PTE_PAGE);

    for (; size; size -= BIT(VADDR_L4_OFFSET_BITS)) {
        u64 idx = (from >> VADDR_L4_OFFSET_BITS) & MASK(VADDR_L4_INDEX_BITS);
        u64 *l4 = hv_pt_get_l4(from);

        l4[idx] = to;
        from += BIT(VADDR_L4_OFFSET_BITS);
        to += incr * BIT(VADDR_L4_OFFSET_BITS);
    }
}

int hv_map(u64 from, u64 to, u64 size, u64 incr)
{
    u64 chunk;
    bool hw = IS_HW(to);

    if (from & MASK(VADDR_L4_OFFSET_BITS) || size & MASK(VADDR_L4_OFFSET_BITS))
        return -1;

    if (hw && (from & MASK(VADDR_L3_OFFSET_BITS) || size & MASK(VADDR_L3_OFFSET_BITS))) {
        printf("HV: cannot use L4 pages with HW mappings (0x%lx -> 0x%lx)\n", from, to);
        return -1;
    }

    // L4 mappings to boundary
    chunk = min(size, ALIGN_UP(from, BIT(VADDR_L3_OFFSET_BITS)) - from);
    if (chunk) {
        assert(!hw);
        hv_pt_map_l4(from, to, chunk, incr);
        from += chunk;
        to += incr * chunk;
        size -= chunk;
    }

    // L3 mappings to boundary
    chunk = ALIGN_DOWN(min(size, ALIGN_UP(from, BIT(VADDR_L2_OFFSET_BITS)) - from),
                       BIT(VADDR_L3_OFFSET_BITS));
    if (chunk) {
        hv_pt_map_l3(from, to, chunk, incr);
        from += chunk;
        to += incr * chunk;
        size -= chunk;
    }

    // L2 mappings
    chunk = ALIGN_DOWN(size, BIT(VADDR_L2_OFFSET_BITS));
    if (chunk && (!hw || (to & VADDR_L2_ALIGN_MASK) == 0)) {
        hv_pt_map_l2(from, to, chunk, incr);
        from += chunk;
        to += incr * chunk;
        size -= chunk;
    }

    // L3 mappings to end
    chunk = ALIGN_DOWN(size, BIT(VADDR_L3_OFFSET_BITS));
    if (chunk) {
        hv_pt_map_l3(from, to, chunk, incr);
        from += chunk;
        to += incr * chunk;
        size -= chunk;
    }

    // L4 mappings to end
    if (size) {
        assert(!hw);
        hv_pt_map_l4(from, to, size, incr);
    }

    return 0;
}

int hv_unmap(u64 from, u64 size)
{
    return hv_map(from, 0, size, 0);
}

int hv_map_hw(u64 from, u64 to, u64 size)
{
    return hv_map(from, to | PTE_ATTRIBUTES | PTE_VALID, size, 1);
}

int hv_map_sw(u64 from, u64 to, u64 size)
{
    return hv_map(from, to | FIELD_PREP(SPTE_TYPE, SPTE_MAP), size, 1);
}

int hv_map_hook(u64 from, hv_hook_t *hook, u64 size)
{
    return hv_map(from, ((u64)hook) | FIELD_PREP(SPTE_TYPE, SPTE_HOOK), size, 0);
}

u64 hv_translate(u64 addr, bool s1, bool w, u64 *par_out)
{
    if (!(mrs(SCTLR_EL12) & SCTLR_M))
        return addr; // MMU off

    u64 el = FIELD_GET(SPSR_M, hv_get_spsr()) >> 2;
    u64 save = mrs(PAR_EL1);

    if (w) {
        if (s1) {
            if (el == 0)
                asm("at s1e0w, %0" : : "r"(addr));
            else
                asm("at s1e1w, %0" : : "r"(addr));
        } else {
            if (el == 0)
                asm("at s12e0w, %0" : : "r"(addr));
            else
                asm("at s12e1w, %0" : : "r"(addr));
        }
    } else {
        if (s1) {
            if (el == 0)
                asm("at s1e0r, %0" : : "r"(addr));
            else
                asm("at s1e1r, %0" : : "r"(addr));
        } else {
            if (el == 0)
                asm("at s12e0r, %0" : : "r"(addr));
            else
                asm("at s12e1r, %0" : : "r"(addr));
        }
    }

    u64 par = mrs(PAR_EL1);
    if (par_out)
        *par_out = par;
    msr(PAR_EL1, save);

    if (par & PAR_F) {
        dprintf("hv_translate(0x%lx, %d, %d): fault 0x%lx\n", addr, s1, w, par);
        return 0; // fault
    } else {
        return (par & PAR_PA) | (addr & 0xfff);
    }
}

u64 hv_pt_walk(u64 addr)
{
    dprintf("hv_pt_walk(0x%lx)\n", addr);

    u64 idx = addr >> VADDR_L1_OFFSET_BITS;
    u64 *l2;
    if (vaddr_bits > 36) {
        assert(idx < ENTRIES_PER_L1_TABLE);

        u64 l1d = hv_Ltop[idx];

        dprintf("  l1d = 0x%lx\n", l2d);

        if (!L1_IS_TABLE(l1d)) {
            dprintf("  result: 0x%lx\n", l1d);
            return l1d;
        }
        l2 = (u64 *)(l1d & PTE_TARGET_MASK);
    } else {
        assert(idx == 0);
        l2 = hv_Ltop;
    }

    idx = (addr >> VADDR_L2_OFFSET_BITS) & MASK(VADDR_L2_INDEX_BITS);
    u64 l2d = l2[idx];
    dprintf("  l2d = 0x%lx\n", l2d);

    if (!L2_IS_TABLE(l2d)) {
        if (L2_IS_SW_BLOCK(l2d))
            l2d += addr & (VADDR_L2_ALIGN_MASK | VADDR_L3_ALIGN_MASK);
        if (L2_IS_HW_BLOCK(l2d)) {
            l2d &= ~PTE_LOWER_ATTRIBUTES;
            l2d |= addr & (VADDR_L2_ALIGN_MASK | VADDR_L3_ALIGN_MASK);
        }

        dprintf("  result: 0x%lx\n", l2d);
        return l2d;
    }

    idx = (addr >> VADDR_L3_OFFSET_BITS) & MASK(VADDR_L3_INDEX_BITS);
    u64 l3d = ((u64 *)(l2d & PTE_TARGET_MASK))[idx];
    dprintf("  l3d = 0x%lx\n", l3d);

    if (!L3_IS_TABLE(l3d)) {
        if (L3_IS_SW_BLOCK(l3d))
            l3d += addr & VADDR_L3_ALIGN_MASK;
        if (L3_IS_HW_BLOCK(l3d)) {
            l3d &= ~PTE_LOWER_ATTRIBUTES;
            l3d |= addr & VADDR_L3_ALIGN_MASK;
        }
        dprintf("  result: 0x%lx\n", l3d);
        return l3d;
    }

    idx = (addr >> VADDR_L4_OFFSET_BITS) & MASK(VADDR_L4_INDEX_BITS);
    dprintf("  l4 idx = 0x%lx\n", idx);
    u64 l4d = ((u64 *)(l3d & PTE_TARGET_MASK))[idx];
    dprintf("  l4d = 0x%lx\n", l4d);
    return l4d;
}

#define CHECK_RN                                                                                   \
    if (Rn == 31)                                                                                  \
    return false
#define DECODE_OK                                                                                  \
    if (!val)                                                                                      \
    return true

#define EXT(n, b) (((s32)(((u32)(n)) << (32 - (b)))) >> (32 - (b)))

union simd_reg {
    u64 d[2];
    u32 s[4];
    u16 h[8];
    u8 b[16];
};

static bool emulate_load(struct exc_info *ctx, u32 insn, u64 *val, u64 *width, u64 *vaddr)
{
    u64 Rt = insn & 0x1f;
    u64 Rn = (insn >> 5) & 0x1f;
    u64 imm12 = EXT((insn >> 10) & 0xfff, 12);
    u64 imm9 = EXT((insn >> 12) & 0x1ff, 9);
    u64 imm7 = EXT((insn >> 15) & 0x7f, 7);
    u64 *regs = ctx->regs;

    union simd_reg simd[32];

    *width = insn >> 30;

    if (val)
        dprintf("emulate_load(%p, 0x%08x, 0x%08lx, %ld\n", regs, insn, *val, *width);

    if ((insn & 0x3fe00400) == 0x38400400) {
        // LDRx (immediate) Pre/Post-index
        CHECK_RN;
        DECODE_OK;
        regs[Rn] += imm9;
        regs[Rt] = *val;
    } else if ((insn & 0x3fc00000) == 0x39400000) {
        // LDRx (immediate) Unsigned offset
        DECODE_OK;
        regs[Rt] = *val;
    } else if ((insn & 0x3fa00400) == 0x38800400) {
        // LDRSx (immediate) Pre/Post-index
        CHECK_RN;
        DECODE_OK;
        regs[Rn] += imm9;
        regs[Rt] = (s64)EXT(*val, 8 << *width);
        if (insn & (1 << 22))
            regs[Rt] &= 0xffffffff;
    } else if ((insn & 0x3fa00000) == 0x39800000) {
        // LDRSx (immediate) Unsigned offset
        DECODE_OK;
        regs[Rt] = (s64)EXT(*val, 8 << *width);
        if (insn & (1 << 22))
            regs[Rt] &= 0xffffffff;
    } else if ((insn & 0x3fe04c00) == 0x38604800) {
        // LDRx (register)
        DECODE_OK;
        regs[Rt] = *val;
    } else if ((insn & 0x3fa04c00) == 0x38a04800) {
        // LDRSx (register)
        DECODE_OK;
        regs[Rt] = (s64)EXT(*val, 8 << *width);
        if (insn & (1 << 22))
            regs[Rt] &= 0xffffffff;
    } else if ((insn & 0x3fe00c00) == 0x38400000) {
        // LDURx (unscaled)
        DECODE_OK;
        regs[Rt] = *val;
    } else if ((insn & 0x3fa00c00) == 0x38a00000) {
        // LDURSx (unscaled)
        DECODE_OK;
        regs[Rt] = (s64)EXT(*val, (8 << *width));
        if (insn & (1 << 22))
            regs[Rt] &= 0xffffffff;
    } else if ((insn & 0xffc00000) == 0x29400000) {
        // LDP (Signed offset, 32-bit)
        *width = 3;
        *vaddr = regs[Rn] + (imm7 * 4);
        DECODE_OK;
        u64 Rt2 = (insn >> 10) & 0x1f;
        regs[Rt] = val[0] & 0xffffffff;
        regs[Rt2] = val[0] >> 32;
    } else if ((insn & 0xffc00000) == 0xa9400000) {
        // LDP (Signed offset, 64-bit)
        *width = 4;
        *vaddr = regs[Rn] + (imm7 * 8);
        DECODE_OK;
        u64 Rt2 = (insn >> 10) & 0x1f;
        regs[Rt] = val[0];
        regs[Rt2] = val[1];
    } else if ((insn & 0xfec00000) == 0xa8c00000) {
        // LDP (pre/post-increment, 64-bit)
        *width = 4;
        *vaddr = regs[Rn] + ((insn & BIT(24)) ? (imm7 * 8) : 0);
        DECODE_OK;
        regs[Rn] += imm7 * 8;
        u64 Rt2 = (insn >> 10) & 0x1f;
        regs[Rt] = val[0];
        regs[Rt2] = val[1];
    } else if ((insn & 0xfec00000) == 0xac400000) {
        // LD[N]P (SIMD&FP, 128-bit) Signed offset
        *width = 5;
        *vaddr = regs[Rn] + (imm7 * 16);
        DECODE_OK;
        u64 Rt2 = (insn >> 10) & 0x1f;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = val[1];
        simd[Rt2].d[0] = val[2];
        simd[Rt2].d[1] = val[3];
        put_simd_state(simd);
    } else if ((insn & 0x3fc00000) == 0x3d400000) {
        // LDR (immediate, SIMD&FP) Unsigned offset
        *vaddr = regs[Rn] + (imm12 << *width);
        DECODE_OK;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = 0;
        put_simd_state(simd);
    } else if ((insn & 0xffc00000) == 0x3dc00000) {
        // LDR (immediate, SIMD&FP) Unsigned offset, 128-bit
        *width = 4;
        *vaddr = regs[Rn] + (imm12 << *width);
        DECODE_OK;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = val[1];
        put_simd_state(simd);
    } else if ((insn & 0xffe00c00) == 0x3cc00000) {
        // LDURx (unscaled, SIMD&FP, 128-bit)
        *width = 4;
        *vaddr = regs[Rn] + (imm9 << *width);
        DECODE_OK;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = val[1];
        put_simd_state(simd);
    } else if ((insn & 0x3fe00400) == 0x3c400400) {
        // LDR (immediate, SIMD&FP) Pre/Post-index
        CHECK_RN;
        DECODE_OK;
        regs[Rn] += imm9;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = 0;
        put_simd_state(simd);
    } else if ((insn & 0xffe00400) == 0x3cc00400) {
        // LDR (immediate, SIMD&FP) Pre/Post-index, 128-bit
        *width = 4;
        CHECK_RN;
        DECODE_OK;
        regs[Rn] += imm9;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = val[1];
        put_simd_state(simd);
    } else if ((insn & 0x3fe04c00) == 0x3c604800) {
        // LDR (register, SIMD&FP)
        DECODE_OK;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = 0;
        put_simd_state(simd);
    } else if ((insn & 0xffe04c00) == 0x3ce04800) {
        // LDR (register, SIMD&FP), 128-bit
        *width = 4;
        DECODE_OK;
        get_simd_state(simd);
        simd[Rt].d[0] = val[0];
        simd[Rt].d[1] = val[1];
        put_simd_state(simd);
    } else if ((insn & 0xbffffc00) == 0x0d408400) {
        // LD1 (single structure) No offset, 64-bit
        *width = 3;
        DECODE_OK;
        u64 index = (insn >> 30) & 1;
        get_simd_state(simd);
        simd[Rt].d[index] = val[0];
        put_simd_state(simd);
    } else if ((insn & 0x3ffffc00) == 0x08dffc00) {
        // LDAR*
        DECODE_OK;
        regs[Rt] = *val;
    } else {
        return false;
    }
    return true;
}

static bool emulate_store(struct exc_info *ctx, u32 insn, u64 *val, u64 *width, u64 *vaddr)
{
    u64 Rt = insn & 0x1f;
    u64 Rn = (insn >> 5) & 0x1f;
    u64 imm9 = EXT((insn >> 12) & 0x1ff, 9);
    u64 imm7 = EXT((insn >> 15) & 0x7f, 7);
    u64 *regs = ctx->regs;

    union simd_reg simd[32];

    *width = insn >> 30;

    dprintf("emulate_store(%p, 0x%08x, ..., %ld) = ", regs, insn, *width);

    regs[31] = 0;

    u64 mask = 0xffffffffffffffffUL;

    if (*width < 3)
        mask = (1UL << (8 << *width)) - 1;

    if ((insn & 0x3fe00400) == 0x38000400) {
        // STRx (immediate) Pre/Post-index
        CHECK_RN;
        regs[Rn] += imm9;
        *val = regs[Rt] & mask;
    } else if ((insn & 0x3fc00000) == 0x39000000) {
        // STRx (immediate) Unsigned offset
        *val = regs[Rt] & mask;
    } else if ((insn & 0x3fe04c00) == 0x38204800) {
        // STRx (register)
        *val = regs[Rt] & mask;
    } else if ((insn & 0xfec00000) == 0x28000000) {
        // ST[N]P (Signed offset, 32-bit)
        *vaddr = regs[Rn] + (imm7 * 4);
        u64 Rt2 = (insn >> 10) & 0x1f;
        val[0] = (regs[Rt] & 0xffffffff) | (regs[Rt2] << 32);
        *width = 3;
    } else if ((insn & 0xfec00000) == 0xa8000000) {
        // ST[N]P (Signed offset, 64-bit)
        *vaddr = regs[Rn] + (imm7 * 8);
        u64 Rt2 = (insn >> 10) & 0x1f;
        val[0] = regs[Rt];
        val[1] = regs[Rt2];
        *width = 4;
    } else if ((insn & 0xfec00000) == 0xa8800000) {
        // ST[N]P (immediate, 64-bit, pre/post-index)
        CHECK_RN;
        *vaddr = regs[Rn] + ((insn & BIT(24)) ? (imm7 * 8) : 0);
        regs[Rn] += (imm7 * 8);
        u64 Rt2 = (insn >> 10) & 0x1f;
        val[0] = regs[Rt];
        val[1] = regs[Rt2];
        *width = 4;
    } else if ((insn & 0x3fc00000) == 0x3d000000) {
        // STR (immediate, SIMD&FP) Unsigned offset, 8..64-bit
        get_simd_state(simd);
        *val = simd[Rt].d[0];
    } else if ((insn & 0x3fe04c00) == 0x3c204800) {
        // STR (register, SIMD&FP) 8..64-bit
        get_simd_state(simd);
        *val = simd[Rt].d[0];
    } else if ((insn & 0xffe04c00) == 0x3ca04800) {
        // STR (register, SIMD&FP) 128-bit
        get_simd_state(simd);
        val[0] = simd[Rt].d[0];
        val[1] = simd[Rt].d[1];
        *width = 4;
    } else if ((insn & 0xffc00000) == 0x3d800000) {
        // STR (immediate, SIMD&FP) Unsigned offset, 128-bit
        get_simd_state(simd);
        val[0] = simd[Rt].d[0];
        val[1] = simd[Rt].d[1];
        *width = 4;
    } else if ((insn & 0xffe00000) == 0xbc000000) {
        // STUR (immediate, SIMD&FP) 32-bit
        get_simd_state(simd);
        val[0] = simd[Rt].s[0];
        *width = 2;
    } else if ((insn & 0xffe00000) == 0xfc000000) {
        // STUR (immediate, SIMD&FP) 64-bit
        get_simd_state(simd);
        val[0] = simd[Rt].d[0];
        *width = 3;
    } else if ((insn & 0xffe00000) == 0x3c800000) {
        // STUR (immediate, SIMD&FP) 128-bit
        get_simd_state(simd);
        val[0] = simd[Rt].d[0];
        val[1] = simd[Rt].d[1];
        *width = 4;
    } else if ((insn & 0xffc00000) == 0x2d000000) {
        // STP (SIMD&FP, 128-bit) Signed offset
        *vaddr = regs[Rn] + (imm7 * 4);
        u64 Rt2 = (insn >> 10) & 0x1f;
        get_simd_state(simd);
        val[0] = simd[Rt].s[0] | (((u64)simd[Rt2].s[0]) << 32);
        *width = 3;
    } else if ((insn & 0xffc00000) == 0xad000000) {
        // STP (SIMD&FP, 128-bit) Signed offset
        *vaddr = regs[Rn] + (imm7 * 16);
        u64 Rt2 = (insn >> 10) & 0x1f;
        get_simd_state(simd);
        val[0] = simd[Rt].d[0];
        val[1] = simd[Rt].d[1];
        val[2] = simd[Rt2].d[0];
        val[3] = simd[Rt2].d[1];
        *width = 5;
    } else if ((insn & 0x3fe00c00) == 0x38000000) {
        // STURx (unscaled)
        *val = regs[Rt] & mask;
    } else if ((insn & 0xffffffe0) == 0xd50b7420) {
        // DC ZVA
        *vaddr = regs[Rt];
        memset(val, 0, CACHE_LINE_SIZE);
        *width = CACHE_LINE_LOG2;
    } else if ((insn & 0x3ffffc00) == 0x089ffc00) {
        // STL  qR*
        *val = regs[Rt] & mask;
    } else {
        return false;
    }

    dprintf("0x%lx\n", *width);

    return true;
}

static void emit_mmiotrace(u64 pc, u64 addr, u64 *data, u64 width, u64 flags, bool sync)
{
    struct hv_evt_mmiotrace evt = {
        .flags = flags | FIELD_PREP(MMIO_EVT_CPU, smp_id()),
        .pc = pc,
        .addr = addr,
    };

    if (width > 3)
        evt.flags |= FIELD_PREP(MMIO_EVT_WIDTH, 3) | MMIO_EVT_MULTI;
    else
        evt.flags |= FIELD_PREP(MMIO_EVT_WIDTH, width);

    for (int i = 0; i < (1 << width); i += 8) {
        evt.data = *data++;
        hv_wdt_suspend();
        uartproxy_send_event(EVT_MMIOTRACE, &evt, sizeof(evt));
        if (sync) {
            iodev_flush(uartproxy_iodev);
        }
        hv_wdt_resume();
        evt.addr += 8;
    }
}

bool hv_pa_write(struct exc_info *ctx, u64 addr, u64 *val, int width)
{
    sysop("dsb sy");
    exc_count = 0;
    exc_guard = GUARD_SKIP;
    switch (width) {
        case 0:
            write8(addr, val[0]);
            break;
        case 1:
            write16(addr, val[0]);
            break;
        case 2:
            write32(addr, val[0]);
            break;
        case 3:
            write64(addr, val[0]);
            break;
        case 4:
        case 5:
        case 6:
            for (u64 i = 0; i < (1UL << (width - 3)); i++)
                write64(addr + 8 * i, val[i]);
            break;
        default:
            dprintf("HV: unsupported write width %ld\n", width);
            exc_guard = GUARD_OFF;
            return false;
    }
    // Make sure we catch SErrors here
    sysop("dsb sy");
    sysop("isb");
    exc_guard = GUARD_OFF;
    if (exc_count) {
        printf("HV: Exception during write to 0x%lx (width: %d)\n", addr, width);
        // Update exception info with "real" cause
        ctx->esr = hv_get_esr();
        ctx->far = hv_get_far();
        return false;
    }
    return true;
}

bool hv_pa_read(struct exc_info *ctx, u64 addr, u64 *val, int width)
{
    sysop("dsb sy");
    exc_count = 0;
    exc_guard = GUARD_SKIP;
    switch (width) {
        case 0:
            val[0] = read8(addr);
            break;
        case 1:
            val[0] = read16(addr);
            break;
        case 2:
            val[0] = read32(addr);
            break;
        case 3:
            val[0] = read64(addr);
            break;
        case 4:
            val[0] = read64(addr);
            val[1] = read64(addr + 8);
            break;
        case 5:
            val[0] = read64(addr);
            val[1] = read64(addr + 8);
            val[2] = read64(addr + 16);
            val[3] = read64(addr + 24);
            break;
        default:
            dprintf("HV: unsupported read width %ld\n", width);
            exc_guard = GUARD_OFF;
            return false;
    }
    sysop("dsb sy");
    exc_guard = GUARD_OFF;
    if (exc_count) {
        dprintf("HV: Exception during read from 0x%lx (width: %d)\n", addr, width);
        // Update exception info with "real" cause
        ctx->esr = hv_get_esr();
        ctx->far = hv_get_far();
        return false;
    }
    return true;
}

bool hv_pa_rw(struct exc_info *ctx, u64 addr, u64 *val, bool write, int width)
{
    if (write)
        return hv_pa_write(ctx, addr, val, width);
    else
        return hv_pa_read(ctx, addr, val, width);
}

static bool hv_emulate_rw_aligned(struct exc_info *ctx, u64 pte, u64 vaddr, u64 ipa, u64 *val,
                                  bool is_write, u64 width, u64 elr, u64 par)
{
    assert(pte);
    assert(((ipa & 0x3fff) + (1 << width)) <= 0x4000);

    u64 target = pte & PTE_TARGET_MASK_L4;
    u64 paddr = target | (vaddr & MASK(VADDR_L4_OFFSET_BITS));
    u64 flags = FIELD_PREP(MMIO_EVT_ATTR, FIELD_GET(PAR_ATTR, par)) |
                FIELD_PREP(MMIO_EVT_SH, FIELD_GET(PAR_SH, par));

    // For split ops, treat hardware mapped pages as SPTE_MAP
    if (IS_HW(pte))
        pte = target | FIELD_PREP(PTE_TYPE, PTE_BLOCK) | FIELD_PREP(SPTE_TYPE, SPTE_MAP);

    if (is_write) {
        // Write
        hv_wdt_breadcrumb('3');

        if (pte & SPTE_TRACE_WRITE)
            emit_mmiotrace(elr, ipa, val, width, flags | MMIO_EVT_WRITE, pte & SPTE_TRACE_UNBUF);

        hv_wdt_breadcrumb('4');

        switch (FIELD_GET(SPTE_TYPE, pte)) {
            case SPTE_PROXY_HOOK_R:
                paddr = ipa;
                // fallthrough
            case SPTE_MAP:
                hv_wdt_breadcrumb('5');
                dprintf("HV: SPTE_MAP[W] @0x%lx 0x%lx -> 0x%lx (w=%d): 0x%lx\n", elr, ipa, paddr,
                        1 << width, val[0]);
                if (!hv_pa_write(ctx, paddr, val, width))
                    return false;
                break;
            case SPTE_HOOK: {
                hv_wdt_breadcrumb('6');
                hv_hook_t *hook = (hv_hook_t *)target;
                if (!hook(ctx, ipa, val, true, width))
                    return false;
                dprintf("HV: SPTE_HOOK[W] @0x%lx 0x%lx -> 0x%lx (w=%d) @%p: 0x%lx\n", elr, far, ipa,
                        1 << width, hook, wval);
                break;
            }
            case SPTE_PROXY_HOOK_RW:
            case SPTE_PROXY_HOOK_W: {
                hv_wdt_breadcrumb('7');
                struct hv_vm_proxy_hook_data hook = {
                    .flags = FIELD_PREP(MMIO_EVT_WIDTH, width) | MMIO_EVT_WRITE | flags,
                    .id = FIELD_GET(PTE_TARGET_MASK_L4, pte),
                    .addr = ipa,
                    .data = {0},
                };
                memcpy(hook.data, val, 1 << width);
                hv_exc_proxy(ctx, START_HV, HV_HOOK_VM, &hook);
                break;
            }
            default:
                printf("HV: invalid SPTE 0x%016lx for IPA 0x%lx\n", pte, ipa);
                return false;
        }
    } else {
        hv_wdt_breadcrumb('3');
        switch (FIELD_GET(SPTE_TYPE, pte)) {
            case SPTE_PROXY_HOOK_W:
                paddr = ipa;
                // fallthrough
            case SPTE_MAP:
                hv_wdt_breadcrumb('4');
                if (!hv_pa_read(ctx, paddr, val, width))
                    return false;
                dprintf("HV: SPTE_MAP[R] @0x%lx 0x%lx -> 0x%lx (w=%d): 0x%lx\n", elr, ipa, paddr,
                        1 << width, val[0]);
                break;
            case SPTE_HOOK: {
                hv_wdt_breadcrumb('5');
                hv_hook_t *hook = (hv_hook_t *)target;
                if (!hook(ctx, ipa, val, false, width))
                    return false;
                dprintf("HV: SPTE_HOOK[R] @0x%lx 0x%lx -> 0x%lx (w=%d) @%p: 0x%lx\n", elr, far, ipa,
                        1 << width, hook, val);
                break;
            }
            case SPTE_PROXY_HOOK_RW:
            case SPTE_PROXY_HOOK_R: {
                hv_wdt_breadcrumb('6');
                struct hv_vm_proxy_hook_data hook = {
                    .flags = FIELD_PREP(MMIO_EVT_WIDTH, width) | flags,
                    .id = FIELD_GET(PTE_TARGET_MASK_L4, pte),
                    .addr = ipa,
                };
                hv_exc_proxy(ctx, START_HV, HV_HOOK_VM, &hook);
                memcpy(val, hook.data, 1 << width);
                break;
            }
            default:
                printf("HV: invalid SPTE 0x%016lx for IPA 0x%lx\n", pte, ipa);
                return false;
        }

        hv_wdt_breadcrumb('7');
        if (pte & SPTE_TRACE_READ)
            emit_mmiotrace(elr, ipa, val, width, flags, pte & SPTE_TRACE_UNBUF);
    }

    hv_wdt_breadcrumb('*');

    return true;
}

static bool hv_emulate_rw(struct exc_info *ctx, u64 pte, u64 vaddr, u64 ipa, u8 *val, bool is_write,
                          u64 bytes, u64 elr, u64 par)
{
    u64 aval[HV_MAX_RW_WORDS];

    bool advance = (IS_HW(pte) || (IS_SW(pte) && FIELD_GET(SPTE_TYPE, pte) == SPTE_MAP)) ? 1 : 0;
    u64 off = 0;
    u64 width;

    bool first = true;

    u64 left = bytes;
    u64 paddr = (pte & PTE_TARGET_MASK_L4) | (vaddr & MASK(VADDR_L4_OFFSET_BITS));

    while (left > 0) {
        memset(aval, 0, sizeof(aval));

        if (left >= 64 && (ipa & 63) == 0)
            width = 6;
        else if (left >= 32 && (ipa & 31) == 0)
            width = 5;
        else if (left >= 16 && (ipa & 15) == 0)
            width = 4;
        else if (left >= 8 && (ipa & 7) == 0)
            width = 3;
        else if (left >= 4 && (ipa & 3) == 0)
            width = 2;
        else if (left >= 2 && (ipa & 1) == 0)
            width = 1;
        else
            width = 0;

        u64 chunk = 1 << width;

        /*
        if (chunk != bytes)
            printf("HV: Splitting unaligned %ld-byte %s: %ld bytes @ 0x%lx\n", bytes,
                is_write ? "write" : "read", chunk, vaddr);
        */

        if (is_write)
            memcpy(aval, val + off, chunk);

        if (advance)
            pte = (paddr & PTE_TARGET_MASK_L4) | (pte & ~PTE_TARGET_MASK_L4);

        if (!hv_emulate_rw_aligned(ctx, pte, vaddr, ipa, aval, is_write, width, elr, par)) {
            if (!first)
                printf("HV: WARNING: Failed to emulate split op but part of it did commit!\n");
            return false;
        }

        if (!is_write)
            memcpy(val + off, aval, chunk);

        left -= chunk;
        off += chunk;

        ipa += chunk;
        vaddr += chunk;
        if (advance)
            paddr += chunk;

        first = 0;
    }

    return true;
}

bool hv_handle_dabort(struct exc_info *ctx)
{
    hv_wdt_breadcrumb('0');
    u64 esr = hv_get_esr();
    bool is_write = esr & ESR_ISS_DABORT_WnR;

    u64 far = hv_get_far();
    u64 par;
    u64 ipa = hv_translate(far, true, is_write, &par);

    dprintf("hv_handle_abort(): stage 1 0x%0lx -> 0x%lx\n", far, ipa);

    if (!ipa) {
        printf("HV: stage 1 translation failed at VA 0x%0lx\n", far);
        return false;
    }

    if (ipa >= BIT(vaddr_bits)) {
        printf("hv_handle_abort(): IPA out of bounds: 0x%0lx -> 0x%lx\n", far, ipa);
        return false;
    }

    u64 pte = hv_pt_walk(ipa);

    if (!pte) {
        printf("HV: Unmapped IPA 0x%lx\n", ipa);
        return false;
    }

    if (IS_HW(pte)) {
        printf("HV: Data abort on mapped page (0x%lx -> 0x%lx)\n", far, pte);
        // Try again, this is usually a race
        ctx->elr -= 4;
        return true;
    }

    hv_wdt_breadcrumb('1');

    assert(IS_SW(pte));

    u64 elr = ctx->elr;
    u64 elr_pa = hv_translate(elr, false, false, NULL);
    if (!elr_pa) {
        printf("HV: Failed to fetch instruction for data abort at 0x%lx\n", elr);
        return false;
    }

    u32 insn = read32(elr_pa);
    u64 width;

    hv_wdt_breadcrumb('2');

    u64 vaddr = far;

    u8 val[HV_MAX_RW_SIZE] ALIGNED(HV_MAX_RW_SIZE);
    memset(val, 0, sizeof(val));

    if (is_write) {
        hv_wdt_breadcrumb('W');

        if (!emulate_store(ctx, insn, (u64 *)val, &width, &vaddr)) {
            printf("HV: store not emulated: 0x%08x at 0x%lx\n", insn, ipa);
            return false;
        }
    } else {
        hv_wdt_breadcrumb('R');

        if (!emulate_load(ctx, insn, NULL, &width, &vaddr)) {
            printf("HV: load not emulated: 0x%08x at 0x%lx\n", insn, ipa);
            return false;
        }
    }

    /*
     Check for HW page-straddling conditions
     Right now we only support the case where the page boundary is exactly halfway
     through the read/write.
    */
    u64 bytes = 1 << width;
    u64 vaddrp0 = vaddr & ~MASK(VADDR_L3_OFFSET_BITS);
    u64 vaddrp1 = (vaddr + bytes - 1) & ~MASK(VADDR_L3_OFFSET_BITS);

    if (vaddrp0 == vaddrp1) {
        // Easy case, no page straddle
        if (far != vaddr) {
            printf("HV: faulted at 0x%lx, but expecting 0x%lx\n", far, vaddr);
            return false;
        }

        if (!hv_emulate_rw(ctx, pte, vaddr, ipa, val, is_write, bytes, elr, par))
            return false;
    } else {
        // Oops, we're straddling a page boundary
        // Treat it as two separate loads or stores

        assert(bytes > 1);
        hv_wdt_breadcrumb('s');

        u64 off = vaddrp1 - vaddr;

        u64 vaddr2;
        const char *other;
        if (far == vaddr) {
            other = "upper";
            vaddr2 = vaddrp1;
        } else {
            if (far != vaddrp1) {
                printf("HV: faulted at 0x%lx, but expecting 0x%lx\n", far, vaddrp1);
                return false;
            }
            other = "lower";
            vaddr2 = vaddr;
        }

        u64 par2;
        u64 ipa2 = hv_translate(vaddr2, true, esr & ESR_ISS_DABORT_WnR, &par2);
        if (!ipa2) {
            printf("HV: %s half stage 1 translation failed at VA 0x%0lx\n", other, vaddr2);
            return false;
        }
        if (ipa2 >= BIT(vaddr_bits)) {
            printf("hv_handle_abort(): %s half IPA out of bounds: 0x%0lx -> 0x%lx\n", other, vaddr2,
                   ipa2);
            return false;
        }

        u64 pte2 = hv_pt_walk(ipa2);
        if (!pte2) {
            printf("HV: Unmapped %s half IPA 0x%lx\n", other, ipa2);
            return false;
        }

        hv_wdt_breadcrumb('S');

        printf("HV: Emulating %s straddling page boundary as two ops @ 0x%lx (%ld bytes)\n",
               is_write ? "write" : "read", vaddr, bytes);

        bool upper_ret;
        if (far == vaddr) {
            if (!hv_emulate_rw(ctx, pte, vaddr, ipa, val, is_write, off, elr, par))
                return false;
            upper_ret =
                hv_emulate_rw(ctx, pte2, vaddr2, ipa2, val + off, is_write, bytes - off, elr, par2);
        } else {
            if (!hv_emulate_rw(ctx, pte2, vaddr2, ipa2, val, is_write, off, elr, par2))
                return false;
            upper_ret =
                hv_emulate_rw(ctx, pte, vaddrp1, ipa, val + off, is_write, bytes - off, elr, par);
        }

        if (!upper_ret) {
            printf("HV: WARNING: Failed to emulate upper half but lower half did commit!\n");
            return false;
        }
    }

    if (vaddrp0 != vaddrp1) {
        printf("HV: Straddled r/w data:\n");
        hexdump(val, bytes);
    }

    hv_wdt_breadcrumb('8');
    if (!is_write && !emulate_load(ctx, insn, (u64 *)val, &width, &vaddr))
        return false;

    hv_wdt_breadcrumb('9');

    return true;
}
