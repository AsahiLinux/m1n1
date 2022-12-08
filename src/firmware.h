/* SPDX-License-Identifier: MIT */

#ifndef __FIRMWARE_H__
#define __FIRMWARE_H__

#include "types.h"

enum fw_version {
    V_UNKNOWN,
    V12_1,
    V12_2,
    V12_3,
    V12_3_1,
    V12_4,
    V12_5,
    // V12_6,
    V13_0B4,
    V13_0,
    NUM_FW_VERSIONS,
};

struct fw_version_info {
    enum fw_version version;
    const char *string;
    u32 num[4];
    size_t num_length;
    const char *iboot;
};

extern struct fw_version_info os_firmware;
extern struct fw_version_info system_firmware;
extern const struct fw_version_info fw_versions[NUM_FW_VERSIONS];

int firmware_init(void);
int firmware_set_fdt(void *fdt, int node, const char *prop, const struct fw_version_info *ver);

#endif
