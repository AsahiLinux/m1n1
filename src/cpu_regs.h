/* SPDX-License-Identifier: MIT */

#include "arm_cpu_regs.h"
#include "types.h"

/* ARM extensions */
#define ESR_EC_IMPDEF      0b111111
#define ESR_ISS_IMPDEF_MSR 0x20

#define SYS_IMP_APL_ACTLR_EL12 sys_reg(3, 6, 15, 14, 6)

#define SYS_IMP_APL_AMX_CTL_EL1  sys_reg(3, 4, 15, 1, 4)
#define SYS_IMP_APL_AMX_CTL_EL2  sys_reg(3, 4, 15, 4, 7)
#define SYS_IMP_APL_AMX_CTL_EL12 sys_reg(3, 4, 15, 4, 6)

#define AMX_CTL_EN     BIT(63)
#define AMX_CTL_EN_EL1 BIT(62)

#define SYS_IMP_APL_CNTVCT_ALIAS_EL0 sys_reg(3, 4, 15, 10, 6)

/* HID registers */
#define SYS_IMP_APL_HID0                sys_reg(3, 0, 15, 0, 0)
#define HID0_FETCH_WIDTH_DISABLE        BIT(28)
#define HID0_CACHE_FUSION_DISABLE       BIT(36)
#define HID0_SAME_PG_POWER_OPTIMIZATION BIT(45)

#define SYS_IMP_APL_EHID0 sys_reg(3, 0, 15, 0, 1)
#define EHID0_BLI_UNK32   BIT(32)

#define SYS_IMP_APL_HID1                    sys_reg(3, 0, 15, 1, 0)
#define HID1_TRAP_SMC                       BIT(54)
#define HID1_ENABLE_MDSB_STALL_PIPELINE_ECO BIT(58)
#define HID1_ENABLE_BR_KILL_LIMIT           BIT(60)

#define HID1_ZCL_RF_RESTART_THRESHOLD_MASK    GENMASK(23, 22)
#define HID1_ZCL_RF_RESTART_THRESHOLD(x)      (((unsigned long)x) << 22)
#define HID1_ZCL_RF_MISPREDICT_THRESHOLD_MASK GENMASK(43, 42)
#define HID1_ZCL_RF_MISPREDICT_THRESHOLD(x)   (((unsigned long)x) << 42)

#define SYS_IMP_APL_HID3                  sys_reg(3, 0, 15, 3, 0)
#define HID3_DISABLE_ARBITER_FIX_BIF_CRD  BIT(44)
#define HID3_DEV_PCIE_THROTTLE_LIMIT_MASK GENMASK(62, 57)
#define HID3_DEV_PCIE_THROTTLE_LIMIT(x)   (((unsigned long)x) << 57)
#define HID3_DEV_PCIE_THROTTLE_ENABLE     BIT(63)

#define SYS_IMP_APL_HID4                         sys_reg(3, 0, 15, 4, 0)
#define SYS_IMP_APL_EHID4                        sys_reg(3, 0, 15, 4, 1)
#define HID4_DISABLE_DC_MVA                      BIT(11)
#define HID4_DISABLE_DC_SW_L2_OPS                BIT(44)
#define HID4_STNT_COUNTER_THRESHOLD(x)           (((unsigned long)x) << 40)
#define HID4_STNT_COUNTER_THRESHOLD_MASK         (3UL << 40)
#define HID4_ENABLE_LFSR_STALL_LOAD_PIPE_2_ISSUE BIT(49)
#define HID4_ENABLE_LFSR_STALL_STQ_REPLAY        BIT(53)

#define SYS_IMP_APL_HID5           sys_reg(3, 0, 15, 5, 0)
#define HID5_BLZ_UNK_19_18_MASK    GENMASK(19, 18)
#define HID5_BLZ_UNK18             BIT(18)
#define HID5_BLZ_UNK19             BIT(19)
#define HID5_DISABLE_FILL_2C_MERGE BIT(61)

#define SYS_IMP_APL_HID6             sys_reg(3, 0, 15, 6, 0)
#define HID6_UP_CRD_TKN_INIT_C2(x)   (((unsigned long)x) << 5)
#define HID6_UP_CRD_TKN_INIT_C2_MASK (0x1FUL << 5)

