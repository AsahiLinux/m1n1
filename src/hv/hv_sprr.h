/* SPDX-License-Identifier: GPL-2.0-or-later */

#ifndef HV_SPRR_H
#define HV_SPRR_H

#define HV_HVC_GENTER_BASE 0x1420
#define HV_HVC_GENTER_MASK GENMASK(15, 4)
#define HV_HVC_GENTER_IMM  GENMASK(3, 0)
#define HV_HVC_VECTOR_BASE 0x1500
#define HV_HVC_VECTOR_MASK 0xfff0
#define HV_HVC_VECTOR_SLOT GENMASK(3, 0)
#define HV_HVC_GEXIT       0x1400

#define HV_HVC_GXF_TLBI_ALL  0x1401
#define HV_HVC_GXF_TLBI_ARG  0x1300
#define HV_HVC_GXF_TLBI_MASK 0xffc0

#define HV_HVC_SYSREG_FLAG BIT(15)
#define HV_HVC_SYSREG_VREG GENMASK(13, 6) /* enum hv_vreg */
#define HV_HVC_SYSREG_DIR  BIT(5)         /* 1 = MRS */
#define HV_HVC_SYSREG_RT   GENMASK(4, 0)

#define SPRR_N_INDICES 16

#ifndef __ASSEMBLER__

#include "exception.h"
#include "types.h"

/* Must be kept in sync with HV_VREGS in proxyclient/m1n1/hv/sprr.py. */
enum hv_vreg {
    /* SPRR */
    HV_VREG_SPRR_AMRANGE_EL1,
    HV_VREG_SPRR_AMRANGE_EL12,
    HV_VREG_SPRR_CONFIG_EL1,
    HV_VREG_SPRR_CONFIG_EL12,
    HV_VREG_SPRR_PERM_EL0,
    HV_VREG_SPRR_PERM_EL1,
    HV_VREG_SPRR_PMPRR_EL1,
    HV_VREG_SPRR_PMPRR_EL12,
    HV_VREG_SPRR_PPERM_EL12,
    HV_VREG_SPRR_PPERM_SH1_EL1,
    HV_VREG_SPRR_PPERM_SH1_EL12,
    HV_VREG_SPRR_PPERM_SH2_EL1,
    HV_VREG_SPRR_PPERM_SH2_EL12,
    HV_VREG_SPRR_PPERM_SH3_EL1,
    HV_VREG_SPRR_PPERM_SH3_EL12,
    HV_VREG_SPRR_UMPRR_EL1,
    HV_VREG_SPRR_UMPRR_EL12,
    HV_VREG_SPRR_UPERM_SH1_EL1,
    HV_VREG_SPRR_UPERM_SH1_EL12,
    HV_VREG_SPRR_UPERM_SH2_EL1,
    HV_VREG_SPRR_UPERM_SH2_EL12,
    HV_VREG_SPRR_UPERM_SH3_EL1,
    HV_VREG_SPRR_UPERM_SH3_EL12,

    /* GXF */
    HV_VREG_GXF_ABORT_EL1,
    HV_VREG_GXF_CONFIG_EL1,
    HV_VREG_GXF_CONFIG_EL12,
    HV_VREG_GXF_ENTER_EL1,
    HV_VREG_GXF_ENTRY_EL12,
    HV_VREG_GXF_PABENTRY_EL12,
    HV_VREG_GXF_STATUS_EL1,

    /* Exception state */
    HV_VREG_AFSR0_EL12,
    HV_VREG_AFSR1_EL1,
    HV_VREG_AFSR1_EL12,
    HV_VREG_AFSR1_EL2,
    HV_VREG_AFSR1_GL1,
    HV_VREG_ASPSR_EL1,
    HV_VREG_ASPSR_GL1,
    HV_VREG_ELR_EL1,
    HV_VREG_ELR_EL12,
    HV_VREG_ELR_GL1,
    HV_VREG_ESR_EL1,
    HV_VREG_ESR_EL12,
    HV_VREG_ESR_GL1,
    HV_VREG_FAR_EL1,
    HV_VREG_FAR_EL12,
    HV_VREG_FAR_GL1,
    HV_VREG_HPFAR_EL2,
    HV_VREG_SPSR_EL1,
    HV_VREG_SPSR_EL12,
    HV_VREG_SPSR_GL1,
    HV_VREG_SP_GL12,
    HV_VREG_TPIDR_GL1,
    HV_VREG_TPIDR_GL2,
    HV_VREG_VBAR_EL1,
    HV_VREG_VBAR_EL12,
    HV_VREG_VBAR_GL1,
    HV_VREG_VBAR_GL12,

