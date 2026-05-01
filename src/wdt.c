/* SPDX-License-Identifier: MIT */

#include "wdt.h"
#include "adt.h"
#include "types.h"
#include "utils.h"

#define WDT_COUNT 0x10
#define WDT_ALARM 0x14
#define WDT_CTL   0x1c

#define WDT_2ND_OFFSET 0x8008

static u64 wdt_base = 0;

void wdt_disable(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/wdt", path);

    if (node < 0) {
        printf("WDT node not found!\n");
        return;
    }

    if (adt_get_reg(adt, path, "reg", 0, &wdt_base, NULL)) {
        printf("Failed to get WDT reg property!\n");
        return;
    }

    u64 wdt_2nd = 0;
    if (adt_get_reg(adt, path, "reg", 2, &wdt_2nd, NULL)) {
        printf("Failed to get WDT reg[2] property!\n");
    }

    printf("WDT registers @ 0x%lx (0x%lx)\n", wdt_base, wdt_2nd);

    write32(wdt_base + WDT_CTL, 0);
    // disable seconmdary watchdog enabled on M4 / A18 Pro with macOS 26
    if ((wdt_2nd - wdt_base) == WDT_2ND_OFFSET)
        write32(wdt_2nd, 0);

    printf("WDT disabled\n");
}

void wdt_reboot(void)
{
    if (!wdt_base)
        return;

    write32(wdt_base + WDT_ALARM, 0x100000);
    write32(wdt_base + WDT_COUNT, 0);
    write32(wdt_base + WDT_CTL, 4);
}