#define SYS_IMP_APL_HID7                                              sys_reg(3, 0, 15, 7, 0)
#define HID7_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_INVALID_AND_MP_VALID BIT(16)
#define HID7_FORCE_NONSPEC_IF_STEPPING                                BIT(20)
#define HID7_FORCE_NONSPEC_TARGET_TIMER_SEL(x)                        (((unsigned long)x) << 24)
#define HID7_FORCE_NONSPEC_TARGET_TIMER_SEL_MASK                      (3UL << 24)

#define SYS_IMP_APL_HID9                sys_reg(3, 0, 15, 9, 0)
#define HID9_AVL_UNK17                  BIT(17)
#define HID9_TSO_ALLOW_DC_ZVA_WC        BIT(26)
#define HID9_TSO_SERIALIZE_VLD_MICROOPS BIT(29)
#define HID9_FIX_BUG_51667805           BIT(48)
#define HID9_FIX_BUG_55719865           BIT(55)

#define SYS_IMP_APL_EHID9               sys_reg(3, 0, 15, 9, 1)
#define EHID9_DEV_2_THROTTLE_ENABLE     BIT(5)
#define EHID9_DEV_2_THROTTLE_LIMIT_MASK GENMASK(11, 6)
#define EHID9_DEV_2_THROTTLE_LIMIT(x)   (((unsigned long)x) << 6)

#define SYS_IMP_APL_HID10               sys_reg(3, 0, 15, 10, 0)
#define SYS_IMP_APL_EHID10              sys_reg(3, 0, 15, 10, 1)
#define HID10_FORCE_WAIT_STATE_DRAIN_UC BIT(32)
#define HID10_DISABLE_ZVA_TEMPORAL_TSO  BIT(49)

#define SYS_IMP_APL_HID11            sys_reg(3, 0, 15, 11, 0)
#define HID11_ENABLE_FIX_UC_55719865 BIT(15)
#define HID11_DISABLE_LD_NT_WIDGET   BIT(59)

#define SYS_IMP_APL_HID13           sys_reg(3, 0, 15, 14, 0)
#define HID13_POST_OFF_CYCLES(x)    (((unsigned long)x))
#define HID13_POST_OFF_CYCLES_MASK  GENMASK(6, 0)
#define HID13_POST_ON_CYCLES(x)     (((unsigned long)x) << 7)
#define HID13_POST_ON_CYCLES_MASK   GENMASK(13, 7)
#define HID13_PRE_CYCLES(x)         (((unsigned long)x) << 14)
#define HID13_PRE_CYCLES_MASK       GENMASK(17, 14)
#define HID13_GROUP0_FF1_DELAY(x)   (((unsigned long)x) << 26)
#define HID13_GROUP0_FF1_DELAY_MASK GENMASK(29, 26)
#define HID13_GROUP0_FF2_DELAY(x)   (((unsigned long)x) << 30)
#define HID13_GROUP0_FF2_DELAY_MASK GENMASK(33, 30)
#define HID13_GROUP0_FF3_DELAY(x)   (((unsigned long)x) << 34)
#define HID13_GROUP0_FF3_DELAY_MASK GENMASK(37, 34)
#define HID13_GROUP0_FF4_DELAY(x)   (((unsigned long)x) << 38)
#define HID13_GROUP0_FF4_DELAY_MASK GENMASK(41, 38)
#define HID13_GROUP0_FF5_DELAY(x)   (((unsigned long)x) << 42)
#define HID13_GROUP0_FF5_DELAY_MASK GENMASK(45, 42)
#define HID13_GROUP0_FF6_DELAY(x)   (((unsigned long)x) << 46)
#define HID13_GROUP0_FF6_DELAY_MASK GENMASK(49, 46)
#define HID13_GROUP0_FF7_DELAY(x)   (((unsigned long)x) << 50)
#define HID13_GROUP0_FF7_DELAY_MASK GENMASK(53, 50)
#define HID13_RESET_CYCLES(x)       (((unsigned long)x) << 60)
#define HID13_RESET_CYCLES_MASK     (0xFUL << 60)

#define SYS_IMP_APL_HID16         sys_reg(3, 0, 15, 15, 2)
#define HID16_AVL_UNK12           BIT(12)
#define HID16_SPAREBIT0           BIT(56)
#define HID16_SPAREBIT3           BIT(59)
#define HID16_ENABLE_MPX_PICK_45  BIT(61)
#define HID16_ENABLE_MP_CYCLONE_7 BIT(62)

