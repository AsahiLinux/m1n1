/* SPDX-License-Identifier: MIT */
#ifndef SPTM_PRIVATE_H
#define SPTM_PRIVATE_H

/*
 * DO NOT MERGE: tainted SPTM endpoint emulator imported from the bringup tree.
 *
 * This is intentionally isolated under src/sptm while we separate the clean
 * hypervisor plumbing from the reverse-engineered SPTM behavior. The old tree
 * built this as a hot-loaded C object; this branch links it directly into the
 * streamed stage2 hypervisor so endpoint state has one C source of truth.
 */

typedef unsigned long      u64;
typedef unsigned int       u32;
typedef unsigned short     u16;
typedef unsigned char      u8;
typedef int                bool_t;   /* avoid <stdbool.h> in freestanding */

void dc_civac_range(void *addr, u64 length);
void mmu_add_mapping(u64 from, u64 to, u64 size, u8 attribute_index, u64 perms);
int hv_map(u64 from, u64 to, u64 size, u64 incr);
u64 hv_pt_walk(u64 addr);

/* SPTM constants — match the proxyclient/tools/sptm Python helpers. */
#define SPTM_SUCCESS                  0
#define SPTM_MAP_VALID                1
#define SPTM_UPDATE_DELAYED_TLBI      5
#define SPTM_MAP_PADDR_CONFLICT       6
#define SPTM_TABLE_NOT_PRESENT        7
#define SPTM_TABLE_ALREADY_PRESENT    8

#define SPTM_UPDATE_SW_WIRED          (1U << 0)
#define SPTM_UPDATE_PERMS_AND_WAS_WRITABLE (1U << 1)
#define SPTM_UPDATE_NG                (1U << 2)
#define SPTM_UPDATE_AF                (1U << 3)
#define SPTM_UPDATE_SH                (1U << 4)
#define SPTM_UPDATE_MAIR              (1U << 5)
#define SPTM_UPDATE_MASK              0x3fU
#define SPTM_UPDATE_DEFER_TLBI        (1U << 8)
#define SPTM_UPDATE_SKIP_PAPT         (1U << 9)

#define HV_S2_PTE_ACCESS              (1UL << 10)
#define HV_S2_PTE_SH_NS               (3UL << 8)
#define HV_S2_PTE_S2AP_RW             (3UL << 6)
#define HV_S2_MEMATTR_WB              (0xfUL << 2)
/* With HCR_EL2.FWB set, stage-2 MemAttr 5 is Normal Non-cacheable. */
#define HV_S2_MEMATTR_NORMAL_NC       (0x5UL << 2)
/*
 * GPU-shared coherency type: Outer-WB, Inner-NC (matches XNU's MAIR 0xf4 "Shared"
 * and the AGX UAT AttrIndex-2). Inner-NC makes CPU writes skip L1/L2 and reach the
 * SLC (Point of Coherency) the GPU reads, so the GPU sees ongoing CPU writes with
 * no per-write flush. Under FWB=1: bits[3:2]=outer,[1:0]=inner,{01=NC,11=WB} -> 0b1101.
 */
#define HV_S2_MEMATTR_SHARED          (0xdUL << 2)
#define HV_S2_PTE_VALID               1UL
#define HV_S2_PTE_NORMAL_WB           (HV_S2_PTE_ACCESS | HV_S2_PTE_SH_NS | \
                                       HV_S2_PTE_S2AP_RW | HV_S2_MEMATTR_WB | \
                                       HV_S2_PTE_VALID)
#define HV_S2_PTE_NORMAL_NC           (HV_S2_PTE_ACCESS | HV_S2_PTE_SH_NS | \
                                       HV_S2_PTE_S2AP_RW | \
                                       HV_S2_MEMATTR_NORMAL_NC | \
                                       HV_S2_PTE_VALID)
#define HV_S2_PTE_SHARED              (HV_S2_PTE_ACCESS | HV_S2_PTE_SH_NS | \
                                       HV_S2_PTE_S2AP_RW | \
                                       HV_S2_MEMATTR_SHARED | \
                                       HV_S2_PTE_VALID)

#define SPTM_EL2_MAIR_NORMAL          0U
#define SPTM_EL2_MAIR_NORMAL_NC       1U
#define SPTM_EL2_PERM_RWX             0UL
#define SPTM_PAPT_ATTR_RT_NC          (1UL << 2)  /* AttrIdx=1, SH=0 */
#define SPTM_PAPT_ATTR_NORMAL_WB      (2UL << 8)  /* AttrIdx=0, inner-shareable */
#define SPTM_PAPT_OPT_ALT_TO_NC       0x80000000U
#define SPTM_PAPT_OPT_ALT_TO_WB       0x40000000U

#define PAPT_UPDATE_RING_SLOTS        64
#define PAPT_UPDATE_RC_WRITE          1
#define PAPT_UPDATE_RC_SKIP_PAPT      2
#define PAPT_UPDATE_RC_NO_ATTR        3
#define PAPT_UPDATE_RC_UNMANAGED      4
#define PAPT_UPDATE_RC_BAD_TEMPLATE   5
#define PAPT_UPDATE_RC_BAD_ROOT       6
#define PAPT_UPDATE_RC_BAD_WALK       7
#define PAPT_UPDATE_RC_BAD_EXISTING   8
#define PAPT_UPDATE_RC_SAME_ATTRS     9
#define ALT_PTD_TRACE_RING_SLOTS      4
#define PAPT_NVME_CLASS_COUNT         8
#define PAPT_NVME_SEED_ASQ            0
#define PAPT_NVME_SEED_ACQ            1
#define PAPT_NVME_PRP_LIST            2
#define PAPT_NVME_XNU_ASQ             3
#define PAPT_NVME_XNU_ACQ             4
#define PAPT_NVME_XNU_IOSQ            5
#define PAPT_NVME_XNU_IOCQ            6
#define PAPT_NVME_ACTIVE_PRP          7

#define SPTM_TABLE_XNU_BOOTSTRAP      0
#define SPTM_TABLE_TXM_BOOTSTRAP      1
#define SPTM_TABLE_SK_BOOTSTRAP       2
#define SPTM_TABLE_T8110_DART_XNU     3
#define SPTM_TABLE_T8110_DART_SK      4
#define SPTM_TABLE_SART               5
#define SPTM_TABLE_NVME               6
#define SPTM_TABLE_UAT                7
#define SPTM_TABLE_SHART              8
/* Public SPTM tables call 9 "reserved", but the t8140 SPTM firmware uses it
 * for CPU trace/perf-trace helpers. Boot does not need a real trace buffer:
 * report unsupported/no-carveout/success and keep moving. */
#define SPTM_TABLE_CPUTRACE           9
#define SPTM_TABLE_HIB                10
#define SPTM_TABLE_GEN3_DART_XNU      11
#define SPTM_TABLE_GEN3_DART_SK       12
#define SPTM_TABLE_T6000_DART_XNU     13
#define SPTM_TABLE_INVALID            14
#define DART_OBJ_CACHE_SLOTS          64
#define NVME_C_MAX_CID                0x101
#define SART_C_MAX_ENTRIES            16
#define SART_C_MAX_ENDPOINTS          3

#define SPTM_GENTER_DISPATCH_CALL     0
#define SPTM_DISPATCH_RESERVED_MASK   0xff00ff0000000000UL
#define ESR_ISS_MASK                  0x1ffffffUL

/* t8140 top-level non-dispatch GENTER return sites.  Mechanical
 * genter->HVC patching erases the original immediate, so GENTER #1..#4
 * reach us as HVC #0 with arbitrary/poison x16.  Only the observed returning
 * stub is fast-pathed here; other invalid HVC #0 sites still fall through
 * loudly instead of hiding a corrupted dispatch call. */
#define XNU_265_GENTER_NODISPATCH_RET_PC 0xfffffe000bcf4d9cUL
#define XNU_266_GENTER_NODISPATCH_RET_PC 0xfffffe000bcfac08UL

#define SPTM_FN_LOCKDOWN              0
#define SPTM_FN_RETYPE                1
#define SPTM_FN_MAP_PAGE              2
#define SPTM_FN_MAP_TABLE             3
#define SPTM_FN_UNMAP_TABLE           4
#define SPTM_FN_UPDATE_REGION         5
#define SPTM_FN_UPDATE_DISJOINT       6
#define SPTM_FN_UNMAP_REGION          7
#define SPTM_FN_UNMAP_DISJOINT        8
#define SPTM_FN_CONFIGURE_SHAREDREGION 9
#define SPTM_FN_NEST_REGION           10
#define SPTM_FN_UNNEST_REGION         11
#define SPTM_FN_CONFIGURE_ROOT        12
#define SPTM_FN_SWITCH_ROOT           13
#define SPTM_FN_REGISTER_CPU          14
#define SPTM_FN_FIXUPS_COMPLETE       15
#define SPTM_FN_SIGN_USER_POINTER     16
#define SPTM_FN_AUTH_USER_POINTER     17
#define SPTM_FN_REGISTER_EXC_RETURN   18
#define SPTM_FN_CPU_ID                19
#define SPTM_FN_SLIDE_REGION          20
#define SPTM_FN_UPDATE_DISJOINT_MULTIPAGE 21
#define SPTM_FN_REG_READ              22
#define SPTM_FN_REG_WRITE             23
#define SPTM_FN_GUEST_VA_TO_IPA       24
#define SPTM_FN_GUEST_STAGE1_TLBOP    25
#define SPTM_FN_GUEST_STAGE2_TLBOP    26
#define SPTM_FN_GUEST_DISPATCH        27
#define SPTM_FN_GUEST_EXIT            28
#define SPTM_FN_MAP_SK_DOMAIN         29
#define SPTM_FN_HIB_BEGIN             30
#define SPTM_FN_HIB_VERIFY_HASH_NON_WIRED 31
#define SPTM_FN_HIB_FINALIZE_NON_WIRED 32
#define SPTM_FN_IOFILTER_PROTECTED_WRITE 33
#define SPTM_FN_SPTM_SYSCTL           37
#define SPTM_FN_DISABLE_KERNEL_MODE_CPA2 38
#define SPTM_FN_SET_SHARED_REGION     39
#define SPTM_FN_BATCH_SIGN_USER_POINTER 40
#define SPTM_FN_SURT_ALLOC            41
#define SPTM_FN_SURT_FREE             42
#define SPTM_FN_CONDEMN_LEAF_TABLE    43
#define SPTM_FN_UNCONDEMN_LEAF_TABLE  44
#define SPTM_FN_SERIAL_PUTC           45
#define SPTM_FN_SERIAL_DISABLE        46
#define SPTM_FN_PROGRAM_IRGKEY        48
#define SPTM_FN_REG_SNAPSHOT          49

#define SPTM_MAX_CPUS_EMUL            16

#define SPTM_CPU_PIO_F_SEEDED         (1ULL << 0)
#define SPTM_CPU_PIO_F_REGISTERED     (1ULL << 1)
#define SPTM_CPU_PIO_F_MISSING        (1ULL << 2)

/* NVMe table 6 endpoint IDs and state-machine constants. Endpoint semantics
 * live here; Python only seeds ADT-derived configuration and SPTM-owned
 * buffers before guest start. Endpoint 1 receives a TCB template PA and a
 * segment-list PA; it does not receive direct PRP1/PRP2 arguments. */
#define NVME_FN_ENABLE_COASTGUARD     0
#define NVME_FN_MAP_PAGES             1
#define NVME_FN_UNMAP_PAGES           2
#define NVME_FN_VALIDATE_QENTRIES     3
#define NVME_FN_BAR_ADMIN_QUEUE_REGS  4
#define NVME_FN_BAR_IOQA_REG          5
#define NVME_FN_BAR_IOSQ_REG          6
#define NVME_FN_BAR_IOCQ_REG          7
#define NVME_FN_ANS_SHA_REG           8

#define NVME_AF_ENABLE_COASTGUARD     (1u << 0)
#define NVME_AF_TCB_REGISTER          (1u << 1)
#define NVME_AF_TCB_INVALIDATE        (1u << 2)
#define NVME_AF_QUEUE_VALIDATE        (1u << 3)
#define NVME_AF_BAR_ADMIN_Q           (1u << 4)
#define NVME_AF_BAR_IOQA              (1u << 5)
#define NVME_AF_BAR_IOSQ              (1u << 6)
#define NVME_AF_BAR_IOCQ              (1u << 7)
#define NVME_AF_ANS_SHA               (1u << 8)

#define NVME_STATUS_VIOLATION         0x100UL
#define NVME_PAGE_SIZE                0x4000UL
#define NVME_PRP_PAGE_SIZE            0x1000UL
#define NVME_QSIZE_MAX                0xffeU
#define NVME_COASTGUARD_VALUE         0x3fU

#define NVME_BAR_AQA                  0x24U
#define NVME_BAR_ASQ                  0x28U
#define NVME_BAR_ACQ                  0x30U
#define NVME_BAR_COASTGUARD           0x100U
#define NVME_BAR_CG_ASQ               0x108U
#define NVME_BAR_CG_ACQ               0x110U
#define NVME_BAR_IOSQ_BASE            0x1200U
#define NVME_BAR_IOCQ_BASE            0x1208U
#define NVME_BAR_IOQA                 0x1210U
#define NVME_BAR_TCB_INVALIDATE       0x118U

#define NVME_CID_AVAILABLE            0
#define NVME_CID_BUSY                 1
#define NVME_IOMMU_RO                 1
#define NVME_IOMMU_RW                 2

#define NVME_QUIRK_PRP_FLUSH_WA       (1u << 0)
#define NVME_QUIRK_TL_WA              (1u << 1)
#define NVME_QUIRK_VDMA_WA            (1u << 2)

#define NVME_DBG_PRINT_CALLS          (1u << 0)
#define NVME_DBG_PRP_WINDOW           (1u << 1)
#define NVME_DBG_PRINT_MINIMAL        (1u << 2)
#define NVME_DBG_SUMMARY              (1u << 3)
#define NVME_DBG_IOMMU                (1u << 4)
#define NVME_DBG_CMD_TRACE            (1u << 5)

