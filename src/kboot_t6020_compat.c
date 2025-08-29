/* SPDX-License-Identifier: MIT */

#include "kboot.h"
#include "utils.h"

#include "libfdt/libfdt.h"

// clang-format off
static const char *dt_compat_fixup_tbl[][2] = {
    { "apple,t6020-admac",           "apple,admac" },
    { "apple,t6020-cluster-cpufreq", "apple,cluster-cpufreq" },
    { "apple,t6020-i2c",             "apple,i2c" },
    { "apple,t6020-mca",             "apple,mca" },
    { "apple,t6020-nco",             "apple,nco" },
    { "apple,t6020-nvme-ans2",       "apple,nvme-ans2" },
    { "apple,t6020-pinctrl",         "apple,pinctrl" },
    { "apple,t6020-smc",             "apple,smc" },
    { "apple,t6020-spi",             "apple,spi" },
    { "apple,t6020-spmi",            "apple,spmi" },
    { "apple,t6020-wdt",             "apple,wdt" },
};
// clang-format on

static const char pmgr_compat[] = "apple,t6020-pmgr\0"
                                  "apple,t8103-pmgr\0"
                                  "apple,pmgr\0"
                                  "syscon\0"
                                  "simple-mfd";

static int dt_fixup_t6020_pmgr(void *dt)
{
    int pmgr_node = fdt_node_offset_by_compatible(dt, -1, "apple,t6020-pmgr");

    while (pmgr_node >= 0) {
        int node, ret;
        // insert "apple,pmgr" if it is missing
        if (fdt_node_check_compatible(dt, pmgr_node, "apple,pmgr")) {
            ret = fdt_setprop(dt, pmgr_node, "compatible", pmgr_compat, sizeof(pmgr_compat));
            if (ret < 0)
                printf("FDT: backward compat fixup for %s failed: %d\n",
                       fdt_get_name(dt, pmgr_node, NULL), ret);
        }

        fdt_for_each_subnode(node, dt, pmgr_node)
        {
            // append "apple,pmgr-pwrstate" if it is missing
            if (!fdt_node_check_compatible(dt, node, "apple,t6020-pmgr-pwrstate") &&
                fdt_node_check_compatible(dt, node, "apple,pmgr-pwrstate")) {
                ret = fdt_appendprop_string(dt, node, "compatible", "apple,pmgr-pwrstate");
                if (ret < 0)
                    printf("FDT: backward compat fixup for %s failed: %d\n",
                           fdt_get_name(dt, node, NULL), ret);
            }
        }
        pmgr_node = fdt_node_offset_by_compatible(dt, pmgr_node, "apple,t6020-pmgr");
    }

    return 0;
}

static int dt_fixup_t6020_node(void *dt, const char *compat, const char *backward)
{
    int node = fdt_node_offset_by_compatible(dt, -1, compat);

    while (node >= 0) {
        // append generic compatible for backward compatibility
        if (fdt_node_check_compatible(dt, node, backward)) {
            int ret = fdt_appendprop_string(dt, node, "compatible", backward);
            if (ret < 0)
                printf("FDT: backward compat fixup for %s failed: %d\n",
                       fdt_get_name(dt, node, NULL), ret);
        }
        node = fdt_node_offset_by_compatible(dt, node, compat);
    }

    return 0;
}

int dt_fixup_t6020_compat(void *dt)
{
    dt_fixup_t6020_pmgr(dt);

    for (size_t i = 0; i < ARRAY_SIZE(dt_compat_fixup_tbl); i++)
        dt_fixup_t6020_node(dt, dt_compat_fixup_tbl[i][0], dt_compat_fixup_tbl[i][1]);

    return 0;
}
