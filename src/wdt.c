/* SPDX-License-Identifier: MIT */

#include "wdt.h"
#include "adt.h"
#include "types.h"
#include "utils.h"

void wdt_disable(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/wdt", path);

    if (node < 0) {
        printf("WDT node not found!\n");
        return;
    }

    u64 wdt_regs;

    if (adt_get_reg(adt, path, "reg", 0, &wdt_regs, NULL)) {
        printf("Failed to get WDT reg property!\n");
        return;
    }

    printf("WDT registers @ 0x%lx\n", wdt_regs);

    write32(wdt_regs + 0x1c, 0);

    printf("WDT disabled\n");
}
