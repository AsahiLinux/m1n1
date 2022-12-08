/* SPDX-License-Identifier: MIT */

#include "firmware.h"
#include "adt.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#include "libfdt/libfdt.h"
#include "libfdt/libfdt_env.h"

struct fw_version_info os_firmware;
struct fw_version_info system_firmware;

const struct fw_version_info fw_versions[NUM_FW_VERSIONS] = {
    [V_UNKNOWN] = {V_UNKNOWN, "unknown", {0}, 1, "unknown"},
    [V12_1] = {V12_1, "12.1", {12, 1, 0}, 3, "iBoot-7429.61.2"},
    [V12_2] = {V12_2, "12.2", {12, 2, 0}, 3, "iBoot-7429.81.3"},
    [V12_3] = {V12_3, "12.3", {12, 3, 0}, 3, "iBoot-7459.101.2"},
    [V12_3_1] = {V12_3_1, "12.3.1", {12, 3, 1}, 3, "iBoot-7459.101.3"},
    [V12_4] = {V12_4, "12.4", {12, 4, 0}, 3, "iBoot-7459.121.3"},
    [V12_5] = {V12_5, "12.5", {12, 5, 0}, 3, "iBoot-7459.141.1"},
    // Same as 12.5
    // {V12_6, "12.6", {12, 6, 0}, 3, "iBoot-7459.141.1"},
    [V13_0B4] = {V13_0B4, "13.0 beta4", {12, 99, 4}, 3, "iBoot-8419.0.151.0.1"},
    [V13_0] = {V13_0, "13.0", {13, 0, 0}, 3, "iBoot-8419.41.10"},
};

int firmware_set_fdt(void *fdt, int node, const char *prop, const struct fw_version_info *ver)
{
    fdt32_t data[ARRAY_SIZE(ver->num)];

    for (size_t i = 0; i < ver->num_length; i++) {
        data[i] = cpu_to_fdt32(ver->num[i]);
    }

    return fdt_setprop(fdt, node, prop, data, ver->num_length * sizeof(u32));
}

static void detect_firmware(struct fw_version_info *info, const char *ver)
{
    for (size_t i = 0; i < ARRAY_SIZE(fw_versions); i++) {
        if (!strcmp(fw_versions[i].iboot, ver)) {
            *info = fw_versions[i];
            return;
        }
    }

    *info = fw_versions[V_UNKNOWN];
    info->iboot = ver;
}

int firmware_init(void)
{
    int node = adt_path_offset(adt, "/chosen");

    if (node < 0) {
        printf("ADT: no /chosen found\n");
        return -1;
    }

    u32 len;
    const char *p = adt_getprop(adt, node, "firmware-version", &len);
    if (p && len && p[len - 1] == 0) {
        detect_firmware(&os_firmware, p);
        printf("OS FW version: %s (%s)\n", os_firmware.string, os_firmware.iboot);
    } else {
        printf("ADT: failed to find firmware-version\n");
        return -1;
    }

    p = adt_getprop(adt, node, "system-firmware-version", &len);
    if (p && len && p[len - 1] == 0) {
        detect_firmware(&system_firmware, p);
        printf("System FW version: %s (%s)\n", system_firmware.string, system_firmware.iboot);
    } else {
        printf("ADT: failed to find system-firmware-version\n");
        return -1;
    }

    return 0;
}