/*
 * T8110 DART C emulator.
 *
 * The register constants and TLB/error sequencing below intentionally follow
 * the public Asahi Linux apple-dart.c T8110 model:
 *   archive/references/asahi_linux/apple-dart.c
 *
 * This is SPTM endpoint emulation, not Linux's ownership driver. Endpoint 6
 * preserves bootloader-owned state instead of doing apple_dart_hw_reset()'s
 * destructive TCR/TTBR clear. Later endpoints install roots, stream enables,
 * and TLB operations explicitly, matching the SPTM ABI observed in the real
 * t8140 firmware.
 */
#define DART_C_MAX_DARTS              32
#define DART_C_MAX_BASES              16
#define DART_C_MAX_SIDS               256
#define DART_C_MAX_IDENTITY_RANGES    1024
#define DART_C_MAX_ENDPOINTS          19
#define DART_C_RECENT_SLOTS           1024
#define DART_C_SID0_TRACE_SLOTS       4096
#define DART_C_MAX_DAPF_SLICES        32
#define DART_C_MAX_PIOGW_RANGES       2
#define DART_C_MAX_PIOGW_DESCS        2

#define UAT_C_MAX_ENDPOINTS           13
#define UAT_C_MAX_STATES              32
#define UAT_C_RECENT_SLOTS            32
#define UAT_C_PAGE_SIZE               0x4000UL
#define UAT_C_CTX_NONE                0xffffU

#define UAT_FN_INIT_STATE             0
#define UAT_FN_DESTROY_STATE          1
#define UAT_FN_MAP_TABLE              2
#define UAT_FN_UNMAP_TABLE            3
#define UAT_FN_MAP_BEGIN              4
#define UAT_FN_MAP_CONTINUE           5
#define UAT_FN_PREP_FW_UNMAP_BEGIN    6
#define UAT_FN_PREP_FW_UNMAP_CONTINUE 7
#define UAT_FN_UNMAP_BEGIN            8
#define UAT_FN_UNMAP_CONTINUE         9
#define UAT_FN_SET_CTX_ID             10
#define UAT_FN_REMOVE_CTX_ID          11
#define UAT_FN_GET_INFO               12

#define DART_C_STATUS_VIOLATION       0x100UL
#define DART_C_PAGE_SIZE              0x4000UL
#define DART_C_TT_ENTRIES             2048
#define DART_C_MAX_STREAMS            256
#define DART_C_PTE_NO_CACHE           (1UL << 1)

#define DART_C_RANGE_SID_MASK         0xffffUL
#define DART_C_RANGE_FLAG_REMAP       (1UL << 63)
#define DART_C_RANGE_FLAG_BOOT_PREMAP (1UL << 60)
#define DART_C_RANGE_FLAG_VM_WINDOW   (1UL << 59)
#define DART_C_RANGE_FLAG_PT_REGION   (1UL << 58)
#define DART_C_RANGE_FLAG_BYPASS      (1UL << 57)
#define DART_C_RANGE_FLAG_APF_BYPASS  (1UL << 56)
#define DART_C_RANGE_FLAG_REAL_TIME   (1UL << 55)

/* TXM peer domain (domain=2/table=0) constants. XNU 26.5 passes the TXM
 * selector in x16's endpoint field, x0 is the physical TXM thread-stack page,
 * and TXM writes TXMSharedContextData_t at PAGE_SIZE - 1024 inside that page. */
#define TXM_DOMAIN                    2
#define TXM_TABLE_XNU                 0
#define TXM_C_MAX_ENDPOINTS           64
#define TXM_C_TRACK_SLOTS             32
#define TXM_C_SYNTH_ALIGN             0x40UL
#define TXM_THREAD_STACK_SHARED_OFF   0x3c00UL
#define TXM_SHARED_RETURN_CODE_OFF    0x08UL
#define TXM_SHARED_RETURN_TYPE_OFF    0x10UL
#define TXM_SHARED_NUM_WORDS_OFF      0x18UL
#define TXM_SHARED_WORDS_OFF          0x20UL
#define TXM_STACK_RETURN_WORDS        6

#define TXM_SUCCESS                   0UL
#define TXM_RETURN_GENERIC            1UL
#define TXM_RETURN_NOT_FOUND          8UL
#define TXM_RETURN_NOT_PERMITTED      38UL
#define TXM_RETURN_NOT_SUPPORTED      41UL

#define TXM_SEL_GET_LOG_INFO          1U
#define TXM_SEL_GET_CODE_SIGNING_INFO 2U
#define TXM_SEL_GET_TRUST_CACHE_INFO  3U
#define TXM_SEL_GET_SECURE_CHANNEL    7U
#define TXM_SEL_ADD_FREE_LIST_PAGE    10U
#define TXM_SEL_GET_FREE_LIST_PAGE    11U
#define TXM_SEL_LOAD_TRUST_CACHE      12U
#define TXM_SEL_QUERY_TRUST_CACHE     14U
#define TXM_SEL_QUERY_TC_REM          15U
#define TXM_SEL_CHECK_TC_UUID         16U
#define TXM_SEL_REGISTER_PROFILE      17U
#define TXM_SEL_UNREGISTER_PROFILE    19U
#define TXM_SEL_REGISTER_SIGNATURE    22U
#define TXM_SEL_UNREGISTER_SIGNATURE  23U
#define TXM_SEL_RECONSTITUTE_SIG      25U
#define TXM_SEL_GET_LOCAL_PUBKEY      27U
#define TXM_SEL_MATCH_COMPILATION     30U
#define TXM_SEL_ACQUIRE_SIGNING_ID    32U
#define TXM_SEL_ACCEL_ENTITLEMENTS    34U
#define TXM_SEL_REGISTER_ASPACE       35U
#define TXM_SEL_GET_ENTITLEMENTS_CTX  43U
#define TXM_SEL_RESOLVE_KENT_ASPACE   44U
#define TXM_SEL_IMAGE4_DISPATCH       45U
#define TXM_SEL_IMAGE4_GET_EXPORTS    46U
#define TXM_SEL_IMAGE4_GET_NONCE      51U

#define DART_T8110_PARAMS3            0x008U
#define DART_T8110_PARAMS4            0x00cU
#define DART_T8110_TLB_CMD            0x080U
#define DART_T8110_TLB_CMD_BUSY       (1U << 31)
#define DART_T8110_TLB_CMD_NEW_DART   (1U << 15)
#define DART_T8110_TLB_CMD_VA_RANGE   (1U << 14)
#define DART_T8110_TLB_CMD_STT_FLUSH  (1U << 13)
#define DART_T8110_TLB_CMD_NO_STC_FLUSH (1U << 12)
#define DART_T8110_TLB_OP_FLUSH_ALL   0U
#define DART_T8110_TLB_OP_FLUSH_SID   1U
#define DART_T8110_TLB_START_DVA_PAGE 0x098U
#define DART_T8110_TLB_END_DVA_PAGE   0x0a0U
#define DART_T8110_ERROR              0x100U
#define DART_T8110_ERROR_MASK         0x104U
#define DART_T8110_ERROR_STREAMS      0x1c0U
#define DART_T8110_PROTECT            0x200U
#define DART_T8110_PROTECT_TTBR_TCR   (1U << 0)
#define DART_T8110_PROTECT_LOCK       0x208U
#define DART_T8110_ENABLE_STREAMS     0xc00U
#define DART_T8110_DISABLE_STREAMS    0xc20U
#define DART_T8110_TCR                0x1000U
#define DART_T8110_TCR_TRANSLATE_EN   (1U << 0)
#define DART_T8110_TCR_BYPASS_DART    (1U << 1)
#define DART_T8110_TCR_BYPASS_DAPF    (1U << 2)
#define DART_T8110_TCR_FOUR_LEVEL     (1U << 3)
#define DART_T8110_TCR_REMAP_EN       (1U << 7)
#define DART_T8110_TCR_REMAP_TARGET(x) (((x) & 0xffU) << 8)
#define DART_T8110_TCR_DISABLED       (DART_T8110_TCR_BYPASS_DART | \
                                       DART_T8110_TCR_BYPASS_DAPF)
#define DART_T8110_TTBR               0x1400U
#define DART_T8110_TTBR_VALID         (1U << 0)

#define DART_C_HOT_OK                 0U
#define DART_C_ERR_LOCKED             (1U << 0)
#define DART_C_ERR_TIMEOUT            (1U << 1)
#define DART_C_ERR_ALIGN              (1U << 2)
#define DART_C_ERR_NO_TTBR            (1U << 3)
#define DART_C_ERR_NO_TABLE           (1U << 4)

struct dart_c_sid_state {
    u32 tcr;
    u32 ttbr;
    u32 protection;
    u32 status;
    u64 root_pt_pa;
    u8 valid;
    u8 root_valid;
    u8 root_level;
    u8 stream_enabled;
    u8 translation_enabled;
    u8 exclave;
    u8 raw_replay;
    u8 initial_stream_enabled;
};

struct dart_c_piogw_desc {
    u32 slice;
    u32 pad;
    u64 addr;
};

struct dart_c_dapf_slice {
    u64 start;
    u64 end;
    u32 ctrl;
    u32 words[8];
};

struct dart_c_dapf_state {
    u64 base_pa;
    u32 count;
    u32 sid_count;
    struct dart_c_dapf_slice slice[DART_C_MAX_DAPF_SLICES];
    u8 reserved[0x800 - 0x10 - DART_C_MAX_DAPF_SLICES * 0x38];
};

struct dart_c_instance {
    u64 dart_id;
    u64 obj_va;
    u64 state_va;
    u64 base_pa[DART_C_MAX_BASES];
    u32 base_count;
    u32 init_state;
    u32 clock_protection;
    u32 locked;
    u32 used;
    u8 avoid_tlbi_in_map;
    u8 relaxed_rw_protections;
    u8 flush_by_dva;
    u8 pad0[1];
    u64 total_calls;
    u64 fast_path_calls;
    u64 violations;
    u64 last[16];
    u64 ep_count[DART_C_MAX_ENDPOINTS];
    struct dart_c_dapf_state dapf;
    struct dart_c_sid_state sid[DART_C_MAX_SIDS];
    u64 piogw_base_pa[DART_C_MAX_PIOGW_RANGES];
    u32 piogw_count;
    u32 piogw_desc_count;
    struct dart_c_piogw_desc piogw_desc[DART_C_MAX_PIOGW_DESCS];
};

struct dart_c_recent_event {
    u64 seq;
    u64 table;
    u64 endpoint;
    u64 dart_id;
    u64 sid;
    u64 regs[6];
    u64 before_slot;
    u64 before_pte;
    u64 after_slot;
    u64 after_pte;
    u64 rc;
};

struct dart_c_sid0_event {
    u64 seq;
    u64 meta; /* table, endpoint, dart_id, reason: 16 bits each */
    u64 regs[4];
    u64 before_tcr_ttbr;
    u64 before_root_flags;
    u64 before_pte;
    u64 after_tcr_ttbr;
    u64 after_root_flags;
    u64 after_pte;
    u64 rc;
};

struct dart_c_identity_range {
    u64 base_pa;
    u64 sid;
    u64 start;
    u64 end;
};

struct dart_c_state {
    u32 enabled;
    u32 pad0;
    u32 violations;
    u32 pad1;
    u64 total_calls;
    u64 fast_path_calls;
    u64 fallthrough_calls;
    u64 last[16];
    struct dart_c_instance inst[DART_C_MAX_DARTS];
    u64 pt_pool_base;
    u64 pt_pool_end;
    u64 pt_pool_next;
    u64 pt_pool_allocs;
    u64 pt_pool_failures;
    u64 identity_count;
    struct dart_c_identity_range identity[DART_C_MAX_IDENTITY_RANGES];
    u64 recent_idx;
    struct dart_c_recent_event recent[DART_C_RECENT_SLOTS];
    u64 sid0_trace_idx;
    struct dart_c_sid0_event sid0_trace[DART_C_SID0_TRACE_SLOTS];
};

struct nvme_c_state {
    u32 enabled;
    u32 queue_count;
    u32 allowed_functions;
    u8  secure_reg_layout;
    u8  packed_writes_present;
    u8  linear_sq;
    u8  ans_sha_present;
    u8  debug_flags;
    u8  quirks;
    u16 max_cid;
    u32 violations;
    u64 total_calls;
    u64 fast_path_calls;
    u64 fallthrough_calls;
    u64 bar_pa;
    u64 trusted_io_base;
    u64 trusted_io_size;
    u64 secondary_io_base;
    u64 secondary_io_size;
    u64 admin_asq_kva;
    u64 admin_acq_kva;
    u64 prp_list_kva;
    u64 ans_sha_kva;
    u64 tcb_kva[2];
    u32 aqa_cached;
    u32 ioqa_cached;
    u32 ans_sha_pwc_cached;
    u32 last_rc;
    u64 asq_pa_cached;
    u64 acq_pa_cached;
    u64 iosq_pa_cached;
    u64 iocq_pa_cached;
    u64 ans_sha_pa_cached;
    u64 last[16];
    u64 ep_count[16];
    u8  cid_mode[NVME_C_MAX_CID];
    u8  func_state[16];
    u16 tcb_dir[NVME_C_MAX_CID];
    u16 tcb_nlb[NVME_C_MAX_CID];
    u32 tcb_count[NVME_C_MAX_CID];
    u8  tcb_mode[NVME_C_MAX_CID];
    u8  tcb_qid[NVME_C_MAX_CID];
    u16 pad0[NVME_C_MAX_CID];
    u64 tcb_prp1[NVME_C_MAX_CID];
    u64 tcb_prp2[NVME_C_MAX_CID];
    u64 nvmmu_pa;
    u64 tl_status_pa;
    u64 tl_mask_pa;
    u64 tl_ctrl_pa;
    u32 tl_num_sl;
    u32 tl_timeouts;
    u16 tl_slot_done[NVME_C_MAX_CID];
    u64 vdma_status_pa;
};
_Static_assert(sizeof(struct nvme_c_state) == 0x2128, "nvme_c_state layout drift");

