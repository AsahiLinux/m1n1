// SPDX-License-Identifier: GPL-2.0-only OR MIT
#![allow(clippy::unusual_byte_groupings)]

use versions::versions;

use super::hw;
use super::raw;
use super::types::*;
use crate::adt::{self, ADTNode};
use crate::f32;
use crate::float::F32;
use crate::gpu::hw::{DynConfig, GpuIdConfig, HwConfig, PState};
use crate::println;
use alloc::vec::Vec;
use core::ffi::c_void;
use core::mem;

/// Number of bits in a page offset.
pub(crate) const UAT_PGBIT: usize = 14;
/// UAT page size.
pub(crate) const UAT_PGSZ: usize = 1 << UAT_PGBIT;

/// UAT input address space
pub(crate) const UAT_IAS: usize = 39;

/// Lower/user top VA
pub(crate) const IOVA_USER_TOP: u64 = 1 << (UAT_IAS as u64);

/// Address of a special dummy page?
pub(crate) const IOVA_UNK_PAGE: u64 = IOVA_USER_TOP - 2 * UAT_PGSZ as u64;

pub(crate) const IOVA_KERN_TIMESTAMP_RANGE_START: u64 = 0xffffffae10000000;

#[versions(AGX)]
pub(crate) struct InitDataBuilder;

#[versions(AGX)]
impl InitDataBuilder::ver {
    /// Create the HwDataShared1 structure, which is used in two places in InitData.
    fn hw_shared1(cfg: &hw::HwConfig, ret: &mut raw::HwDataShared1) {
        ret.unk_a4 = cfg.shared1_a4;
        for (i, val) in cfg.shared1_tab.iter().enumerate() {
            ret.table[i] = *val;
        }
    }

    fn init_curve(
        curve: &mut raw::HwDataShared2Curve,
        unk_0: u32,
        unk_4: u32,
        t1: &[u16],
        t2: &[i16],
        t3: &[Vec<i32>],
    ) {
        curve.unk_0 = unk_0;
        curve.unk_4 = unk_4;
        (*curve.t1)[..t1.len()].copy_from_slice(t1);
        (*curve.t1)[t1.len()..].fill(t1[0]);
        (*curve.t2)[..t2.len()].copy_from_slice(t2);
        (*curve.t2)[t2.len()..].fill(t2[0]);
        for (i, a) in curve.t3.iter_mut().enumerate() {
            a.fill(0x3ffffff);
            if i < t3.len() {
                let b = &t3[i];
                (**a)[..b.len()].copy_from_slice(b);
            }
        }
    }

    /// Create the HwDataShared2 structure, which is used in two places in InitData.
    fn hw_shared2(cfg: &hw::HwConfig, pwr: &hw::PwrConfig, ret: &mut raw::HwDataShared2) {
        ret.unk_28 = Array::new([0xff; 16]);
        ret.g14 = Default::default();
        ret.unk_508 = cfg.shared2_unk_508;

        for (i, val) in cfg.shared2_tab.iter().enumerate() {
            ret.table[i] = *val;
        }

        let curve_cfg = match cfg.shared2_curves.as_ref() {
            None => return,
            Some(a) => a,
        };

        let mut t1 = Vec::new();
        let mut t3 = Vec::new();

        for _ in 0..curve_cfg.t3_scales.len() {
            t3.push(Vec::new());
        }

        for (i, ps) in pwr.perf_states.iter().enumerate() {
            let t3_coef = curve_cfg.t3_coefs[i];
            if t3_coef == 0 {
                t1.push(0xffff);
                for j in t3.iter_mut() {
                    j.push(0x3ffffff);
                }
                continue;
            }

            let f_khz = (ps.freq_hz / 1000) as u64;
            let v_max = ps.max_volt_mv() as u64;

            t1.push(
                (1000000000 * (curve_cfg.t1_coef as u64) / (f_khz * v_max))
                    .try_into()
                    .unwrap(),
            );

            for (j, scale) in curve_cfg.t3_scales.iter().enumerate() {
                t3[j].push(
                    (t3_coef as u64 * 1000000100 * *scale as u64 / (f_khz * v_max * 6))
                        .try_into()
                        .unwrap(),
                );
            }
        }

        ret.g14.unk_14 = 0x6000000;
        Self::init_curve(
            &mut ret.g14.curve1,
            0,
            0x20000000,
            &[0xffff],
            &[0x0f07],
            &[],
        );

        Self::init_curve(&mut ret.g14.curve2, 7, 0x80000000, &t1, curve_cfg.t2, &t3);
    }

    /// Create the HwDataShared3 structure, which is used in two places in InitData.
    fn hw_shared3(cfg: &hw::HwConfig, ret: &mut raw::HwDataShared3) {
        if !cfg.shared3_tab.is_empty() {
            ret.unk_0 = 1;
            ret.unk_4 = 500;
            ret.unk_8 = cfg.shared3_unk;
            ret.table.copy_from_slice(cfg.shared3_tab);
            ret.unk_4c = 1;
        }
    }

    fn t81xx_data(cfg: &hw::HwConfig, pwr: &hw::PwrConfig, _ret: &mut raw::T81xxData) {
        let _perf_max_pstate = pwr.perf_max_pstate;
        match cfg.chip_id {
            0x8103 | 0x8112 => {
                #[ver(V < V13_3)]
                {
                    _ret.unk_d8c = 0x80000000;
                    _ret.unk_d90 = 4;
                    _ret.unk_d9c = f32!(0.6);
                    _ret.unk_da4 = f32!(0.4);
                    _ret.unk_dac = f32!(0.38552);
                    _ret.unk_db8 = f32!(65536.0);
                    _ret.unk_dbc = f32!(13.56);
                    _ret.max_pstate_scaled = 100 * _perf_max_pstate;
                }
            }
            _ => (),
        }
    }

