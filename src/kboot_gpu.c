/* SPDX-License-Identifier: MIT */

#include "kboot.h"
#include "adt.h"
#include "assert.h"
#include "firmware.h"
#include "math.h"
#include "pmgr.h"
#include "soc.h"
#include "utils.h"

#include "libfdt/libfdt.h"

#define bail(...)                                                                                  \
    do {                                                                                           \
        printf(__VA_ARGS__);                                                                       \
        return -1;                                                                                 \
    } while (0)

#define MAX_PSTATES  16
#define MAX_CLUSTERS 8

struct perf_state {
    u32 freq;
    u32 volt;
};

static int get_core_counts(u32 *count, u32 nclusters, u32 ncores)
{
    u64 base;
    pmgr_adt_power_enable("/arm-io/sgx");

    int adt_sgx_path[8];
    if (adt_path_offset_trace(adt, "/arm-io/sgx", adt_sgx_path) < 0)
        bail("ADT: GPU: Failed to get sgx\n");

    if (adt_get_reg(adt, adt_sgx_path, "reg", 0, &base, NULL) < 0)
        bail("ADT: GPU: Failed to get sgx reg 0\n");

    u32 cores_lo = read32(base + 0xd01500);
    u32 cores_hi = read32(base + 0xd01514);

    u64 cores = (((u64)cores_hi) << 32) | cores_lo;

    for (u32 i = 0; i < nclusters; i++) {
        count[i] = __builtin_popcount(cores & MASK(ncores));
        cores >>= ncores;
    }

    return 0;
}

static void adjust_leakage(float *val, u32 clusters, u32 *cores, u32 max, float uncore_fraction)
{
    for (u32 i = 0; i < clusters; i++) {
        float uncore = val[i] * uncore_fraction;
        float core = val[i] - uncore;

        val[i] = uncore + (cores[i] / (float)max) * core;
    }
}

static void load_fuses(float *out, u32 count, u64 base, u32 start, u32 width, float scale,
                       float offset, bool flip)
{
    for (u32 i = 0; i < count; i++) {
        base += (start / 32) * 4;
        start &= 31;

        u32 low = read32(base);
        u32 high = read32(base + 4);
        u32 val = (((((u64)high) << 32) | low) >> start) & MASK(width);

        float fval = (float)val * scale + offset;

        if (flip)
            out[count - i - 1] = fval;
        else
            out[i] = fval;

        start += width;
    }
}

static u32 t8103_pwr_scale[] = {0, 63, 80, 108, 150, 198, 210};

static int calc_power_t8103(u32 count, u32 table_count, const struct perf_state *core,
                            const struct perf_state *sram, u32 *max_pwr, float *core_leak,
                            float *sram_leak)
{
    UNUSED(sram);
    UNUSED(core_leak);
    UNUSED(sram_leak);
    u32 *pwr_scale;
    u32 pwr_scale_count;
    u32 core_count;
    u32 max_cores;

    switch (chip_id) {
        case T8103:
            pwr_scale = t8103_pwr_scale;
            pwr_scale_count = ARRAY_SIZE(t8103_pwr_scale);
            max_cores = 8;
            break;
        default:
            bail("ADT: GPU: Unsupported chip\n");
    }

    if (get_core_counts(&core_count, 1, max_cores))
        return -1;

    if (table_count != 1)
        bail("ADT: GPU: expected 1 perf state table but got %d\n", table_count);

    if (count != pwr_scale_count)
        bail("ADT: GPU: expected %d perf states but got %d\n", pwr_scale_count, count);

    for (u32 i = 0; i < pwr_scale_count; i++)
        max_pwr[i] = (u32)core[i].volt * (u32)pwr_scale[i] * 100;

    core_leak[0] = 1000.0;
    sram_leak[0] = 45.0;

    adjust_leakage(core_leak, 1, &core_count, max_cores, 0.12);
    adjust_leakage(sram_leak, 1, &core_count, max_cores, 0.2);

    return 0;
}