struct sart_c_entry {
    u64 paddr;
    u64 size;
    u32 flags;
    u32 guard;
};

struct sart_c_state {
    u32 enabled;
    u32 active;
    u32 version;
    u32 flags_allow;
    u32 size_shift;
    u32 paddr_shift;
    u32 size_max;
    u32 protected_mask;
    u32 violations;
    u32 last_rc;
    u64 total_calls;
    u64 fast_path_calls;
    u64 fallthrough_calls;
    u64 base_pa;
    u64 power_canary_pa;
    u32 power_canary_offset;
    u32 power_canary_count;
    u32 exclusive_bounds;
    u32 reserved;
    u64 last[8];
    u64 ep_count[SART_C_MAX_ENDPOINTS];
    struct sart_c_entry shadow[SART_C_MAX_ENTRIES];
};
_Static_assert(sizeof(struct sart_c_entry) == 0x18, "sart_c_entry layout drift");
_Static_assert(sizeof(struct sart_c_state) == 0x238, "sart_c_state layout drift");

struct uat_c_root_state {
    u64 handle;
    u64 root0_pa;
    u64 root1_pa;
    u64 current_va;
    u64 seglist_pa;
    u64 num_segs;
    u64 current_seg;
    u64 seg_offset;
    u64 options;
    u64 last[8];
    u16 ctx_id;
    u8 used;
    u8 state;
    u8 type;
    u8 pad[19];
};

struct uat_c_recent_event {
    u64 seq;
    u64 endpoint;
    u64 handle;
    u64 regs[5];
    u64 root_pa;
    u64 slot_pa;
    u64 before;
    u64 after;
    u64 rc;
};

struct uat_c_state {
    u32 enabled;
    u32 violations;
    u64 total_calls;
    u64 fast_path_calls;
    u64 fallthrough_calls;
    u64 last_rc;
    u64 mode;
    u64 vaddr_shift;
    u64 l1_index_mask;
    u64 segment_limit;
    u64 mapping_limit;
    u64 state_object_size;
    u64 gpu_region_pa;
    u64 gpu_region_size;
    u64 gfx_shared_region_pa;
    u64 gfx_shared_region_size;
    u64 gfx_shared_l2_pa;
    u64 gfx_shared_l2_size;
    u64 gfx_handoff_pa;
    u64 gfx_handoff_size;
    u64 last[16];
    u64 ep_count[UAT_C_MAX_ENDPOINTS];
    struct uat_c_root_state roots[UAT_C_MAX_STATES];
    u64 recent_idx;
    struct uat_c_recent_event recent[UAT_C_RECENT_SLOTS];
    u64 selector2_pa;
    u64 selector9_pa;
    u64 raw_gfx_shared_l2_pa;
    u64 selector2_root_pa;
    u64 sapt_base;
    u64 sapt_entries;
    u64 sapt_dram_base;
    u64 sapt_dram_end;
    u64 sapt_policy;
};
_Static_assert(sizeof(struct uat_c_root_state) == 0xa0, "uat_c_root_state layout drift");
_Static_assert(sizeof(struct uat_c_recent_event) == 0x68, "uat_c_recent_event layout drift");
_Static_assert(sizeof(struct uat_c_state) == 0x22d0, "uat_c_state layout drift");

struct sptm_cpu_pio_entry {
    u64 phys_id;
    u64 cpu_base;
    u64 cpu_size;
    u64 acc_base;
    u64 acc_size;
    u64 cpm_base;
    u64 cpm_size;
    u64 cpu_pages;
    u64 acc_pages;
    u64 cpm_pages;
    u64 registered;
    u64 logical_id;
    u64 flags;
    u64 reserved[3];
};

struct sptm_cpu_pio_state {
    u64 seeded_count;
    u64 registered_count;
    u64 last_phys;
    u64 last_slot;
    u64 last_flags;
    u64 reserved[3];
    struct sptm_cpu_pio_entry entries[SPTM_MAX_CPUS_EMUL];
};

struct papt_update_event {
    u64 rc;
    u64 pa;
    u64 options;
    u64 papt_va;
    u64 root_pa;
    u64 template_pte;
    u64 existing_pte;
    u64 new_pte;
    u64 caller_elr;
    u64 inner_root_pa;
    u64 inner_va;
    u64 inner_template_pte;
};

struct papt_update_state {
    u64 calls;
    u64 candidates;
    u64 writes;
    u64 skip_no_attr;
    u64 skip_skip_papt;
    u64 skip_unmanaged;
    u64 skip_bad_template;
    u64 skip_bad_root;
    u64 skip_bad_walk;
    u64 skip_bad_existing;
    u64 skip_same_attrs;
    u64 ring_idx;
    struct papt_update_event ring[PAPT_UPDATE_RING_SLOTS];
    u64 nvme_hits[PAPT_NVME_CLASS_COUNT];
    u64 nvme_writes[PAPT_NVME_CLASS_COUNT];
};
_Static_assert(sizeof(struct papt_update_event) == 0x60, "papt_update_event layout drift");
_Static_assert(sizeof(struct papt_update_state) == 0x18e0, "papt_update_state layout drift");

struct alt_ptd_trace_event {
    u64 seq;
    u64 pa;
    u64 caller_elr;
    u64 caller_lr;
    u64 caller_fp;
    u64 types_flags;
    u64 retype_params;
    u64 ft_idx;
    u64 refs_before;
    u64 refs_after;
    u64 papt_ring_before;
    u64 papt_ring_after;
    u64 papt_rc;
    u64 papt_existing_pte;
    u64 papt_new_pte;
    u64 papt_va;
    u64 caller_sp0;
    u64 caller_sp1;
    u64 bt_count;
    u64 bt_base;
    u64 bt[12];
};

struct alt_ptd_trace_state {
    u64 ring_idx;
    struct alt_ptd_trace_event ring[ALT_PTD_TRACE_RING_SLOTS];
};
_Static_assert(sizeof(struct alt_ptd_trace_event) == 0x100, "alt_ptd_trace_event layout drift");
_Static_assert(sizeof(struct alt_ptd_trace_state) == 0x408, "alt_ptd_trace_state layout drift");

struct txm_c_state {
    u32 enabled;
    u32 violations;
    u64 total_calls;
    u64 fast_path_calls;
    u64 fallthrough_calls;
    u64 last_selector;
    u64 last_stack_pa;
    u64 last_x16;
    u64 last_rc;
    u64 last_args[8];
    u64 last_words[TXM_STACK_RETURN_WORDS];
    u64 ep_count[TXM_C_MAX_ENDPOINTS];
    u64 secure_chan_pa;
    u64 secure_chan_size;
    u64 synth_base_va;
    u64 synth_base_pa;
    u64 synth_size;
    u64 synth_next_off;
    u64 log_page_va;
    u64 log_head_va;
    u64 log_sync_va;
    u64 txm_rw_data_va;
    u64 txm_ro_data_va;
    u64 developer_mode_flag_va;
    u64 managed_signature_size;
    u64 trust_cache_runtime_va;
    u64 trust_cache_static_count;
    u64 trust_cache_caps0;
    u64 trust_cache_caps1;
    u64 local_signing_pubkey_va;
    u64 kernel_entitlements_va;
    u64 ce_ctx_va;
    u64 signing_id_va;
    u64 image4_exports_va;
    u64 nonce_va;
    u64 default_address_space_va;
    u64 default_signature_va;
    u64 default_profile_va;
    u64 next_token;
    u64 free_count;
    u64 free_pages[TXM_C_TRACK_SLOTS];
    u64 loaded_tc_count;
    u64 loaded_tc[TXM_C_TRACK_SLOTS];
    u64 secure_chan_dva;
    u64 secure_chan_reserved_pa;
};

/* Frame types (XNU's per-frame state). */
#define SPTM_KERNEL_ROOT_TABLE         8
#define SPTM_PAGE_TABLE                9
#define XNU_DEFAULT                   11
#define XNU_USER_ROOT_TABLE           18
#define XNU_SHARED_ROOT_TABLE         19
#define XNU_PAGE_TABLE                20
#define XNU_PAGE_TABLE_SHARED         21
#define XNU_PAGE_TABLE_ROZONE         22
#define XNU_PAGE_TABLE_COMMPAGE       23
#define XNU_PAGE_TABLE_ALT            24
#define XNU_IO                        27
#define XNU_PROTECTED_IO              28
#define XNU_COPROCESSOR_RO_IO         29
#define XNU_STAGE2_ROOT_TABLE         33
#define XNU_STAGE2_PAGE_TABLE         34
#define XNU_SUBPAGE_USER_ROOT_TABLES  40
#define TXM_SEP_SECURE_CHANNEL        61

#define SPTM_PT_GEOMETRY_16K          0
#define SPTM_PT_GEOMETRY_4K           1
#define SPTM_PT_GEOMETRY_16K_KERN     2
#define ROOT_GEOM_UNKNOWN             0xff
#define TTBR_ASID_SHIFT               48
#define TTBR_BADDR_MASK               0x0000fffffffffffeUL
#define ROOT_GEOM_SLOTS               64

#define PAGE_SIZE_GUEST_EMUL          0x4000UL
#define PAGE_SIZE_4K_EMUL             0x1000UL
#define ARM_TTE_TABLE_MASK            0x0000fffffffff000UL
#define ARM_PTE_PAGE_MASK             0x0000ffffffffc000UL
#define ARM_PTE_PAGE_MASK_4K          0x0000fffffffff000UL
#define ARM_PTE_AP_MASK               (3UL << 6)
#define ARM_PTE_ATTRINDX_MASK         (7UL << 2)
#define ARM_PTE_SH_MASK               (3UL << 8)
#define ARM_PTE_AF                    (1UL << 10)
#define ARM_PTE_NG                    (1UL << 11)
#define ARM_PTE_NS                    (1UL << 5)
#define ARM_PTE_AP_RO                 (2UL << 6)
#define ARM_PTE_GP                    (1UL << 50)
#define ARM_PTE_PNX                   (1UL << 53)
#define ARM_PTE_NX                    (1UL << 54)
#define ARM_PTE_WIRED                 (1UL << 58)
#define ARM_PTE_WRITEABLE             (1UL << 59)
#define FRAME_PAGE_MASK               0x0000ffffffffc000UL
#define FT_KIND5_REFCNT_OFF           0x04UL
#define FT_TABLE_MAPPING_REFCNT_OFF   0x06UL
#define FT_TABLE_NESTED_REFCNT_OFF    0x08UL
#define FT_DATA_RO_REFCNT_OFF         0x08UL
#define FT_DATA_WX_REFCNT_OFF         0x0cUL
#define DISJOINT_OP_SIZE              24UL
#define SURT_SUBPAGE_SIZE             128UL
#define TTE_CONDEMNED_BIT             0x4UL
#define UINT64_MAX_VALUE              0xffffffffffffffffUL

/* PT walk indices for XNU's 16K and 4K pmap geometries. */
static inline u64 va_16k_l1_idx(u64 va) { return (va >> 36) & 0x7ff; }
static inline u64 va_16k_l2_idx(u64 va) { return (va >> 25) & 0x7ff; }
static inline u64 va_16k_l3_idx(u64 va) { return (va >> 14) & 0x7ff; }
static inline u64 va_4k_l0_idx(u64 va)  { return (va >> 39) & 0x1ff; }
static inline u64 va_4k_l1_idx(u64 va)  { return (va >> 30) & 0x1ff; }
static inline u64 va_4k_l2_idx(u64 va)  { return (va >> 21) & 0x1ff; }
static inline u64 va_4k_l3_idx(u64 va)  { return (va >> 12) & 0x1ff; }

static inline u8 ft_get_type(u64 pa);
static inline u8 root_geom_lookup(u64 root_pa);
static inline bool_t root_uses_4k(u64 root_pa, u32 target_level);
static inline bool_t is_pt_type(u8 t);

/* Translate xnu's PTE template to a plain ARM PTE we can actually install.
 * Preserve the architectural leaf fields XNU controls plus the software bits
 * XNU later compares in prev-PTE results; force only the valid leaf type. */
__attribute__((unused))
static inline u64 xnu_pte_to_arm_geom(u64 xnu_pte, bool_t geom4k) {
    if ((xnu_pte & 3) == 0) return 0;
    u64 pa    = xnu_pte & (geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK);
    u64 leaf = xnu_pte & (ARM_PTE_ATTRINDX_MASK | ARM_PTE_SH_MASK |
                          ARM_PTE_AP_MASK | ARM_PTE_AF | ARM_PTE_NG |
                          ARM_PTE_NS | ARM_PTE_GP | ARM_PTE_PNX |
                          ARM_PTE_NX | ARM_PTE_WIRED |
                          ARM_PTE_WRITEABLE);
    /* Preserve Apple-impdef bits (49=SK, 60-62=SPRR idx) so XNU's bookkeeping
     * reads see what it wrote. Our MMU ignores the SPRR index bits. */
    u64 apple_bits = xnu_pte & ((1UL << 49) | (1UL << 60) | (1UL << 61) |
                                 (1UL << 62));
    return pa | leaf | apple_bits | 3UL;
}

/*
 * UPDATE_REGION/DISJOINT receive masked attribute templates. XNU may pass only
 * the bits selected by options, with valid/type and PA fields clear, such as
 * permissions-only templates. Real SPTM still applies those selected fields to
 * the existing PTE; do not collapse partial templates to zero just because
 * ARM_PTE_TYPE_VALID is absent.
 */
__attribute__((unused))
static inline u64 xnu_pte_update_template_to_arm_geom(u64 xnu_pte, bool_t geom4k) {
    u64 leaf = xnu_pte & (ARM_PTE_ATTRINDX_MASK | ARM_PTE_SH_MASK |
                          ARM_PTE_AP_MASK | ARM_PTE_AF | ARM_PTE_NG |
                          ARM_PTE_NS | ARM_PTE_GP | ARM_PTE_PNX |
                          ARM_PTE_NX | ARM_PTE_WIRED |
                          ARM_PTE_WRITEABLE);
    u64 apple_bits = xnu_pte & ((1UL << 49) | (1UL << 60) | (1UL << 61) |
                                 (1UL << 62));

    if ((xnu_pte & 3) == 0)
        return leaf | apple_bits;

    u64 pa = xnu_pte & (geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK);
    return pa | leaf | apple_bits | 3UL;
}

