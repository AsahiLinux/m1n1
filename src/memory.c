/* SPDX-License-Identifier: MIT */

#include "memory.h"
#include "utils.h"

#define PAGE_SIZE       0x4000
#define CACHE_LINE_SIZE 64

#define CACHE_RANGE_OP(func, op)                                                                   \
    void func(void *addr, size_t length)                                                           \
    {                                                                                              \
        u64 p = (u64)addr;                                                                         \
        u64 end = p + length;                                                                      \
        while (p < end) {                                                                          \
            cacheop(op, p);                                                                        \
            p += CACHE_LINE_SIZE;                                                                  \
        }                                                                                          \
    }

CACHE_RANGE_OP(ic_ivau_range, "ic ivau")
CACHE_RANGE_OP(dc_ivac_range, "dc ivac")
CACHE_RANGE_OP(dc_zva_range, "dc zva")
CACHE_RANGE_OP(dc_cvac_range, "dc cvac")
CACHE_RANGE_OP(dc_cvau_range, "dc cvau")
CACHE_RANGE_OP(dc_civac_range, "dc civac")

static inline u64 read_sctlr(void)
{
    sysop("isb");
    return mrs(SCTLR_EL2);
}

static inline void write_sctlr(u64 val)
{
    msr(SCTLR_EL2, val);
    sysop("isb");
}

/*
 * https://armv8-ref.codingbelief.com/en/chapter_d4/d43_2_armv8_translation_table_level_3_descriptor_formats.html
 * PTE_TYPE_BLOCK indicates that the page table entry (PTE) points to a physical memory block
 * PTE_TYPE_TABLE indicates that the PTE points to another PTE
 * PTE_FLAG_ACCESS is required to allow access to the memory region
 * PTE_MAIR_INDEX sets the MAIR index to be used for this PTE
 */
#define PTE_TYPE_BLOCK    0b01
#define PTE_TYPE_TABLE    0b11
#define PTE_FLAG_ACCESS   (1 << 10)
#define PTE_MAIR_INDEX(i) ((i & 7) << 2)
#define PTE_PXN           (1L << 53)
#define PTE_UXN           (1L << 54)
#define PTE_AP_RO         (1L << 7)
#define PTE_AP_EL0        (1L << 6)

#define PERM_RO  PTE_AP_RO | PTE_PXN | PTE_UXN
#define PERM_RW  PTE_PXN | PTE_UXN
#define PERM_RWX 0

/*
 * https://developer.arm.com/docs/ddi0595/g/aarch64-system-registers/sctlr_el2
 * SCTLR_I enables instruction caches.
 * SCTLR_C enables data caches.
 * SCTLR_M enables the MMU.
 */
#define SCTLR_I (1UL << 12)
#define SCTLR_C (1UL << 2)
#define SCTLR_M (1UL)

/*
 * https://developer.arm.com/docs/ddi0595/h/aarch64-system-registers/tcr_el2
 * TCR_IPS_1TB selects 40 bits/1TB intermediate physical address size
 * TCR_PS_1TB selects 40 bits/1TB physical address size
 * TCR_TG0_16K selects 16K pages
 * TCR_SH0_IS marks memory used during translation table walks as inner sharable
 * TCR_ORGN0_WBWA and TCR_IRGN0_WBWA set the cacheability atrributes for memory
 *                used during translation table walks to Inner/Outer
 *                Write-Back Read-Allocate Write-Allocate Cacheable
 * TCR_T0SZ_48BIT selects 48bit virtual addresses
 */
#define TCR_IPS_1TB    ((0b010UL) << 32)
#define TCR_TG1_16K    ((0b01UL) << 30)
#define TCR_SH1_IS     ((0b11UL) << 28)
#define TCR_ORGN1_WBWA ((0b01UL) << 26)
#define TCR_IRGN1_WBWA ((0b01UL) << 24)
#define TCR_T1SZ_48BIT ((16UL) << 16)
#define TCR_TG0_16K    ((0b10UL) << 14)
#define TCR_SH0_IS     ((0b11UL) << 12)
#define TCR_ORGN0_WBWA ((0b01UL) << 10)
#define TCR_IRGN0_WBWA ((0b01UL) << 8)
#define TCR_T0SZ_48BIT ((16UL) << 0)

/*
 * aarch64 allows to configure attribute sets for up to eight different memory
 * types. we need normal memory and two types of device memory (nGnRnE and
 * nGnRE) in m1n1.
 * The indexes here are selected arbitrarily: A page table entry
 * contains a field to select one of these which will then be used
 * to select the corresponding memory access flags from MAIR.
 */
#define MAIR_INDEX_NORMAL        0
#define MAIR_INDEX_DEVICE_nGnRnE 1
#define MAIR_INDEX_DEVICE_nGnRE  2