    /// Create the HwDataA structure. This mostly contains power-related configuration.
    fn hwdata_a(cfg: &hw::HwConfig, pwr: &hw::PwrConfig, raw: &mut raw::HwDataA::ver) {
        let period_ms = cfg.power_sample_period;
        let period_s = F32::from(period_ms) / f32!(1000.0);
        let ppm_filter_tc_periods = cfg.ppm_filter_time_constant_ms / period_ms;
        #[ver(V >= V13_0B4)]
        let ppm_filter_tc_ms_rounded = ppm_filter_tc_periods * period_ms;
        let ppm_filter_a = f32!(1.0) / ppm_filter_tc_periods.into();
        let perf_filter_a = f32!(1.0) / cfg.perf_filter_time_constant.into();
        let perf_filter_a2 = f32!(1.0) / cfg.perf_filter_time_constant2.into();
        let avg_power_target_filter_a = f32!(1.0) / cfg.avg_power_target_filter_tc.into();
        let avg_power_filter_tc_periods = cfg.avg_power_filter_tc_ms / period_ms;
        #[ver(V >= V13_0B4)]
        let avg_power_filter_tc_ms_rounded = avg_power_filter_tc_periods * period_ms;
        let avg_power_filter_a = f32!(1.0) / avg_power_filter_tc_periods.into();
        let pwr_filter_a = f32!(1.0) / cfg.pwr_filter_time_constant.into();

        let base_ps = pwr.perf_base_pstate;
        let base_ps_scaled = 100 * base_ps;
        let max_ps = pwr.perf_max_pstate;
        let max_ps_scaled = 100 * max_ps;
        let boost_ps_count = max_ps - base_ps;

        let base_clock_khz = cfg.base_clock_hz / 1000;

        let clocks_per_period_coarse = base_clock_khz * cfg.power_sample_period;
        let clocks_per_period = cfg
            .pwr_sample_period_aic_clks
            .unwrap_or(clocks_per_period_coarse);

        #[allow(unused_variables)]
        let filter_a = f32!(1.0) / cfg.se_filter_time_constant.into();
        #[allow(unused_variables)]
        let filter_1_a = f32!(1.0) / cfg.se_filter_time_constant_1.into();

        raw.clocks_per_period = clocks_per_period;
        #[ver(V >= V13_0B4)]
        raw.clocks_per_period_2 = clocks_per_period;
        raw.pwr_status = 4;
        raw.unk_10 = f32!(1.0);
        raw.actual_pstate = 1;
        raw.tgt_pstate = 1;
        raw.base_pstate_scaled = base_ps_scaled;
        raw.unk_40 = 1;
        raw.max_pstate_scaled = max_ps_scaled;
        raw.min_pstate_scaled = 100;
        raw.unk_64c = 625;
        raw.pwr_filter_a_neg = f32!(1.0) - pwr_filter_a;
        raw.pwr_filter_a = pwr_filter_a;
        raw.pwr_integral_gain = cfg.pwr_integral_gain;
        raw.pwr_integral_min_clamp = cfg.pwr_integral_min_clamp.into();
        raw.max_power_1 = pwr.max_power_mw.into();
        raw.pwr_proportional_gain = cfg.pwr_proportional_gain;
        raw.pwr_pstate_related_k = -F32::from(max_ps_scaled) / pwr.max_power_mw.into();
        raw.pwr_pstate_max_dc_offset = cfg.pwr_min_duty_cycle as i32 - max_ps_scaled as i32;
        raw.max_pstate_scaled_2 = max_ps_scaled;
        raw.max_power_2 = pwr.max_power_mw;
        raw.max_pstate_scaled_3 = max_ps_scaled;
        raw.ppm_filter_tc_periods_x4 = ppm_filter_tc_periods * 4;
        raw.ppm_filter_a_neg = f32!(1.0) - ppm_filter_a;
        raw.ppm_filter_a = ppm_filter_a;
        raw.ppm_ki_dt = cfg.ppm_ki * period_s;
        raw.unk_6fc = f32!(65536.0);
        raw.ppm_kp = cfg.ppm_kp;
        raw.pwr_min_duty_cycle = cfg.pwr_min_duty_cycle;
        raw.max_pstate_scaled_4 = max_ps_scaled;
        raw.unk_71c = f32!(0.0);
        raw.max_power_3 = pwr.max_power_mw;
        raw.cur_power_mw_2 = 0x0;
        raw.ppm_filter_tc_ms = cfg.ppm_filter_time_constant_ms;

        #[ver(V >= V13_0B4)]
        raw.ppm_filter_tc_clks = ppm_filter_tc_ms_rounded * base_clock_khz;

        raw.perf_tgt_utilization = cfg.perf_tgt_utilization;
        raw.perf_boost_min_util = cfg.perf_boost_min_util;
        raw.perf_boost_ce_step = cfg.perf_boost_ce_step;
        raw.perf_reset_iters = cfg.perf_reset_iters;
        raw.unk_774 = 6;
        raw.unk_778 = 1;
        raw.perf_filter_drop_threshold = cfg.perf_filter_drop_threshold;
        raw.perf_filter_a_neg = f32!(1.0) - perf_filter_a;
        raw.perf_filter_a2_neg = f32!(1.0) - perf_filter_a2;
        raw.perf_filter_a = perf_filter_a;
        raw.perf_filter_a2 = perf_filter_a2;
        raw.perf_ki = cfg.perf_integral_gain;
        raw.perf_ki2 = cfg.perf_integral_gain2;
        raw.perf_integral_min_clamp = cfg.perf_integral_min_clamp.into();
        raw.unk_79c = f32!(95.0);
        raw.perf_kp = cfg.perf_proportional_gain;
        raw.perf_kp2 = cfg.perf_proportional_gain2;
        raw.boost_state_unk_k = F32::from(boost_ps_count) / f32!(0.95);
        raw.base_pstate_scaled_2 = base_ps_scaled;
        raw.max_pstate_scaled_5 = max_ps_scaled;
        raw.base_pstate_scaled_3 = base_ps_scaled;
        raw.perf_tgt_utilization_2 = cfg.perf_tgt_utilization;
        raw.base_pstate_scaled_4 = base_ps_scaled;
        raw.unk_7fc = f32!(65536.0);
        raw.pwr_min_duty_cycle_2 = cfg.pwr_min_duty_cycle.into();
        raw.max_pstate_scaled_6 = max_ps_scaled.into();
        raw.max_freq_mhz = pwr.max_freq_mhz;
        raw.pwr_min_duty_cycle_3 = cfg.pwr_min_duty_cycle;
        raw.min_pstate_scaled_4 = f32!(100.0);
        raw.max_pstate_scaled_7 = max_ps_scaled;
        raw.unk_alpha_neg = f32!(0.8);
        raw.unk_alpha = f32!(0.2);
        raw.fast_die0_sensor_mask = U64(cfg.fast_sensor_mask[0]);
        #[ver(G >= G14X)]
        raw.fast_die1_sensor_mask = U64(cfg.fast_sensor_mask[1]);
        raw.fast_die0_release_temp_cc = 100 * cfg.fast_die0_release_temp;
        raw.unk_87c = cfg.da.unk_87c;
        raw.unk_880 = 0x4;
        raw.unk_894 = f32!(1.0);

        raw.fast_die0_ki_dt = cfg.fast_die0_integral_gain * period_s;
        raw.unk_8a8 = f32!(65536.0);
        raw.fast_die0_kp = cfg.fast_die0_proportional_gain;
        raw.pwr_min_duty_cycle_4 = cfg.pwr_min_duty_cycle;
        raw.max_pstate_scaled_8 = max_ps_scaled;
        raw.max_pstate_scaled_9 = max_ps_scaled;
        raw.fast_die0_prop_tgt_delta = 100 * cfg.fast_die0_prop_tgt_delta;
        raw.unk_8cc = cfg.da.unk_8cc;
        raw.max_pstate_scaled_10 = max_ps_scaled;
        raw.max_pstate_scaled_11 = max_ps_scaled;
        raw.unk_c2c = 1;
        raw.power_zone_count = cfg.power_zones.len() as u32;
        raw.max_power_4 = pwr.max_power_mw;
        raw.max_power_5 = pwr.max_power_mw;
        raw.max_power_6 = pwr.max_power_mw;
        raw.avg_power_target_filter_a_neg = f32!(1.0) - avg_power_target_filter_a;
        raw.avg_power_target_filter_a = avg_power_target_filter_a;
        raw.avg_power_target_filter_tc_x4 = 4 * cfg.avg_power_target_filter_tc;
        raw.avg_power_target_filter_tc_xperiod = period_ms * cfg.avg_power_target_filter_tc;
        #[ver(V >= V13_0B4)]
        raw.avg_power_target_filter_tc_clks =
            period_ms * cfg.avg_power_target_filter_tc * base_clock_khz;
        raw.avg_power_filter_tc_periods_x4 = 4 * avg_power_filter_tc_periods;
        raw.avg_power_filter_a_neg = f32!(1.0) - avg_power_filter_a;
        raw.avg_power_filter_a = avg_power_filter_a;
        raw.avg_power_ki_dt = cfg.avg_power_ki_only * period_s;
        raw.unk_d20 = f32!(65536.0);
        raw.avg_power_kp = cfg.avg_power_kp;
        raw.avg_power_min_duty_cycle = cfg.avg_power_min_duty_cycle;
        raw.max_pstate_scaled_12 = max_ps_scaled;
        raw.max_pstate_scaled_13 = max_ps_scaled;
        raw.max_power_7 = pwr.max_power_mw.into();
        raw.max_power_8 = pwr.max_power_mw;
        raw.avg_power_filter_tc_ms = cfg.avg_power_filter_tc_ms;
        #[ver(V >= V13_0B4)]
        raw.avg_power_filter_tc_clks = avg_power_filter_tc_ms_rounded * base_clock_khz;
        raw.max_pstate_scaled_14 = max_ps_scaled;

        #[ver(V >= V13_0B4)]
        {
            let extra = &mut raw.unk_e10_0;
            extra.unk_38 = 4;
            extra.unk_3c = 8000;
            extra.gpu_se_inactive_threshold = cfg.se_inactive_threshold;
            extra.gpu_se_engagement_criteria = cfg.se_engagement_criteria;
            extra.gpu_se_reset_criteria = cfg.se_reset_criteria;
            extra.unk_54 = 50;
            extra.unk_58 = 0x1;
            extra.gpu_se_filter_a_neg = f32!(1.0) - filter_a;
            extra.gpu_se_filter_1_a_neg = f32!(1.0) - filter_1_a;
            extra.gpu_se_filter_a = filter_a;
            extra.gpu_se_filter_1_a = filter_1_a;
            extra.gpu_se_ki_dt = cfg.se_ki * period_s;
            extra.gpu_se_ki_1_dt = cfg.se_ki_1 * period_s;
            extra.unk_7c = f32!(65536.0);
            extra.gpu_se_kp = cfg.se_kp;
            extra.gpu_se_kp_1 = cfg.se_kp_1;

            #[ver(V >= V13_3)]
            extra.unk_8c = 100;
            #[ver(V < V13_3)]
            extra.unk_8c = 40;

            extra.max_pstate_scaled_1 = max_ps_scaled;
            extra.unk_9c = f32!(8000.0);
            extra.unk_a0 = 1400;
            extra.gpu_se_filter_time_constant_ms = cfg.se_filter_time_constant * period_ms;
            extra.gpu_se_filter_time_constant_1_ms = cfg.se_filter_time_constant_1 * period_ms;
            extra.gpu_se_filter_time_constant_clks =
                U64((cfg.se_filter_time_constant * clocks_per_period_coarse).into());
            extra.gpu_se_filter_time_constant_1_clks =
                U64((cfg.se_filter_time_constant_1 * clocks_per_period_coarse).into());
            extra.unk_c4 = f32!(65536.0);
            extra.unk_114 = f32!(65536.0);
            extra.unk_124 = 40;
            extra.max_pstate_scaled_2 = max_ps_scaled;
        }
        raw.fast_die0_sensor_mask_2 = U64(cfg.fast_sensor_mask[0]);
        #[ver(G >= G14X)]
        raw.fast_die1_sensor_mask_2 = U64(cfg.fast_sensor_mask[1]);
        raw.unk_e24 = cfg.da.unk_e24;
        raw.unk_e28 = 1;
        raw.fast_die0_sensor_mask_alt = U64(cfg.fast_sensor_mask_alt[0]);
        #[ver(G >= G14X)]
        raw.fast_die1_sensor_mask_alt = U64(cfg.fast_sensor_mask_alt[1]);
        #[ver(V < V13_0B4)]
        raw.fast_die0_sensor_present = U64(cfg.fast_die0_sensor_present as u64);
        raw.unk_163c = 1;
        raw.unk_3644 = 0;
        raw.unk_3ce8 = 1;

        Self::t81xx_data(cfg, pwr, &mut raw.t81xx_data);
        Self::hw_shared1(cfg, &mut raw.hws1);
        Self::hw_shared2(cfg, pwr, &mut raw.hws2);
        Self::hw_shared3(cfg, &mut raw.hws3);

        for i in 0..pwr.perf_states.len() {
            raw.sram_k[i] = cfg.sram_k;
        }

        for (i, coef) in pwr.core_leak_coef.iter().enumerate() {
            raw.core_leak_coef[i] = *coef;
        }

        for (i, coef) in pwr.sram_leak_coef.iter().enumerate() {
            raw.sram_leak_coef[i] = *coef;
        }

        #[ver(V >= V13_0B4)]
        if let Some(csafr) = pwr.csafr.as_ref() {
            for (i, coef) in csafr.leak_coef_afr.iter().enumerate() {
                raw.aux_leak_coef.cs_1[i] = *coef;
                raw.aux_leak_coef.cs_2[i] = *coef;
            }

            for (i, coef) in csafr.leak_coef_cs.iter().enumerate() {
                raw.aux_leak_coef.afr_1[i] = *coef;
                raw.aux_leak_coef.afr_2[i] = *coef;
            }
        }

        for i in 0..cfg.num_clusters as usize {
            if let Some(coef_a) = cfg.unk_coef_a.get(i) {
                (*raw.unk_coef_a1[i])[..coef_a.len()].copy_from_slice(coef_a);
                (*raw.unk_coef_a2[i])[..coef_a.len()].copy_from_slice(coef_a);
            }
            if let Some(coef_b) = cfg.unk_coef_b.get(i) {
                (*raw.unk_coef_b1[i])[..coef_b.len()].copy_from_slice(coef_b);
                (*raw.unk_coef_b2[i])[..coef_b.len()].copy_from_slice(coef_b);
            }
        }

        for (i, pz) in cfg.power_zones.iter().enumerate() {
            raw.power_zones[i].target = pz.target;
            raw.power_zones[i].target_off = pz.target - pz.target_offset;
            raw.power_zones[i].filter_tc_x4 = 4 * pz.filter_tc;
            raw.power_zones[i].filter_tc_xperiod = period_ms * pz.filter_tc;
            let filter_a = f32!(1.0) / pz.filter_tc.into();
            raw.power_zones[i].filter_a = filter_a;
            raw.power_zones[i].filter_a_neg = f32!(1.0) - filter_a;
            #[ver(V >= V13_0B4)]
            raw.power_zones[i].unk_10 = 1320000000;
        }

        #[ver(V >= V13_0B4 && G >= G14X)]
        for (i, j) in raw.hws2.g14.curve2.t1.iter().enumerate() {
            raw.unk_hws2[i] = if *j == 0xffff { 0 } else { j / 2 };
        }
    }