__attribute__((unused))
static inline u64 xnu_pte_to_arm(u64 xnu_pte) {
    return xnu_pte_to_arm_geom(xnu_pte, 0);
}
static inline u64 xnu_tte_to_arm(u64 xnu_tte) {
    if ((xnu_tte & 3) == 0) return 0;
    return (xnu_tte & ARM_TTE_TABLE_MASK) | 3UL;
}

static inline u64 merge_pte_with_mask_geom(u64 existing, u64 new_template,
                                           u64 mask, bool_t geom4k) {
    if (mask == SPTM_UPDATE_MASK || mask == 0)
        return new_template;

    u64 pa_mask = geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK;
    u64 pa_bits = existing & pa_mask;
    u64 out = existing;

    if (mask & SPTM_UPDATE_SW_WIRED)
        out = (out & ~ARM_PTE_WIRED) | (new_template & ARM_PTE_WIRED);
    if (mask & SPTM_UPDATE_PERMS_AND_WAS_WRITABLE) {
        u64 clr = ARM_PTE_PNX | ARM_PTE_NX | ARM_PTE_AP_MASK |
                  ARM_PTE_WRITEABLE;
        out = (out & ~clr) | (new_template & clr);
    }
    if (mask & SPTM_UPDATE_NG)
        out = (out & ~ARM_PTE_NG) | (new_template & ARM_PTE_NG);
    if (mask & SPTM_UPDATE_AF)
        out = (out & ~ARM_PTE_AF) | (new_template & ARM_PTE_AF);
    if (mask & SPTM_UPDATE_SH)
        out = (out & ~ARM_PTE_SH_MASK) | (new_template & ARM_PTE_SH_MASK);
    if (mask & SPTM_UPDATE_MAIR)
        out = (out & ~ARM_PTE_ATTRINDX_MASK) |
              (new_template & ARM_PTE_ATTRINDX_MASK);

    return (out & ~pa_mask) | pa_bits;
}

__attribute__((unused))
static inline u64 merge_pte_with_mask(u64 existing, u64 new_template, u64 mask) {
    return merge_pte_with_mask_geom(existing, new_template, mask, 0);
}

static inline volatile u64 *pt_u64_ptr(u64 pa) {
    return (volatile u64 *)pa;
}

static inline volatile u64 *pt_slot_ptr(u64 table_pa, u64 idx) {
    return pt_u64_ptr(table_pa + idx * 8);
}

static inline u64 pt_read_slot_poc(volatile u64 *slot) {
    return *slot;
}

static inline u64 walk_to_l3_16k(u64 root_pa, u64 va, u64 *out_idx) {
    volatile u64 *l1 = pt_u64_ptr(root_pa);
    u64 l1e = pt_read_slot_poc(&l1[va_16k_l1_idx(va)]);
    if ((l1e & 3) != 3) return 0;
    volatile u64 *l2 = pt_u64_ptr(l1e & ARM_TTE_TABLE_MASK);
    u64 l2e = pt_read_slot_poc(&l2[va_16k_l2_idx(va)]);
    if ((l2e & 3) != 3 || (l2e & TTE_CONDEMNED_BIT)) return 0;
    *out_idx = va_16k_l3_idx(va);
    return l2e & ARM_TTE_TABLE_MASK;
}

static inline u64 walk_to_l3_4k(u64 root_pa, u64 va, u64 *out_idx) {
    volatile u64 *l0 = pt_u64_ptr(root_pa);
    u64 l0e = pt_read_slot_poc(&l0[va_4k_l0_idx(va)]);
    if ((l0e & 3) != 3) return 0;
    volatile u64 *l1 = pt_u64_ptr(l0e & ARM_TTE_TABLE_MASK);
    u64 l1e = pt_read_slot_poc(&l1[va_4k_l1_idx(va)]);
    if ((l1e & 3) != 3) return 0;
    volatile u64 *l2 = pt_u64_ptr(l1e & ARM_TTE_TABLE_MASK);
    u64 l2e = pt_read_slot_poc(&l2[va_4k_l2_idx(va)]);
    if ((l2e & 3) != 3 || (l2e & TTE_CONDEMNED_BIT)) return 0;
    *out_idx = va_4k_l3_idx(va);
    return l2e & ARM_TTE_TABLE_MASK;
}

/* Walk to the leaf PTE table for either geometry. */
__attribute__((unused))
static inline u64 walk_to_l3(u64 root_pa, u64 va, u64 *out_idx) {
    return root_uses_4k(root_pa, 3) ?
        walk_to_l3_4k(root_pa, va, out_idx) :
        walk_to_l3_16k(root_pa, va, out_idx);
}

/* Walk xnu's pmap geometry to find the parent table at `target_level`.
 * 16K roots start at L1; 4K roots can start at L0. Real SPTM gets this from
 * root metadata; this emulator records the geometry from sptm_retype params. */
static inline u64 walk_to_level(u64 root_pa, u64 va, u32 target_level,
                                 u64 *out_idx) {
    if (root_uses_4k(root_pa, target_level)) {
        if (target_level == 0) { *out_idx = va_4k_l0_idx(va); return root_pa; }
        volatile u64 *l0 = pt_u64_ptr(root_pa);
        u64 l0e = pt_read_slot_poc(&l0[va_4k_l0_idx(va)]);
        if ((l0e & 3) != 3) return 0;
        if (target_level == 1) {
            *out_idx = va_4k_l1_idx(va);
            return l0e & ARM_TTE_TABLE_MASK;
        }
        volatile u64 *l1 = pt_u64_ptr(l0e & ARM_TTE_TABLE_MASK);
        u64 l1e = pt_read_slot_poc(&l1[va_4k_l1_idx(va)]);
        if ((l1e & 3) != 3) return 0;
        if (target_level == 2) {
            *out_idx = va_4k_l2_idx(va);
            return l1e & ARM_TTE_TABLE_MASK;
        }
        volatile u64 *l2 = pt_u64_ptr(l1e & ARM_TTE_TABLE_MASK);
        u64 l2e = pt_read_slot_poc(&l2[va_4k_l2_idx(va)]);
        if ((l2e & 3) != 3) return 0;
        *out_idx = va_4k_l3_idx(va);
        return l2e & ARM_TTE_TABLE_MASK;
    }

    if (target_level <= 1) { *out_idx = va_16k_l1_idx(va); return root_pa; }
    volatile u64 *l1 = pt_u64_ptr(root_pa);
    u64 l1e = pt_read_slot_poc(&l1[va_16k_l1_idx(va)]);
    if ((l1e & 3) != 3) return 0;
    if (target_level == 2) {
        *out_idx = va_16k_l2_idx(va);
        return l1e & ARM_TTE_TABLE_MASK;
    }
    volatile u64 *l2 = pt_u64_ptr(l1e & ARM_TTE_TABLE_MASK);
    u64 l2e = pt_read_slot_poc(&l2[va_16k_l2_idx(va)]);
    if ((l2e & 3) != 3) return 0;
    *out_idx = va_16k_l3_idx(va);
    return l2e & ARM_TTE_TABLE_MASK;
}

static inline void barrier(void) {
    __asm__ volatile("dsb ish; isb" ::: "memory");
}

static inline void tlbi_vmalle1is(void) {
    __asm__ volatile(
        "dsb ish\n\t"
        "tlbi vmalle1is\n\t"
        "dsb ish\n\t"
        "isb\n\t"
        : : : "memory");
}

static inline void tlbi_vmalle1os(void) {
    __asm__ volatile(
        "dsb oshst\n\t"
        "sys #0, c8, c1, #0\n\t"  // TLBI VMALLE1OS; mnemonic requires tlb-rmi in clang.
        "dsb osh\n\t"
        "isb\n\t"
        : : : "memory");
}

static inline void tlbi_aside1os(u64 asid)
{
    __asm__ volatile(
        "dsb oshst\n\t"
        "sys #0, c8, c1, #2, %0\n\t"  // TLBI ASIDE1OS; operand is ASID << 48.
        "dsb osh\n\t"
        "isb\n\t"
        : : "r"(asid) : "memory");
}

static inline void tlbi_vmalls12e1is(void) {
    __asm__ volatile(
        "dsb ish\n\t"
        "tlbi vmalls12e1is\n\t"
        "dsb ish\n\t"
        "isb\n\t"
        : : : "memory");
}

static inline u64 ttbr1_el12_root_pa(void) {
    u64 ttbr;
    __asm__ volatile("mrs %0, TTBR1_EL12" : "=r"(ttbr));
    return ttbr & TTBR_BADDR_MASK;
}

static inline void clean_range(void *ptr, u64 size) {
    u64 p = (u64)ptr;
    u64 end = p + size;
    p &= ~63UL;
    while (p < end) {
        __asm__ volatile("dc cvau, %0" : : "r"(p) : "memory");
        p += 64;
    }
    __asm__ volatile("dsb ish" ::: "memory");
}

static inline void clean_range_poc(void *ptr, u64 size) {
    u64 p = (u64)ptr;
    u64 end = p + size;
    p &= ~63UL;
    while (p < end) {
        __asm__ volatile("dc cvac, %0" : : "r"(p) : "memory");
        p += 64;
    }
    __asm__ volatile("dsb sy" ::: "memory");
}

static inline void sptm_coproc_cache_maint_page(u64 pa) {
    /*
     * M4/A18 SPTM uses guarded implementation-defined ops such as 0x00201401
     * for coprocessor/IOMMU page-cache maintenance. We cannot issue those from
     * the emulator context, but the M3 SPTM path uses this older CRn=7 pair for
     * the same by-page maintenance, and live probing on A18 Pro shows it does
     * not fault from our EL2 context.
     */
    register u64 x8 __asm__("x8") = pa & FRAME_PAGE_MASK;
    __asm__ volatile(
        /*
         * LEADING outer-shareable barrier. Real SPTM brackets its per-page
         * coprocessor maintenance with an outer-shareable barrier on BOTH sides
         * (dsb oshnxs/oshst before, dsb oshnxs/dmb osh after). The caller's
         * preceding dc_civac_range (sptm_frame_clean_page) emits no barrier, so
         * without this the coprocessor invalidate/refetch below can race AHEAD
         * of the CPU's clean reaching the PoC -> the GPU refetches stale page
         * contents. The trailing dsb osh alone cannot fix an ordering that has
         * already gone wrong before the sys ops execute.
         */
        "dsb osh\n\t"
        "sys #3, c7, c3, #4, x8\n\t"
        "sys #3, c7, c3, #5, x8\n\t"
        /*
         * The AGX GPU coprocessor is an OUTER-SHAREABLE observer. Real SPTM
         * drains its per-page coprocessor maintenance with outer-shareable
         * barriers (dsb oshnxs / dmb osh) at every flush site. A `dsb nsh`
         * here only guarantees completion for the local PE, so a freshly
         * dc_civac'd GPU data page (drained only by this barrier, since
         * dc_civac_range emits none) is never published to the GPU coherency
         * point -> the GPU reads stale command/ring data, never advances its
         * completion stamp, and agx_scheduler spins with faulted=0.
         */
        "dsb osh\n\t"
        "isb\n\t"
        : "+r"(x8) : : "memory");
}

static inline void sptm_coproc_cache_maint_range(const void *ptr, u64 size) {
    u64 p = (u64)ptr & FRAME_PAGE_MASK;
    u64 end = ((u64)ptr + size + PAGE_SIZE_GUEST_EMUL - 1UL) &
              FRAME_PAGE_MASK;

    while (p < end) {
        sptm_coproc_cache_maint_page(p);
        p += PAGE_SIZE_GUEST_EMUL;
    }
}

static inline void sptm_frame_clean_page(u64 pa) {
    u64 page = pa & ARM_PTE_PAGE_MASK;

    dc_civac_range((void *)page, PAGE_SIZE_GUEST_EMUL);
}

static inline void sptm_coproc_cache_maint_data_page(u64 pa) {
    u64 page = pa & ARM_PTE_PAGE_MASK;

    sptm_frame_clean_page(page);
    sptm_coproc_cache_maint_page(page);
}

static inline void clean_pt_range_poc(volatile u64 *ptr, u64 size) {
    clean_range_poc((void *)ptr, size);
    sptm_coproc_cache_maint_range((const void *)ptr, size);
    __asm__ volatile("isb" ::: "memory");
}

static inline void clean_pt_slot_poc(volatile u64 *slot) {
    clean_pt_range_poc(slot, 8);
}

static inline void zero_16k(u64 pa) {
    volatile u64 *q = pt_u64_ptr(pa);
    for (u32 i = 0; i < (PAGE_SIZE_GUEST_EMUL / 8); i++)
        q[i] = 0;
    sptm_coproc_cache_maint_data_page(pa);
}

static inline void alt_ptd_set_el2_cacheable(u64 pa, bool_t cacheable) {
    /*
     * Type 24 is firmware kind 5, not an ordinary CPU page-table kind. XNU/PMP
     * later read these PTD/ALT frames with non-coherent transactions; if the
     * emulator keeps touching them through m1n1's Normal-WB identity alias, AMCC
     * can see a stale SLC directory tag and raise UNEXP_RT_HIT_DIR. Mirror the
     * /vram fix for m1n1's own alias only: clean the old identity mapping, then
     * make future EL2 identity accesses Normal-NC while the frame is type 24.
     */
    u64 page = pa & FRAME_PAGE_MASK;
    u8 mair = cacheable ? SPTM_EL2_MAIR_NORMAL : SPTM_EL2_MAIR_NORMAL_NC;

    dc_civac_range((void *)page, PAGE_SIZE_GUEST_EMUL);
    mmu_add_mapping(page, page, PAGE_SIZE_GUEST_EMUL, mair, SPTM_EL2_PERM_RWX);
}

