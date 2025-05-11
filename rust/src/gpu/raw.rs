// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! GPU initialization / global structures

use versions::versions;

use super::types::*;
use crate::float::F32;

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataShared1 {
    pub(crate) table: Array<16, i32>,
    pub(crate) unk_44: Array<0x60, u8>,
    pub(crate) unk_a4: u32,
    pub(crate) unk_a8: u32,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataShared2Curve {
    pub(crate) unk_0: u32,
    pub(crate) unk_4: u32,
    pub(crate) t1: Array<16, u16>,
    pub(crate) t2: Array<16, i16>,
    pub(crate) t3: Array<8, Array<16, i32>>,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataShared2G14 {
    pub(crate) unk_0: Array<5, u32>,
    pub(crate) unk_14: u32,
    pub(crate) unk_18: Array<8, u32>,
    pub(crate) curve1: HwDataShared2Curve,
    pub(crate) curve2: HwDataShared2Curve,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataShared2 {
    pub(crate) table: Array<10, i32>,
    pub(crate) unk_28: Array<0x10, u8>,
    pub(crate) g14: HwDataShared2G14,
    pub(crate) unk_500: u32,
    pub(crate) unk_504: u32,
    pub(crate) unk_508: u32,
    pub(crate) unk_50c: u32,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataShared3 {
    pub(crate) unk_0: u32,
    pub(crate) unk_4: u32,
    pub(crate) unk_8: u32,
    pub(crate) table: Array<16, u32>,
    pub(crate) unk_4c: u32,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataA130Extra {
    pub(crate) unk_0: Array<0x38, u8>,
    pub(crate) unk_38: u32,
    pub(crate) unk_3c: u32,
    pub(crate) gpu_se_inactive_threshold: u32,
    pub(crate) unk_44: u32,
    pub(crate) gpu_se_engagement_criteria: i32,
    pub(crate) gpu_se_reset_criteria: u32,
    pub(crate) unk_50: u32,
    pub(crate) unk_54: u32,
    pub(crate) unk_58: u32,
    pub(crate) unk_5c: u32,
    pub(crate) gpu_se_filter_a_neg: F32,
    pub(crate) gpu_se_filter_1_a_neg: F32,
    pub(crate) gpu_se_filter_a: F32,
    pub(crate) gpu_se_filter_1_a: F32,
    pub(crate) gpu_se_ki_dt: F32,
    pub(crate) gpu_se_ki_1_dt: F32,
    pub(crate) unk_78: F32,
    pub(crate) unk_7c: F32,
    pub(crate) gpu_se_kp: F32,
    pub(crate) gpu_se_kp_1: F32,
    pub(crate) unk_88: u32,
    pub(crate) unk_8c: u32,
    pub(crate) max_pstate_scaled_1: u32,
    pub(crate) unk_94: u32,
    pub(crate) unk_98: u32,
    pub(crate) unk_9c: F32,
    pub(crate) unk_a0: u32,
    pub(crate) unk_a4: u32,
    pub(crate) gpu_se_filter_time_constant_ms: u32,
    pub(crate) gpu_se_filter_time_constant_1_ms: u32,
    pub(crate) gpu_se_filter_time_constant_clks: U64,
    pub(crate) gpu_se_filter_time_constant_1_clks: U64,
    pub(crate) unk_c0: u32,
    pub(crate) unk_c4: F32,
    pub(crate) unk_c8: Array<0x4c, u8>,
    pub(crate) unk_114: F32,
    pub(crate) unk_118: u32,
    pub(crate) unk_11c: u32,
    pub(crate) unk_120: u32,
    pub(crate) unk_124: u32,
    pub(crate) max_pstate_scaled_2: u32,
    pub(crate) unk_12c: Array<0x8c, u8>,
}

#[derive(Default)]
#[repr(C)]
pub(crate) struct T81xxData {
    pub(crate) unk_d8c: u32,
    pub(crate) unk_d90: u32,
    pub(crate) unk_d94: u32,
    pub(crate) unk_d98: u32,
    pub(crate) unk_d9c: F32,
    pub(crate) unk_da0: u32,
    pub(crate) unk_da4: F32,
    pub(crate) unk_da8: u32,
    pub(crate) unk_dac: F32,
    pub(crate) unk_db0: u32,
    pub(crate) unk_db4: u32,
    pub(crate) unk_db8: F32,
    pub(crate) unk_dbc: F32,
    pub(crate) unk_dc0: u32,
    pub(crate) unk_dc4: u32,
    pub(crate) unk_dc8: u32,
    pub(crate) max_pstate_scaled: u32,
}

#[versions(AGX)]
const MAX_CORES_PER_CLUSTER: usize = {
    #[ver(G >= G14X)]
    {
        16
    }
    #[ver(G < G14X)]
    {
        8
    }
};

#[versions(AGX)]
#[derive(Default, Copy, Clone)]
#[repr(C)]
pub(crate) struct PowerZone {
    pub(crate) val: F32,
    pub(crate) target: u32,
    pub(crate) target_off: u32,
    pub(crate) filter_tc_x4: u32,
    pub(crate) filter_tc_xperiod: u32,
    #[ver(V >= V13_0B4)]
    pub(crate) unk_10: u32,
    #[ver(V >= V13_0B4)]
    pub(crate) unk_14: u32,
    pub(crate) filter_a_neg: F32,
    pub(crate) filter_a: F32,
    pub(crate) pad: u32,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct AuxLeakCoef {
    pub(crate) afr_1: Array<2, F32>,
    pub(crate) cs_1: Array<2, F32>,
    pub(crate) afr_2: Array<2, F32>,
    pub(crate) cs_2: Array<2, F32>,
}

#[versions(AGX)]
#[repr(C)]
#[derive(Default)]
pub(crate) struct HwDataA {
    pub(crate) unk_0: u32,
    pub(crate) clocks_per_period: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) clocks_per_period_2: u32,

    pub(crate) unk_8: u32,
    pub(crate) pwr_status: u32,
    pub(crate) unk_10: F32,
    pub(crate) unk_14: u32,
    pub(crate) unk_18: u32,
    pub(crate) unk_1c: u32,
    pub(crate) unk_20: u32,
    pub(crate) unk_24: u32,
    pub(crate) actual_pstate: u32,
    pub(crate) tgt_pstate: u32,
    pub(crate) unk_30: u32,
    pub(crate) cur_pstate: u32,
    pub(crate) unk_38: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_3c_0: u32,

    pub(crate) base_pstate_scaled: u32,
    pub(crate) unk_40: u32,
    pub(crate) max_pstate_scaled: u32,
    pub(crate) unk_48: u32,
    pub(crate) min_pstate_scaled: u32,
    pub(crate) freq_mhz: F32,
    pub(crate) unk_54: Array<0x20, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_74_0: u32,

    pub(crate) sram_k: Array<0x10, F32>,
    pub(crate) unk_b4: Array<0x100, u8>,
    pub(crate) unk_1b4: u32,
    pub(crate) temp_c: u32,
    pub(crate) avg_power_mw: u32,
    pub(crate) update_ts: U64,
    pub(crate) unk_1c8: u32,
    pub(crate) unk_1cc: Array<0x478, u8>,
    pub(crate) pad_644: Pad<0x8>,
    pub(crate) unk_64c: u32,
    pub(crate) unk_650: u32,
    pub(crate) pad_654: u32,
    pub(crate) pwr_filter_a_neg: F32,
    pub(crate) pad_65c: u32,
    pub(crate) pwr_filter_a: F32,
    pub(crate) pad_664: u32,
    pub(crate) pwr_integral_gain: F32,
    pub(crate) pad_66c: u32,
    pub(crate) pwr_integral_min_clamp: F32,
    pub(crate) max_power_1: F32,
    pub(crate) pwr_proportional_gain: F32,
    pub(crate) pad_67c: u32,
    pub(crate) pwr_pstate_related_k: F32,
    pub(crate) pwr_pstate_max_dc_offset: i32,
    pub(crate) unk_688: u32,
    pub(crate) max_pstate_scaled_2: u32,
    pub(crate) pad_690: u32,
    pub(crate) unk_694: u32,
    pub(crate) max_power_2: u32,
    pub(crate) pad_69c: Pad<0x18>,
    pub(crate) unk_6b4: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_6b8_0: Array<0x10, u8>,

    pub(crate) max_pstate_scaled_3: u32,
    pub(crate) unk_6bc: u32,
    pub(crate) pad_6c0: Pad<0x14>,
    pub(crate) ppm_filter_tc_periods_x4: u32,
    pub(crate) unk_6d8: u32,
    pub(crate) pad_6dc: u32,
    pub(crate) ppm_filter_a_neg: F32,
    pub(crate) pad_6e4: u32,
    pub(crate) ppm_filter_a: F32,
    pub(crate) pad_6ec: u32,
    pub(crate) ppm_ki_dt: F32,
    pub(crate) pad_6f4: u32,
    pub(crate) pwr_integral_min_clamp_2: u32,
    pub(crate) unk_6fc: F32,
    pub(crate) ppm_kp: F32,
    pub(crate) pad_704: u32,
    pub(crate) unk_708: u32,
    pub(crate) pwr_min_duty_cycle: u32,
    pub(crate) max_pstate_scaled_4: u32,
    pub(crate) unk_714: u32,
    pub(crate) pad_718: u32,
    pub(crate) unk_71c: F32,
    pub(crate) max_power_3: u32,
    pub(crate) cur_power_mw_2: u32,
    pub(crate) ppm_filter_tc_ms: u32,
    pub(crate) unk_72c: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) ppm_filter_tc_clks: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_730_4: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_730_8: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_730_c: u32,

    pub(crate) unk_730: F32,
    pub(crate) unk_734: u32,
    pub(crate) unk_738: u32,
    pub(crate) unk_73c: u32,
    pub(crate) unk_740: u32,
    pub(crate) unk_744: u32,
    pub(crate) unk_748: Array<0x4, F32>,
    pub(crate) unk_758: u32,
    pub(crate) perf_tgt_utilization: u32,
    pub(crate) pad_760: u32,
    pub(crate) perf_boost_min_util: u32,
    pub(crate) perf_boost_ce_step: u32,
    pub(crate) perf_reset_iters: u32,
    pub(crate) pad_770: u32,
    pub(crate) unk_774: u32,
    pub(crate) unk_778: u32,
    pub(crate) perf_filter_drop_threshold: u32,
    pub(crate) perf_filter_a_neg: F32,
    pub(crate) perf_filter_a2_neg: F32,
    pub(crate) perf_filter_a: F32,
    pub(crate) perf_filter_a2: F32,
    pub(crate) perf_ki: F32,
    pub(crate) perf_ki2: F32,
    pub(crate) perf_integral_min_clamp: F32,
    pub(crate) unk_79c: F32,
    pub(crate) perf_kp: F32,
    pub(crate) perf_kp2: F32,
    pub(crate) boost_state_unk_k: F32,
    pub(crate) base_pstate_scaled_2: u32,
    pub(crate) max_pstate_scaled_5: u32,
    pub(crate) base_pstate_scaled_3: u32,
    pub(crate) pad_7b8: u32,
    pub(crate) perf_cur_utilization: F32,
    pub(crate) perf_tgt_utilization_2: u32,
    pub(crate) pad_7c4: Pad<0x18>,
    pub(crate) unk_7dc: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_7e0_0: Array<0x10, u8>,

    pub(crate) base_pstate_scaled_4: u32,
    pub(crate) pad_7e4: u32,
    pub(crate) unk_7e8: Array<0x14, u8>,
    pub(crate) unk_7fc: F32,
    pub(crate) pwr_min_duty_cycle_2: F32,
    pub(crate) max_pstate_scaled_6: F32,
    pub(crate) max_freq_mhz: u32,
    pub(crate) pad_80c: u32,
    pub(crate) unk_810: u32,
    pub(crate) pad_814: u32,
    pub(crate) pwr_min_duty_cycle_3: u32,
    pub(crate) unk_81c: u32,
    pub(crate) pad_820: u32,
    pub(crate) min_pstate_scaled_4: F32,
    pub(crate) max_pstate_scaled_7: u32,
    pub(crate) unk_82c: u32,
    pub(crate) unk_alpha_neg: F32,
    pub(crate) unk_alpha: F32,
    pub(crate) unk_838: u32,
    pub(crate) unk_83c: u32,
    pub(crate) pad_840: Pad<0x2c>,
    pub(crate) unk_86c: u32,
    pub(crate) fast_die0_sensor_mask: U64,
    #[ver(G >= G14X)]
    pub(crate) fast_die1_sensor_mask: U64,
    pub(crate) fast_die0_release_temp_cc: u32,
    pub(crate) unk_87c: i32,
    pub(crate) unk_880: u32,
    pub(crate) unk_884: u32,
    pub(crate) pad_888: u32,
    pub(crate) unk_88c: u32,
    pub(crate) pad_890: u32,
    pub(crate) unk_894: F32,
    pub(crate) pad_898: u32,
    pub(crate) fast_die0_ki_dt: F32,
    pub(crate) pad_8a0: u32,
    pub(crate) unk_8a4: u32,
    pub(crate) unk_8a8: F32,
    pub(crate) fast_die0_kp: F32,
    pub(crate) pad_8b0: u32,
    pub(crate) unk_8b4: u32,
    pub(crate) pwr_min_duty_cycle_4: u32,
    pub(crate) max_pstate_scaled_8: u32,
    pub(crate) max_pstate_scaled_9: u32,
    pub(crate) fast_die0_prop_tgt_delta: u32,
    pub(crate) unk_8c8: u32,
    pub(crate) unk_8cc: u32,
    pub(crate) pad_8d0: Pad<0x14>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_8e4_0: Array<0x10, u8>,

    pub(crate) unk_8e4: u32,
    pub(crate) unk_8e8: u32,
    pub(crate) max_pstate_scaled_10: u32,
    pub(crate) unk_8f0: u32,
    pub(crate) unk_8f4: u32,
    pub(crate) pad_8f8: u32,
    pub(crate) pad_8fc: u32,
    pub(crate) unk_900: Array<0x24, u8>,

    pub(crate) unk_coef_a1: Array<8, Array<MAX_CORES_PER_CLUSTER::ver, F32>>,
    pub(crate) unk_coef_a2: Array<8, Array<MAX_CORES_PER_CLUSTER::ver, F32>>,

    pub(crate) pad_b24: Pad<0x70>,
    pub(crate) max_pstate_scaled_11: u32,
    pub(crate) freq_with_off: u32,
    pub(crate) unk_b9c: u32,
    pub(crate) unk_ba0: U64,
    pub(crate) unk_ba8: U64,
    pub(crate) unk_bb0: u32,
    pub(crate) unk_bb4: u32,

    #[ver(V >= V13_3)]
    pub(crate) pad_bb8_0: Pad<0x200>,
    #[ver(V >= V13_5)]
    pub(crate) pad_bb8_200: Pad<0x8>,

    pub(crate) pad_bb8: Pad<0x74>,
    pub(crate) unk_c2c: u32,
    pub(crate) power_zone_count: u32,
    pub(crate) max_power_4: u32,
    pub(crate) max_power_5: u32,
    pub(crate) max_power_6: u32,
    pub(crate) unk_c40: u32,
    pub(crate) unk_c44: F32,
    pub(crate) avg_power_target_filter_a_neg: F32,
    pub(crate) avg_power_target_filter_a: F32,
    pub(crate) avg_power_target_filter_tc_x4: u32,
    pub(crate) avg_power_target_filter_tc_xperiod: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) avg_power_target_filter_tc_clks: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_c58_4: u32,

    pub(crate) power_zones: Array<5, PowerZone::ver>,
    pub(crate) avg_power_filter_tc_periods_x4: u32,
    pub(crate) unk_cfc: u32,
    pub(crate) unk_d00: u32,
    pub(crate) avg_power_filter_a_neg: F32,
    pub(crate) unk_d08: u32,
    pub(crate) avg_power_filter_a: F32,
    pub(crate) unk_d10: u32,
    pub(crate) avg_power_ki_dt: F32,
    pub(crate) unk_d18: u32,
    pub(crate) unk_d1c: u32,
    pub(crate) unk_d20: F32,
    pub(crate) avg_power_kp: F32,
    pub(crate) unk_d28: u32,
    pub(crate) unk_d2c: u32,
    pub(crate) avg_power_min_duty_cycle: u32,
    pub(crate) max_pstate_scaled_12: u32,
    pub(crate) max_pstate_scaled_13: u32,
    pub(crate) unk_d3c: u32,
    pub(crate) max_power_7: F32,
    pub(crate) max_power_8: u32,
    pub(crate) unk_d48: u32,
    pub(crate) avg_power_filter_tc_ms: u32,
    pub(crate) unk_d50: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) avg_power_filter_tc_clks: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_d54_4: Array<0xc, u8>,

    pub(crate) unk_d54: Array<0x10, u8>,
    pub(crate) max_pstate_scaled_14: u32,
    pub(crate) unk_d68: Array<0x24, u8>,

    pub(crate) t81xx_data: T81xxData,

    pub(crate) unk_dd0: Array<0x40, u8>,

    #[ver(V >= V13_2)]
    pub(crate) unk_e10_pad: Array<0x10, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_e10_0: HwDataA130Extra,

    pub(crate) unk_e10: Array<0xc, u8>,

    pub(crate) fast_die0_sensor_mask_2: U64,
    #[ver(G >= G14X)]
    pub(crate) fast_die1_sensor_mask_2: U64,

    pub(crate) unk_e24: u32,
    pub(crate) unk_e28: u32,
    pub(crate) unk_e2c: Pad<0x1c>,
    pub(crate) unk_coef_b1: Array<8, Array<MAX_CORES_PER_CLUSTER::ver, F32>>,
    pub(crate) unk_coef_b2: Array<8, Array<MAX_CORES_PER_CLUSTER::ver, F32>>,

    #[ver(G >= G14X)]
    pub(crate) pad_1048_0: Pad<0x600>,

    pub(crate) pad_1048: Pad<0x5e4>,

    pub(crate) fast_die0_sensor_mask_alt: U64,
    #[ver(G >= G14X)]
    pub(crate) fast_die1_sensor_mask_alt: U64,
    #[ver(V < V13_0B4)]
    pub(crate) fast_die0_sensor_present: U64,

    pub(crate) unk_163c: u32,

    pub(crate) unk_1640: Array<0x2000, u8>,

    #[ver(G >= G14X)]
    pub(crate) unk_3640_0: Array<0x2000, u8>,

    pub(crate) unk_3640: u32,
    pub(crate) unk_3644: u32,
    pub(crate) hws1: HwDataShared1,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_hws2: Array<16, u16>,

    pub(crate) hws2: HwDataShared2,
    pub(crate) unk_3c00: u32,
    pub(crate) unk_3c04: u32,
    pub(crate) hws3: HwDataShared3,
    pub(crate) unk_3c58: Array<0x3c, u8>,
    pub(crate) unk_3c94: u32,
    pub(crate) unk_3c98: U64,
    pub(crate) unk_3ca0: U64,
    pub(crate) unk_3ca8: U64,
    pub(crate) unk_3cb0: U64,
    pub(crate) ts_last_idle: U64,
    pub(crate) ts_last_poweron: U64,
    pub(crate) ts_last_poweroff: U64,
    pub(crate) unk_3cd0: U64,
    pub(crate) unk_3cd8: U64,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_3ce0_0: u32,

    pub(crate) unk_3ce0: u32,
    pub(crate) unk_3ce4: u32,
    pub(crate) unk_3ce8: u32,
    pub(crate) unk_3cec: u32,
    pub(crate) unk_3cf0: u32,
    pub(crate) core_leak_coef: Array<8, F32>,
    pub(crate) sram_leak_coef: Array<8, F32>,

    #[ver(V >= V13_0B4)]
    pub(crate) aux_leak_coef: AuxLeakCoef,
    #[ver(V >= V13_0B4)]
    pub(crate) unk_3d34_0: Array<0x18, u8>,

    pub(crate) unk_3d34: Array<0x38, u8>,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataBAuxPStates {
    pub(crate) cs_max_pstate: u32,
    pub(crate) cs_frequencies: Array<0x10, u32>,
    pub(crate) cs_voltages: Array<0x10, Array<0x2, u32>>,
    pub(crate) cs_voltages_sram: Array<0x10, Array<0x2, u32>>,
    pub(crate) cs_unkpad: u32,
    pub(crate) afr_max_pstate: u32,
    pub(crate) afr_frequencies: Array<0x8, u32>,
    pub(crate) afr_voltages: Array<0x8, Array<0x2, u32>>,
    pub(crate) afr_voltages_sram: Array<0x8, Array<0x2, u32>>,
    pub(crate) afr_unkpad: u32,
}

#[derive(Debug, Default, Clone, Copy)]
#[repr(C)]
pub(crate) struct IOMapping {
    pub(crate) phys_addr: U64,
    pub(crate) virt_addr: U64,
    pub(crate) total_size: u32,
    pub(crate) element_size: u32,
    pub(crate) readwrite: U64,
}

#[versions(AGX)]
const IO_MAPPING_COUNT: usize = {
    #[ver(V < V13_0B4)]
    {
        0x14
    }
    #[ver(V >= V13_0B4 && V < V13_3)]
    {
        0x17
    }
    #[ver(V >= V13_3 && V < V13_5)]
    {
        0x18
    }
    #[ver(V >= V13_5)]
    {
        0x19
    }
};

#[versions(AGX)]
#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct HwDataB {
    #[ver(V < V13_0B4)]
    pub(crate) unk_0: U64,

    pub(crate) unk_8: U64,

    #[ver(V < V13_0B4)]
    pub(crate) unk_10: U64,

    pub(crate) unk_18: U64,
    pub(crate) unk_20: U64,
    pub(crate) unk_28: U64,
    pub(crate) unk_30: U64,
    pub(crate) timestamp_area_base: U64,
    pub(crate) pad_40: Pad<0x20>,

    #[ver(V < V13_0B4)]
    pub(crate) yuv_matrices: Array<0xf, Array<3, Array<4, i16>>>,

    #[ver(V >= V13_0B4)]
    pub(crate) yuv_matrices: Array<0x3f, Array<3, Array<4, i16>>>,

    pub(crate) pad_1c8: Pad<0x8>,
    pub(crate) io_mappings: Array<IO_MAPPING_COUNT::ver, IOMapping>,

    #[ver(V >= V13_0B4)]
    pub(crate) sgx_sram_ptr: U64,

    pub(crate) chip_id: u32,
    pub(crate) unk_454: u32,
    pub(crate) unk_458: u32,
    pub(crate) unk_45c: u32,
    pub(crate) unk_460: u32,
    pub(crate) unk_464: u32,
    pub(crate) unk_468: u32,
    pub(crate) unk_46c: u32,
    pub(crate) unk_470: u32,
    pub(crate) unk_474: u32,
    pub(crate) unk_478: u32,
    pub(crate) unk_47c: u32,
    pub(crate) unk_480: u32,
    pub(crate) unk_484: u32,
    pub(crate) unk_488: u32,
    pub(crate) unk_48c: u32,
    pub(crate) base_clock_khz: u32,
    pub(crate) power_sample_period: u32,
    pub(crate) pad_498: Pad<0x4>,
    pub(crate) unk_49c: u32,
    pub(crate) unk_4a0: u32,
    pub(crate) unk_4a4: u32,
    pub(crate) pad_4a8: Pad<0x4>,
    pub(crate) unk_4ac: u32,
    pub(crate) pad_4b0: Pad<0x8>,
    pub(crate) unk_4b8: u32,
    pub(crate) unk_4bc: Array<0x4, u8>,
    pub(crate) unk_4c0: u32,
    pub(crate) unk_4c4: u32,
    pub(crate) unk_4c8: u32,
    pub(crate) unk_4cc: u32,
    pub(crate) unk_4d0: u32,
    pub(crate) unk_4d4: u32,
    pub(crate) unk_4d8: Array<0x4, u8>,
    pub(crate) unk_4dc: u32,
    pub(crate) unk_4e0: U64,
    pub(crate) unk_4e8: u32,
    pub(crate) unk_4ec: u32,
    pub(crate) unk_4f0: u32,
    pub(crate) unk_4f4: u32,
    pub(crate) unk_4f8: u32,
    pub(crate) unk_4fc: u32,
    pub(crate) unk_500: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_504_0: u32,

    pub(crate) unk_504: u32,
    pub(crate) unk_508: u32,
    pub(crate) unk_50c: u32,
    pub(crate) unk_510: u32,
    pub(crate) unk_514: u32,
    pub(crate) unk_518: u32,
    pub(crate) unk_51c: u32,
    pub(crate) unk_520: u32,
    pub(crate) unk_524: u32,
    pub(crate) unk_528: u32,
    pub(crate) unk_52c: u32,
    pub(crate) unk_530: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_534_0: u32,

    pub(crate) unk_534: u32,
    pub(crate) unk_538: u32,

    pub(crate) num_frags: u32,
    pub(crate) unk_540: u32,
    pub(crate) unk_544: u32,
    pub(crate) unk_548: u32,
    pub(crate) unk_54c: u32,
    pub(crate) unk_550: u32,
    pub(crate) unk_554: u32,
    pub(crate) uat_ttb_base: U64,
    pub(crate) gpu_core_id: u32,
    pub(crate) gpu_rev_id: u32,
    pub(crate) num_cores: u32,
    pub(crate) max_pstate: u32,

    #[ver(V < V13_0B4)]
    pub(crate) num_pstates: u32,

    pub(crate) frequencies: Array<0x10, u32>,
    pub(crate) voltages: Array<0x10, [u32; 0x8]>,
    pub(crate) voltages_sram: Array<0x10, [u32; 0x8]>,

    #[ver(V >= V13_3)]
    pub(crate) unk_9f4_0: Pad<64>,

    pub(crate) sram_k: Array<0x10, F32>,
    pub(crate) unk_9f4: Array<0x10, u32>,
    pub(crate) rel_max_powers: Array<0x10, u32>,
    pub(crate) rel_boost_freqs: Array<0x10, u32>,

    #[ver(V >= V13_3)]
    pub(crate) unk_arr_0: Array<32, u32>,

    #[ver(V < V13_0B4)]
    pub(crate) min_sram_volt: u32,

    #[ver(V < V13_0B4)]
    pub(crate) unk_ab8: u32,

    #[ver(V < V13_0B4)]
    pub(crate) unk_abc: u32,

    #[ver(V < V13_0B4)]
    pub(crate) unk_ac0: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) aux_ps: HwDataBAuxPStates,

    #[ver(V >= V13_3)]
    pub(crate) pad_ac4_0: Array<0x44c, u8>,

    pub(crate) pad_ac4: Pad<0x8>,
    pub(crate) unk_acc: u32,
    pub(crate) unk_ad0: u32,
    pub(crate) pad_ad4: Pad<0x10>,
    pub(crate) unk_ae4: Array<0x4, u32>,
    pub(crate) pad_af4: Pad<0x4>,
    pub(crate) unk_af8: u32,
    pub(crate) pad_afc: Pad<0x8>,
    pub(crate) unk_b04: u32,
    pub(crate) unk_b08: u32,
    pub(crate) unk_b0c: u32,

    #[ver(G >= G14X)]
    pub(crate) pad_b10_0: Array<0x8, u8>,

    pub(crate) unk_b10: u32,
    pub(crate) timer_offset: U64,
    pub(crate) unk_b1c: u32,
    pub(crate) unk_b20: u32,
    pub(crate) unk_b24: u32,
    pub(crate) unk_b28: u32,
    pub(crate) unk_b2c: u32,
    pub(crate) unk_b30: u32,
    pub(crate) unk_b34: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_b38_0: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_b38_4: u32,

    #[ver(V >= V13_3)]
    pub(crate) unk_b38_8: u32,

    pub(crate) unk_b38: Array<0xc, u32>,
    pub(crate) unk_b68: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_b6c: Array<0xd0, u8>,

    #[ver(G >= G14X)]
    pub(crate) unk_c3c_0: Array<0x8, u8>,

    #[ver(G < G14X && V >= V13_5)]
    pub(crate) unk_c3c_8: Array<0x10, u8>,

    #[ver(V >= V13_5)]
    pub(crate) unk_c3c_18: Array<0x20, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_c3c: u32,
}

#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct PendingStamp {
    pub(crate) info: u32,
    pub(crate) wait_value: u32,
}

