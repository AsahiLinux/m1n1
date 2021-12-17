/* SPDX-License-Identifier: MIT */

#include "../config.h"

#include "adt.h"
#include "aic.h"
#include "cpufreq.h"
#include "exception.h"
#include "fb.h"
#include "gxf.h"
#include "heapblock.h"
#include "mcc.h"
#include "memory.h"
#include "payload.h"
#include "pcie.h"
#include "pmgr.h"
#include "smp.h"
#include "string.h"
#include "uart.h"
#include "uartproxy.h"
#include "usb.h"
#include "utils.h"
#include "wdt.h"
#include "xnuboot.h"

#include "../build/build_tag.h"

struct vector_args next_stage;

const char version_tag[] = "##m1n1_ver##" BUILD_TAG;
const char *const m1n1_version = version_tag + 12;

u32 board_id = ~0, chip_id = ~0;

void get_device_info(void)
{
    printf("Device info:\n");
    printf("  Model: %s\n", (const char *)adt_getprop(adt, 0, "model", NULL));
    printf("  Target: %s\n", (const char *)adt_getprop(adt, 0, "target-type", NULL));

    int chosen = adt_path_offset(adt, "/chosen");
    if (chosen > 0) {
        if (ADT_GETPROP(adt, chosen, "board-id", &board_id) < 0)
            printf("Failed to find board-id\n");
        if (ADT_GETPROP(adt, chosen, "chip-id", &chip_id) < 0)
            printf("Failed to find chip-id\n");

        printf("  Board-ID: 0x%x\n", board_id);
        printf("  Chip-ID: 0x%x\n", chip_id);
    } else {
        printf("No chosen node!\n");
    }

    printf("\n");
}

void run_actions(void)
{
    printf("Checking for payloads...\n");

    if (payload_run() == 0) {
        printf("Valid payload found\n");
        return;
    }

    printf("No valid payload found\n");

    usb_init();
    usb_iodev_init();

    printf("Running proxy...\n");

    uartproxy_run(NULL);
}

void m1n1_main(void)
{
    printf("\n\nm1n1 v%s\n", m1n1_version);
    printf("Copyright (C) 2021 The Asahi Linux Contributors\n");
    printf("Licensed under the MIT license\n\n");

    printf("Running in EL%lu\n\n", mrs(CurrentEL) >> 2);

    get_device_info();

    heapblock_init();
    gxf_init();
    mcc_init();
    mmu_init();

#ifdef USE_FB
    fb_init();
    fb_display_logo();
#endif

    aic_init();
    wdt_disable();
    pmgr_init();
    cpufreq_init();

    printf("Initialization complete.\n");

    run_actions();

    if (!next_stage.entry) {
        panic("Nothing to do!\n");
    }

    printf("Preparing to run next stage at %p...\n", next_stage.entry);

    exception_shutdown();
    usb_iodev_shutdown();
#ifdef USE_FB
    fb_shutdown(next_stage.restore_logo);
#endif
    mmu_shutdown();

    printf("Vectoring to next stage...\n");

    next_stage.entry(next_stage.args[0], next_stage.args[1], next_stage.args[2],
                     next_stage.args[3]);

    panic("Next stage returned!\n");
}