/* SEV — wake any guest CPU stuck in WFE waiting on us to complete an op.
 * Real SPTM implicitly posts events; we mirror that for every fast-path
 * return so xnu's spinlocks don't deadlock waiting for a TLB sync, etc. */
static inline void sev(void) {
    __asm__ volatile("sev" ::: "memory");
}

/* Refcount helpers ft_inc_refcount / ft_dec_refcount are defined below the
 * g_state extern declaration. */

/* ----------------------------------------------------------------------
 * Shared state struct. Python reads counters here for telemetry.
 * MUST match proxyclient/tools/sptm/seed.py.
 * ---------------------------------------------------------------------- */
struct sptm_emul_state {
    u64 total_calls;          /* +0x000 — every HVC the C emulator saw */
    u64 fast_path_calls;      /* +0x008 — handled in C without falling through */
    u64 fallthrough_calls;    /* +0x010 — fell through to host */
    u64 unknown_calls;        /* +0x018 — unrecognized endpoint, fell through */
    u64 last_x16;             /* +0x020 — last x16 seen (for debug) */
    u64 last_endpoint;        /* +0x028 — last endpoint we saw */
    u64 last_elr;             /* +0x030 — last ELR we saw */
    /* Per-endpoint counters: index by endpoint id, 0..63. */
    u64 ep_count[64];         /* +0x038 */
    /* Frame-table state: written at install time by the Python loader.
     * RETYPE handler updates frame_table[pa_index(pa)] = new_type so
     * xnu's direct frame_table reads (no HVC) stay coherent with our
     * emul. Zero frame_table_base = disabled (RETYPE just acks). */
    u64 frame_table_base;     /* +0x238 */
    u64 vm_first_phys;        /* +0x240 */
    u64 frame_table_size;     /* +0x248 — bytes; bounds-check */
    /* AUDIT FIX #1: prev_ptes scratch PA (per-CPU; CPU0 only here) and
     * physmap_va base used to compute PAPT VA for sptm_map_page_output_t.
     * papt_va = first_papt + (pa - vm_first_phys). xnu reads scratch+0
     * = prev_pte and scratch+8 = ptep PAPT VA. */
    u64 scratch_pa;           /* +0x250: base of per-CPU prev_ptes pages */
    u64 first_papt;           /* +0x258 */
    /* Circular buffer of LAST 128 calls' (x16, x0, x1, x2, x3, esr, elr, x30)
     * for post-hang inspection. ring_idx is the next slot to write.
     * Total size 128 * 8 * 8 = 8192 bytes. */
    u64 ring_idx;             /* +0x260 */
    u64 ring[128][8];         /* +0x268 — x16, x0, x1, x2, x3, esr, elr, x30 */
    /* SPRR fast-path state. Set by Python at install time. When kc_vmin
     * is non-zero, the C handler intercepts EL1t_sync HVCs whose ELR_EL12
     * is in [kc_vmin, kc_vmax) and decodes the trapping instruction by
     * reading PA = kc_guest_base + (elr12 - kc_vmin). Avoids a UART round
     * trip per pmap_ro_zone_memcpy_internal SPRR write. */
    u64 kc_vmin;              /* +0x2268 — kernelcache lowest VA */
    u64 kc_vmax;              /* +0x2270 — kernelcache highest VA (exclusive) */
    u64 kc_guest_base;        /* +0x2278 — PA where kernelcache is loaded */
    u64 sprr_fast_count;      /* +0x2280 — # of SPRR sysreg traps fast-pathed */
    u64 sprr_perm_el1_cache;  /* +0x2288 — last MSR'd SPRR_PERM_EL1 value */
    u64 sprr_perm_el0_cache;  /* +0x2290 — last MSR'd SPRR_PERM_EL0 value */
    u64 sprr_config_el1_cache;/* +0x2298 — last MSR'd SPRR_CONFIG_EL1 value */
    /* Ring buffer of pmap_ro_zone_memcpy_internal call args. The C
     * SPRR fast-path detects when ELR_EL12 is inside the function range
     * [pmap_rzm_lo, pmap_rzm_hi) and pushes (zid, va, offset, src,
     * size) into this ring. Captured at the SPRR write inside the
     * function — by then the args have been moved to x19..x24 by
     * the prologue and are stable. Ring size 128 entries × 6 u64s. */
    u64 pmap_rzm_lo;          /* +0x22a0 — function start VA */
    u64 pmap_rzm_hi;          /* +0x22a8 — function end VA (exclusive) */
    u64 pmap_rzm_idx;         /* +0x22b0 — next ring slot to write */
    u64 pmap_rzm_count;       /* +0x22b8 — total pushes */
    u64 pmap_rzm_ring[128][6];/* +0x22c0 — (elr, zid, va, offset, src, size) */
    /* Wider-context ring capturing FULL register snapshot at each
     * pmap_rzm fast-path. Same length and indexing as pmap_rzm_ring;
     * use pmap_rzm_idx to find the matching slot. Captures x0..x31
     * (33 u64 = 264 B per slot, 128 * 264 = 33 KB). */
    u64 pmap_rzm_full[128][33];/* +0x3ac0 — full reg snapshot per slot (128*264B = 33KB) */
    /* DEBUG (2026-05-09): full register snapshot at every SPTM dispatch
     * entry — saves ALL 31 GP regs BEFORE any C handler can touch them.
     * Used to bisect register-clobber bugs introduced by new C handlers.
     * 128 slots * 31 u64 = ~32 KB. */
    u64 sptm_in_idx;          /* +0xbec0 — next slot to write */
    u64 sptm_in_regs[128][31];/* +0xbec8 — x0..x30 verbatim from ctx->regs */
    /* Last table/refcount ops. These sit after sptm_in_regs at +0x13ac8.
     * Python dumps them on panic to correlate libsptm refcount failures. */
    u64 last_retype[8];       /* pa,current,new,old_type,page_ref,table_ref,idx,flags */
    u64 last_map_table[10];   /* root,va,level,parent,idx,existing,new_tte,arm_tte,child_pa,table_ref */
    u64 last_unmap_table[10]; /* root,va,level,parent,idx,existing,freed_pa,type,table_ref,ft_idx */
    u64 root_geom_pa[ROOT_GEOM_SLOTS];   /* roots/SURT slots with explicit pmap geometry */
    u64 root_geom_attr[ROOT_GEOM_SLOTS]; /* bits[7:0]=SPTM_PT_GEOMETRY_*, bits[31:16]=ASID */
    u64 last_map_page[14];    /* root,va,l3,idx,ptep_pa,ptep_papt,existing,new_pte,arm_pte,target_pa,target_type,page_ref,ptep_table_ref,ptep_ft_idx */
    /* C-side DART object recovery cache. Endpoint 5 used to walk the guest
     * frame chain over UART, which is slow enough to wedge boot. Do the same
     * verifier-shaped AppleT8110DART object recovery in EL2 and publish the
     * decoded object for diagnostics. */
    u64 dart_obj_cache_idx;    /* +0x14018 */
    u64 dart_obj_cache_hits;   /* +0x14020 */
    u64 dart_obj_cache_misses; /* +0x14028 */
    u64 dart_obj_cache_id[DART_OBJ_CACHE_SLOTS]; /* +0x14030 */
    u64 dart_obj_cache_va[DART_OBJ_CACHE_SLOTS]; /* +0x14230 */
    u64 dart_obj_last[8];      /* +0x14430: table,ep,dart_id,obj,source,gapf_count,inst_count,state */
    u64 dart_obj_last_base_va[16]; /* +0x14470: XNU state MMIO VA per instance */
    u64 dart_obj_last_base_pa[16]; /* +0x144f0: translated MMIO PA per instance */
    struct nvme_c_state nvme;  /* +0x14570: C-side NVMe table-6 emulator */
    struct dart_c_state dart;  /* C-side T8110 DART table-3/4 emulator */
    /* Appended after the fixed-offset telemetry region so old Python offsets
     * remain stable. Real SPTM assigns logical CPU IDs at register_cpu time;
     * XNU then uses sptm_prev_ptes + PAGE_SIZE * sptm_cpu_id(phys_id). */
    u64 cpu_count;
    u64 cpu_phys_ids[SPTM_MAX_CPUS_EMUL];
    u64 cpu_last_mpidr;
    u64 cpu_last_id;
    u64 cpu_unknown_mpidr;
    struct txm_c_state txm;   /* C-side TXM domain=2/table=0 emulator */
    struct sart_c_state sart; /* C-side SART table=5 emulator */
    /*
     * Real SPTM's register_cpu endpoint records each CPU's cpu-impl-reg,
     * acc-impl-reg, and cpm-impl-reg windows from ADT and creates private SPTM
     * mappings for them. Keep the same discovered metadata here. This is
     * Mostly bookkeeping; on T8140 the first reserved word can hold a private
     * backing page for E-core cpu-impl-reg leaves that fault as locked PIO when
     * exposed directly to XNU.
     */
    struct sptm_cpu_pio_state cpu_pio;
    struct papt_update_state papt_update;
    u64 papt_span;
    struct uat_c_state uat;   /* C-side UAT table=7 emulator */
    struct alt_ptd_trace_state alt_ptd_trace;
};

typedef char sptm_emul_state_fits_in_scratch[
    (sizeof(struct sptm_emul_state) <= 0x100000UL) ? 1 : -1];

/* The single state instance exported for Python-side boot seeding. Keep this
 * 1MiB even though struct sptm_emul_state is smaller: a few emulated SPTM
 * devices use the tail as private scratch, matching the old bringup layout. */
extern u8 g_sptm_state[0x100000];
#define g_state (*(struct sptm_emul_state *)g_sptm_state)

static inline bool_t finish_hvc_success(void *ctx, u64 *regs) {
    u64 elr2;
    __asm__ volatile("mrs %0, elr_el2" : "=r"(elr2));
    u64 *ctx_elr = (u64 *)((unsigned char *)ctx + 0x108);
    *ctx_elr = elr2;
    regs[0] = SPTM_SUCCESS;
    g_state.fast_path_calls++;
    sev();
    return 1;
}

static inline bool_t compat_void_non_xnu_table(u32 table) {
    /*
     * Temporary parity shim for the removed Python fallback.  After TXM,
     * DART, SART, NVMe, UAT, and CPUTRACE had first crack, the mixed
     * Python/C emulator acknowledged remaining non-XNU dispatch tables with
     * x0=0.  Keep that behavior only for known auxiliary tables so C-only
     * bringup reaches the same wall without hiding real DART/NVMe/UAT
     * state-machine failures.
     */
    return table == SPTM_TABLE_TXM_BOOTSTRAP ||
           table == SPTM_TABLE_SK_BOOTSTRAP ||
           table == SPTM_TABLE_SHART ||
           table == SPTM_TABLE_HIB;
}

static inline u64 current_mpidr_phys(void) {
    u64 mpidr;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(mpidr));
    return mpidr & 0xffffffffUL;
}

static inline u64 cpu_phys_compact(u64 phys) {
    return phys & 0x00ffffffUL;
}

static inline u64 cpu_phys_adt_reg(u64 phys) {
    return phys & 0x0000ffffUL;
}

static inline bool_t cpu_phys_matches(u64 a, u64 b) {
    if (a == b)
        return 1;
    if ((a & 0xffffffffUL) == (b & 0xffffffffUL))
        return 1;
    if (cpu_phys_compact(a) == cpu_phys_compact(b))
        return 1;
    if (cpu_phys_adt_reg(a) == cpu_phys_adt_reg(b))
        return 1;
    return 0;
}

static inline void sptm_cpu_pio_note_registered(u64 phys, u64 logical_id) {
    struct sptm_cpu_pio_state *st = &g_state.cpu_pio;
    u64 count = st->seeded_count;
    u64 flags = SPTM_CPU_PIO_F_MISSING;

    if (count > SPTM_MAX_CPUS_EMUL)
        count = SPTM_MAX_CPUS_EMUL;

    st->last_phys = phys;
    st->last_slot = UINT64_MAX_VALUE;

    for (u64 i = 0; i < count; i++) {
        struct sptm_cpu_pio_entry *ent = &st->entries[i];

        if (!cpu_phys_matches(ent->phys_id, phys))
            continue;

        flags = ent->flags | SPTM_CPU_PIO_F_REGISTERED;
        if (!ent->registered)
            st->registered_count++;
        ent->registered++;
        ent->logical_id = logical_id;
        ent->flags = flags;
        st->last_slot = i;
        break;
    }

    st->last_flags = flags;
}

#define T8140_CPU_IMPL_LOCKED_REG_OFF 0x9000UL
#define T8140_CPM_DPE_LOCKED_REG_OFF  0x40f8UL

static inline u64 t8140_cpu_pio_shadow_pa(void) {
    return g_state.cpu_pio.reserved[0] & FRAME_PAGE_MASK;
}

static inline bool_t t8140_cpu_pio_shadow_target(u64 pa, u64 page_mask) {
    struct sptm_cpu_pio_state *st = &g_state.cpu_pio;
    u64 count = st->seeded_count;

    if (count > SPTM_MAX_CPUS_EMUL)
        count = SPTM_MAX_CPUS_EMUL;

    pa &= page_mask;
    for (u64 i = 0; i < count; i++) {
        struct sptm_cpu_pio_entry *ent = &st->entries[i];

        if (ent->cpu_base && ent->cpu_size > T8140_CPU_IMPL_LOCKED_REG_OFF) {
            u64 locked_page =
                (ent->cpu_base + T8140_CPU_IMPL_LOCKED_REG_OFF) & page_mask;
            if (pa == locked_page)
                return 1;
        }

        if (ent->cpm_base && ent->cpm_size > T8140_CPM_DPE_LOCKED_REG_OFF) {
            u64 locked_page =
                (ent->cpm_base + T8140_CPM_DPE_LOCKED_REG_OFF) & page_mask;
            if (pa == locked_page)
                return 1;
        }
    }

    return 0;
}

