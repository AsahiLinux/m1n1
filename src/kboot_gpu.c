/* SPDX-License-Identifier: MIT */

#include "kboot.h"
#include "adt.h"
#include "assert.h"
#include "soc.h"
#include "utils.h"

#include "libfdt/libfdt.h"

#define bail(...)                                                                                  \
    do {                                                                                           \
        printf(__VA_ARGS__);                                                                       \
        return -1;                                                                                 \
    } while (0)

u32 t8103_pwr_scale[] = {0, 63, 80, 108, 150, 198, 210};

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

int dt_set_gpu(void *dt)
{
    u32 *pwr_scale;
    u32 pwr_scale_count;
    switch (chip_id) {
        case T8103:
            pwr_scale = t8103_pwr_scale;
            pwr_scale_count = ARRAY_SIZE(t8103_pwr_scale);
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

    if (perf_state_count != pwr_scale_count)
        bail("ADT: GPU: expected %d perf states but got %d\n", pwr_scale_count, perf_state_count);

    u32 perf_states_len;
    const struct {
        u32 freq;
        u32 volt;
    } * perf_states;

    perf_states = adt_getprop(adt, sgx, "perf-states", &perf_states_len);
    if (!perf_states || perf_states_len != sizeof(*perf_states) * perf_state_count)
        bail("ADT: GPU: invalid perf-states length\n");

    u64 max_pwr[16];

    for (u32 i = 0; i < pwr_scale_count; i++)
        max_pwr[i] = (u64)perf_states[i].volt * (u64)pwr_scale[i];

    for (u32 i = 0; i < pwr_scale_count; i++)
        max_pwr[i] = 100 * max_pwr[i] / max_pwr[pwr_scale_count - 1];

    u32 i = 0;
    int opp;
    fdt_for_each_subnode(opp, dt, opps)
    {
        if (i >= perf_state_count)
            bail("FDT: GPU: Expected %d operating points, but found more\n", perf_state_count);

        if (fdt_setprop_inplace_u32(dt, opp, "opp-microvolt", perf_states[i].volt * 1000))
            bail("FDT: GPU: Failed to set opp-microvolt for PS %d\n", i);

        if (fdt_setprop_inplace_u64(dt, opp, "opp-hz", perf_states[i].freq))
            bail("FDT: GPU: Failed to set opp-hz for PS %d\n", i);

        if (fdt_setprop_inplace_u32(dt, opp, "apple,opp-rel-power", max_pwr[i]))
            bail("FDT: GPU: Failed to set apple,opp-rel-power for PS %d\n", i);

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