    /// Create the HwDataB structure. This mostly contains GPU-related configuration.
    fn hwdata_b(cfg: &hw::HwConfig, dyncfg: &hw::DynConfig, raw: &mut raw::HwDataB::ver) {
        // Userspace VA map related
        #[ver(V < V13_0B4)]
        raw.unk_0 = U64(0x13_00000000);
        raw.unk_8 = U64(0x14_00000000);
        #[ver(V < V13_0B4)]
        raw.unk_10 = U64(0x1_00000000);
        raw.unk_18 = U64(0xffc00000);
        // USC start
        raw.unk_20 = U64(0); // U64(0x11_00000000),
        raw.unk_28 = U64(0); // U64(0x11_00000000),

        // Unknown page
        raw.unk_30 = U64(IOVA_UNK_PAGE); //unk_30: U64(0x6f_ffff8000),
        raw.timestamp_area_base = U64(IOVA_KERN_TIMESTAMP_RANGE_START);
        // TODO: yuv matrices
        raw.chip_id = cfg.chip_id;
        raw.unk_454 = cfg.db.unk_454;
        raw.unk_458 = 0x1;
        raw.unk_460 = 0x1;
        raw.unk_464 = 0x1;
        raw.unk_468 = 0x1;
        raw.unk_47c = 0x1;
        raw.unk_484 = 0x1;
        raw.unk_48c = 0x1;
        raw.base_clock_khz = cfg.base_clock_hz / 1000;
        raw.power_sample_period = cfg.power_sample_period;
        raw.unk_49c = 0x1;
        raw.unk_4a0 = 0x1;
        raw.unk_4a4 = 0x1;
        raw.unk_4c0 = 0x1f;
        raw.unk_4e0 = U64(cfg.db.unk_4e0);
        raw.unk_4f0 = 0x1;
        raw.unk_4f4 = 0x1;
        raw.unk_504 = 0x31;
        raw.unk_524 = 0x1; // use_secure_cache_flush
        raw.unk_534 = cfg.db.unk_534;
        raw.num_frags = dyncfg.id.num_frags * cfg.num_clusters;
        raw.unk_554 = 0x1;
        raw.uat_ttb_base = U64(dyncfg.uat_ttb_base);
        raw.gpu_core_id = cfg.gpu_core as u32;
        raw.gpu_rev_id = dyncfg.id.gpu_rev_id as u32;
        raw.num_cores = dyncfg.id.num_cores * cfg.num_clusters;
        raw.max_pstate = dyncfg.pwr.perf_states.len() as u32 - 1;
        #[ver(V < V13_0B4)]
        raw.num_pstates = dyncfg.pwr.perf_states.len() as u32;
        #[ver(V < V13_0B4)]
        raw.min_sram_volt = cfg.min_sram_microvolt / 1000;
        #[ver(V < V13_0B4)]
        raw.unk_ab8 = cfg.db.unk_ab8;
        #[ver(V < V13_0B4)]
        raw.unk_abc = cfg.db.unk_abc;
        #[ver(V < V13_0B4)]
        raw.unk_ac0 = 0x1020;

        #[ver(V >= V13_0B4)]
        raw.unk_ae4 = Array::new([0x0, 0x3, 0x7, 0x7]);
        #[ver(V < V13_0B4)]
        raw.unk_ae4 = Array::new([0x0, 0xf, 0x3f, 0x3f]);
        raw.unk_b10 = 0x1;
        raw.timer_offset = U64(0);
        raw.unk_b24 = 0x1;
        raw.unk_b28 = 0x1;
        raw.unk_b2c = 0x1;
        raw.unk_b30 = cfg.db.unk_b30;
        #[ver(V >= V13_0B4)]
        raw.unk_b38_0 = 1;
        #[ver(V >= V13_0B4)]
        raw.unk_b38_4 = 1;
        raw.unk_b38 = Array::new([0xffffffff; 12]);
        #[ver(V >= V13_0B4 && V < V13_3)]
        raw.unk_c3c = 0x19;
        #[ver(V >= V13_3)]
        raw.unk_c3c = 0x1a;

        #[ver(V >= V13_3)]
        for i in 0..16 {
            raw.unk_arr_0[i] = i as u32;
        }

        let base_ps = dyncfg.pwr.perf_base_pstate as usize;
        let max_ps = dyncfg.pwr.perf_max_pstate as usize;
        let base_freq = dyncfg.pwr.perf_states[base_ps].freq_hz;
        let max_freq = dyncfg.pwr.perf_states[max_ps].freq_hz;

        for (i, ps) in dyncfg.pwr.perf_states.iter().enumerate() {
            raw.frequencies[i] = ps.freq_hz / 1000000;
            for (j, mv) in ps.volt_mv.iter().enumerate() {
                let sram_mv = (*mv).max(cfg.min_sram_microvolt / 1000);
                raw.voltages[i][j] = *mv;
                raw.voltages_sram[i][j] = sram_mv;
            }
            for j in ps.volt_mv.len()..raw.voltages[i].len() {
                raw.voltages[i][j] = raw.voltages[i][0];
                raw.voltages_sram[i][j] = raw.voltages_sram[i][0];
            }
            raw.sram_k[i] = cfg.sram_k;
            raw.rel_max_powers[i] = ps.pwr_mw * 100 / dyncfg.pwr.max_power_mw;
            raw.rel_boost_freqs[i] = if i > base_ps {
                (ps.freq_hz - base_freq) / ((max_freq - base_freq) / 100)
            } else {
                0
            };
        }

        #[ver(V >= V13_0B4)]
        if let Some(csafr) = dyncfg.pwr.csafr.as_ref() {
            let aux = &mut raw.aux_ps;
            aux.cs_max_pstate = (csafr.perf_states_cs.len() - 1).try_into().unwrap();
            aux.afr_max_pstate = (csafr.perf_states_afr.len() - 1).try_into().unwrap();

            for (i, ps) in csafr.perf_states_cs.iter().enumerate() {
                aux.cs_frequencies[i] = ps.freq_hz / 1000000;
                for (j, mv) in ps.volt_mv.iter().enumerate() {
                    let sram_mv = (*mv).max(cfg.csafr_min_sram_microvolt / 1000);
                    aux.cs_voltages[i][j] = *mv;
                    aux.cs_voltages_sram[i][j] = sram_mv;
                }
            }

            for (i, ps) in csafr.perf_states_afr.iter().enumerate() {
                aux.afr_frequencies[i] = ps.freq_hz / 1000000;
                for (j, mv) in ps.volt_mv.iter().enumerate() {
                    let sram_mv = (*mv).max(cfg.csafr_min_sram_microvolt / 1000);
                    aux.afr_voltages[i][j] = *mv;
                    aux.afr_voltages_sram[i][j] = sram_mv;
                }
            }
        }

        // Special case override for T602x
        #[ver(G == G14X)]
        if dyncfg.id.gpu_rev_id == hw::GpuRevisionID::B1 {
            raw.gpu_rev_id = hw::GpuRevisionID::B0 as u32;
        }
    }

