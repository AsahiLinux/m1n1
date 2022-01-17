/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "nvme.h"
#include "pmgr.h"
#include "rtkit.h"
#include "sart.h"
#include "utils.h"

#define NVME_BOOT_STATUS    0x1300
#define NVME_BOOT_STATUS_OK 0xde71ce55

static bool nvme_initialized = false;

static asc_dev_t *nvme_asc = NULL;
static rtkit_dev_t *nvme_rtkit = NULL;
static sart_dev_t *nvme_sart = NULL;

static u64 nvme_base;

bool nvme_init(void)
{
    if (nvme_initialized) {
        printf("nvme: already initialized\n");
        return true;
    }

    int adt_path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/ans", adt_path);
    if (node < 0) {
        printf("nvme: Error getting NVMe node /arm-io/ans\n");
        return NULL;
    }

    if (adt_get_reg(adt, adt_path, "reg", 3, &nvme_base, NULL) < 0) {
        printf("nvme: Error getting NVMe base address.\n");
        return NULL;
    }

    nvme_asc = asc_init("/arm-io/ans");
    if (!nvme_asc)
        return false;
    asc_cpu_start(nvme_asc);

    nvme_sart = sart_init("/arm-io/sart-ans");
    if (!nvme_sart)
        goto out_asc;

    nvme_rtkit = rtkit_init("nvme", nvme_asc, NULL, NULL, nvme_sart);
    if (!nvme_rtkit)
        goto out_sart;

    if (!rtkit_boot(nvme_rtkit))
        goto out_rtkit;

    if (poll32(nvme_base + NVME_BOOT_STATUS, 0xffffffff, NVME_BOOT_STATUS_OK, USEC_PER_SEC) < 0) {
        printf("nvme: ANS did not boot correctly.\n");
        goto out_shutdown;
    }

    nvme_initialized = true;
    printf("nvme: initialized at 0x%lx\n", nvme_base);
    return true;

out_shutdown:
    rtkit_sleep(nvme_rtkit);
    pmgr_reset("ANS2");
out_rtkit:
    rtkit_free(nvme_rtkit);
out_sart:
    sart_free(nvme_sart);
out_asc:
    asc_free(nvme_asc);
    return false;
}

void nvme_shutdown(void)
{
    if (!nvme_initialized) {
        printf("nvme: trying to shut down but not initialized\n");
        return;
    }

    rtkit_sleep(nvme_rtkit);
    pmgr_reset("ANS2");
    rtkit_free(nvme_rtkit);
    sart_free(nvme_sart);
    asc_free(nvme_asc);
    nvme_initialized = false;

    printf("nvme: shutdown done\n");
}
