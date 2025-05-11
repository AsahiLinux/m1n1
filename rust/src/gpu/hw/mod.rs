// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! Per-SoC hardware configuration structures
//!
//! This module contains the definitions used to store per-GPU and per-SoC configuration data.

use crate::float::F32;
use alloc::vec::Vec;

pub(crate) mod t600x;
pub(crate) mod t602x;
pub(crate) mod t8103;
pub(crate) mod t8112;

/// GPU generation enumeration. Note: Part of the UABI.
#[derive(Debug, PartialEq, Copy, Clone)]
#[repr(u32)]
pub(crate) enum GpuGen {
    G13 = 13,
    G14 = 14,
}

/// GPU variant enumeration. Note: Part of the UABI.
#[derive(Debug, PartialEq, Copy, Clone)]
#[repr(u32)]
pub(crate) enum GpuVariant {
    #[allow(dead_code)]
    P = 'P' as u32,
    G = 'G' as u32,
    S = 'S' as u32,
    C = 'C' as u32,
    D = 'D' as u32,
}

/// GPU core type enumeration. Note: Part of the firmware ABI.
#[derive(Debug, Copy, Clone)]
#[repr(u32)]
pub(crate) enum GpuCore {
    // Unknown = 0,
    // G5P = 1,
    // G5G = 2,
    // G9P = 3,
    // G9G = 4,
    // G10P = 5,
    // G11P = 6,
    // G11M = 7,
    // G11G = 8,
    // G12P = 9,
    // G13P = 10,
    G13G = 11,
    G13S = 12,
    G13C = 13,
    // G14P = 14,
    G14G = 15,
    G14S = 16,
    G14C = 17,
    G14D = 18, // Split out, unlike G13D
}

/// GPU revision ID. Note: Part of the firmware ABI.
#[derive(Debug, PartialEq, Copy, Clone)]
#[repr(u32)]
pub(crate) enum GpuRevisionID {
    // Unknown = 0,
    A0 = 1,
    A1 = 2,
    B0 = 3,
    B1 = 4,
    C0 = 5,
    C1 = 6,
}

/// A single performance state of the GPU.
#[derive(Debug)]
pub(crate) struct PState {
    /// Voltage in millivolts, per GPU cluster.
    pub(crate) volt_mv: Vec<u32>,
    /// Frequency in hertz.
    pub(crate) freq_hz: u32,
    /// Maximum power consumption of the GPU at this pstate, in milliwatts.
    pub(crate) pwr_mw: u32,
}

impl PState {
    pub(crate) fn max_volt_mv(&self) -> u32 {
        *self.volt_mv.iter().max().expect("No voltages")
    }
}

/// A power zone definition (we have no idea what this is but Apple puts them in the DT).
#[allow(missing_docs)]
#[derive(Debug, Copy, Clone)]
pub(crate) struct PowerZone {
    pub(crate) target: u32,
    pub(crate) target_offset: u32,
    pub(crate) filter_tc: u32,
}

/// Unknown HwConfigA fields that vary from SoC to SoC.
#[allow(missing_docs)]
#[derive(Debug, Copy, Clone)]
pub(crate) struct HwConfigA {
    pub(crate) unk_87c: i32,
    pub(crate) unk_8cc: u32,
    pub(crate) unk_e24: u32,
}

/// Unknown HwConfigB fields that vary from SoC to SoC.
#[allow(missing_docs)]
#[derive(Debug, Copy, Clone)]
pub(crate) struct HwConfigB {
    pub(crate) unk_454: u32,
    pub(crate) unk_4e0: u64,
    pub(crate) unk_534: u32,
    pub(crate) unk_ab8: u32,
    pub(crate) unk_abc: u32,
    pub(crate) unk_b30: u32,
}

#[derive(Debug)]
pub(crate) struct HwConfigShared2Curves {
    pub(crate) t1_coef: u32,
    pub(crate) t2: &'static [i16],
    pub(crate) t3_coefs: &'static [u32],
    pub(crate) t3_scales: &'static [u32],
}

/// Static hardware configuration for a given SoC model.
#[derive(Debug)]
pub(crate) struct HwConfig {
    /// Chip ID in hex format (e.g. 0x8103 for t8103).
    pub(crate) chip_id: u32,
    /// GPU generation.
    pub(crate) gpu_gen: GpuGen,
    /// GPU variant type.
    pub(crate) gpu_variant: GpuVariant,
    /// GPU core type ID (as known by the firmware).
    pub(crate) gpu_core: GpuCore,

