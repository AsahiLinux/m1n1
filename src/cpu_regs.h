/* SPDX-License-Identifier: MIT */

#include "arm_cpu_regs.h"
#include "types.h"

/* ARM extensions */
#define ESR_EC_IMPDEF      0b111111
#define ESR_ISS_IMPDEF_MSR 0x20

#define SYS_IMP_APL_ACTLR_EL12 sys_reg(3, 6, 15, 14, 6)

/* HID registers */
#define SYS_IMP_APL_HID0                sys_reg(3, 0, 15, 0, 0)
#define HID0_FETCH_WIDTH_DISABLE        (1UL << 28)
#define HID0_CACHE_FUSION_DISABLE       (1UL << 36)
#define HID0_SAME_PG_POWER_OPTIMIZATION (1UL << 45)

#define SYS_IMP_APL_HID1 sys_reg(3, 0, 15, 1, 0)
#define HID1_TRAP_SMC    (1UL << 54)

#define SYS_IMP_APL_HID3                 sys_reg(3, 0, 15, 3, 0)
#define HID3_DEV_PCIE_THROTTLE_ENABLE    (1UL << 63)
#define HID3_DISABLE_ARBITER_FIX_BIF_CRD (1UL << 44)

#define SYS_IMP_APL_HID4                 sys_reg(3, 0, 15, 4, 0)
#define SYS_IMP_APL_EHID4                sys_reg(3, 0, 15, 4, 1)
#define HID4_DISABLE_DC_MVA              (1UL << 11)
#define HID4_DISABLE_DC_SW_L2_OPS        (1UL << 44)
#define HID4_STNT_COUNTER_THRESHOLD(x)   (((unsigned long)x) << 40)
#define HID4_STNT_COUNTER_THRESHOLD_MASK (3UL << 40)

#define SYS_IMP_APL_HID5           sys_reg(3, 0, 15, 5, 0)
#define HID5_DISABLE_FILL_2C_MERGE (1UL << 61)

#define SYS_IMP_APL_HID6             sys_reg(3, 0, 15, 6, 0)
#define HID6_UP_CRD_TKN_INIT_C2(x)   (((unsigned long)x) << 5)
#define HID6_UP_CRD_TKN_INIT_C2_MASK (0x1FUL << 5)

#define SYS_IMP_APL_HID7                                              sys_reg(3, 0, 15, 7, 0)
#define HID7_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_INVALID_AND_MP_VALID (1UL << 16)
#define HID7_FORCE_NONSPEC_IF_STEPPING                                (1UL << 20)
#define HID7_FORCE_NONSPEC_TARGET_TIMER_SEL(x)                        (((unsigned long)x) << 24)
#define HID7_FORCE_NONSPEC_TARGET_TIMER_SEL_MASK                      (3UL << 24)

#define SYS_IMP_APL_HID9                sys_reg(3, 0, 15, 9, 0)
#define HID9_TSO_ALLOW_DC_ZVA_WC        (1UL << 26)
#define HID9_TSO_SERIALIZE_VLD_MICROOPS (1UL << 29)
#define HID9_FIX_BUG_51667805           (1UL << 48)

#define SYS_IMP_APL_EHID9           sys_reg(3, 0, 15, 9, 1)
#define EHID9_DEV_THROTTLE_2_ENABLE (1UL << 5)

#define SYS_IMP_APL_EHID10              sys_reg(3, 0, 15, 10, 1)
#define HID10_FORCE_WAIT_STATE_DRAIN_UC (1UL << 32)
#define HID10_DISABLE_ZVA_TEMPORAL_TSO  (1UL << 49)

#define SYS_IMP_APL_HID11          sys_reg(3, 0, 15, 11, 0)
#define HID11_DISABLE_LD_NT_WIDGET (1UL << 59)