static inline u64 t8140_cpu_pio_shadow_pte(u64 arm_pte, bool_t geom4k) {
    if ((arm_pte & 3) != 3)
        return arm_pte;

    u64 shadow_pa = t8140_cpu_pio_shadow_pa();
    if (!shadow_pa)
        return arm_pte;

    u64 page_mask = geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK;
    u64 target_pa = arm_pte & page_mask;
    if (!t8140_cpu_pio_shadow_target(target_pa, page_mask))
        return arm_pte;

    u64 shadow_target_pa =
        shadow_pa + (target_pa & (PAGE_SIZE_GUEST_EMUL - 1UL));
    return (arm_pte & ~page_mask) | (shadow_target_pa & page_mask);
}

static inline u64 cpu_id_for_phys(u64 phys) {
    u64 count = g_state.cpu_count;
    if (count > SPTM_MAX_CPUS_EMUL)
        count = SPTM_MAX_CPUS_EMUL;
    for (u64 i = 0; i < count; i++) {
        if (cpu_phys_matches(g_state.cpu_phys_ids[i], phys))
            return i;
    }
    g_state.cpu_unknown_mpidr = phys;
    return 0;
}

static inline u64 current_sptm_cpu_id(void) {
    u64 mpidr = current_mpidr_phys();
    u64 id = cpu_id_for_phys(mpidr);
    g_state.cpu_last_mpidr = mpidr;
    g_state.cpu_last_id = id;
    return id;
}

static inline volatile u64 *scratch_for_current_cpu(void) {
    if (g_state.scratch_pa == 0)
        return (volatile u64 *)0;
    u64 id = current_sptm_cpu_id();
    if (id >= SPTM_MAX_CPUS_EMUL)
        id = 0;
    return (volatile u64 *)(g_state.scratch_pa + id * PAGE_SIZE_GUEST_EMUL);
}

static inline bool_t ft_get_idx(u64 pa, u64 *idx_out) {
    pa &= FRAME_PAGE_MASK;
    if (g_state.frame_table_base == 0 || pa < g_state.vm_first_phys) return 0;
    u64 idx = (pa - g_state.vm_first_phys) >> 14;
    if ((idx * 16UL) >= g_state.frame_table_size) return 0;
    *idx_out = idx;
    return 1;
}

static inline bool_t papt_va_for_managed_pa(u64 pa, u64 *papt_va_out) {
    u64 idx;

    pa &= FRAME_PAGE_MASK;
    if (g_state.first_papt == 0)
        return 0;
    if (!ft_get_idx(pa, &idx))
        return 0;
    if (g_state.papt_span && idx * PAGE_SIZE_GUEST_EMUL >= g_state.papt_span)
        return 0;

    *papt_va_out = g_state.first_papt + idx * PAGE_SIZE_GUEST_EMUL;
    return 1;
}

static inline void note_papt_nvme_hit_class(u64 cls, u64 rc) {
    if (cls >= PAPT_NVME_CLASS_COUNT)
        return;
    g_state.papt_update.nvme_hits[cls]++;
    if (rc == PAPT_UPDATE_RC_WRITE)
        g_state.papt_update.nvme_writes[cls]++;
}

static inline bool_t papt_pa_overlaps(u64 pa, u64 start, u64 size) {
    if (start == 0 || start == UINT64_MAX_VALUE || size == 0)
        return 0;

    u64 page = pa & FRAME_PAGE_MASK;
    u64 first = start & FRAME_PAGE_MASK;
    u64 end = (start + size + PAGE_SIZE_GUEST_EMUL - 1UL) & FRAME_PAGE_MASK;
    if (end < start)
        end = UINT64_MAX_VALUE;
    return first <= page && page < end;
}

static inline void note_papt_nvme_hits(u64 rc, u64 pa) {
    u32 queue_count = g_state.nvme.queue_count;
    if (queue_count == 0)
        queue_count = 1;
    if (queue_count > NVME_C_MAX_CID)
        queue_count = NVME_C_MAX_CID;

    u64 admin_span = (((u64)queue_count * 0x80UL) + 0xfffUL) & ~0xfffUL;
    u64 cq_span = (((u64)queue_count * 0x10UL) + 0xfffUL) & ~0xfffUL;

    if (papt_pa_overlaps(pa, g_state.nvme.admin_asq_kva, admin_span))
        note_papt_nvme_hit_class(PAPT_NVME_SEED_ASQ, rc);
    if (papt_pa_overlaps(pa, g_state.nvme.admin_acq_kva, admin_span))
        note_papt_nvme_hit_class(PAPT_NVME_SEED_ACQ, rc);
    if (papt_pa_overlaps(pa, g_state.nvme.prp_list_kva,
                         (u64)queue_count * 0x800UL))
        note_papt_nvme_hit_class(PAPT_NVME_PRP_LIST, rc);
    if (papt_pa_overlaps(pa, g_state.nvme.asq_pa_cached, admin_span))
        note_papt_nvme_hit_class(PAPT_NVME_XNU_ASQ, rc);
    if (papt_pa_overlaps(pa, g_state.nvme.acq_pa_cached, cq_span))
        note_papt_nvme_hit_class(PAPT_NVME_XNU_ACQ, rc);
    if (papt_pa_overlaps(pa, g_state.nvme.iosq_pa_cached, admin_span))
        note_papt_nvme_hit_class(PAPT_NVME_XNU_IOSQ, rc);
    if (papt_pa_overlaps(pa, g_state.nvme.iocq_pa_cached, cq_span))
        note_papt_nvme_hit_class(PAPT_NVME_XNU_IOCQ, rc);

    for (u32 cid = 0; cid < queue_count && cid < NVME_C_MAX_CID; cid++) {
        if (g_state.nvme.cid_mode[cid] == NVME_CID_AVAILABLE ||
            g_state.nvme.cid_mode[cid] == NVME_CID_BUSY)
            continue;
        if (papt_pa_overlaps(pa, g_state.nvme.tcb_prp1[cid],
                             PAGE_SIZE_GUEST_EMUL) ||
            papt_pa_overlaps(pa, g_state.nvme.tcb_prp2[cid],
                             PAGE_SIZE_GUEST_EMUL)) {
            note_papt_nvme_hit_class(PAPT_NVME_ACTIVE_PRP, rc);
            break;
        }
    }
}

static inline u64 sptm_ctx_elr(void *ctx) {
    if (!ctx)
        return 0;
    return *(volatile u64 *)((unsigned char *)ctx + 0x108);
}

static inline void note_papt_update(u64 rc, u64 pa, u32 options, u64 papt_va,
                                    u64 root_pa, u64 template_pte,
                                    u64 existing_pte, u64 new_pte,
                                    u64 caller_elr, u64 inner_root_pa,
                                    u64 inner_va, u64 inner_template_pte) {
    struct papt_update_state *st = &g_state.papt_update;
    u64 slot;

    note_papt_nvme_hits(rc, pa);
    st->calls++;
    switch (rc) {
    case PAPT_UPDATE_RC_WRITE:
        st->candidates++;
        st->writes++;
        break;
    case PAPT_UPDATE_RC_SKIP_PAPT:
        st->skip_skip_papt++;
        break;
    case PAPT_UPDATE_RC_NO_ATTR:
        st->skip_no_attr++;
        break;
    case PAPT_UPDATE_RC_UNMANAGED:
        st->candidates++;
        st->skip_unmanaged++;
        break;
    case PAPT_UPDATE_RC_BAD_TEMPLATE:
        st->candidates++;
        st->skip_bad_template++;
        break;
    case PAPT_UPDATE_RC_BAD_ROOT:
        st->candidates++;
        st->skip_bad_root++;
        break;
    case PAPT_UPDATE_RC_BAD_WALK:
        st->candidates++;
        st->skip_bad_walk++;
        break;
    case PAPT_UPDATE_RC_BAD_EXISTING:
        st->candidates++;
        st->skip_bad_existing++;
        break;
    case PAPT_UPDATE_RC_SAME_ATTRS:
        st->candidates++;
        st->skip_same_attrs++;
        break;
    default:
        break;
    }

    slot = st->ring_idx++ & (PAPT_UPDATE_RING_SLOTS - 1);
    st->ring[slot].rc = rc;
    st->ring[slot].pa = pa;
    st->ring[slot].options = options;
    st->ring[slot].papt_va = papt_va;
    st->ring[slot].root_pa = root_pa;
    st->ring[slot].template_pte = template_pte;
    st->ring[slot].existing_pte = existing_pte;
    st->ring[slot].new_pte = new_pte;
    st->ring[slot].caller_elr = caller_elr;
    st->ring[slot].inner_root_pa = inner_root_pa;
    st->ring[slot].inner_va = inner_va;
    st->ring[slot].inner_template_pte = inner_template_pte;
}

static inline bool_t papt_attrs_are_rt_nc(u64 pte) {
    const u64 attr_mask = ARM_PTE_ATTRINDX_MASK | ARM_PTE_SH_MASK;

    return (pte & attr_mask) == (1UL << 2);
}

static inline bool_t mirror_stage2_for_papt_attrs(u64 pa, u64 old_pte,
                                                  u64 new_pte) {
    bool_t old_rt = papt_attrs_are_rt_nc(old_pte);
    bool_t new_rt = papt_attrs_are_rt_nc(new_pte);
    u64 page = pa & ARM_PTE_PAGE_MASK;
    u64 attrs;

    if (old_rt == new_rt)
        return 0;

    attrs = new_rt ? HV_S2_PTE_NORMAL_NC : HV_S2_PTE_NORMAL_WB;
    return hv_map(page, page | attrs, PAGE_SIZE_GUEST_EMUL, 1) == 0;
}

static inline bool_t update_kernel_papt_attrs(u64 pa, u64 papt_template,
                                              u32 options, u64 caller_elr,
                                              u64 inner_root_pa, u64 inner_va,
                                              u64 inner_template_pte) {
    u64 papt_va;
    u64 idx;
    u64 root_pa;
    u64 l3;
    volatile u64 *slot;
    u64 existing;
    u64 template_pte;
    u64 new_pte;
    const u64 attr_mask = (7UL << 2) | (3UL << 8);

    if (options & SPTM_UPDATE_SKIP_PAPT) {
        note_papt_update(PAPT_UPDATE_RC_SKIP_PAPT, pa, options, 0, 0, 0, 0, 0,
                         caller_elr, inner_root_pa, inner_va, inner_template_pte);
        return 0;
    }
    if ((options & (SPTM_UPDATE_SH | SPTM_UPDATE_MAIR)) == 0) {
        note_papt_update(PAPT_UPDATE_RC_NO_ATTR, pa, options, 0, 0, 0, 0, 0,
                         caller_elr, inner_root_pa, inner_va, inner_template_pte);
        return 0;
    }
    if (!papt_va_for_managed_pa(pa, &papt_va)) {
        note_papt_update(PAPT_UPDATE_RC_UNMANAGED, pa, options, 0, 0, 0, 0, 0,
                         caller_elr, inner_root_pa, inner_va, inner_template_pte);
        return 0;
    }

    template_pte = xnu_pte_to_arm_geom(papt_template, 0);
    if ((template_pte & 3) != 3) {
        note_papt_update(PAPT_UPDATE_RC_BAD_TEMPLATE, pa, options, papt_va, 0,
                         template_pte, 0, 0, caller_elr, inner_root_pa,
                         inner_va, inner_template_pte);
        return 0;
    }
    if ((template_pte & ARM_PTE_PAGE_MASK) != (pa & ARM_PTE_PAGE_MASK)) {
        note_papt_update(PAPT_UPDATE_RC_BAD_TEMPLATE, pa, options, papt_va, 0,
                         template_pte, 0, 0, caller_elr, inner_root_pa,
                         inner_va, inner_template_pte);
        return 0;
    }

    root_pa = ttbr1_el12_root_pa();
    if (root_pa == 0) {
        note_papt_update(PAPT_UPDATE_RC_BAD_ROOT, pa, options, papt_va, root_pa,
                         template_pte, 0, 0, caller_elr, inner_root_pa,
                         inner_va, inner_template_pte);
        return 0;
    }

    l3 = walk_to_l3_16k(root_pa, papt_va, &idx);
    if (l3 == 0) {
        note_papt_update(PAPT_UPDATE_RC_BAD_WALK, pa, options, papt_va, root_pa,
                         template_pte, 0, 0, caller_elr, inner_root_pa,
                         inner_va, inner_template_pte);
        return 0;
    }

    slot = pt_slot_ptr(l3, idx);
    existing = pt_read_slot_poc(slot);
    if ((existing & 3) != 3) {
        note_papt_update(PAPT_UPDATE_RC_BAD_EXISTING, pa, options, papt_va,
                         root_pa, template_pte, existing, 0, caller_elr,
                         inner_root_pa, inner_va, inner_template_pte);
        return 0;
    }
    if ((existing & ARM_PTE_PAGE_MASK) != (pa & ARM_PTE_PAGE_MASK)) {
        note_papt_update(PAPT_UPDATE_RC_BAD_EXISTING, pa, options, papt_va,
                         root_pa, template_pte, existing, 0, caller_elr,
                         inner_root_pa, inner_va, inner_template_pte);
        return 0;
    }

    new_pte = existing;
    if (options & SPTM_UPDATE_SH)
        new_pte = (new_pte & ~(3UL << 8)) | (template_pte & (3UL << 8));
    if (options & SPTM_UPDATE_MAIR)
        new_pte = (new_pte & ~(7UL << 2)) | (template_pte & (7UL << 2));

    if ((new_pte & attr_mask) == (existing & attr_mask)) {
        note_papt_update(PAPT_UPDATE_RC_SAME_ATTRS, pa, options, papt_va,
                         root_pa, template_pte, existing, new_pte, caller_elr,
                         inner_root_pa, inner_va, inner_template_pte);
        return 0;
    }

    /*
     * XNU may be moving a managed DRAM page from cacheable to RT/NC
     * semantics. Clean+invalidate the data page while our identity alias is
     * still cacheable so the downstream RT mapping cannot hit stale cache/SLC
     * directory state.
     */
    sptm_coproc_cache_maint_data_page(pa);
    mirror_stage2_for_papt_attrs(pa, existing, new_pte);
    *slot = new_pte;
    clean_pt_slot_poc(slot);
    note_papt_update(PAPT_UPDATE_RC_WRITE, pa, options, papt_va, root_pa,
                     template_pte, existing, new_pte, caller_elr, inner_root_pa,
                     inner_va, inner_template_pte);
    return 1;
}

