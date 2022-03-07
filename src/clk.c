/* SPDX-License-Identifier: MIT */

#include "clk.h"
#include "adt.h"
#include "types.h"
#include "utils.h"

#define CLK_MUX GENMASK(27, 24)

#define NCO_BASE 5
#define NUM_NCOS 5

void clk_init(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/mca-switch", path);

    if (node < 0) {
        printf("mca-switch node not found!\n");
        return;
    }

    u64 mca_clk_base, mca_clk_size;
    if (adt_get_reg(adt, path, "reg", 2, &mca_clk_base, &mca_clk_size)) {
        printf("Failed to get mca-switch reg property!\n");
        return;
    }

    printf("CLK: MCA clock registers @ 0x%lx (0x%lx)\n", mca_clk_base, mca_clk_size);

    unsigned int i;
    for (i = 0; i < (mca_clk_size / 4); i++)
        mask32(mca_clk_base + 4 * i, CLK_MUX, FIELD_PREP(CLK_MUX, NCO_BASE + min(NUM_NCOS - 1, i)));

    printf("CLK: Initialized %d MCA clock muxes\n", i);
}