#define MAIR_SHIFT_NORMAL        (MAIR_INDEX_NORMAL * 8)
#define MAIR_SHIFT_DEVICE_nGnRnE (MAIR_INDEX_DEVICE_nGnRnE * 8)
#define MAIR_SHIFT_DEVICE_nGnRE  (MAIR_INDEX_DEVICE_nGnRE * 8)

/*
 * https://developer.arm.com/documentation/ddi0500/e/system-control/aarch64-register-descriptions/memory-attribute-indirection-register--el1
 *
 * MAIR_ATTR_NORMAL_DEFAULT sets Normal Memory, Outer Write-back non-transient,
 *                          Inner Write-back non-transient, R=1, W=1
 * MAIR_ATTR_DEVICE_nGnRnE  sets Device-nGnRnE memory
 * MAIR_ATTR_DEVICE_nGnRE   sets Device-nGnRE memory
 */
#define MAIR_ATTR_NORMAL_DEFAULT 0xffUL
#define MAIR_ATTR_DEVICE_nGnRnE  0x00UL
#define MAIR_ATTR_DEVICE_nGnRE   0x04UL

/*
 * We want use 16KB pages which would usually result in the following
 * virtual address space:
 *
 * [L0 index]  [L1 index]  [L2 index]  [L3 index] [page offset]
 *   1 bit      11 bits      11 bits     11 bits    14 bits
 *
 * To simplify things we only allow 32MB mappings directly from
 * the L2 tables such that in m1n1 all virtual addresses will look like this
 * instead (Block maps from L0 or L1 are not possible with 16KB pages):
 *
 * [L0 index]  [L1 index]  [L2 index]  [page offset]
 *   1 bit      11 bits      11 bits     25 bits
 *
 * We initalize two L1 tables which cover the entire virtual memory space,
 * point to them in the singe L0 table and then create L2 tables on demand.
 */
#define VADDR_PAGE_OFFSET_BITS 25
#define VADDR_L2_INDEX_BITS    11
#define VADDR_L1_INDEX_BITS    11
#define VADDR_L0_INDEX_BITS    1

#define MAX_L2_TABLES     10
#define ENTRIES_PER_TABLE 2048
#define L2_PAGE_SIZE      0x2000000

static u64 pagetable_L0[2] ALIGNED(PAGE_SIZE);
static u64 pagetable_L1[2][ENTRIES_PER_TABLE] ALIGNED(PAGE_SIZE);
static u64 pagetable_L2[MAX_L2_TABLES][ENTRIES_PER_TABLE] ALIGNED(PAGE_SIZE);
static u32 pagetable_L2_next = 0;

static u64 mmu_make_block_pte(uintptr_t addr, u8 attribute_index, u64 perms)
{
    u64 pte = PTE_TYPE_BLOCK;
    pte |= addr;
    pte |= PTE_FLAG_ACCESS;
    pte |= PTE_MAIR_INDEX(attribute_index);
    pte |= perms;

    return pte;
}

static u64 mmu_make_table_pte(u64 *addr)
{
    u64 pte = PTE_TYPE_TABLE;
    pte |= (uintptr_t)addr;
    pte |= PTE_FLAG_ACCESS;
    return pte;
}

static void mmu_init_pagetables(void)
{
    memset64(pagetable_L0, 0, sizeof pagetable_L0);
    memset64(pagetable_L1, 0, sizeof pagetable_L1);
    memset64(pagetable_L2, 0, sizeof pagetable_L2);

    pagetable_L0[0] = mmu_make_table_pte(&pagetable_L1[0][0]);
    pagetable_L0[1] = mmu_make_table_pte(&pagetable_L1[1][0]);
}

static u8 mmu_extract_L0_index(uintptr_t addr)
{
    addr >>= VADDR_PAGE_OFFSET_BITS;
    addr >>= VADDR_L2_INDEX_BITS;
    addr >>= VADDR_L1_INDEX_BITS;
    addr &= (1 << VADDR_L0_INDEX_BITS) - 1;
    return (u8)addr;
}

static u64 mmu_extract_L1_index(uintptr_t addr)
{
    addr >>= VADDR_PAGE_OFFSET_BITS;
    addr >>= VADDR_L2_INDEX_BITS;
    addr &= (1 << VADDR_L1_INDEX_BITS) - 1;
    return (u64)addr;
}

static u64 mmu_extract_L2_index(uintptr_t addr)
{
    addr >>= VADDR_PAGE_OFFSET_BITS;
    addr &= (1 << VADDR_L2_INDEX_BITS) - 1;
    return (u64)addr;
}

static uintptr_t mmu_extract_addr(u64 pte)
{
    /*
     * https://armv8-ref.codingbelief.com/en/chapter_d4/d43_1_vmsav8-64_translation_table_descriptor_formats.html
     * need to extract bits [47:14]
     */
    pte &= ((1ULL << 48) - 1);
    pte &= ~((1ULL << 14) - 1);
    return (uintptr_t)pte;
}

