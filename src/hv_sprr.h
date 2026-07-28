/* SPDX-License-Identifier: MIT */

#ifndef HV_SPRR_H
#define HV_SPRR_H

#include "exception.h"
#include "types.h"

#define HV_HVC_GENTER_BASE 0x1420
#define HV_HVC_GENTER_MASK GENMASK(15, 4)
#define HV_HVC_GENTER_IMM  GENMASK(3, 0)
#define HV_HVC_GEXIT       0x1400

#define HV_HVC_SYSREG_FLAG BIT(15)
#define HV_HVC_SYSREG_VREG GENMASK(13, 6) /* enum hv_vreg */
#define HV_HVC_SYSREG_DIR  BIT(5)         /* 1 = MRS */
#define HV_HVC_SYSREG_RT   GENMASK(4, 0)

#define SPRR_N_INDICES 16

/* Must be kept in sync with HV_VREGS in proxyclient/m1n1/hv/sprr.py. */
enum hv_vreg {
    HV_VREG_SPRR_CONFIG_EL1 = 0,
    HV_VREG_GXF_CONFIG_EL1,
    HV_VREG_GXF_STATUS_EL1,
    HV_VREG_GXF_ENTER_EL1,
    HV_VREG_GXF_ABORT_EL1,
    HV_VREG_SPRR_PERM_EL0,
    HV_VREG_SPRR_PERM_EL1,
    HV_VREG_TPIDR_GL1,
    HV_VREG_VBAR_GL1,
    HV_VREG_SPSR_GL1,
    HV_VREG_ASPSR_GL1,
    HV_VREG_ESR_GL1,
    HV_VREG_ELR_GL1,
    HV_VREG_FAR_GL1,
    HV_VREG_AFSR1_GL1,
    HV_VREG_ASPSR_EL1,
    HV_VREG_SPRR_UMPRR_EL1,
    HV_VREG_TTBR0_EL1,
    HV_VREG_TTBR1_EL1,
    HV_VREG_TCR_EL1,
    HV_VREG_SCTLR_EL1,
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

    u64 gxf_enter, gxf_abort;
    u64 vbar_gl1;
    u64 sprr_config;
    u64 sprr_perm_el0, sprr_perm_el1;
    u64 sprr_umprr;
    u64 tpidr_gl1;
    u64 elr_gl1, spsr_gl1;
    u64 aspsr_el1, aspsr_gl1;

    // inactive world's banked regs: genter/gexit swap these with the real _EL1 ones.
    // required since these are updated by hardware on any exception so we can't just
    // patch all msr/mrs with hvc like for the rest
    struct hv_world_regs {
        u64 sp_el1;
        u64 vbar;
        u64 spsr, elr, esr, far, afsr1;
    } bank;

    u64 guest_ttbr[2];
    struct hv_sprr_shadow *cur[2];

    u64 n_genter, n_gexit;
};

extern bool hv_sprr_active;
void hv_sprr_set_active(bool active);

bool hv_hvc_dispatch(struct exc_info *ctx, u16 imm);
bool hv_sprr_handle_msr(struct exc_info *ctx, u64 reg, u32 rt, bool is_read);
bool hv_sprr_traps_tlbi(void);
bool hv_sprr_is_pt_page(u64 ipa);
bool hv_sprr_is_shadow_page(u64 ipa);
void hv_sprr_pt_updated(struct exc_info *ctx, u64 ipa, u64 bytes);
void hv_sprr_pt_writer_check(struct exc_info *ctx, u64 ipa, u64 far);

#endif