static int calc_power_t600x(u32 count, u32 table_count, const struct perf_state *core,
                            const struct perf_state *sram, u32 *max_pwr, float *core_leak,
                            float *sram_leak)
{
    float s_sram, k_sram, s_core, k_core;
    float dk_core, dk_sram;
    float imax = 1000;

    u32 nclusters = 0;
    u32 ncores = 0;
    u32 core_count[MAX_CLUSTERS];

    bool simple_exps = false;
    bool adjust_leakages = true;

    switch (chip_id) {
        case T6002:
            nclusters += 4;
            load_fuses(core_leak + 4, 4, 0x22922bc1b8, 25, 13, 2, 2, true);
            load_fuses(sram_leak + 4, 4, 0x22922bc1cc, 4, 9, 1, 1, true);
            // fallthrough
        case T6001:
            nclusters += 2;
        case T6000:
            nclusters += 2;
            load_fuses(core_leak + 0, min(4, nclusters), 0x2922bc1b8, 25, 13, 2, 2, false);
            load_fuses(sram_leak + 0, min(4, nclusters), 0x2922bc1cc, 4, 9, 1, 1, false);

            s_sram = 4.3547606;
            k_sram = 0.024927923;
            // macOS difference: macOS uses a misbehaved piecewise function here
            // Since it's obviously wrong, let's just use only the first component
            s_core = 1.48461742;
            k_core = 0.39013552;
            dk_core = 8.558;
            dk_sram = 0.05;

            ncores = 8;
            adjust_leakages = true;
            imax = 26.0;
            break;
        case T8112:
            nclusters = 1;
            load_fuses(core_leak, 1, 0x23d2c84dc, 30, 13, 2, 2, false);
            load_fuses(sram_leak, 1, 0x23d2c84b0, 15, 9, 1, 1, false);

            s_sram = 3.61619841;
            k_sram = 0.0529281;
            // macOS difference: macOS uses a misbehaved piecewise function here
            // Since it's obviously wrong, let's just use only the first component
            s_core = 1.21356187;
            k_core = 0.43328839;
            dk_core = 9.83196;
            dk_sram = 0.07828;

            simple_exps = true;
            ncores = 10;
            adjust_leakages = false; // pre-adjusted?
            imax = 24.0;
            break;
    }

    if (get_core_counts(core_count, nclusters, ncores))
        return -1;

    printf("FDT: GPU: Core counts: ");
    for (u32 i = 0; i < nclusters; i++) {
        printf("%d ", core_count[i]);
    }
    printf("\n");

    if (adjust_leakages) {
        adjust_leakage(core_leak, nclusters, core_count, ncores, 0.0825);
        adjust_leakage(sram_leak, nclusters, core_count, ncores, 0.2247);
    }

    if (table_count != nclusters)
        bail("ADT: GPU: expected %d perf state tables but got %d\n", nclusters, table_count);

    max_pwr[0] = 0;

    for (u32 i = 1; i < count; i++) {
        u32 total_mw = 0;

        for (u32 j = 0; j < nclusters; j++) {
            // macOS difference: macOS truncates Hz to integer MHz before doing this math.
            // That's probably wrong, so let's not do that.

            float mw = 0;
            size_t idx = j * count + i;

            mw += sram[idx].volt / 1000.f * sram_leak[j] * k_sram *
                  expf(sram[idx].volt / 1000.f * s_sram);
            mw += core[idx].volt / 1000.f * core_leak[j] * k_core *
                  expf(core[idx].volt / 1000.f * s_core);

            float sbase = sram[idx].volt / 750.f;
            float sram_v_p;
            if (simple_exps)
                sram_v_p = sbase * sbase; // v ^ 2
            else
                sram_v_p = sbase * sbase * sbase; // v ^ 3
            mw += dk_sram * (sram[idx].freq / 1000000.f) * sram_v_p;

            float cbase = core[idx].volt / 750.f;
            float core_v_p;
            if (simple_exps || core[idx].volt < 750)
                core_v_p = cbase * cbase; // v ^ 2
            else
                core_v_p = cbase * cbase * cbase; // v ^ 3
            mw += dk_core * (core[idx].freq / 1000000.f) * core_v_p;

            if (mw > imax * core[idx].volt)
                mw = imax * core[idx].volt;

            total_mw += mw;
        }

        max_pwr[i] = total_mw * 1000;
    }

    return 0;
}

