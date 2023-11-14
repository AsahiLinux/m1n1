/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "dart.h"
#include "firmware.h"
#include "isp.h"
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

static bool isp_initialized = false;
static u64 heap_phys, heap_iova, heap_size, heap_top;

int isp_get_heap(u64 *phys, u64 *iova, u64 *size)
{
    if (!isp_initialized)
        return -1;

    *phys = heap_phys;
    *iova = heap_iova | isp_iova_base();
    *size = heap_size;
    return 0;
}

u64 isp_iova_base(void)
{
    switch (chip_id) {
        case 0x6020 ... 0x6fff:
            return 0x10000000000;
        default:
            return 0;
    }
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
                case V13_6_2:
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
                case V13_6_2:
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

    printf("isp: Code: 0x%lx..0x%lx (0x%x @ 0x%lx)\n", seg[0].iova, seg[0].iova + seg[0].size,
           seg[0].size, seg[0].phys);
    printf("isp: Data: 0x%lx..0x%lx (0x%x @ 0x%lx)\n", seg[1].iova, seg[1].iova + seg[1].size,
           seg[1].size, seg[1].phys);
    printf("isp: Heap: 0x%lx..0x%lx (0x%lx @ 0x%lx)\n", heap_iova, heap_top, heap_size, heap_phys);

    isp_initialized = true;

    pmgr_adt_power_disable(isp_path);
    return err;
}