static inline bool_t set_kernel_papt_cacheable_for_managed_pa(u64 pa,
                                                              bool_t cacheable,
                                                              u64 caller_elr) {
    u64 papt_va;
    u64 root_pa;
    u64 idx;
    u64 l3;
    volatile u64 *slot;
    u64 existing;
    u64 new_pte;
    const u64 attr_mask = ARM_PTE_ATTRINDX_MASK | ARM_PTE_SH_MASK;
    u32 options = cacheable ? SPTM_PAPT_OPT_ALT_TO_WB :
                              SPTM_PAPT_OPT_ALT_TO_NC;

    if (!papt_va_for_managed_pa(pa, &papt_va)) {
        note_papt_update(PAPT_UPDATE_RC_UNMANAGED, pa, options, 0, 0, 0, 0, 0,
                         caller_elr, 0, 0, 0);
        return 0;
    }

    root_pa = ttbr1_el12_root_pa();
    if (root_pa == 0) {
        note_papt_update(PAPT_UPDATE_RC_BAD_ROOT, pa, options, papt_va, root_pa,
                         0, 0, 0, caller_elr, 0, 0, 0);
        return 0;
    }

    l3 = walk_to_l3_16k(root_pa, papt_va, &idx);
    if (l3 == 0) {
        note_papt_update(PAPT_UPDATE_RC_BAD_WALK, pa, options, papt_va, root_pa,
                         0, 0, 0, caller_elr, 0, 0, 0);
        return 0;
    }

    slot = pt_slot_ptr(l3, idx);
    existing = pt_read_slot_poc(slot);
    if ((existing & 3) != 3 ||
        ((existing & ARM_PTE_PAGE_MASK) != (pa & ARM_PTE_PAGE_MASK))) {
        note_papt_update(PAPT_UPDATE_RC_BAD_EXISTING, pa, options, papt_va,
                         root_pa, 0, existing, 0, caller_elr, 0, 0, 0);
        return 0;
    }

    new_pte = (existing & ~attr_mask) |
              (cacheable ? SPTM_PAPT_ATTR_NORMAL_WB : SPTM_PAPT_ATTR_RT_NC);
    if ((new_pte & attr_mask) == (existing & attr_mask)) {
        note_papt_update(PAPT_UPDATE_RC_SAME_ATTRS, pa, options, papt_va,
                         root_pa, new_pte, existing, new_pte, caller_elr,
                         0, 0, 0);
        return 0;
    }

    /*
     * Real SPTM routes type-24/kind-5 frames through the coprocessor/IOMMU
     * coherency path. We cannot issue that GXF/SLC operation here, so prevent
     * XNU's PAPT/direct-map alias from creating the cacheable tag in the first
     * place while the frame is a coprocessor-visible ALT/PTD page.
     */
    sptm_coproc_cache_maint_data_page(pa);
    mirror_stage2_for_papt_attrs(pa, existing, new_pte);
    *slot = new_pte;
    clean_pt_slot_poc(slot);
    note_papt_update(PAPT_UPDATE_RC_WRITE, pa, options, papt_va, root_pa,
                     new_pte, existing, new_pte, caller_elr, 0, 0, 0);
    return 1;
}

static inline u16 ft_read_u16(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return 0;
    volatile u16 *cnt = (volatile u16 *)(g_state.frame_table_base + idx * 16 + off);
    return *cnt;
}

static inline void ft_clean_entry_idx(u64 idx) {
    clean_range_poc((void *)(g_state.frame_table_base + idx * 16), 16);
}

static inline void ft_write_u16(u64 pa, u64 off, u16 val) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return;
    volatile u16 *cnt = (volatile u16 *)(g_state.frame_table_base + idx * 16 + off);
    *cnt = val;
    ft_clean_entry_idx(idx);
}

static inline void ft_inc_u16(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return;
    volatile u16 *cnt = (volatile u16 *)(g_state.frame_table_base + idx * 16 + off);
    u16 v = *cnt;
    if (v < 0xFFFF) {
        *cnt = v + 1;
        ft_clean_entry_idx(idx);
    }
}

static inline void ft_dec_u16(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return;
    volatile u16 *cnt = (volatile u16 *)(g_state.frame_table_base + idx * 16 + off);
    u16 v = *cnt;
    if (v > 0) {
        *cnt = v - 1;
        ft_clean_entry_idx(idx);
    }
}

static inline void ft_inc_u32(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return;
    volatile u32 *cnt = (volatile u32 *)(g_state.frame_table_base + idx * 16 + off);
    u32 v = *cnt;
    if (v < 0xffffffffU) {
        *cnt = v + 1;
        ft_clean_entry_idx(idx);
    }
}

static inline void ft_dec_u32(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return;
    volatile u32 *cnt = (volatile u32 *)(g_state.frame_table_base + idx * 16 + off);
    u32 v = *cnt;
    if (v > 0) {
        *cnt = v - 1;
        ft_clean_entry_idx(idx);
    }
}

static inline u32 ft_read_u32(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return 0;
    volatile u32 *cnt = (volatile u32 *)(g_state.frame_table_base + idx * 16 + off);
    return *cnt;
}

/* Refcount maintenance.
 *
 * Firmware-visible fields:
 *   - kind=5 secondary pages: u16 refcount at FTE+0x04.
 *   - page-table frames: u16 parent/table-link count at FTE+0x06.
 *   - page-table frames: u16 live child/leaf count at FTE+0x08.
 *   - kind=3 data pages: u32 ro_refcnt at FTE+0x08, wx_refcnt at FTE+0x0c.
 */
static inline bool_t pte_uses_wx_refcount(u64 pte) {
    bool_t writable = (pte & ARM_PTE_WRITEABLE) ||
                      ((pte & ARM_PTE_AP_RO) == 0);
    bool_t executable = (pte & (ARM_PTE_PNX | ARM_PTE_NX)) !=
                        (ARM_PTE_PNX | ARM_PTE_NX);
    return writable || executable;
}

static inline void ft_inc_page_refcount_for_pte(u64 pa, u64 pte) {
    u8 type = ft_get_type(pa);
    if (type == XNU_PAGE_TABLE_ALT) {
        ft_inc_u16(pa, FT_KIND5_REFCNT_OFF);
        return;
    }
    if (is_pt_type(type))
        return;
    if (pte_uses_wx_refcount(pte))
        ft_inc_u32(pa, FT_DATA_WX_REFCNT_OFF);
    else
        ft_inc_u32(pa, FT_DATA_RO_REFCNT_OFF);
}

static inline void ft_dec_page_refcount_for_pte(u64 pa, u64 pte) {
    u8 type = ft_get_type(pa);
    if (type == XNU_PAGE_TABLE_ALT) {
        ft_dec_u16(pa, FT_KIND5_REFCNT_OFF);
        return;
    }
    if (is_pt_type(type))
        return;
    if (pte_uses_wx_refcount(pte))
        ft_dec_u32(pa, FT_DATA_WX_REFCNT_OFF);
    else
        ft_dec_u32(pa, FT_DATA_RO_REFCNT_OFF);
}

static inline void ft_inc_table_mapping_refcount(u64 pa) {
    ft_inc_u16(pa, FT_TABLE_MAPPING_REFCNT_OFF);
}

static inline void ft_dec_table_mapping_refcount(u64 pa) {
    ft_dec_u16(pa, FT_TABLE_MAPPING_REFCNT_OFF);
}

static inline void ft_inc_table_nested_refcount(u64 pa) {
    ft_inc_u16(pa, FT_TABLE_NESTED_REFCNT_OFF);
}

static inline void ft_dec_table_nested_refcount(u64 pa) {
    ft_dec_u16(pa, FT_TABLE_NESTED_REFCNT_OFF);
}

static inline u32 ft_read_page_refcount(u64 pa) {
    if (ft_get_type(pa) == XNU_PAGE_TABLE_ALT)
        return ft_read_u16(pa, FT_KIND5_REFCNT_OFF);
    return ft_read_u32(pa, FT_DATA_RO_REFCNT_OFF) +
           ft_read_u32(pa, FT_DATA_WX_REFCNT_OFF);
}

static inline u16 ft_read_table_refcount(u64 pa) {
    return ft_read_u16(pa, FT_TABLE_NESTED_REFCNT_OFF);
}

static inline bool_t is_kernel_va(u64 va);
static inline bool_t guest_read64(u64 va, u64 *out);

static inline void alt_ptd_trace_add_bt(struct alt_ptd_trace_event *ev,
                                        u64 value) {
    if (!is_kernel_va(value))
        return;

    for (u64 i = 0; i < ev->bt_count && i < 12; i++) {
        if (ev->bt[i] == value)
            return;
    }

    if (ev->bt_count < 12)
        ev->bt[ev->bt_count++] = value;
}

static inline void alt_ptd_trace_walk_frame(struct alt_ptd_trace_event *ev,
                                            u64 fp) {
    for (u32 depth = 0; depth < 8; depth++) {
        u64 saved_fp;
        u64 saved_lr;

        if (!is_kernel_va(fp))
            break;
        if (!guest_read64(fp, &saved_fp) ||
            !guest_read64(fp + 8, &saved_lr))
            break;

        alt_ptd_trace_add_bt(ev, saved_lr);

        if (saved_fp == fp || saved_fp < fp || saved_fp - fp > 0x200000UL)
            break;
        fp = saved_fp;
    }
}

static inline void alt_ptd_trace_scan_stack(struct alt_ptd_trace_event *ev,
                                            u64 sp) {
    if (!is_kernel_va(sp))
        return;
    if (!ev->bt_base)
        ev->bt_base = sp;

    for (u32 off = 0; off < 0x180; off += 8) {
        u64 value;

        if (!guest_read64(sp + off, &value))
            break;
        alt_ptd_trace_add_bt(ev, value);
    }
}

static inline void note_alt_ptd_retype(u64 pa, u64 caller_elr, u64 caller_lr,
                                       u64 caller_fp, u64 caller_sp0,
                                       u64 caller_sp1, u8 current_type,
                                       u8 existing_type, u8 new_type,
                                       u64 retype_params,
                                       u64 page_ref_before,
                                       u64 table_ref_before,
                                       u64 page_ref_after,
                                       u64 table_ref_after, u64 ft_idx,
                                       u64 papt_ring_before, u64 flags) {
    struct alt_ptd_trace_state *st = &g_state.alt_ptd_trace;
    u64 seq = st->ring_idx++;
    struct alt_ptd_trace_event *ev =
        &st->ring[seq & (ALT_PTD_TRACE_RING_SLOTS - 1)];
    u64 papt_ring_after = g_state.papt_update.ring_idx;
    u64 papt_rc = 0;
    u64 papt_existing = 0;
    u64 papt_new = 0;
    u64 papt_va = 0;

    if (papt_ring_after > papt_ring_before) {
        struct papt_update_event *pev =
            &g_state.papt_update.ring[(papt_ring_after - 1) &
                                      (PAPT_UPDATE_RING_SLOTS - 1)];
        if ((pev->pa & FRAME_PAGE_MASK) == (pa & FRAME_PAGE_MASK)) {
            papt_rc = pev->rc;
            papt_existing = pev->existing_pte;
            papt_new = pev->new_pte;
            papt_va = pev->papt_va;
        }
    }

    ev->seq = seq;
    ev->pa = pa & FRAME_PAGE_MASK;
    ev->caller_elr = caller_elr;
    ev->caller_lr = caller_lr;
    ev->caller_fp = caller_fp;
    ev->types_flags = ((u64)current_type) |
                      ((u64)existing_type << 8) |
                      ((u64)new_type << 16) |
                      (flags << 32);
    ev->retype_params = retype_params;
    ev->ft_idx = ft_idx;
    ev->refs_before = (page_ref_before & 0xffffffffUL) |
                      ((table_ref_before & 0xffffffffUL) << 32);
    ev->refs_after = (page_ref_after & 0xffffffffUL) |
                     ((table_ref_after & 0xffffffffUL) << 32);
    ev->papt_ring_before = papt_ring_before;
    ev->papt_ring_after = papt_ring_after;
    ev->papt_rc = papt_rc;
    ev->papt_existing_pte = papt_existing;
    ev->papt_new_pte = papt_new;
    ev->papt_va = papt_va;
    ev->caller_sp0 = caller_sp0;
    ev->caller_sp1 = caller_sp1;
    ev->bt_count = 0;
    ev->bt_base = 0;
    for (u32 i = 0; i < 12; i++)
        ev->bt[i] = 0;

    alt_ptd_trace_add_bt(ev, caller_lr);
    alt_ptd_trace_walk_frame(ev, caller_fp);
    alt_ptd_trace_scan_stack(ev, caller_sp0);
    alt_ptd_trace_scan_stack(ev, caller_sp1);
}

static inline u64 ft_idx_or_bad(u64 pa) {
    u64 idx;
    return ft_get_idx(pa, &idx) ? idx : UINT64_MAX_VALUE;
}

static inline void ft_inc_refcount(u64 pa) {
    ft_inc_page_refcount_for_pte(pa, 0);
}

static inline void ft_dec_refcount(u64 pa) {
    ft_dec_page_refcount_for_pte(pa, 0);
}

#if 0
/* Kept disabled to document the old single-refcount model. It was wrong for
 * page-table frames because libsptm_get_table_mapping_count only accepts
 * frame_type_params kind 1/2, not kind 5. */
