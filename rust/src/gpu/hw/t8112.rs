// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! Hardware configuration for t8112 platforms (M2).

use crate::f32;

use super::*;

pub(crate) const HWCONFIG: super::HwConfig = HwConfig {
    chip_id: 0x8112,
    gpu_gen: GpuGen::G14,
    gpu_variant: GpuVariant::G,
    gpu_core: GpuCore::G14G,

    base_clock_hz: 24_000_000,
    num_dies: 1,

    da: HwConfigA {
        unk_87c: 900,
        unk_8cc: 11000,
        unk_e24: 125,
    },
    db: HwConfigB {
        unk_454: 1,
        unk_4e0: 4,
        unk_534: 0,
        unk_ab8: 0x2048,
        unk_abc: 0x4000,
        unk_b30: 1,
    },
    shared1_tab: &[
        0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff,
        0xffff, 0xffff, 0xffff, 0xffff, 0xffff,
    ],
    shared1_a4: 0,
    shared2_tab: &[-1, -1, -1, -1, -1, -1, -1, -1, 0xaa5aa, 0],
    shared2_unk_508: 0xc00000,
    shared2_curves: Some(HwConfigShared2Curves {
        t1_coef: 7200,
        t2: &[
            0xf07, 0x4c0, 0x6c0, 0x8c0, 0xac0, 0xc40, 0xdc0, 0xec0, 0xf80,
        ],
        t3_coefs: &[0, 20, 28, 36, 44, 50, 56, 60, 63],
        t3_scales: &[9, 3209, 10400],
    }),
    shared3_unk: 5,
    shared3_tab: &[
        10700, 10700, 10700, 10700, 10700, 6000, 1000, 1000, 1000, 10700, 10700, 10700, 10700,
        10700, 10700, 10700,
    ],
    idle_off_standby_timer_default: 0,
    unk_hws2_4: None,
    unk_hws2_24: 0,
    global_unk_54: 0xffff,

    sram_k: f32!(1.02),
    // 13.2: last coef changed from 6.6 to 5.3, assuming that was a fix we can backport
    unk_coef_a: &[&f32!([0.0, 0.0, 0.0, 0.0, 5.3, 0.0, 5.3, /*6.6*/ 5.3])],
    unk_coef_b: &[&f32!([0.0, 0.0, 0.0, 0.0, 5.3, 0.0, 5.3, /*6.6*/ 5.3])],
    global_tab: None,
    has_csafr: false,
    fast_sensor_mask: [0x6800, 0],
    fast_sensor_mask_alt: [0x6800, 0],
    fast_die0_sensor_present: 0x02,

    power_zones: &[],
    min_sram_microvolt: 780000,
    avg_power_filter_tc_ms: 300,
    avg_power_ki_only: f32!(9.375),
    avg_power_kp: f32!(3.22),
    avg_power_min_duty_cycle: 40,
    avg_power_target_filter_tc: 1,
    fast_die0_integral_gain: f32!(200.0),
    fast_die0_proportional_gain: f32!(5.0),
    fast_die0_prop_tgt_delta: 0,
    fast_die0_release_temp: 80,
    fender_idle_off_delay_ms: 40,
    fw_early_wake_timeout_ms: 5,
    idle_off_delay_ms: 2,
    perf_boost_ce_step: 50,
    perf_boost_min_util: 90,
    perf_filter_drop_threshold: 0,
    perf_filter_time_constant: 5,
    perf_filter_time_constant2: 200,
    perf_integral_gain: f32!(5.94),
    perf_integral_gain2: f32!(5.94),
    perf_integral_min_clamp: 0,
    perf_proportional_gain: f32!(14.85),
    perf_proportional_gain2: f32!(14.85),
    perf_reset_iters: 6,
    perf_tgt_utilization: 85,
    power_sample_period: 8,
    ppm_filter_time_constant_ms: 34,
    ppm_ki: f32!(205.0),
    ppm_kp: f32!(0.75),
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

    num_clusters: 1,
};