    /* MMU and Virtualization */
    HV_VREG_ACTLR_EL12_PRE,
    HV_VREG_AMAIR_EL12,
    HV_VREG_CONTEXTIDR_EL12,
    HV_VREG_CPACR_EL12,
    HV_VREG_HACR_EL2,
    HV_VREG_HCRX_EL2,
    HV_VREG_HCR_EL2,
    HV_VREG_ICH_HCR_EL2,
    HV_VREG_ICH_VMCR_EL2,
    HV_VREG_MAIR_EL12,
    HV_VREG_MDCR_EL2,
    HV_VREG_SCTLR_EL1,
    HV_VREG_SCTLR_EL12,
    HV_VREG_SCXTNUM_EL0,
    HV_VREG_SCXTNUM_EL12,
    HV_VREG_TCR_EL1,
    HV_VREG_TCR_EL12,
    HV_VREG_TTBR0_EL1,
    HV_VREG_TTBR0_EL12,
    HV_VREG_TTBR1_EL1,
    HV_VREG_TTBR1_EL12,
    HV_VREG_VMPIDR_EL2,
    HV_VREG_VPIDR_EL2,
    HV_VREG_VTCR_EL2,
    HV_VREG_VTTBR_EL2,

    /* Timers */
    HV_VREG_AGTCNTRDIR_EL1,
    HV_VREG_AGTCNTRDIR_EL12,
    HV_VREG_APL_CNTV_CTL_EL0,
    HV_VREG_APL_CNTV_TVAL_EL0,
    HV_VREG_CNTKCTL_EL12,
    HV_VREG_CNTVOFF_EL2,
    HV_VREG_VM_TMR_FIQ_ENA_EL2,

    /* CTxR */
    HV_VREG_CTRR_A_CTL_EL1,
    HV_VREG_ACC_CTRR_A_CTL_EL2,
    HV_VREG_CTRR_A_LWR_EL12,
    HV_VREG_CTRR_A_LWR_EL2,
    HV_VREG_CTRR_A_UPR_EL12,
    HV_VREG_CTRR_A_UPR_EL2,
    HV_VREG_CTRR_B_CTL_EL1,
    HV_VREG_ACC_CTRR_B_CTL_EL2,
    HV_VREG_CTRR_B_LWR_EL12,
    HV_VREG_CTRR_B_UPR_EL12,
    HV_VREG_CTRR_CTL_EL12,
    HV_VREG_CTRR_C_CTL_EL1,
    HV_VREG_CTRR_C_CTL_EL12,
    HV_VREG_ACC_CTRR_C_CTL_EL2,
    HV_VREG_CTRR_C_LWR_EL1,
    HV_VREG_CTRR_C_LWR_EL12,
    HV_VREG_ACC_CTRR_C_LWR_EL2,
    HV_VREG_CTRR_C_UPR_EL1,
    HV_VREG_CTRR_C_UPR_EL12,
    HV_VREG_ACC_CTRR_C_UPR_EL2,
    HV_VREG_CTRR_D_CTL_EL1,
    HV_VREG_CTRR_D_CTL_EL12,
    HV_VREG_ACC_CTRR_D_CTL_EL2,
    HV_VREG_CTRR_D_LWR_EL1,
    HV_VREG_CTRR_D_LWR_EL12,
    HV_VREG_CTRR_D_LWR_EL2,
    HV_VREG_ACC_CTRR_D_LWR_EL2,
    HV_VREG_CTRR_D_UPR_EL1,
    HV_VREG_CTRR_D_UPR_EL12,
    HV_VREG_CTRR_D_UPR_EL2,
    HV_VREG_ACC_CTRR_D_UPR_EL2,
    HV_VREG_CTRR_LOCK_EL12,
    HV_VREG_CTXR_A_CTL_EL1,
    HV_VREG_CTXR_A_CTL_EL12,
    HV_VREG_ACC_CTXR_A_CTL_EL2,
    HV_VREG_CTXR_A_LWR_EL1,
    HV_VREG_CTXR_A_LWR_EL12,
    HV_VREG_ACC_CTXR_A_LWR_EL2,
    HV_VREG_CTXR_A_UPR_EL1,
    HV_VREG_CTXR_A_UPR_EL12,
    HV_VREG_ACC_CTXR_A_UPR_EL2,
    HV_VREG_CTXR_B_CTL_EL1,
    HV_VREG_CTXR_B_CTL_EL12,
    HV_VREG_ACC_CTXR_B_CTL_EL2,
    HV_VREG_CTXR_B_LWR_EL1,
    HV_VREG_CTXR_B_LWR_EL12,
    HV_VREG_ACC_CTXR_B_LWR_EL2,
    HV_VREG_CTXR_B_UPR_EL1,
    HV_VREG_CTXR_B_UPR_EL12,
    HV_VREG_ACC_CTXR_B_UPR_EL2,
    HV_VREG_CTXR_C_CTL_EL1,
    HV_VREG_CTXR_C_CTL_EL12,
    HV_VREG_ACC_CTXR_C_CTL_EL2,
    HV_VREG_CTXR_C_LWR_EL1,
    HV_VREG_CTXR_C_LWR_EL12,
    HV_VREG_ACC_CTXR_C_LWR_EL2,
    HV_VREG_CTXR_C_UPR_EL1,
    HV_VREG_CTXR_C_UPR_EL12,
    HV_VREG_ACC_CTXR_C_UPR_EL2,
    HV_VREG_CTXR_D_CTL_EL1,
    HV_VREG_CTXR_D_CTL_EL12,
    HV_VREG_ACC_CTXR_D_CTL_EL2,
    HV_VREG_CTXR_D_LWR_EL1,
    HV_VREG_CTXR_D_LWR_EL12,
    HV_VREG_ACC_CTXR_D_LWR_EL2,
    HV_VREG_CTXR_D_UPR_EL1,
    HV_VREG_CTXR_D_UPR_EL12,
    HV_VREG_ACC_CTXR_D_UPR_EL2,
    HV_VREG_VMSA_LOCK_EL1,
    HV_VREG_VMSA_LOCK_EL12,