    /// Base clock used used for timekeeping.
    pub(crate) base_clock_hz: u32,
    /// Number of dies on this SoC.
    pub(crate) num_dies: u32,

    /// Misc HWDataA field values.
    pub(crate) da: HwConfigA,
    /// Misc HWDataB field values.
    pub(crate) db: HwConfigB,
    /// HwDataShared1.table.
    pub(crate) shared1_tab: &'static [i32],
    /// HwDataShared1.unk_a4.
    pub(crate) shared1_a4: u32,
    /// HwDataShared2.table.
    pub(crate) shared2_tab: &'static [i32],
    /// HwDataShared2.unk_508.
    pub(crate) shared2_unk_508: u32,
    /// HwDataShared2.unk_508.
    pub(crate) shared2_curves: Option<HwConfigShared2Curves>,

    /// HwDataShared3.unk_8.
    pub(crate) shared3_unk: u32,
    /// HwDataShared3.table.
    pub(crate) shared3_tab: &'static [u32],

    /// Globals.idle_off_standby_timer.
    pub(crate) idle_off_standby_timer_default: u32,
    /// Globals.unk_hws2_4.
    pub(crate) unk_hws2_4: Option<[F32; 8]>,
    /// Globals.unk_hws2_24.
    pub(crate) unk_hws2_24: u32,
    /// Globals.unk_54
    pub(crate) global_unk_54: u16,

    /// Constant related to SRAM voltages.
    pub(crate) sram_k: F32,
    /// Unknown per-cluster coefficients 1.
    pub(crate) unk_coef_a: &'static [&'static [F32]],
    /// Unknown per-cluster coefficients 2.
    pub(crate) unk_coef_b: &'static [&'static [F32]],
    /// Unknown table in Global struct.
    pub(crate) global_tab: Option<&'static [u8]>,
    /// Whether this GPU has CS/AFR performance states
    pub(crate) has_csafr: bool,

    /// Temperature sensor list (8 bits per sensor).
    pub(crate) fast_sensor_mask: [u64; 2],
    /// Temperature sensor list (alternate).
    pub(crate) fast_sensor_mask_alt: [u64; 2],
    /// Temperature sensor present bitmask.
    pub(crate) fast_die0_sensor_present: u32,

    /// GPU power zone list.
    pub(crate) power_zones: &'static [PowerZone],
    /// Minimum voltage for the SRAM power domain in microvolts.
    pub(crate) min_sram_microvolt: u32,

    // Most of these fields are just named after Apple ADT property names and we don't fully
    // understand them. They configure various power-related PID loops and filters.
    /// Average power filter time constant in milliseconds.
    pub(crate) avg_power_filter_tc_ms: u32,
    /// Average power filter PID integral gain?
    pub(crate) avg_power_ki_only: F32,
    /// Average power filter PID proportional gain?
    pub(crate) avg_power_kp: F32,
    pub(crate) avg_power_min_duty_cycle: u32,
    /// Average power target filter time constant in periods.
    pub(crate) avg_power_target_filter_tc: u32,
    /// "Fast die0" (temperature?) PID integral gain.
    pub(crate) fast_die0_integral_gain: F32,
    /// "Fast die0" (temperature?) PID proportional gain.
    pub(crate) fast_die0_proportional_gain: F32,
    pub(crate) fast_die0_prop_tgt_delta: u32,
    pub(crate) fast_die0_release_temp: u32,
    /// Delay from the fender (?) becoming idle to powerdown
    pub(crate) fender_idle_off_delay_ms: u32,
    /// Timeout from firmware early wake to sleep if no work was submitted (?)
    pub(crate) fw_early_wake_timeout_ms: u32,
    /// Delay from the GPU becoming idle to powerdown
    pub(crate) idle_off_delay_ms: u32,
    /// Percent?
    pub(crate) perf_boost_ce_step: u32,
    /// Minimum utilization before performance state is increased in %.
    pub(crate) perf_boost_min_util: u32,
    pub(crate) perf_filter_drop_threshold: u32,
    /// Performance PID filter time constant? (periods?)
    pub(crate) perf_filter_time_constant: u32,
    /// Performance PID filter time constant 2? (periods?)
    pub(crate) perf_filter_time_constant2: u32,
    /// Performance PID integral gain.
    pub(crate) perf_integral_gain: F32,
    /// Performance PID integral gain 2 (?).
    pub(crate) perf_integral_gain2: F32,
    pub(crate) perf_integral_min_clamp: u32,
    /// Performance PID proportional gain.
    pub(crate) perf_proportional_gain: F32,
    /// Performance PID proportional gain 2 (?).
    pub(crate) perf_proportional_gain2: F32,
    pub(crate) perf_reset_iters: u32,
    /// Target GPU utilization for the performance controller in %.
    pub(crate) perf_tgt_utilization: u32,
    /// Power sampling period in milliseconds.
    pub(crate) power_sample_period: u32,
    /// PPM (?) filter time constant in milliseconds.
    pub(crate) ppm_filter_time_constant_ms: u32,
    /// PPM (?) filter PID integral gain.
    pub(crate) ppm_ki: F32,
    /// PPM (?) filter PID proportional gain.
    pub(crate) ppm_kp: F32,
    /// Power consumption filter time constant (periods?)
    pub(crate) pwr_filter_time_constant: u32,
    /// Power consumption filter PID integral gain.
    pub(crate) pwr_integral_gain: F32,
    pub(crate) pwr_integral_min_clamp: u32,
    pub(crate) pwr_min_duty_cycle: u32,
    pub(crate) pwr_proportional_gain: F32,
    /// Power sample period in base clocks, used when not an integer number of ms
    pub(crate) pwr_sample_period_aic_clks: Option<u32>,
    pub(crate) se_engagement_criteria: i32,
    pub(crate) se_filter_time_constant: u32,
    pub(crate) se_filter_time_constant_1: u32,
    pub(crate) se_inactive_threshold: u32,
    pub(crate) se_ki: F32,
    pub(crate) se_ki_1: F32,
    pub(crate) se_kp: F32,
    pub(crate) se_kp_1: F32,
    pub(crate) se_reset_criteria: u32,

    /// Minimum voltage for the CS/AFR SRAM power domain in microvolts.
    pub(crate) csafr_min_sram_microvolt: u32,

    pub(crate) num_clusters: u32,
}

