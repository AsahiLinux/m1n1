/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "dart.h"
#include "firmware.h"
#include "pmgr.h"
#include "soc.h"
#include "utils.h"

#define ISP_ASC_VERSION 0x1800000

#define ISP_VER_T8103 0xb0090
#define ISP_VER_T6000 0xb3091
#define ISP_VER_T8112 0xc1090
#define ISP_VER_T6020 0xc3091

// PMGR offset to enable to get the version info to work
#define ISP_PMGR_T8103 0x4018
#define ISP_PMGR_T6000 0x8
#define ISP_PMGR_T6020 0x4008

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

static void isp_ctrr_init_t6000(u64 base, const struct dart_tunables *config, u32 length, int index)
{
    write32(base + DART_T8020_ENABLED_STREAMS, 0x1);
    write32(base + 0x2f0, 0x0);
    mask32(base + DART_T8020_STREAM_SELECT, read32(base + DART_T8020_STREAM_SELECT), 0xffff);
    // write32(base + DART_T8020_STREAM_SELECT, 0xffff); // diff from t8020
    write32(base + DART_T8020_STREAM_COMMAND, 0x0);

    int count = length / sizeof(*config);
    for (int i = 0; i < count; i++) {
        u64 offset = config->offset & 0xffff;
        u32 set = config->set & 0xffffffff;
        mask32(base + offset, read32(base + offset), set);
        config++;
    }

    write32(base + DART_T8020_TCR_OFF, DART_T8020_TCR_TRANSLATE_ENABLE);
    u32 val = 0x20000;
    if (!index)
        val |= 0x100;
    write32(base + 0x13c, val);
}

static bool isp_initialized = false;
static u64 heap_phys, heap_iova, heap_size, heap_top;

int isp_get_heap(u64 *phys, u64 *iova, u64 *size)
{
    if (!isp_initialized)
        return -1;

    *phys = heap_phys;
    *iova = heap_iova;
    *size = heap_size;
    return 0;
}

int isp_init(void)
{
    int err = 0;

    const char *isp_path = "/arm-io/isp";
    const char *dart_path = "/arm-io/dart-isp";

    int adt_path[8], adt_isp_path[8];
    int isp_node = adt_path_offset_trace(adt, isp_path, adt_isp_path);
    int node = adt_path_offset_trace(adt, dart_path, adt_path);
    if (node < 0 || isp_node < 0) {
        isp_path = "/arm-io/isp0";
        dart_path = "/arm-io/dart-isp0";
        isp_node = adt_path_offset_trace(adt, isp_path, adt_isp_path);
        node = adt_path_offset_trace(adt, dart_path, adt_path);
    }
    if (node < 0)
        return 0;

    if (pmgr_adt_power_enable(isp_path) < 0)
        return -1;

    u64 isp_base;
    u64 pmgr_base;
    err = adt_get_reg(adt, adt_isp_path, "reg", 0, &isp_base, NULL);
    if (err)
        return err;

    err = adt_get_reg(adt, adt_isp_path, "reg", 1, &pmgr_base, NULL);
    if (err)
        return err;

    u32 pmgr_off;
    switch (chip_id) {
        case T8103:
        case T8112:
            pmgr_off = ISP_PMGR_T8103;
            break;
        case T6000 ... T6002:
            pmgr_off = ISP_PMGR_T6000;
            break;
        case T6020 ... T6022:
            pmgr_off = ISP_PMGR_T6020;
            break;
        default:
            printf("isp: Unsupported SoC\n");
            return -1;
    }

    err = pmgr_set_mode(pmgr_base + pmgr_off, PMGR_PS_ACTIVE);
    if (err) {
        printf("isp: Failed to power on\n");
        return err;
    }

    u32 ver_rev = read32(isp_base + ISP_ASC_VERSION);
    printf("isp: Version 0x%x\n", ver_rev);

    pmgr_set_mode(pmgr_base + pmgr_off, PMGR_PS_PWRGATE);

    /* TODO: confirm versions */
    switch (ver_rev) {
        case ISP_VER_T8103:
        case ISP_VER_T8112:
            switch (os_firmware.version) {
                case V12_3 ... V12_4:
                    heap_top = 0x1800000;
                    break;
                case V13_5:
                    heap_top = 0x1000000;
                    break;
                default:
                    printf("isp: unsupported firmware\n");
                    return -1;
            }
            break;
        case ISP_VER_T6000:
            switch (os_firmware.version) {
                case V12_3:
                    heap_top = 0xe00000;
                    break;
                case V13_5:
                    heap_top = 0xf00000;
                    break;
                default:
                    printf("isp: unsupported firmware\n");
                    return -1;
            }
            break;
        case ISP_VER_T6020:
            switch (os_firmware.version) {
                case V13_5:
                    heap_top = 0xf00000;
                    break;
                default:
                    printf("isp: unsupported firmware\n");
                    return -1;
            }
            break;
        default:
            printf("isp: unknown revision 0x%x\n", ver_rev);
            return -1;
    }

    const struct adt_segment_ranges *seg;
    u32 segments_len;

    seg = adt_getprop(adt, isp_node, "segment-ranges", &segments_len);
    unsigned int count = segments_len / sizeof(*seg);

    heap_iova = seg[count - 1].iova + seg[count - 1].size;
    heap_size = heap_top - heap_iova;
    heap_phys = top_of_memory_alloc(heap_size);

    printf("isp: Heap: 0x%lx..0x%lx (0x%lx @ 0x%lx)\n", heap_iova, heap_top, heap_size, heap_phys);

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
                isp_ctrr_init_t6000(base, config, length, index);
                break;
            case DART_T8110:
                printf("isp: warning: dart type %s not tested yet!\n", type_s);
                isp_ctrr_init_t8020(base, config, length);
                break;
        }
    }

    isp_initialized = true;

out:
    pmgr_adt_power_disable(isp_path);
    return err;
}
