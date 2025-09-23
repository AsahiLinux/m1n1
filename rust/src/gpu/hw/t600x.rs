// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! Hardware configuration for t600x (M1 Pro/Max/Ultra) platforms.

use crate::f32;

use super::*;

pub(crate) const HWCONFIG_T6002: HwConfig = HwConfig {
    chip_id: 0x6002,
    gpu_gen: GpuGen::G13,
    gpu_variant: GpuVariant::D,
    gpu_core: GpuCore::G13C,

    base_clock_hz: 24_000_000,
    num_dies: 2,

    da: HwConfigA {
        unk_87c: 900,
        unk_8cc: 11000,
        unk_e24: 125,
    },
    db: HwConfigB {
        unk_454: 1,
        unk_4e0: 4,
        unk_534: 1,
        unk_ab8: 0x2084,
        unk_abc: 0x80,
        unk_b30: 0,
    },
    shared1_tab: &[
        0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff,
        0xffff, 0xffff, 0xffff, 0xffff, 0xffff,
    ],
    shared1_a4: 0xffff,
    shared2_tab: &[-1, -1, -1, -1, 0x2aa, 0xaaa, -1, -1, 0, 0],
    shared2_unk_508: 0xcc00001,
    shared2_curves: None,
    shared3_unk: 0,
    shared3_tab: &[],
    idle_off_standby_timer_default: 0,
    unk_hws2_4: None,
    unk_hws2_24: 0,
    global_unk_54: 0xffff,
    sram_k: f32!(1.02),
    unk_coef_a: &[
        &f32!([9.838]),
        &f32!([9.819]),
        &f32!([9.826]),
        &f32!([9.799]),
        &f32!([9.799]),
        &f32!([9.826]),
        &f32!([9.819]),
        &f32!([9.838]),
    ],
    unk_coef_b: &[
        &f32!([13.0]),
        &f32!([13.0]),
        &f32!([13.0]),
        &f32!([13.0]),
        &f32!([13.0]),
        &f32!([13.0]),
        &f32!([13.0]),
        &f32!([13.0]),
    ],
    global_tab: Some(&[
        0, 1, 2, 1, 1, 90, 75, 1, 1, 1, 2, 90, 75, 1, 1, 1, 1, 90, 75, 1, 1,
    ]),
    has_csafr: false,
    fast_sensor_mask: [0x8080808080808080, 0],
    fast_sensor_mask_alt: [0x9090909090909090, 0],
    fast_die0_sensor_present: 0xff,

    power_zones: &[],
    min_sram_microvolt: 790000,
    avg_power_filter_tc_ms: 1000,
    avg_power_ki_only: f32!(0.6375),
    avg_power_kp: f32!(0.58),
    avg_power_min_duty_cycle: 40,
    avg_power_target_filter_tc: 1,
    fast_die0_integral_gain: f32!(500.0),
    fast_die0_proportional_gain: f32!(72.0),
    fast_die0_prop_tgt_delta: 0,
    fast_die0_release_temp: 80,
    fender_idle_off_delay_ms: 40,
    fw_early_wake_timeout_ms: 5,
    idle_off_delay_ms: 2,
    perf_boost_ce_step: 50,
    perf_boost_min_util: 90,
    perf_filter_drop_threshold: 0,
    perf_filter_time_constant: 5,
    perf_filter_time_constant2: 50,
    perf_integral_gain: f32!(6.3),
    perf_integral_gain2: f32!(0.197392),
    perf_integral_min_clamp: 0,
    perf_proportional_gain: f32!(15.75),
    perf_proportional_gain2: f32!(6.853981),
    perf_reset_iters: 6,
    perf_tgt_utilization: 85,
    power_sample_period: 8,
    ppm_filter_time_constant_ms: 100,
    ppm_ki: f32!(5.8),
    ppm_kp: f32!(0.355),
    pwr_filter_time_constant: 313,
    pwr_integral_gain: f32!(0.0202129),
    pwr_integral_min_clamp: 0,
    pwr_min_duty_cycle: 40,
    pwr_proportional_gain: f32!(5.2831855),
    pwr_sample_period_aic_clks: None,
    se_engagement_criteria: -1,
    se_filter_time_constant: 9,
    se_filter_time_constant_1: 3,
    se_inactive_threshold: 2500,
    se_ki: f32!(-50.0),
    se_ki_1: f32!(-100.0),
    se_kp: f32!(-5.0),
    se_kp_1: f32!(-10.0),
    se_reset_criteria: 50,
    csafr_min_sram_microvolt: 0,

    num_clusters: 8,
};

pub(crate) const HWCONFIG_T6001: HwConfig = HwConfig {
    chip_id: 0x6001,
    gpu_variant: GpuVariant::C,
    gpu_core: GpuCore::G13C,

    num_dies: 1,
    fast_sensor_mask: [0x80808080, 0],
    fast_sensor_mask_alt: [0x90909090, 0],
    fast_die0_sensor_present: 0x0f,

    avg_power_ki_only: f32!(2.4),
    avg_power_kp: f32!(1.5),
    avg_power_target_filter_tc: 125,
    ppm_ki: f32!(30.0),
    ppm_kp: f32!(1.5),

    num_clusters: 4,
    ..HWCONFIG_T6002
};

pub(crate) const HWCONFIG_T6001_STUDIO: HwConfig = HwConfig {
    avg_power_ki_only: f32!(0.6375),
    avg_power_kp: f32!(0.58),
    avg_power_target_filter_tc: 1,
    ppm_ki: f32!(5.8),
    ppm_kp: f32!(0.355),

    ..HWCONFIG_T6001
};

pub(crate) const HWCONFIG_T6000: HwConfig = HwConfig {
    chip_id: 0x6000,
    gpu_variant: GpuVariant::S,
    gpu_core: GpuCore::G13S,

    fast_sensor_mask: [0x8080, 0],
    fast_sensor_mask_alt: [0x9090, 0],
    fast_die0_sensor_present: 0x03,

    num_clusters: 2,
    ..HWCONFIG_T6001
};