#define SYS_IMP_APL_HID18             sys_reg(3, 0, 15, 11, 2)
#define HID18_HVC_SPECULATION_DISABLE BIT(14)
#define HID18_AVL_UNK27               BIT(27)
#define HID18_AVL_UNK29               BIT(29)
#define HID18_SPAREBIT7               BIT(39)
#define HID18_SPAREBIT17              BIT(49)

#define SYS_IMP_APL_EHID18 sys_reg(3, 0, 15, 11, 3)
#define EHID18_BLZ_UNK34   BIT(34)

#define SYS_IMP_APL_EHID20                                            sys_reg(3, 0, 15, 1, 2)
#define EHID20_TRAP_SMC                                               BIT(8)
#define EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER          BIT(15)
#define EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER BIT(16)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(x)                    (((unsigned long)x) << 21)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK                  (3UL << 21)

#define SYS_IMP_APL_HID21                            sys_reg(3, 0, 15, 1, 3)
#define HID21_ENABLE_LDREX_FILL_REPLY                BIT(19)
#define HID21_LDQ_RTR_WAIT_FOR_OLD_ST_REL_COMPLETION BIT(33)
#define HID21_DISABLE_CDP_REPLY_PURGED_TRANSACTION   BIT(34)
#define HID21_AVL_UNK52                              BIT(52)

#define SYS_IMP_APL_HID26        sys_reg(3, 0, 15, 0, 3)
#define HID26_GROUP1_OFFSET(x)   (((unsigned long)x) << 0)
#define HID26_GROUP1_OFFSET_MASK (0xffUL << 0)
#define HID26_GROUP2_OFFSET(x)   (((unsigned long)x) << 36)
#define HID26_GROUP2_OFFSET_MASK (0xffUL << 36)

#define SYS_IMP_APL_HID27        sys_reg(3, 0, 15, 0, 4)
#define HID27_GROUP3_OFFSET(x)   (((unsigned long)x) << 8)
#define HID27_GROUP3_OFFSET_MASK (0xffUL << 8)

#define SYS_IMP_APL_PMCR0 sys_reg(3, 1, 15, 0, 0)
#define PMCR0_CNT_EN_MASK (MASK(8) | GENMASK(33, 32))
#define PMCR0_IMODE_OFF   (0 << 8)
#define PMCR0_IMODE_PMI   (1 << 8)
#define PMCR0_IMODE_AIC   (2 << 8)
#define PMCR0_IMODE_HALT  (3 << 8)
#define PMCR0_IMODE_FIQ   (4 << 8)
#define PMCR0_IMODE_MASK  (7 << 8)
#define PMCR0_IACT        (BIT(11))
#define PMCR0_PMI_SHIFT   12
#define PMCR0_CNT_MASK    (PMCR0_CNT_EN_MASK | (PMCR0_CNT_EN_MASK << PMCR0_PMI_SHIFT))

#define SYS_IMP_APL_PMCR1 sys_reg(3, 1, 15, 1, 0)
#define SYS_IMP_APL_PMCR2 sys_reg(3, 1, 15, 2, 0)
#define SYS_IMP_APL_PMCR3 sys_reg(3, 1, 15, 3, 0)
#define SYS_IMP_APL_PMCR4 sys_reg(3, 1, 15, 4, 0)

#define SYS_IMP_APL_PMESR0 sys_reg(3, 1, 15, 5, 0)
#define SYS_IMP_APL_PMESR1 sys_reg(3, 1, 15, 6, 0)

#define SYS_IMP_APL_PMSR sys_reg(3, 1, 15, 13, 0)

#define SYS_IMP_APL_PMC0 sys_reg(3, 2, 15, 0, 0)
#define SYS_IMP_APL_PMC1 sys_reg(3, 2, 15, 1, 0)
#define SYS_IMP_APL_PMC2 sys_reg(3, 2, 15, 2, 0)
#define SYS_IMP_APL_PMC3 sys_reg(3, 2, 15, 3, 0)
#define SYS_IMP_APL_PMC4 sys_reg(3, 2, 15, 4, 0)
#define SYS_IMP_APL_PMC5 sys_reg(3, 2, 15, 5, 0)
#define SYS_IMP_APL_PMC6 sys_reg(3, 2, 15, 6, 0)
#define SYS_IMP_APL_PMC7 sys_reg(3, 2, 15, 7, 0)
#define SYS_IMP_APL_PMC8 sys_reg(3, 2, 15, 9, 0)
#define SYS_IMP_APL_PMC9 sys_reg(3, 2, 15, 10, 0)