#[derive(Debug, Clone, Copy, Default)]
#[repr(C, packed)]
pub(crate) struct FaultInfo {
    pub(crate) unk_0: u32,
    pub(crate) unk_4: u32,
    pub(crate) queue_uuid: u32,
    pub(crate) unk_c: u32,
    pub(crate) unk_10: u32,
    pub(crate) unk_14: u32,
}

#[versions(AGX)]
#[derive(Debug, Clone, Copy, Default)]
#[repr(C, packed)]
pub(crate) struct GlobalsSub {
    pub(crate) unk_54: u16,
    pub(crate) unk_56: u16,
    pub(crate) unk_58: u16,
    pub(crate) unk_5a: U32,
    pub(crate) unk_5e: U32,
    pub(crate) unk_62: U32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_66_0: Array<0xc, u8>,

    pub(crate) unk_66: U32,
    pub(crate) unk_6a: Array<0x16, u8>,
}

#[derive(Debug, Clone, Copy, Default)]
#[repr(C)]
pub(crate) struct PowerZoneGlobal {
    pub(crate) target: u32,
    pub(crate) target_off: u32,
    pub(crate) filter_tc: u32,
}

#[versions(AGX)]
#[derive(Debug, Default)]
#[repr(C)]
pub(crate) struct Globals {
    pub(crate) ktrace_enable: u32,
    pub(crate) unk_4: Array<0x20, u8>,