    /// Create the Globals structure, which contains global firmware config including more power
    /// configuration data and globals used to exchange state between the firmware and driver.
    fn globals(cfg: &hw::HwConfig, pwr: &hw::PwrConfig, raw: &mut raw::Globals::ver) {
        let period_ms = cfg.power_sample_period;
        let period_s = F32::from(period_ms) / f32!(1000.0);
        let avg_power_filter_tc_periods = cfg.avg_power_filter_tc_ms / period_ms;

        let max_ps = pwr.perf_max_pstate;
        let max_ps_scaled = 100 * max_ps;

        //ktrace_enable: 0xffffffff,
        raw.ktrace_enable = 0;
        #[ver(V >= V13_2)]
        raw.unk_24_0 = 3000;
        raw.unk_24 = 0;
        #[ver(V >= V13_0B4)]
        raw.debug = 0;
        raw.unk_28 = 1;
        #[ver(G >= G14X)]
        raw.unk_2c_0 = 1;
        #[ver(V >= V13_0B4 && G < G14X)]
        raw.unk_2c_0 = 0;
        raw.unk_2c = 1;
        raw.unk_30 = 0;
        raw.unk_34 = 120;

        raw.sub.unk_54 = cfg.global_unk_54;
        raw.sub.unk_56 = 40;
        raw.sub.unk_58 = 0xffff;
        raw.sub.unk_5e = U32(1);
        raw.sub.unk_66 = U32(1);

        raw.unk_8900 = 1;
        raw.pending_submissions = 0;
        raw.max_power = pwr.max_power_mw;
        raw.max_pstate_scaled = max_ps_scaled;
        raw.max_pstate_scaled_2 = max_ps_scaled;
        raw.max_pstate_scaled_3 = max_ps_scaled;
        raw.power_zone_count = cfg.power_zones.len() as u32;
        raw.avg_power_filter_tc_periods = avg_power_filter_tc_periods;
        raw.avg_power_ki_dt = cfg.avg_power_ki_only * period_s;
        raw.avg_power_kp = cfg.avg_power_kp;
        raw.avg_power_min_duty_cycle = cfg.avg_power_min_duty_cycle;
        raw.avg_power_target_filter_tc = cfg.avg_power_target_filter_tc;
        raw.unk_89bc = cfg.da.unk_8cc;
        raw.fast_die0_release_temp = 100 * cfg.fast_die0_release_temp;
        raw.unk_89c4 = cfg.da.unk_87c;
        raw.fast_die0_prop_tgt_delta = 100 * cfg.fast_die0_prop_tgt_delta;
        raw.fast_die0_kp = cfg.fast_die0_proportional_gain;
        raw.fast_die0_ki_dt = cfg.fast_die0_integral_gain * period_s;
        raw.unk_89e0 = 1;
        raw.max_power_2 = pwr.max_power_mw;
        raw.ppm_kp = cfg.ppm_kp;
        raw.ppm_ki_dt = cfg.ppm_ki * period_s;
        #[ver(V >= V13_0B4)]
        raw.unk_89f4_8 = 1;
        raw.unk_89f4 = 0;
        #[ver(V >= V13_0B4)]
        raw.idle_off_standby_timer = cfg.idle_off_standby_timer_default;
        #[ver(V >= V13_0B4)]
        raw.unk_hws2_4 = cfg.unk_hws2_4.map(Array::new).unwrap_or_default();
        #[ver(V >= V13_0B4)]
        raw.unk_hws2_24 = cfg.unk_hws2_24;
        raw.unk_900c = 1;
        #[ver(V >= V13_0B4)]
        raw.unk_9010_0 = 1;
        #[ver(V >= V13_0B4)]
        raw.unk_903c = 1;
        #[ver(V < V13_0B4)]
        raw.unk_903c = 0;
        raw.fault_control = 0xb;
        raw.do_init = 1;
        raw.progress_check_interval_3d = 40;
        raw.progress_check_interval_ta = 10;
        raw.progress_check_interval_cl = 250;
        #[ver(V >= V13_0B4)]
        raw.unk_1102c_0 = 1;
        #[ver(V >= V13_0B4)]
        raw.unk_1102c_4 = 1;
        #[ver(V >= V13_0B4)]
        raw.unk_1102c_8 = 100;
        #[ver(V >= V13_0B4)]
        raw.unk_1102c_c = 1;
        raw.idle_off_delay_ms = cfg.idle_off_delay_ms;
        raw.fender_idle_off_delay_ms = cfg.fender_idle_off_delay_ms;
        raw.fw_early_wake_timeout_ms = cfg.fw_early_wake_timeout_ms;
        raw.cl_context_switch_timeout_ms = 40;
        #[ver(V >= V13_0B4)]
        raw.cl_kill_timeout_ms = 50;
        #[ver(V >= V13_0B4)]
        raw.unk_11edc = 0;
        #[ver(V >= V13_0B4)]
        raw.unk_11efc = 0;

        Self::hw_shared1(cfg, &mut raw.hws1);
        Self::hw_shared2(cfg, pwr, &mut raw.hws2);
        Self::hw_shared3(cfg, &mut raw.hws3);

        for (i, pz) in cfg.power_zones.iter().enumerate() {
            raw.power_zones[i].target = pz.target;
            raw.power_zones[i].target_off = pz.target - pz.target_offset;
            raw.power_zones[i].filter_tc = pz.filter_tc;
        }

        if let Some(tab) = cfg.global_tab.as_ref() {
            for (i, x) in tab.iter().enumerate() {
                raw.unk_118ec[i] = *x;
            }
            raw.unk_118e8 = 1;
        }
    }
}

