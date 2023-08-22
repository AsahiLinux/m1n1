/* SPDX-License-Identifier: MIT */

#include "adt.h"
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

int isp_init(void)
{
    int err = 0;
    const char *path = "/arm-io/isp";
    const char *dart_path = "/arm-io/dart-isp";

    if (pmgr_adt_power_enable(path) < 0)
        return -1;

    int adt_path[8];
    int node = adt_path_offset_trace(adt, dart_path, adt_path);
    if (node < 0) {
        printf("isp: Error getting node %s\n", dart_path);
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
            printf("isp: Error getting ADT node %s property %s.\n", path, prop);
            err = -1;
            goto out;
        }

        err = adt_get_reg(adt, adt_path, "reg", index, &base, NULL);
        if (err < 0)
            goto out;

        /* DART error handler gets stuck w/o these */
        write32(base + DART_T8020_ENABLED_STREAMS, 0x1);
        write32(base + 0x2f0, 0x0);
        write32(base + DART_T8020_STREAM_SELECT, 0xffffffff);
        write32(base + DART_T8020_STREAM_COMMAND, DART_T8020_STREAM_COMMAND_INVALIDATE);

        /* I think these lock CTRR? Coproc __TEXT read-only region? */
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

out:
    pmgr_adt_power_disable(path);
    return err;
}
