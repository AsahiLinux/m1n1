/* SPDX-License-Identifier: MIT */

#include "../config.h"

#include "adt.h"
#include "fb.h"
#include "heapblock.h"
#include "memory.h"
#include "payload.h"
#include "smp.h"
#include "string.h"
#include "uart.h"
#include "uartproxy.h"
#include "utils.h"
#include "wdt.h"
#include "xnuboot.h"

#include "../build/build_tag.h"

void print_info(void)
{
    printf("Device info:\n");
    printf("  Model: %s\n", adt_getprop(adt, 0, "model", NULL));
    printf("  Target: %s\n", adt_getprop(adt, 0, "target-type", NULL));

    int chosen = adt_path_offset(adt, "/chosen");
    if (chosen > 0) {
        u32 board_id = ~0, chip_id = ~0;
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

void m1n1_main(void)
{
    printf("\n\nm1n1 v%s\n", BUILD_TAG);
    printf("Copyright (C) 2021 The Asahi Linux Contributors\n");
    printf("Licensed under the MIT license\n\n");

    printf("Running in EL%d\n\n", mrs(CurrentEL) >> 2);

    mmu_init();
    heapblock_init();

#ifdef SHOW_LOGO
    fb_init();
    fb_display_logo();
#endif

    print_info();
    wdt_disable();

    printf("Checking for payloads...\n");

    payload_run();

    printf("No valid payload found\n");

    printf("Running proxy...\n");
    uartproxy_run();

    while (1)
        ;
}