extern "C" {
    static chip_id: u32;
}

#[repr(C)]
pub struct CPerfState {
    freq: u32,
    volt: u32,
}

#[repr(C)]
pub struct CAuxPerfState {
    volt: u64,
    freq: u64,
}

fn chip_hwcfg() -> Option<&'static HwConfig> {
    let chp_id = unsafe { chip_id };
    let is_studio = match ADTNode::root() {
        Ok(node) => {
            let prime_compat = node.compatible(0).unwrap_or("");
            prime_compat == "J375cAP" || prime_compat == ("J475cAP")
        }
        _ => false,
    };
    Some(match chp_id {
        0x8103 => &hw::t8103::HWCONFIG,
        0x8112 => &hw::t8112::HWCONFIG,
        0x6000 => &hw::t600x::HWCONFIG_T6000,
        0x6001 => {
            if is_studio {
                &hw::t600x::HWCONFIG_T6001_STUDIO
            } else {
                &hw::t600x::HWCONFIG_T6001
            }
        }
        0x6002 => &hw::t600x::HWCONFIG_T6002,
        0x6020 => &hw::t602x::HWCONFIG_T6020,
        0x6021 => {
            if is_studio {
                &hw::t602x::HWCONFIG_T6021_STUDIO
            } else {
                &hw::t602x::HWCONFIG_T6021
            }
        }
        0x6022 => &hw::t602x::HWCONFIG_T6022,
        _ => {
            println!("Unknown chip id: 0x{:x}", chp_id);
            return None;
        }
    })
}

