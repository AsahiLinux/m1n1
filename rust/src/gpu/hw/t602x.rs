// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! Hardware configuration for t600x (M1 Pro/Max/Ultra) platforms.

use crate::f32;

use super::*;

// TODO: Tentative
pub(crate) const HWCONFIG_T6022: super::HwConfig = HwConfig {
    chip_id: 0x6022,
    gpu_gen: GpuGen::G14,
    gpu_variant: GpuVariant::D,
    gpu_core: GpuCore::G14D,

    base_clock_hz: 24_000_000,
    num_dies: 2,

    da: HwConfigA {
        unk_87c: 500,
        unk_8cc: 11000,
        unk_e24: 125,
    },
    db: HwConfigB {
        unk_454: 1,
        unk_4e0: 4,
        unk_534: 0,
        unk_ab8: 0, // Unused
        unk_abc: 0, // Unused
        unk_b30: 0,
    },
    shared1_tab: &[
        0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff,
        0xffff, 0xffff, 0xffff, 0xffff, 0xffff,
    ],
    shared1_a4: 0,
    shared2_tab: &[0x800, 0x1555, -1, -1, -1, -1, -1, -1, 0xaaaaa, 0],
    shared2_unk_508: 0xc00007,
    shared2_curves: Some(HwConfigShared2Curves {
        t1_coef: 11000,
        t2: &[
            0xf07, 0x4c0, 0x680, 0x8c0, 0xa80, 0xc40, 0xd80, 0xec0, 0xf40,
        ],
        t3_coefs: &[0, 20, 27, 36, 43, 50, 55, 60, 62],
        t3_scales: &[9, 3209, 10400],
    }),
    shared3_unk: 8,
    shared3_tab: &[
        125, 125, 125, 125, 125, 125, 125, 125, 7500, 125, 125, 125, 125, 125, 125, 125,
    ],
    idle_off_standby_timer_default: 3000,
    unk_hws2_4: Some(f32!([1.0, 0.8, 0.2, 0.9, 0.1, 0.25, 0.5, 0.9])),
    unk_hws2_24: 6,
    global_unk_54: 4000,
    sram_k: f32!(1.02),
    unk_coef_a: &[
        &f32!([0.0, 8.2, 0.0, 6.9, 6.9]),
        &f32!([0.0, 0.0, 0.0, 6.9, 6.9]),
        &f32!([0.0, 8.2, 0.0, 6.9, 0.0]),
        &f32!([0.0, 0.0, 0.0, 6.9, 0.0]),
        &f32!([0.0, 0.0, 0.0, 6.9, 0.0]),
        &f32!([0.0, 8.2, 0.0, 6.9, 0.0]),
        &f32!([0.0, 0.0, 0.0, 6.9, 6.9]),
        &f32!([0.0, 8.2, 0.0, 6.9, 6.9]),
    ],
    unk_coef_b: &[
        &f32!([0.0, 9.0, 0.0, 8.0, 8.0]),
        &f32!([0.0, 0.0, 0.0, 8.0, 8.0]),
        &f32!([0.0, 9.0, 0.0, 8.0, 0.0]),
        &f32!([0.0, 0.0, 0.0, 8.0, 0.0]),
        &f32!([0.0, 0.0, 0.0, 8.0, 0.0]),
        &f32!([0.0, 9.0, 0.0, 8.0, 0.0]),
        &f32!([0.0, 0.0, 0.0, 8.0, 8.0]),
        &f32!([0.0, 9.0, 0.0, 8.0, 8.0]),
    ],
    global_tab: Some(&[
        0, 2, 2, 1, 1, 90, 75, 1, 1, 1, 2, 90, 75, 1, 1, 1, 2, 90, 75, 1, 1, 1, 1, 90, 75, 1, 1,
    ]),
    has_csafr: true,
    fast_sensor_mask: [0x40005000c000d00, 0xd000c0005000400],
    // Apple typo? Should probably be 0x140015001c001d00
    fast_sensor_mask_alt: [0x140015001d001d00, 0x1d001c0015001400],
    fast_die0_sensor_present: 0, // Unused

    power_zones: &[],
    min_sram_microvolt: 790000,
    avg_power_filter_tc_ms: 302,
    avg_power_ki_only: f32!(1.0125),
    avg_power_kp: f32!(0.15),
    avg_power_min_duty_cycle: 40,
    avg_power_target_filter_tc: 1,
    fast_die0_integral_gain: f32!(9.6),
    fast_die0_proportional_gain: f32!(24.0),
    fast_die0_prop_tgt_delta: 0,
    fast_die0_release_temp: 80,
    fender_idle_off_delay_ms: 40,
    fw_early_wake_timeout_ms: 5,
    idle_off_delay_ms: 2,
    perf_boost_ce_step: 100,
    perf_boost_min_util: 75,
    perf_tgt_utilization: 70,
    perf_filter_drop_threshold: 0,
    perf_filter_time_constant: 5,
    perf_filter_time_constant2: 200,
    perf_integral_gain: f32!(1.62),
    perf_integral_gain2: f32!(1.62),
    perf_integral_min_clamp: 0,
    perf_proportional_gain: f32!(5.4),
    perf_proportional_gain2: f32!(5.4),
    perf_reset_iters: 6,
    power_sample_period: 8,
    ppm_filter_time_constant_ms: 34,
    ppm_ki: f32!(11.0),
    ppm_kp: f32!(0.15),
    pwr_filter_time_constant: 313,
    pwr_integral_gain: f32!(0.0202129),
    pwr_integral_min_clamp: 0,
    pwr_min_duty_cycle: 40,
    pwr_proportional_gain: f32!(5.2831855),
    pwr_sample_period_aic_clks: Some(200000),
    se_engagement_criteria: 700,
    se_filter_time_constant: 9,
    se_filter_time_constant_1: 3,
    se_inactive_threshold: 2500,
    se_ki: f32!(-50.0),
    se_ki_1: f32!(-100.0),
    se_kp: f32!(-5.0),
    se_kp_1: f32!(-10.0),
    se_reset_criteria: 50,
    csafr_min_sram_microvolt: 812000,

    num_clusters: 8,
};