#define SYS_IMP_APL_HID13     sys_reg(3, 0, 15, 14, 0)
#define HID13_PRE_CYCLES(x)   (((unsigned long)x) << 14)
#define HID13_PRE_CYCLES_MASK (0xFUL << 14)

#define SYS_IMP_APL_HID16         sys_reg(3, 0, 15, 15, 2)
#define HID16_SPAREBIT0           (1UL << 56)
#define HID16_SPAREBIT3           (1UL << 59)
#define HID16_ENABLE_MPX_PICK_45  (1UL << 61)
#define HID16_ENABLE_MP_CYCLONE_7 (1UL << 62)

#define SYS_IMP_APL_HID18             sys_reg(3, 0, 15, 11, 2)
#define HID18_HVC_SPECULATION_DISABLE (1UL << 14)

#define SYS_IMP_APL_EHID20                                            sys_reg(3, 0, 15, 1, 2)
#define EHID20_TRAP_SMC                                               (1UL << 8)
#define EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER          (1UL << 15)
#define EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER (1UL << 16)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(x)                    (((unsigned long)x) << 21)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK                  (3UL << 21)

#define SYS_IMP_APL_HID21             sys_reg(3, 0, 15, 1, 3)
#define HID21_ENABLE_LDREX_FILL_REPLY (1UL << 19)

#define SYS_IMP_APL_PMCR0 sys_reg(3, 1, 15, 0, 0)
#define PMCR0_IMODE_OFF   (0 << 8)
#define PMCR0_IMODE_PMI   (1 << 8)
#define PMCR0_IMODE_AIC   (2 << 8)
#define PMCR0_IMODE_HALT  (3 << 8)
#define PMCR0_IMODE_FIQ   (4 << 8)
#define PMCR0_IMODE_MASK  (7 << 8)
#define PMCR0_IACT        (BIT(11))

#define SYS_IMP_APL_LSU_ERR_STS   sys_reg(3, 3, 15, 0, 0)
#define SYS_IMP_APL_E_LSU_ERR_STS sys_reg(3, 3, 15, 2, 0)

#define SYS_IMP_APL_L2C_ERR_STS sys_reg(3, 3, 15, 8, 0)

#define L2C_ERR_STS_RECURSIVE_FAULT (1UL << 1)
#define L2C_ERR_STS_ACCESS_FAULT    (1UL << 7)
#define L2C_ERR_STS_ENABLE_W1C      (1UL << 56)

#define SYS_IMP_APL_L2C_ERR_ADR sys_reg(3, 3, 15, 9, 0)
#define SYS_IMP_APL_L2C_ERR_INF sys_reg(3, 3, 15, 10, 0)

#define SYS_IMP_APL_FED_ERR_STS   sys_reg(3, 4, 15, 0, 0)
#define SYS_IMP_APL_E_FED_ERR_STS sys_reg(3, 4, 15, 0, 2)

#define SYS_IMP_APL_MMU_ERR_STS   sys_reg(3, 6, 15, 0, 0)
#define SYS_IMP_APL_E_MMU_ERR_STS sys_reg(3, 6, 15, 2, 0)

/* ACC/CYC Registers */
#define SYS_IMP_APL_ACC_CFG   sys_reg(3, 5, 15, 4, 0)
#define ACC_CFG_BP_SLEEP(x)   (((unsigned long)x) << 2)
#define ACC_CFG_BP_SLEEP_MASK (3UL << 2)

#define SYS_IMP_APL_CYC_OVRD   sys_reg(3, 5, 15, 5, 0)
#define CYC_OVRD_FIQ_MODE(x)   (((unsigned long)x) << 20)
#define CYC_OVRD_FIQ_MODE_MASK (3UL << 20)
#define CYC_OVRD_IRQ_MODE(x)   (((unsigned long)x) << 22)
#define CYC_OVRD_IRQ_MODE_MASK (3UL << 22)
#define CYC_OVRD_WFI_MODE(x)   (((unsigned long)x) << 24)
#define CYC_OVRD_WFI_MODE_MASK (3UL << 20)