#[no_mangle]
pub unsafe extern "C" fn rust_gpu_initdata_size(
    compat_maj: u32,
    compat_min: u32,
    data_a: *mut usize,
    data_b: *mut usize,
    globals: *mut usize,
) -> i32 {
    let hwcfg = if let Some(h) = chip_hwcfg() {
        h
    } else {
        return -1;
    };
    unsafe {
        match (hwcfg.gpu_gen, hwcfg.gpu_variant, compat_maj, compat_min) {
            (hw::GpuGen::G13, _, 12, 3) => {
                *data_a = mem::size_of::<raw::HwDataAG13V12_3>();
                *data_b = mem::size_of::<raw::HwDataBG13V12_3>();
                *globals = mem::size_of::<raw::GlobalsG13V12_3>();
            }
            (hw::GpuGen::G14, hw::GpuVariant::G, 12, 4) => {
                *data_a = mem::size_of::<raw::HwDataAG14V12_4>();
                *data_b = mem::size_of::<raw::HwDataBG14V12_4>();
                *globals = mem::size_of::<raw::GlobalsG14V12_4>();
            }
            (hw::GpuGen::G13, _, 13, 5) => {
                *data_a = mem::size_of::<raw::HwDataAG13V13_5>();
                *data_b = mem::size_of::<raw::HwDataBG13V13_5>();
                *globals = mem::size_of::<raw::GlobalsG13V13_5>();
            }
            (hw::GpuGen::G14, hw::GpuVariant::G, 13, 5) => {
                *data_a = mem::size_of::<raw::HwDataAG14V13_5>();
                *data_b = mem::size_of::<raw::HwDataBG14V13_5>();
                *globals = mem::size_of::<raw::GlobalsG14V13_5>();
            }
            (hw::GpuGen::G14, _, 13, 5) => {
                *data_a = mem::size_of::<raw::HwDataAG14XV13_5>();
                *data_b = mem::size_of::<raw::HwDataBG14XV13_5>();
                *globals = mem::size_of::<raw::GlobalsG14XV13_5>();
            }
            _ => {
                println!(
                    "Unknown gpu type or firmware: {:?}, {:?}, {}, {}",
                    hwcfg.gpu_gen, hwcfg.gpu_variant, compat_maj, compat_min
                );
                return -1;
            }
        }
    }
    0
}