pub(crate) const HWCONFIG_T6021: super::HwConfig = HwConfig {
    chip_id: 0x6021,
    gpu_variant: GpuVariant::C,
    gpu_core: GpuCore::G14C,

    num_dies: 1,
    unk_hws2_4: Some(f32!([1.0, 0.8, 0.2, 0.9, 0.1, 0.25, 0.7, 0.9])),
    fast_sensor_mask: [0x40005000c000d00, 0],
    fast_sensor_mask_alt: [0x140015001d001d00, 0],
    idle_off_standby_timer_default: 700,

    avg_power_filter_tc_ms: 300,
    avg_power_ki_only: f32!(1.5125),
    avg_power_kp: f32!(0.38),
    fast_die0_integral_gain: f32!(700.0),
    fast_die0_proportional_gain: f32!(34.0),
    ppm_ki: f32!(18.0),
    ppm_kp: f32!(0.1),

    perf_boost_ce_step: 50,
    perf_boost_min_util: 90,
    perf_tgt_utilization: 85,

    num_clusters: 4,
    ..HWCONFIG_T6022
};

pub(crate) const HWCONFIG_T6021_STUDIO: super::HwConfig = HwConfig {
    idle_off_standby_timer_default: 3000,
    perf_boost_ce_step: 100,
    perf_boost_min_util: 75,
    perf_tgt_utilization: 70,

    ..HWCONFIG_T6021
};

pub(crate) const HWCONFIG_T6020: super::HwConfig = HwConfig {
    chip_id: 0x6020,
    gpu_variant: GpuVariant::S,
    gpu_core: GpuCore::G14S,

    db: HwConfigB {
        unk_454: 0,
        ..HWCONFIG_T6021.db
    },

    fast_sensor_mask: [0xc000d00, 0],
    fast_sensor_mask_alt: [0x1d001d00, 0],

    avg_power_filter_tc_ms: 302,
    avg_power_ki_only: f32!(2.6375),
    avg_power_kp: f32!(0.18),
    fast_die0_integral_gain: f32!(1350.0),
    ppm_ki: f32!(28.0),
    ppm_filter_time_constant_ms: 32,

    num_clusters: 2,
    ..HWCONFIG_T6021
};
