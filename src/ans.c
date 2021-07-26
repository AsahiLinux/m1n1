/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "iop.h"
#include "malloc.h"
#include "pmgr.h"
#include "sart.h"
#include "types.h"
#include "utils.h"

#define ANS_BOOT_STATUS    0x1300
#define ANS_BOOT_STATUS_OK 0xde71ce55

static const char *adt_sart_path = "/arm-io/sart-ans";
static const char *adt_ans_path = "/arm-io/ans";
static bool ans_initialized = false;

static uintptr_t adt_get_regs(const char *node, u32 idx)
{
    int adt_path[8];
    int adt_offset;
    adt_offset = adt_path_offset_trace(adt, node, adt_path);
    if (adt_offset < 0) {
        printf("adt: Error getting %s node\n", node);
        return 0;
    }

    u64 base;
    if (adt_get_reg(adt, adt_path, "reg", idx, &base, NULL) < 0) {
        printf("adt: Error getting %s regs\n", node);
        return 0;
    }

    return base;
}

void ans_setup(void)
{
    uintptr_t sart_base = adt_get_regs(adt_sart_path, 0);
    uintptr_t iop_base = adt_get_regs(adt_ans_path, 0);
    uintptr_t ans_base = adt_get_regs(adt_ans_path, 3);
    void *shmem_bfr;
    iop_t *iop;

    if (ans_initialized)
        return;
    if (!sart_base || !ans_base)
        return;

    if (pmgr_adt_clocks_enable(adt_ans_path)) {
        printf("ans: Error enabling clocks\n");
        return;
    }

    if (read32(ans_base + ANS_BOOT_STATUS) == ANS_BOOT_STATUS_OK) {
        ans_initialized = true;
        printf("ans: already initialized\n");
        return;
    }

    // TODO: reserve this memory region
    shmem_bfr = memalign(SZ_16K, SZ_1M);
    if (!shmem_bfr) {
        printf("ans: Unable to allocate shared memory buffer\n");
    }

    if (!sart_allow_dma(sart_base, shmem_bfr, SZ_1M)) {
        printf("ans: Unable to map shared memory buffer in SART\n");
        return;
    }

    iop = iop_init(iop_base, shmem_bfr, (uintptr_t)shmem_bfr);
    if (!iop) {
        printf("ans: iop_init failed\n");
        return;
    }

    iop_boot(iop);

    if (poll32(ans_base + ANS_BOOT_STATUS, 0xffffffff, ANS_BOOT_STATUS_OK, 500000)) {
        printf("ans: firmware did not boot: %08x\n", read32(ans_base + ANS_BOOT_STATUS));
        return;
    }
}