    /* PAC */
    HV_VREG_APCTL_EL1,
    HV_VREG_APCTL_EL12,
    HV_VREG_APDAKEYHI_EL12,
    HV_VREG_APDAKEYLO_EL12,
    HV_VREG_APDBKEYHI_EL12,
    HV_VREG_APDBKEYLO_EL12,
    HV_VREG_APGAKEYHI_EL12,
    HV_VREG_APGAKEYLO_EL12,
    HV_VREG_APIAKEYHI_EL12,
    HV_VREG_APIAKEYLO_EL12,
    HV_VREG_APIBKEYHI_EL12,
    HV_VREG_APIBKEYLO_EL12,
    HV_VREG_APSTS_EL1,
    HV_VREG_APSTS_EL12,
    HV_VREG_KERNKEYHI_EL1,
    HV_VREG_KERNKEYHI_EL12,
    HV_VREG_KERNKEYLO_EL1,
    HV_VREG_KERNKEYLO_EL12,
    HV_VREG_VMKEYHI_EL2,
    HV_VREG_VMKEYLO_EL2,

    /* AMX */
    HV_VREG_AMX_CONFIG_EL1,
    HV_VREG_AMX_CONFIG_EL12,
    HV_VREG_AMX_CTL_EL2,
    HV_VREG_AMX_STATE_EL12,

    /* Misc */
    HV_VREG_JCTL_EL0,
    HV_VREG_PMCR1_GL1,

    /* Unknown */
    HV_VREG_S2_1_C9_C8_0,
    HV_VREG_S2_4_C6_C1_6,
    HV_VREG_S3_1_C15_C0_3,
    HV_VREG_S3_1_C15_C13_4,
    HV_VREG_S3_1_C15_C1_3,
    HV_VREG_S3_1_C15_C1_6,
    HV_VREG_S3_1_C15_C2_3,
    HV_VREG_S3_1_C15_C7_2,
    HV_VREG_S3_1_C15_C7_4,
    HV_VREG_S3_1_C15_C9_4,
    HV_VREG_S3_2_C13_C8_2,
    HV_VREG_S3_4_C15_C0_1,
    HV_VREG_S3_4_C15_C10_0,
    HV_VREG_S3_4_C15_C10_1,
    HV_VREG_S3_4_C15_C10_2,
    HV_VREG_S3_4_C15_C10_3,
    HV_VREG_S3_4_C15_C10_7,
    HV_VREG_S3_4_C15_C12_0,
    HV_VREG_S3_4_C15_C12_6,
    HV_VREG_S3_4_C15_C13_6,
    HV_VREG_S3_4_C15_C13_7,
    HV_VREG_S3_4_C15_C14_0,
    HV_VREG_S3_4_C15_C14_1,
    HV_VREG_S3_4_C15_C14_2,
    HV_VREG_S3_4_C15_C14_3,
    HV_VREG_S3_4_C15_C15_1,
    HV_VREG_S3_4_C15_C15_2,
    HV_VREG_S3_4_C15_C15_4,
    HV_VREG_S3_4_C15_C15_5,
    HV_VREG_S3_4_C15_C4_1,
    HV_VREG_S3_4_C15_C4_3,
    HV_VREG_S3_4_C15_C4_4,
    HV_VREG_S3_4_C15_C9_6,
    HV_VREG_S3_4_C15_C9_7,
    HV_VREG_S3_4_C1_C2_5,
    HV_VREG_S3_5_C15_C11_2,
    HV_VREG_S3_5_C15_C3_6,
    HV_VREG_S3_5_C15_C3_7,
    HV_VREG_S3_5_C15_C6_2,
    HV_VREG_S3_6_C15_C0_4,
    HV_VREG_S3_6_C15_C0_5,
    HV_VREG_S3_6_C15_C12_7,
    HV_VREG_S3_6_C15_C1_1,
    HV_VREG_S3_6_C15_C8_5,
    HV_VREG_S3_7_C15_C1_3,
    HV_VREG_S3_7_C15_C3_3,
    HV_VREG_S3_7_C15_C5_0,
    HV_VREG_S3_7_C15_C5_3,
    HV_VREG_S3_7_C15_C7_3,
    HV_VREG_S3_7_C15_C9_3,
    HV_VREG_S3_7_C3_C14_1,

