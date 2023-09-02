/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "dart.h"
#include "pmgr.h"
#include "utils.h"

/* ISP DART has some quirks we must work around */

#define DART_T8020_ENABLED_STREAMS 0xfc
#define DART_T8020_STREAM_COMMAND  0x20
#define DART_T8020_STREAM_SELECT   0x34
#define DART_T8020_TCR_OFF         0x100
#define DART_T8020_TTBR            0x200

#define DART_T8020_TCR_TRANSLATE_ENABLE      BIT(7)
#define DART_T8020_STREAM_COMMAND_INVALIDATE BIT(20)

struct dart_tunables {
    u64 offset;
    u64 clear;
    u64 set;
};

static void isp_ctrr_init_t8020(u64 base, const struct dart_tunables *config, u32 length)
{
    /* DART error handler gets stuck w/o these */
    write32(base + DART_T8020_ENABLED_STREAMS, 0x1);
    write32(base + 0x2f0, 0x0);
    write32(base + DART_T8020_STREAM_SELECT, 0xffffffff);
    write32(base + DART_T8020_STREAM_COMMAND, DART_T8020_STREAM_COMMAND_INVALIDATE);

    /* I think these lock CTRR? Configurable __TEXT read-only region? */
    int count = length / sizeof(*config);
    for (int i = 0; i < count; i++) {
        u64 offset = config->offset & 0xffff;
        u32 set = config->set & 0xffffffff;
        mask32(base + offset, read32(base + offset), set);
        config++;
    }

    write32(base + DART_T8020_TCR_OFF, DART_T8020_TCR_TRANSLATE_ENABLE);
    write32(base + 0x13c, 0x20000);
}

static void isp_ctrr_init_t6000(u64 base, const struct dart_tunables *config, u32 length)
{
    write32(base + DART_T8020_ENABLED_STREAMS, 0x1);
    write32(base + 0x2f0, 0x0);
    write32(base + DART_T8020_STREAM_SELECT, 0xffff); // diff from t8020
    write32(base + DART_T8020_STREAM_COMMAND, 0x0);

    int count = length / sizeof(*config);
    for (int i = 0; i < count; i++) {
        u64 offset = config->offset & 0xffff;
        u32 set = config->set & 0xffffffff;
        mask32(base + offset, read32(base + offset), set);
        config++;
    }

    write32(base + DART_T8020_TCR_OFF, DART_T8020_TCR_TRANSLATE_ENABLE);
    write32(base + 0x13c, 0x20000);
}

int isp_init(void)
{
    int err = 0;

    const char *isp_path = "/arm-io/isp";
    const char *dart_path = "/arm-io/dart-isp";

    int adt_path[8];
    int node = adt_path_offset_trace(adt, dart_path, adt_path);
    if (node < 0) {
        isp_path = "/arm-io/isp0";
        dart_path = "/arm-io/dart-isp0";
        node = adt_path_offset_trace(adt, dart_path, adt_path);
    }
    if (node < 0)
        return 0;

    if (pmgr_adt_power_enable(isp_path) < 0)
        return -1;

    enum dart_type_t type;
    const char *type_s;
    if (adt_is_compatible(adt, node, "dart,t8020")) {
        type = DART_T8020;
        type_s = "t8020";
    } else if (adt_is_compatible(adt, node, "dart,t6000")) {
        type = DART_T6000;
        type_s = "t6000";
    } else if (adt_is_compatible(adt, node, "dart,t8110")) {
        type = DART_T8110;
        type_s = "t8110";
    } else {
        printf("isp: dart %s is of an unknown type\n", dart_path);
        return -1;
    }

    int dart_domain_count = 3; // TODO get from dt
    for (int index = 0; index < dart_domain_count; index++) {
        u64 base;
        err = adt_get_reg(adt, adt_path, "reg", index, &base, NULL);
        if (err < 0)
            goto out;

        u32 length;
        char prop[32] = "dart-tunables-instance";
        snprintf(prop, sizeof(prop), "dart-tunables-instance-%u", index);
        const struct dart_tunables *config = adt_getprop(adt, node, prop, &length);
        if (!config || !length) {
            printf("isp: Error getting ADT node %s property %s.\n", isp_path, prop);
            err = -1;
            goto out;
        }

        err = adt_get_reg(adt, adt_path, "reg", index, &base, NULL);
        if (err < 0)
            goto out;

        switch (type) {
            case DART_T8020:
                isp_ctrr_init_t8020(base, config, length);
                break;
            case DART_T6000:
                isp_ctrr_init_t6000(base, config, length);
                break;
            case DART_T8110:
                printf("isp: warning: dart type %s not tested yet!\n", type_s);
                isp_ctrr_init_t8020(base, config, length);
                break;
        }
    }

out:
    pmgr_adt_power_disable(isp_path);
    return err;
}