#define SYS_IMP_APL_LSU_ERR_STS   sys_reg(3, 3, 15, 0, 0)
#define SYS_IMP_APL_E_LSU_ERR_STS sys_reg(3, 3, 15, 2, 0)

#define SYS_IMP_APL_L2C_ERR_STS sys_reg(3, 3, 15, 8, 0)

#define L2C_ERR_STS_RECURSIVE_FAULT BIT(1)
#define L2C_ERR_STS_ACCESS_FAULT    BIT(7)
#define L2C_ERR_STS_ENABLE_W1C      BIT(56)

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

#define SYS_IMP_APL_CYC_OVRD     sys_reg(3, 5, 15, 5, 0)
#define CYC_OVRD_FIQ_MODE(x)     (((unsigned long)x) << 20)
#define CYC_OVRD_FIQ_MODE_MASK   (3UL << 20)
#define CYC_OVRD_IRQ_MODE(x)     (((unsigned long)x) << 22)
#define CYC_OVRD_IRQ_MODE_MASK   (3UL << 22)
#define CYC_OVRD_WFI_MODE(x)     (((unsigned long)x) << 24)
#define CYC_OVRD_WFI_MODE_MASK   (3UL << 24)
#define CYC_OVRD_DISABLE_WFI_RET BIT(0)

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

#define SYS_IMP_APL_SPRR_PERM_EL0  sys_reg(3, 6, 15, 1, 5)
#define SYS_IMP_APL_SPRR_PERM_EL1  sys_reg(3, 6, 15, 1, 6)
#define SYS_IMP_APL_SPRR_PERM_EL02 sys_reg(3, 4, 15, 5, 2)
#define SYS_IMP_APL_SPRR_PERM_EL12 sys_reg(3, 6, 15, 15, 7)

#define SYS_IMP_APL_TPIDR_GL1 sys_reg(3, 6, 15, 10, 1)
#define SYS_IMP_APL_VBAR_GL1  sys_reg(3, 6, 15, 10, 2)
#define SYS_IMP_APL_SPSR_GL1  sys_reg(3, 6, 15, 10, 3)
#define SYS_IMP_APL_ASPSR_GL1 sys_reg(3, 6, 15, 10, 4)
#define SYS_IMP_APL_ESR_GL1   sys_reg(3, 6, 15, 10, 5)
#define SYS_IMP_APL_ELR_GL1   sys_reg(3, 6, 15, 10, 6)
#define SYS_IMP_APL_FAR_GL1   sys_reg(3, 6, 15, 10, 7)

#define SYS_IMP_APL_VBAR_GL12  sys_reg(3, 6, 15, 9, 2)
#define SYS_IMP_APL_SPSR_GL12  sys_reg(3, 6, 15, 9, 3)
#define SYS_IMP_APL_ASPSR_GL12 sys_reg(3, 6, 15, 9, 4)
#define SYS_IMP_APL_ESR_GL12   sys_reg(3, 6, 15, 9, 5)
#define SYS_IMP_APL_ELR_GL12   sys_reg(3, 6, 15, 9, 6)
#define SYS_IMP_APL_SP_GL12    sys_reg(3, 6, 15, 10, 0)

#define SYS_IMP_APL_AFSR1_GL1 sys_reg(3, 6, 15, 0, 1)

/* PAuth registers */
#define SYS_IMP_APL_APVMKEYLO_EL2 sys_reg(3, 6, 15, 14, 4)
#define SYS_IMP_APL_APVMKEYHI_EL2 sys_reg(3, 6, 15, 14, 5)
#define SYS_IMP_APL_APSTS_EL12    sys_reg(3, 6, 15, 14, 7)

#define SYS_IMP_APL_APCTL_EL1  sys_reg(3, 4, 15, 0, 4)
#define SYS_IMP_APL_APCTL_EL2  sys_reg(3, 6, 15, 12, 2)
#define SYS_IMP_APL_APCTL_EL12 sys_reg(3, 6, 15, 15, 0)

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