static u64 *mmu_get_L1_table(uintptr_t addr)
{
    return pagetable_L1[mmu_extract_L0_index(addr)];
}

static u64 *mmu_get_L2_table(uintptr_t addr)
{
    u64 *tbl_l1 = mmu_get_L1_table(addr);

    u64 l1_idx = mmu_extract_L1_index(addr);
    u64 desc_l1 = tbl_l1[l1_idx];

    if (desc_l1 == 0) {
        if (pagetable_L2_next == MAX_L2_TABLES)
            panic("MMU: not enough space to create an additional L2 table to "
                  "map %lx",
                  addr);

        desc_l1 = mmu_make_table_pte((u64 *)&pagetable_L2[pagetable_L2_next++]);
        tbl_l1[l1_idx] = desc_l1;
    }

    return (u64 *)mmu_extract_addr(desc_l1);
}

static void mmu_add_single_mapping(uintptr_t from, uintptr_t to, u8 attribute_index, u64 perms)
{
    u64 *tbl_l2 = mmu_get_L2_table(from);
    u64 l2_idx = mmu_extract_L2_index(from);

    if (tbl_l2[l2_idx])
        panic("MMU: mapping for %lx already exists", from);

    tbl_l2[l2_idx] = mmu_make_block_pte(to, attribute_index, perms);
}

static void mmu_add_mapping(uintptr_t from, uintptr_t to, size_t size, u8 attribute_index,
                            u64 perms)
{
    if (from % L2_PAGE_SIZE)
        panic("mmu_add_mapping: from address not aligned: %lx", from);
    if (to % L2_PAGE_SIZE)
        panic("mmu_add_mapping: to address not aligned: %lx", to);
    if (size % L2_PAGE_SIZE)
        panic("mmu_add_mapping: size not aligned: %lx", size);

    while (size > 0) {
        mmu_add_single_mapping(from, to, attribute_index, perms);
        from += L2_PAGE_SIZE;
        to += L2_PAGE_SIZE;
        size -= L2_PAGE_SIZE;
    }
}

static void mmu_add_default_mappings(void)
{
    /*
     * create MMIO mapping as both nGnRnE (identity) and nGnRE (starting at
     * 0xf0_0000_0000)
     */
    mmu_add_mapping(0x0000000000, 0x0000000000, 0x0800000000, MAIR_INDEX_DEVICE_nGnRnE, PERM_RW);
    mmu_add_mapping(0xf000000000, 0x0000000000, 0x0800000000, MAIR_INDEX_DEVICE_nGnRE, PERM_RW);

    /*
     * create identity mapping for 16GB RAM from 0x08_0000_0000 to
     * 0x0c_0000_0000
     */
    mmu_add_mapping(0x0800000000, 0x0800000000, 0x0400000000, MAIR_INDEX_NORMAL, PERM_RWX);
}

static void mmu_configure(void)
{
    msr(MAIR_EL2, (MAIR_ATTR_NORMAL_DEFAULT << MAIR_SHIFT_NORMAL) |
                      (MAIR_ATTR_DEVICE_nGnRnE << MAIR_SHIFT_DEVICE_nGnRnE) |
                      (MAIR_ATTR_DEVICE_nGnRE << MAIR_SHIFT_DEVICE_nGnRE));
    msr(TCR_EL2, TCR_IPS_1TB | TCR_TG1_16K | TCR_SH1_IS | TCR_ORGN1_WBWA | TCR_IRGN1_WBWA |
                     TCR_T1SZ_48BIT | TCR_TG0_16K | TCR_SH0_IS | TCR_ORGN0_WBWA | TCR_IRGN0_WBWA |
                     TCR_T0SZ_48BIT);
    msr(TTBR0_EL2, (uintptr_t)pagetable_L0);
    msr(TTBR1_EL2, (uintptr_t)pagetable_L0);

    // Armv8-A Address Translation, 100940_0101_en, page 28
    sysop("dsb ishst");
    sysop("tlbi alle2");
    sysop("dsb ish");
    sysop("isb");
}

void mmu_init(void)
{
    printf("MMU: Initializing...\n");

    mmu_init_pagetables();
    mmu_add_default_mappings();
    mmu_configure();

    u64 sctlr_old = read_sctlr();
    u64 sctlr_new = sctlr_old | SCTLR_I | SCTLR_C | SCTLR_M;

    printf("MMU: SCTLR_EL2: %x -> %x\n", sctlr_old, sctlr_new);
    write_sctlr(sctlr_new);
    printf("MMU: running with MMU and caches enabled!\n");
}

void mmu_shutdown(void)
{
    printf("MMU: shutting down...\n");
    write_sctlr(read_sctlr() & ~(SCTLR_I | SCTLR_C | SCTLR_M));
    printf("MMU: shutdown successful, clearing caches\n");
    dcsw_op_all(DCSW_OP_DCCISW);
}