    #[ver(V >= V13_2)]
    pub(crate) unk_24_0: u32,

    pub(crate) unk_24: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) debug: u32,

    #[ver(V >= V13_3)]
    pub(crate) unk_28_4: u32,

    pub(crate) unk_28: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_2c_0: u32,

    pub(crate) unk_2c: u32,
    pub(crate) unk_30: u32,
    pub(crate) unk_34: u32,
    pub(crate) unk_38: Array<0x1c, u8>,

    pub(crate) sub: GlobalsSub::ver,

    pub(crate) unk_80: Array<0xf80, u8>,
    pub(crate) unk_1000: Array<0x7000, u8>,
    pub(crate) unk_8000: Array<0x900, u8>,

    #[ver(G >= G14X)]
    pub(crate) unk_8900_pad: Array<0x484c, u8>,

    #[ver(V >= V13_3)]
    pub(crate) unk_8900_pad2: Array<0x54, u8>,

    pub(crate) unk_8900: u32,
    pub(crate) pending_submissions: u32,
    pub(crate) max_power: u32,
    pub(crate) max_pstate_scaled: u32,
    pub(crate) max_pstate_scaled_2: u32,
    pub(crate) unk_8914: u32,
    pub(crate) unk_8918: u32,
    pub(crate) max_pstate_scaled_3: u32,
    pub(crate) unk_8920: u32,
    pub(crate) power_zone_count: u32,
    pub(crate) avg_power_filter_tc_periods: u32,
    pub(crate) avg_power_ki_dt: F32,
    pub(crate) avg_power_kp: F32,
    pub(crate) avg_power_min_duty_cycle: u32,
    pub(crate) avg_power_target_filter_tc: u32,
    pub(crate) power_zones: Array<5, PowerZoneGlobal>,
    pub(crate) unk_8978: Array<0x44, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_89bc_0: Array<0x3c, u8>,

    pub(crate) unk_89bc: u32,
    pub(crate) fast_die0_release_temp: u32,
    pub(crate) unk_89c4: i32,
    pub(crate) fast_die0_prop_tgt_delta: u32,
    pub(crate) fast_die0_kp: F32,
    pub(crate) fast_die0_ki_dt: F32,
    pub(crate) unk_89d4: Array<0xc, u8>,
    pub(crate) unk_89e0: u32,
    pub(crate) max_power_2: u32,
    pub(crate) ppm_kp: F32,
    pub(crate) ppm_ki_dt: F32,
    pub(crate) unk_89f0: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_89f4_0: Array<0x8, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_89f4_8: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_89f4_c: Array<0x50, u8>,

    #[ver(V >= V13_3)]
    pub(crate) unk_89f4_5c: Array<0xc, u8>,

    pub(crate) unk_89f4: u32,
    pub(crate) hws1: HwDataShared1,
    pub(crate) hws2: HwDataShared2,

    #[ver(V >= V13_0B4)]
    pub(crate) idle_off_standby_timer: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_hws2_4: Array<0x8, F32>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_hws2_24: u32,

    pub(crate) unk_hws2_28: u32,

    pub(crate) hws3: HwDataShared3,
    pub(crate) unk_9004: Array<8, u8>,
    pub(crate) unk_900c: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_9010_0: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_9010_4: Array<0x14, u8>,

    pub(crate) unk_9010: Array<0x2c, u8>,
    pub(crate) unk_903c: u32,
    pub(crate) unk_9040: Array<0xc0, u8>,
    pub(crate) unk_9100: Array<0x6f00, u8>,
    pub(crate) unk_10000: Array<0xe50, u8>,
    pub(crate) unk_10e50: u32,
    pub(crate) unk_10e54: Array<0x2c, u8>,

    #[ver((G >= G14X && V < V13_3) || (G <= G14 && V >= V13_3))]
    pub(crate) unk_x_pad: Array<0x4, u8>,

    // bit 0: sets sgx_reg 0x17620
    // bit 1: sets sgx_reg 0x17630
    pub(crate) fault_control: u32,
    pub(crate) do_init: u32,
    pub(crate) unk_10e88: Array<0x188, u8>,
    pub(crate) idle_ts: U64,
    pub(crate) idle_unk: U64,
    pub(crate) progress_check_interval_3d: u32,
    pub(crate) progress_check_interval_ta: u32,
    pub(crate) progress_check_interval_cl: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_1102c_0: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_1102c_4: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_1102c_8: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_1102c_c: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_1102c_10: u32,

    pub(crate) unk_1102c: u32,
    pub(crate) idle_off_delay_ms: u32,
    pub(crate) fender_idle_off_delay_ms: u32,
    pub(crate) fw_early_wake_timeout_ms: u32,
    #[ver(V == V13_3)]
    pub(crate) ps_pad_0: Pad<0x8>,
    pub(crate) pending_stamps: Array<0x100, PendingStamp>,
    #[ver(V != V13_3)]
    pub(crate) ps_pad_0: Pad<0x8>,
    pub(crate) unkpad_ps: Pad<0x78>,
    pub(crate) unk_117bc: u32,
    pub(crate) fault_info: FaultInfo,
    pub(crate) counter: u32,
    pub(crate) unk_118dc: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_118e0_0: Array<0x9c, u8>,

    #[ver(G >= G14X)]
    pub(crate) unk_118e0_9c: Array<0x580, u8>,

    #[ver(V >= V13_3)]
    pub(crate) unk_118e0_9c_x: Array<0x8, u8>,

    pub(crate) cl_context_switch_timeout_ms: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) cl_kill_timeout_ms: u32,

    pub(crate) cdm_context_store_latency_threshold: u32,
    pub(crate) unk_118e8: u32,
    pub(crate) unk_118ec: Array<0x400, u8>,
    pub(crate) unk_11cec: Array<0x54, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_11d40: Array<0x19c, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_11edc: u32,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_11ee0: Array<0x1c, u8>,

    #[ver(V >= V13_0B4)]
    pub(crate) unk_11efc: u32,

    #[ver(V >= V13_3)]
    pub(crate) unk_11f00: Array<0x280, u8>,
}