fn raw_rev_to_id(rev: u32) -> Option<hw::GpuRevisionID> {
    Some(match rev {
        0x00 => hw::GpuRevisionID::A0,
        0x01 => hw::GpuRevisionID::A1,
        0x10 => hw::GpuRevisionID::B0,
        0x11 => hw::GpuRevisionID::B1,
        0x20 => hw::GpuRevisionID::C0,
        0x21 => hw::GpuRevisionID::C1,
        _ => return None,
    })
}

#[repr(C)]
pub struct InitdataInputs {
    perf_state_table_count: usize,
    perf_state_count: usize,
    c_perf_states: *const CPerfState,
    max_pwr: *const u32,
    core_leak: *const F32,
    sram_leak: *const F32,
    cs_leak: *const F32,
    afr_leak: *const F32,
    n_perf_states_cs: usize,
    pstates_cs: *const CAuxPerfState,
    n_perf_states_afr: usize,
    pstates_afr: *const CAuxPerfState,
    compat_maj: u32,
    compat_min: u32,
}

unsafe fn read32(ptr: u64) -> u32 {
    unsafe { (ptr as *const u32).read_volatile() }
}

#[no_mangle]
pub unsafe extern "C" fn rust_fill_gpu_initdata(
    ins: *const InitdataInputs,
    data_a: *mut c_void,
    data_b: *mut c_void,
    globals: *mut c_void,
) -> i32 {
    let ins = unsafe { &*ins };
    let hwcfg = if let Some(h) = chip_hwcfg() {
        h
    } else {
        return -1;
    };
    let mut sgx_trace = [None; 8];
    let sgx = match ADTNode::from_path_trace("/arm-io/sgx", Some(&mut sgx_trace)) {
        Ok(sgx) => sgx,
        Err(e) => {
            println!("ADT: GPU: Failed to get sgx {:?}", e);
            return -1;
        }
    };
    let gpu_base = match adt::get_reg_container(&sgx_trace, "reg", 0) {
        Ok(reg) => reg.0,
        Err(e) => {
            println!("ADT: GPU: Failed to get gpu base {:?}", e);
            return -1;
        }
    };
    // SAFETY: reading gpu registers here
    let id_version = unsafe { read32(gpu_base + 0xd04000) };
    let num_cores = unsafe { read32(gpu_base + 0xd04010) } & 0xff;
    let gpu_rev_raw = (id_version >> 8) & 0xff;
    let compatible = ADTNode::root()
        .and_then(|r| Ok(r.compatible(0)))
        .unwrap_or(None);
    let base_pstate = match compatible {
        /* ADT has no "gpu-perf-base-pstate", use 3 as the downstream Linux DT */
        Some("J274AP") => 3,
        /* Apple does not do this, but they probably should */
        Some("J474sAP") => 3,
        _ => sgx
            .named_prop("gpu-perf-base-pstate")
            .and_then(|prop| prop.u32())
            .unwrap_or(1),
    };
    let uat_ttb_base = match sgx
        .named_prop("gpu-region-base")
        .and_then(|prop| prop.u64())
    {
        Ok(t) => t,
        Err(e) => {
            println!("ADT: GPU: Failed to get uat ttb base {:?}", e);
            return -1;
        }
    };

    let mut perf_states = Vec::with_capacity(ins.perf_state_count);
    for i in 0..ins.perf_state_count {
        let mut volt_mv = Vec::with_capacity(ins.perf_state_table_count);
        for j in 0..ins.perf_state_table_count {
            volt_mv.push(unsafe {
                ins.c_perf_states
                    .offset((i + j * ins.perf_state_count) as isize)
                    .read()
                    .volt
            });
        }
        perf_states.push(PState {
            volt_mv,
            pwr_mw: unsafe { ins.max_pwr.offset(i as isize).read() } / 1000,
            freq_hz: unsafe { ins.c_perf_states.offset(i as isize).read().freq },
        });
    }

    let mut core_leak_coef = Vec::with_capacity(ins.perf_state_table_count);
    let mut sram_leak_coef = Vec::with_capacity(ins.perf_state_table_count);
    for i in 0..ins.perf_state_table_count {
        core_leak_coef.push(unsafe { ins.core_leak.offset(i as isize).read() });
        sram_leak_coef.push(unsafe { ins.sram_leak.offset(i as isize).read() });
    }
    let csafr = if hwcfg.has_csafr {
        let mut leak_coef_cs = Vec::with_capacity(hwcfg.num_dies as usize);
        let mut leak_coef_afr = Vec::with_capacity(hwcfg.num_dies as usize);
        for i in 0..hwcfg.num_dies {
            leak_coef_cs.push(unsafe { ins.cs_leak.offset(i as isize).read() });
            leak_coef_afr.push(unsafe { ins.afr_leak.offset(i as isize).read() });
        }
        let mut perf_states_cs = Vec::with_capacity(ins.n_perf_states_cs);
        let mut perf_states_afr = Vec::with_capacity(ins.n_perf_states_afr);
        for i in 0..ins.n_perf_states_cs {
            let mut volts = Vec::with_capacity(hwcfg.num_dies as usize);
            for j in 0..hwcfg.num_dies as usize {
                // convert micro volt to milli volt
                volts.push(unsafe {
                    (ins.pstates_cs
                        .offset((i + j * ins.n_perf_states_cs) as isize)
                        .read()
                        .volt as u32)
                        / 1000
                })
            }
            perf_states_cs.push(hw::PState {
                volt_mv: volts,
                pwr_mw: 0,
                freq_hz: unsafe { ins.pstates_cs.offset(i as isize).read().freq as u32 },
            });
        }
        for i in 0..ins.n_perf_states_afr {
            let mut volts = Vec::with_capacity(hwcfg.num_dies as usize);
            for j in 0..hwcfg.num_dies as usize {
                // convert micro volt to milli volt
                volts.push(unsafe {
                    (ins.pstates_afr
                        .offset((i + j * ins.n_perf_states_afr) as isize)
                        .read()
                        .volt as u32)
                        / 1000
                })
            }
            perf_states_afr.push(hw::PState {
                volt_mv: volts,
                pwr_mw: 0,
                freq_hz: unsafe { ins.pstates_afr.offset(i as isize).read().freq as u32 },
            });
        }
        Some(hw::CsAfrPwrConfig {
            perf_states_cs,
            perf_states_afr,
            leak_coef_cs,
            leak_coef_afr,
        })
    } else {
        None
    };
    let pwrcfg = hw::PwrConfig {
        core_leak_coef,
        sram_leak_coef,

        max_power_mw: perf_states.iter().map(|a| a.pwr_mw).max().unwrap(),
        max_freq_mhz: perf_states.iter().map(|a| a.freq_hz).max().unwrap() / 1_000_000,

        perf_base_pstate: base_pstate,
        perf_max_pstate: perf_states.len() as u32 - 1,

        perf_states,
        csafr,
    };
    let gpu_rev_id = if let Some(r) = raw_rev_to_id(gpu_rev_raw) {
        r
    } else {
        println!("Unknown gpu revision: {}", gpu_rev_raw);
        return -1;
    };
    let dyncfg = DynConfig {
        uat_ttb_base,
        pwr: pwrcfg,
        id: GpuIdConfig {
            gpu_rev_id,
            num_cores,
            num_frags: num_cores,
        },
    };
    unsafe {
        match (
            hwcfg.gpu_gen,
            hwcfg.gpu_variant,
            ins.compat_maj,
            ins.compat_min,
        ) {
            (hw::GpuGen::G13, _, 12, 3) => {
                let data_a = &mut *(data_a as *mut raw::HwDataAG13V12_3);
                InitDataBuilderG13V12_3::hwdata_a(hwcfg, &dyncfg.pwr, data_a);
                let data_b = &mut *(data_b as *mut raw::HwDataBG13V12_3);
                InitDataBuilderG13V12_3::hwdata_b(hwcfg, &dyncfg, data_b);
                let globals = &mut *(globals as *mut raw::GlobalsG13V12_3);
                InitDataBuilderG13V12_3::globals(hwcfg, &dyncfg.pwr, globals);
            }
            (hw::GpuGen::G14, hw::GpuVariant::G, 12, 4) => {
                let data_a = &mut *(data_a as *mut raw::HwDataAG14V12_4);
                InitDataBuilderG14V12_4::hwdata_a(hwcfg, &dyncfg.pwr, data_a);
                let data_b = &mut *(data_b as *mut raw::HwDataBG14V12_4);
                InitDataBuilderG14V12_4::hwdata_b(hwcfg, &dyncfg, data_b);
                let globals = &mut *(globals as *mut raw::GlobalsG14V12_4);
                InitDataBuilderG14V12_4::globals(hwcfg, &dyncfg.pwr, globals);
            }
            (hw::GpuGen::G13, _, 13, 5) => {
                let data_a = &mut *(data_a as *mut raw::HwDataAG13V13_5);
                InitDataBuilderG13V13_5::hwdata_a(hwcfg, &dyncfg.pwr, data_a);
                let data_b = &mut *(data_b as *mut raw::HwDataBG13V13_5);
                InitDataBuilderG13V13_5::hwdata_b(hwcfg, &dyncfg, data_b);
                let globals = &mut *(globals as *mut raw::GlobalsG13V13_5);
                InitDataBuilderG13V13_5::globals(hwcfg, &dyncfg.pwr, globals);
            }
            (hw::GpuGen::G14, hw::GpuVariant::G, 13, 5) => {
                let data_a = &mut *(data_a as *mut raw::HwDataAG14V13_5);
                InitDataBuilderG14V13_5::hwdata_a(hwcfg, &dyncfg.pwr, data_a);
                let data_b = &mut *(data_b as *mut raw::HwDataBG14V13_5);
                InitDataBuilderG14V13_5::hwdata_b(hwcfg, &dyncfg, data_b);
                let globals = &mut *(globals as *mut raw::GlobalsG14V13_5);
                InitDataBuilderG14V13_5::globals(hwcfg, &dyncfg.pwr, globals);
            }
            (hw::GpuGen::G14, _, 13, 5) => {
                let data_a = &mut *(data_a as *mut raw::HwDataAG14XV13_5);
                InitDataBuilderG14XV13_5::hwdata_a(hwcfg, &dyncfg.pwr, data_a);
                let data_b = &mut *(data_b as *mut raw::HwDataBG14XV13_5);
                InitDataBuilderG14XV13_5::hwdata_b(hwcfg, &dyncfg, data_b);
                let globals = &mut *(globals as *mut raw::GlobalsG14XV13_5);
                InitDataBuilderG14XV13_5::globals(hwcfg, &dyncfg.pwr, globals);
            }
            _ => {
                println!(
                    "Unknown gpu type or firmware: {:?}, {:?}, {}, {}",
                    hwcfg.gpu_gen, hwcfg.gpu_variant, ins.compat_maj, ins.compat_min
                );
                return -1;
            }
        }
    }
    0
}