    HV_VREG_MAX,
};

/* ESR_GL1 = HV_GXF_ESR_GENTER | (imm & 0xf) on genter (EC 0x3f). */
#define HV_GXF_ESR_GENTER 0xfe010000

struct sprr_mirror {
    struct sprr_mirror *hnext; // sprr_wp_page::mirrors chain
    struct sprr_mirror *children;
    struct sprr_mirror *sibling;
    struct hv_sprr_shadow *owner;
    u64 *el, *gl;
    u64 ipa;
    u64 va_base;
    u32 nents; // < SPRR_PT_ENTRIES only for the top level
    u16 idx;
    u8 level;
};

struct sprr_wp_page {
    struct sprr_wp_page *hnext;
    struct sprr_mirror *mirrors;
    u64 ipa;
};

struct hv_sprr_shadow {
    u64 guest_ttbr;
    u64 *vector_tables[4]; /* pagetables used to map our exception vectors to the guest*/
    struct sprr_mirror *top;
    u64 perm_el0, perm_el1;
    u64 leaf[2][SPRR_N_INDICES]; // [guarded][guest PTE perm index] -> shadow leaf bits
    u64 active;                  // CPUs holding this shadow in cur[]
    u32 va_bits;
    u32 lru;
    u8 ttbr_idx;
};

struct hv_sprr_cpu {
    bool sprr_en, gxf_en;
    bool guarded;
    u64 apctl_el1, apctl_el12;
    u64 sctlr_pac;

    u64 gxf_enter, gxf_abort;
    u64 vbar_gl1, vbar_el1;
    u64 sprr_config;
    u64 sprr_perm_el0, sprr_perm_el1;
    u64 sprr_umprr;
    u64 sprr_pmprr, sprr_amrange;
    u64 sprr_pperm_sh1, sprr_pperm_sh2, sprr_pperm_sh3;
    u64 sprr_uperm_sh1, sprr_uperm_sh2, sprr_uperm_sh3;
    u64 tpidr_gl1;
    u64 aspsr_el1, aspsr_gl1;

    struct hv_sprr_exc_regs {
        u64 spsr, elr, esr, far, afsr1, sp;
    } el1, gl1;

    u64 guest_ttbr[2];
    struct hv_sprr_shadow *cur[2];

    u64 timer_deadline;
    u64 shadow[HV_VREG_MAX];
};

bool hv_hvc_dispatch(struct exc_info *ctx, u16 imm);
bool hv_sprr_handle_eret(struct exc_info *ctx);
bool hv_hvc_dispatch_unlocked(struct exc_info *ctx, u16 imm);
bool hv_sprr_handle_msr(struct exc_info *ctx, u64 reg, u32 rt, bool is_read);
bool hv_sprr_traps_tlbi(void);
bool hv_sprr_is_pt_page(u64 ipa);
bool hv_sprr_is_shadow_page(u64 ipa);
bool hv_sprr_is_commpage(u64 ipa);
void hv_sprr_commpage_updated(u64 ipa, u64 bytes);
void hv_sprr_pt_updated(struct exc_info *ctx, u64 ipa, u64 bytes);
void hv_sprr_pt_writer_check(struct exc_info *ctx, u64 ipa, u64 far);
void hv_sprr_init(void);
u64 hv_sprr_reserve_pool(u64 size);
void hv_sprr_init_secondary(int cpu);
bool hv_sprr_timer_pending(void);
void hv_sprr_timer_arm(void);

#endif

#endif