static int dt_set_region(void *dt, int sgx, const char *name, const char *path)
{
    u64 base, size;
    char prop[64];

    snprintf(prop, sizeof(prop), "%s-base", name);
    if (ADT_GETPROP(adt, sgx, prop, &base) < 0 || !base)
        bail("ADT: GPU: failed to find %s property\n", prop);

    snprintf(prop, sizeof(prop), "%s-size", name);
    if (ADT_GETPROP(adt, sgx, prop, &size) < 0 || !base)
        bail("ADT: GPU: failed to find %s property\n", prop);

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        bail("FDT: GPU: failed to find %s node\n", path);

    fdt64_t reg[2];

    fdt64_st(&reg[0], base);
    fdt64_st(&reg[1], size);

    if (fdt_setprop_inplace(dt, node, "reg", reg, sizeof(reg)))
        bail("FDT: GPU: failed to set reg prop for %s\n", path);

    return 0;
}

int fdt_set_float_array(void *dt, int node, const char *name, float *val, int count)
{
    fdt32_t data[MAX_CLUSTERS];

    if (count > MAX_CLUSTERS)
        bail("FDT: GPU: fdt_set_float_array() with too many values\n");

    memcpy(data, val, sizeof(float) * count);
    for (int i = 0; i < count; i++) {
        data[i] = cpu_to_fdt32(data[i]);
    }

    if (fdt_setprop_inplace(dt, node, name, data, sizeof(u32) * count))
        bail("FDT: GPU: Failed to set %s\n", name);

    return 0;
}