static inline void ft_inc_refcount_old(u64 pa) {
    if (g_state.frame_table_base == 0 || pa < g_state.vm_first_phys) return;
    u64 idx = (pa - g_state.vm_first_phys) >> 14;
    if (idx >= g_state.frame_table_size) return;
    volatile u16 *cnt = (volatile u16 *)(g_state.frame_table_base + idx * 16 + 4);
    u16 v = *cnt;
    if (v < 0xFFFF) *cnt = v + 1;
}

static inline void ft_dec_refcount_old(u64 pa) {
    if (g_state.frame_table_base == 0 || pa < g_state.vm_first_phys) return;
    u64 idx = (pa - g_state.vm_first_phys) >> 14;
    if (idx >= g_state.frame_table_size) return;
    volatile u16 *cnt = (volatile u16 *)(g_state.frame_table_base + idx * 16 + 4);
    u16 v = *cnt;
    if (v > 0) *cnt = v - 1;
}
#endif

static inline u8 ft_get_type(u64 pa) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return XNU_DEFAULT;
    volatile u8 *ft = (volatile u8 *)g_state.frame_table_base;
    return ft[idx * 16 + 2];
}

static inline bool_t is_root_type(u8 t) {
    return t == SPTM_KERNEL_ROOT_TABLE ||
           t == XNU_USER_ROOT_TABLE ||
           t == XNU_SHARED_ROOT_TABLE ||
           t == XNU_STAGE2_ROOT_TABLE ||
           t == XNU_SUBPAGE_USER_ROOT_TABLES;
}

static inline u8 retype_params_attr_idx(u64 params) {
    return (u8)(params & 0xff);
}

static inline u16 retype_params_flags(u64 params) {
    return (u16)((params >> 16) & 0xffff);
}

static inline u16 retype_params_asid(u64 params) {
    return (u16)((params >> 32) & 0xffff);
}

static inline u8 root_geom_lookup(u64 root_pa) {
    for (u32 i = 0; i < ROOT_GEOM_SLOTS; i++) {
        if (g_state.root_geom_pa[i] == root_pa)
            return (u8)(g_state.root_geom_attr[i] & 0xff);
    }

    if (ft_get_type(root_pa) == XNU_SUBPAGE_USER_ROOT_TABLES)
        return SPTM_PT_GEOMETRY_4K;
    return ROOT_GEOM_UNKNOWN;
}

static inline u16 root_asid_lookup(u64 root_pa) {
    for (u32 i = 0; i < ROOT_GEOM_SLOTS; i++) {
        if (g_state.root_geom_pa[i] == root_pa)
            return (u16)((g_state.root_geom_attr[i] >> 16) & 0xffff);
    }
    return 0;
}

static inline void root_geom_set_meta(u64 root_pa, u8 geom, u16 asid) {
    u32 empty = ROOT_GEOM_SLOTS;
    u64 packed = (u64)geom | ((u64)asid << 16);

    for (u32 i = 0; i < ROOT_GEOM_SLOTS; i++) {
        if (g_state.root_geom_pa[i] == root_pa) {
            g_state.root_geom_attr[i] = packed;
            return;
        }
        if (empty == ROOT_GEOM_SLOTS && g_state.root_geom_pa[i] == 0)
            empty = i;
    }

    if (empty == ROOT_GEOM_SLOTS)
        empty = (u32)(((root_pa >> 14) ^ (root_pa >> 6)) & (ROOT_GEOM_SLOTS - 1));
    g_state.root_geom_pa[empty] = root_pa;
    g_state.root_geom_attr[empty] = packed;
}

static inline void root_geom_set(u64 root_pa, u8 geom) {
    root_geom_set_meta(root_pa, geom, root_asid_lookup(root_pa));
}

static inline bool_t root_uses_4k(u64 root_pa, u32 target_level) {
    if (target_level == 0) {
        /* XNU only calls sptm_map_table(..., level=0, ...) for roots whose
         * walk really starts at L0. Record that runtime fact so the next
         * level=1/2 operation for this same root descends through the table we
         * just installed instead of treating root[0] as an already-present
         * 16K L1 entry. */
        root_geom_set(root_pa, SPTM_PT_GEOMETRY_4K);
        return 1;
    }

    u8 geom = root_geom_lookup(root_pa);
    if (geom != ROOT_GEOM_UNKNOWN)
        return geom == SPTM_PT_GEOMETRY_4K;

    /* Do not infer 4K from XNU_USER_ROOT_TABLE. Apple Silicon supports mixed
     * user geometries, and the normal ARM64 bringup path here uses 16K user
     * roots. The earlier frame-type heuristic returned TABLE_NOT_PRESENT for
     * a valid 16K user root and sent xnu into pmap_expand()'s WFE loop. */
    return 0;
}

static inline u32 table_group_count(bool_t geom4k) {
    return geom4k ? 4U : 1U;
}

static inline u64 table_group_base_idx(u64 idx, bool_t geom4k) {
    return geom4k ? (idx & ~3UL) : idx;
}

static inline u64 table_group_child_pa(u64 child_pa, u32 n, bool_t geom4k) {
    if (!geom4k)
        return child_pa & ARM_TTE_TABLE_MASK;
    return (child_pa & FRAME_PAGE_MASK) + ((u64)n * PAGE_SIZE_4K_EMUL);
}

static inline void ft_set_type(u64 pa, u8 type) {
    u64 idx;
    if (!ft_get_idx(pa, &idx)) return;
    volatile u8 *ft = (volatile u8 *)g_state.frame_table_base;
    ft[idx * 16 + 2] = type;
    ft_clean_entry_idx(idx);
}

static inline bool_t is_pt_type(u8 t) {
    return t == SPTM_KERNEL_ROOT_TABLE ||
           t == SPTM_PAGE_TABLE ||
           t == XNU_USER_ROOT_TABLE ||
           t == XNU_SHARED_ROOT_TABLE ||
           t == XNU_PAGE_TABLE ||
           t == XNU_PAGE_TABLE_SHARED ||
           t == XNU_PAGE_TABLE_ROZONE ||
           t == XNU_PAGE_TABLE_COMMPAGE ||
           t == XNU_STAGE2_ROOT_TABLE ||
           t == XNU_STAGE2_PAGE_TABLE ||
           t == XNU_SUBPAGE_USER_ROOT_TABLES;
}

static inline bool_t is_io_type(u8 t) {
    return t == XNU_IO || t == XNU_PROTECTED_IO || t == XNU_COPROCESSOR_RO_IO;
}

static inline void update_refcounts_for_pte_change_geom(u64 existing, u64 new_pte,
                                                        bool_t geom4k) {
    bool_t old_valid = ((existing & 3) == 3);
    bool_t new_valid = ((new_pte & 3) == 3);
    u64 page_mask = geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK;
    u64 old_pa = existing & page_mask;
    u64 new_pa = new_pte & page_mask;

    if (old_valid && !new_valid) {
        ft_dec_page_refcount_for_pte(old_pa, existing);
    } else if (!old_valid && new_valid) {
        ft_inc_page_refcount_for_pte(new_pa, new_pte);
    } else if (old_valid && new_valid && old_pa != new_pa) {
        ft_dec_page_refcount_for_pte(old_pa, existing);
        ft_inc_page_refcount_for_pte(new_pa, new_pte);
    }
}

static inline void update_refcounts_for_leaf_pte_change(u64 table_pa,
                                                        u64 existing,
                                                        u64 new_pte,
                                                        bool_t geom4k) {
    bool_t old_valid = ((existing & 3) == 3);
    bool_t new_valid = ((new_pte & 3) == 3);

    update_refcounts_for_pte_change_geom(existing, new_pte, geom4k);

    table_pa &= FRAME_PAGE_MASK;
    if (old_valid && !new_valid)
        ft_dec_table_nested_refcount(table_pa);
    else if (!old_valid && new_valid)
        ft_inc_table_nested_refcount(table_pa);
}

static inline bool_t maybe_map_t8140_pmgr_cpustart_window(u64 root_pa, u64 va,
                                                          u64 arm_pte,
                                                          bool_t geom4k,
                                                          u64 known_l3,
                                                          u64 known_idx) {
    /*
     * T8140 ApplePMGR maps PMGR reg[24] at 0x300730000, but the CPUSTART
     * write lands at offset +0x4008 inside that regmap. XNU may install this
     * mapping through MAP_PAGE or a region/disjoint update, and it may hand us
     * any page inside the 0x14000-byte ADT window. If we leave holes in the
     * same real regmap, XNU faults in ApplePMGR::writeReg32 before the
     * hypervisor's physical CPUSTART hook can see the access.
     *
     * This is not generic MMIO expansion: it preserves only this exact ADT
     * PMGR regmap window, with the same PTE attributes XNU requested.
     */
    const u64 pmgr_base = 0x300730000UL;
    const u64 pmgr_size = 0x14000UL;
    u64 page_size = geom4k ? PAGE_SIZE_4K_EMUL : PAGE_SIZE_GUEST_EMUL;
    u64 page_mask = geom4k ? ARM_PTE_PAGE_MASK_4K : ARM_PTE_PAGE_MASK;
    u64 mapped_pa = arm_pte & page_mask;
    if ((arm_pte & 3) != 3)
        return 0;
    if (mapped_pa < pmgr_base || mapped_pa >= (pmgr_base + pmgr_size))
        return 0;

    u64 mapped_off = mapped_pa - pmgr_base;
    u64 window_va = va - mapped_off;
    bool_t changed = 0;
    u64 table_entries = geom4k ? 512UL : 2048UL;
    u64 mapped_page_idx = mapped_off / page_size;
    bool_t can_fill_direct =
        known_l3 != 0 && mapped_off == mapped_page_idx * page_size &&
        known_idx >= mapped_page_idx;
    u64 direct_base_idx = can_fill_direct ? known_idx - mapped_page_idx : 0;

    for (u64 off = 0; off < pmgr_size; off += page_size) {
        u64 idx = 0;
        u64 l3 = 0;
        if (can_fill_direct && direct_base_idx + off / page_size < table_entries) {
            l3 = known_l3;
            idx = direct_base_idx + off / page_size;
        } else {
            l3 = walk_to_l3(root_pa, window_va + off, &idx);
            if (!l3)
                continue;
        }

        volatile u64 *slot = pt_slot_ptr(l3, idx);
        u64 existing = pt_read_slot_poc(slot);
        if ((existing & 3) == 3)
            continue;

        u64 extra_pte = (arm_pte & ~page_mask) | ((pmgr_base + off) & page_mask);
        *slot = extra_pte;
        clean_pt_slot_poc(slot);
        update_refcounts_for_leaf_pte_change(l3, existing, extra_pte, geom4k);
        changed = 1;
    }

    if (changed)
        tlbi_vmalle1is();
    return changed;
}

static inline void write_prev_pte(volatile u64 *prev_out, u32 *prev_count,
                                  u64 existing) {
    if (prev_out != (volatile u64 *)0 && *prev_count < 2048)
        prev_out[*prev_count] = existing;
    *prev_count = *prev_count + 1;
}

/* Hardcoded offset of regs[] in m1n1's struct exc_info (always 0). */
#define REGS_OFFSET 0
#define ESR_OFFSET  0x110

static inline bool_t is_dispatch_hvc(u64 esr, u64 x16) {
    if ((esr & ESR_ISS_MASK) != SPTM_GENTER_DISPATCH_CALL) return 0;
    if (x16 & SPTM_DISPATCH_RESERVED_MASK) return 0;
    if (((x16 >> 48) & 0xff) > 4) return 0;
    if (((x16 >> 32) & 0xff) > 11) return 0;
    return 1;
}

#define KERNEL_VA_BASE 0xfffffe0000000000UL
#define DART_OBJ_MODE_OFF        0x0b8UL
#define DART_OBJ_STATE_OFF       0x0c50UL
#define DART_OBJ_INST_COUNT_OFF  0x14d8UL
#define DART_OBJ_GAPF_COUNT_OFF  0x17b0UL

static inline bool_t is_kernel_va(u64 va) {
    return (va & KERNEL_VA_BASE) == KERNEL_VA_BASE;
}

static inline bool_t guest_va_to_pa(u64 va, bool_t write, u64 *pa_out) {
    u64 par;
    if (write) {
        __asm__ volatile(
            "at s1e1w, %1\n\t"
            "isb\n\t"
            "mrs %0, par_el1\n\t"
            : "=r"(par) : "r"(va) : "memory");
    } else {
        __asm__ volatile(
            "at s1e1r, %1\n\t"
            "isb\n\t"
            "mrs %0, par_el1\n\t"
            : "=r"(par) : "r"(va) : "memory");
    }
    if (par & 1)
        return 0;
    *pa_out = (par & 0xfffffffffc000UL) | (va & 0x3fffUL);
    return 1;
}

static inline bool_t guest_read32(u64 va, u32 *out) {
    u64 pa;
    if (!is_kernel_va(va) || !guest_va_to_pa(va, 0, &pa))
        return 0;
    *out = *(volatile u32 *)pa;
    return 1;
}

static inline bool_t guest_read64(u64 va, u64 *out) {
    u64 pa;
    if (!is_kernel_va(va) || !guest_va_to_pa(va, 0, &pa))
        return 0;
    *out = *(volatile u64 *)pa;
    return 1;
}

static inline bool_t guest_write64(u64 va, u64 value) {
    u64 pa;
    if (!is_kernel_va(va) || !guest_va_to_pa(va, 1, &pa))
        return 0;
    *(volatile u64 *)pa = value;
    clean_range((void *)pa, 8);
    return 1;
}


/* Table/module entry points. */
bool_t dart_handle_table(u32 table, u32 endpoint, u64 *regs);
void dart_cache_xnu_object_from_regs(u32 table, u32 endpoint, u64 *regs);
bool_t nvme_handle_table6(u32 endpoint, u64 *regs);
bool_t sart_handle_table5(u32 endpoint, u64 *regs);
bool_t txm_handle_selector(u32 selector, u64 x16, u64 *regs);
bool_t uat_handle_table7(u32 endpoint, u64 *regs);
bool_t xnu_handle_table0(void *ctx, u32 endpoint, u64 *regs);
bool_t sptm_handler(void *ctx);

#endif /* SPTM_PRIVATE_H */