/// Dynamic (fetched from hardware/DT) configuration.
#[derive(Debug)]
pub(crate) struct DynConfig {
    /// Base physical address of the UAT TTB (from DT reserved memory region).
    pub(crate) uat_ttb_base: u64,
    /// GPU ID configuration read from hardware.
    pub(crate) id: GpuIdConfig,
    /// Power calibration configuration for this specific chip/device.
    pub(crate) pwr: PwrConfig,
}

/// Specific GPU ID configuration fetched from SGX MMIO registers.
#[derive(Debug)]
pub(crate) struct GpuIdConfig {
    /// GPU silicon revision ID (firmware enum).
    pub(crate) gpu_rev_id: GpuRevisionID,
    /// Maximum number of GPU cores per cluster.
    pub(crate) num_cores: u32,
    /// Number of frags per cluster.
    pub(crate) num_frags: u32,
}

/// Configurable CS/AFR GPU power settings from the device tree.
#[derive(Debug)]
pub(crate) struct CsAfrPwrConfig {
    /// GPU CS performance state list.
    pub(crate) perf_states_cs: Vec<PState>,
    /// GPU AFR performance state list.
    pub(crate) perf_states_afr: Vec<PState>,

    /// CS leakage coefficient per die.
    pub(crate) leak_coef_cs: Vec<F32>,
    /// AFR leakage coefficient per die.
    pub(crate) leak_coef_afr: Vec<F32>,
}

/// Configurable GPU power settings from the device tree.
#[derive(Debug)]
pub(crate) struct PwrConfig {
    /// GPU performance state list.
    pub(crate) perf_states: Vec<PState>,

    /// Core leakage coefficient per cluster.
    pub(crate) core_leak_coef: Vec<F32>,
    /// SRAM leakage coefficient per cluster.
    pub(crate) sram_leak_coef: Vec<F32>,

    pub(crate) csafr: Option<CsAfrPwrConfig>,

    /// Maximum total power of the GPU in milliwatts.
    pub(crate) max_power_mw: u32,
    /// Maximum frequency of the GPU in megahertz.
    pub(crate) max_freq_mhz: u32,

    /// Minimum performance state to start at.
    pub(crate) perf_base_pstate: u32,
    /// Maximum enabled performance state.
    pub(crate) perf_max_pstate: u32,
}