#define SYS_IMP_APL_UPMCR0 sys_reg(3, 7, 15, 0, 4)
#define UPMCR0_IMODE_OFF   (0 << 16)
#define UPMCR0_IMODE_AIC   (2 << 16)
#define UPMCR0_IMODE_HALT  (3 << 16)
#define UPMCR0_IMODE_FIQ   (4 << 16)
#define UPMCR0_IMODE_MASK  (7 << 16)

#define SYS_IMP_APL_UPMSR sys_reg(3, 7, 15, 6, 4)
#define UPMSR_IACT        (BIT(0))

/* SPRR and GXF registers */
#define SYS_IMP_APL_SPRR_CONFIG_EL1  sys_reg(3, 6, 15, 1, 0)
#define SPRR_CONFIG_EN               BIT(0)
#define SPRR_CONFIG_LOCK_CONFIG      BIT(1)
#define SPRR_CONFIG_LOCK_PERM        BIT(4)
#define SPRR_CONFIG_LOCK_KERNEL_PERM BIT(5)

#define SYS_IMP_APL_GXF_CONFIG_EL1 sys_reg(3, 6, 15, 1, 2)
#define GXF_CONFIG_EN              BIT(0)

#define SYS_IMP_APL_GXF_STATUS_EL1 sys_reg(3, 6, 15, 8, 0)
#define GXF_STATUS_GUARDED         BIT(0)

#define SYS_IMP_APL_GXF_ABORT_EL1 sys_reg(3, 6, 15, 8, 2)
#define SYS_IMP_APL_GXF_ENTER_EL1 sys_reg(3, 6, 15, 8, 1)

#define SYS_IMP_APL_GXF_ABORT_EL12 sys_reg(3, 6, 15, 15, 3)
#define SYS_IMP_APL_GXF_ENTER_EL12 sys_reg(3, 6, 15, 15, 2)

#define SYS_IMP_APL_SPRR_PERM_EL0 sys_reg(3, 6, 15, 1, 5)
#define SYS_IMP_APL_SPRR_PERM_EL1 sys_reg(3, 6, 15, 1, 6)

#define SYS_IMP_APL_TPIDR_GL1 sys_reg(3, 6, 15, 10, 1)
#define SYS_IMP_APL_VBAR_GL1  sys_reg(3, 6, 15, 10, 2)
#define SYS_IMP_APL_SPSR_GL1  sys_reg(3, 6, 15, 10, 3)
#define SYS_IMP_APL_ASPSR_GL1 sys_reg(3, 6, 15, 10, 4)
#define SYS_IMP_APL_ESR_GL1   sys_reg(3, 6, 15, 10, 5)
#define SYS_IMP_APL_ELR_GL1   sys_reg(3, 6, 15, 10, 6)
#define SYS_IMP_APL_FAR_GL1   sys_reg(3, 6, 15, 10, 7)

#define SYS_IMP_APL_VBAR_GL12 sys_reg(3, 6, 15, 9, 2)
#define SYS_IMP_APL_SP_GL12   sys_reg(3, 6, 15, 10, 0)

/* VM registers */
#define SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2 sys_reg(3, 5, 15, 1, 3)
#define VM_TMR_FIQ_ENA_ENA_V           BIT(0)
#define VM_TMR_FIQ_ENA_ENA_P           BIT(1)

/* IPI registers */
#define SYS_IMP_APL_IPI_RR_LOCAL_EL1  sys_reg(3, 5, 15, 0, 0)
#define SYS_IMP_APL_IPI_RR_GLOBAL_EL1 sys_reg(3, 5, 15, 0, 1)

#define SYS_IMP_APL_IPI_SR_EL1 sys_reg(3, 5, 15, 1, 1)
#define IPI_SR_PENDING         BIT(0)

#define SYS_IMP_APL_IPI_CR_EL1 sys_reg(3, 5, 15, 3, 1)