int dt_set_gpu(void *dt)
{
    int (*calc_power)(u32 count, u32 table_count, const struct perf_state *perf,
                      const struct perf_state *sram, u32 *max_pwr, float *core_leak,
                      float *sram_leak);

    printf("FDT: GPU: Initializing GPU info\n");

    switch (chip_id) {
        case T8103:
            calc_power = calc_power_t8103;
            break;
        case T6000:
        case T6001:
        case T6002:
        case T8112:
            calc_power = calc_power_t600x;
            break;
        default:
            printf("ADT: GPU: unsupported chip!\n");
            return 0;
    }

    int gpu = fdt_path_offset(dt, "gpu");
    if (gpu < 0) {
        printf("FDT: GPU: gpu alias not found in device tree\n");
        return 0;
    }

    int len;
    const fdt32_t *opps_ph = fdt_getprop(dt, gpu, "operating-points-v2", &len);
    if (!opps_ph || len != 4)
        bail("FDT: GPU: operating-points-v2 not found\n");

    int opps = fdt_node_offset_by_phandle(dt, fdt32_ld(opps_ph));
    if (opps < 0)
        bail("FDT: GPU: node for phandle %u not found\n", fdt32_ld(opps_ph));

    int sgx = adt_path_offset(adt, "/arm-io/sgx");
    if (sgx < 0)
        bail("ADT: GPU: /arm-io/sgx node not found\n");

    u32 perf_state_count;
    if (ADT_GETPROP(adt, sgx, "perf-state-count", &perf_state_count) < 0 || !perf_state_count)
        bail("ADT: GPU: missing perf-state-count\n");

    u32 perf_state_table_count;
    if (ADT_GETPROP(adt, sgx, "perf-state-table-count", &perf_state_table_count) < 0 ||
        !perf_state_table_count)
        bail("ADT: GPU: missing perf-state-table-count\n");

    if (perf_state_count > MAX_PSTATES)
        bail("ADT: GPU: perf-state-count too large\n");

    if (perf_state_table_count > MAX_CLUSTERS)
        bail("ADT: GPU: perf-state-table-count too large\n");

    u32 perf_states_len;
    const struct perf_state *perf_states, *perf_states_sram;

    perf_states = adt_getprop(adt, sgx, "perf-states", &perf_states_len);
    if (!perf_states ||
        perf_states_len != sizeof(*perf_states) * perf_state_count * perf_state_table_count)
        bail("ADT: GPU: invalid perf-states length\n");

    perf_states_sram = adt_getprop(adt, sgx, "perf-states-sram", &perf_states_len);
    if (perf_states_sram &&
        perf_states_len != sizeof(*perf_states) * perf_state_count * perf_state_table_count)
        bail("ADT: GPU: invalid perf-states-sram length\n");

    u32 max_pwr[MAX_PSTATES];
    float core_leak[MAX_CLUSTERS];
    float sram_leak[MAX_CLUSTERS];

    if (calc_power(perf_state_count, perf_state_table_count, perf_states, perf_states_sram, max_pwr,
                   core_leak, sram_leak))
        return -1;

    printf("FDT: GPU: Max power table: ");
    for (u32 i = 0; i < perf_state_count; i++) {
        printf("%d ", max_pwr[i]);
    }
    printf("\nFDT: GPU: Core leakage table: ");
    for (u32 i = 0; i < perf_state_table_count; i++) {
        printf("%d.%03d ", (int)core_leak[i], ((int)(core_leak[i] * 1000) % 1000));
    }
    printf("\nFDT: GPU: SRAM leakage table: ");
    for (u32 i = 0; i < perf_state_table_count; i++) {
        printf("%d.%03d ", (int)sram_leak[i], ((int)(sram_leak[i] * 1000) % 1000));
    }
    printf("\n");

    if (fdt_set_float_array(dt, gpu, "apple,core-leak-coef", core_leak, perf_state_table_count))
        return -1;

    if (fdt_set_float_array(dt, gpu, "apple,sram-leak-coef", sram_leak, perf_state_table_count))
        return -1;

    if (firmware_set_fdt(dt, gpu, "apple,firmware-version", &os_firmware))
        return -1;

    const struct fw_version_info *compat;

    switch (os_firmware.version) {
        case V12_3_1:
            compat = &fw_versions[V12_3];
            break;
        default:
            compat = &os_firmware;
            break;
    }

    if (firmware_set_fdt(dt, gpu, "apple,firmware-compat", compat))
        return -1;

    u32 i = 0;
    int opp;
    fdt_for_each_subnode(opp, dt, opps)
    {
        fdt32_t volts[MAX_CLUSTERS];

        for (u32 j = 0; j < perf_state_table_count; j++) {
            volts[j] = cpu_to_fdt32(perf_states[i + j * perf_state_count].volt * 1000);
        }

        if (i >= perf_state_count)
            bail("FDT: GPU: Expected %d operating points, but found more\n", perf_state_count);

        if (fdt_setprop_inplace(dt, opp, "opp-microvolt", &volts,
                                sizeof(u32) * perf_state_table_count))
            bail("FDT: GPU: Failed to set opp-microvolt for PS %d\n", i);

        if (fdt_setprop_inplace_u64(dt, opp, "opp-hz", perf_states[i].freq))
            bail("FDT: GPU: Failed to set opp-hz for PS %d\n", i);

        if (fdt_setprop_inplace_u32(dt, opp, "opp-microwatt", max_pwr[i]))
            bail("FDT: GPU: Failed to set opp-microwatt for PS %d\n", i);

        i++;
    }

    if (i != perf_state_count)
        bail("FDT: GPU: Expected %d operating points, but found %d\n", perf_state_count, i);

    if (dt_set_region(dt, sgx, "gfx-handoff", "/reserved-memory/uat-handoff"))
        return -1;
    if (dt_set_region(dt, sgx, "gfx-shared-region", "/reserved-memory/uat-pagetables"))
        return -1;
    if (dt_set_region(dt, sgx, "gpu-region", "/reserved-memory/uat-ttbs"))
        return -1;

    return 0;
}
