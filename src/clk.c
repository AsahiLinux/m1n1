/* SPDX-License-Identifier: MIT */

#include "clk.h"
#include "adt.h"
#include "soc.h"
#include "types.h"
#include "utils.h"

#define CLK_ENABLE BIT(31)
#define CLK_MUX    GENMASK(27, 24)

#define NCO_BASE 5
#define NUM_NCOS 5

void clk_set_mca_muxes(void)
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

struct soc_pdm_clk_data {
    int soc;
    uint64_t leap_pdm_feed_clkgates[10];
    uint64_t pdm_pin_clkgates[10];
};

struct soc_pdm_clk_data pdm_clk_data_t8103 = {
    .pdm_pin_clkgates =
        {
            0x23d240334,
            0x23d240338,
            0x23d24033c,
            0x23d240340,
            0x23d240344,
            0x23d240348,
        },
    .leap_pdm_feed_clkgates =
        {
            0x23d24035c,
            0x23d240360,
            0x23d240364,
            0x23d240368,
            0x23d24036c,
            0x23d240370,
        },
};

struct soc_pdm_clk_data pdm_clk_data_t600x = {
    .pdm_pin_clkgates =
        {
            0x292240348,
            0x29224034c,
            0x292240350,
            0x292240354,
            0x292240358,
            0x29224035c,
        },
    .leap_pdm_feed_clkgates =
        {
            0x292240360,
            0x292240364,
            0x292240368,
            0x29224036c,
            0x292240370,
            0x292240374,
        },
};

struct soc_pdm_clk_data pdm_clk_data_t8110 = {
    /* FILL ME: range 0x23d240300...0x23d24037c */
};

struct soc_pdm_clk_data pdm_clk_data_t602x = {
    /* FILL ME: range 0x29e240300...0x29e240374 */
};

void clk_ungate_pdm_channels(struct soc_pdm_clk_data *data, int chanmask)
{
    int nhits = 0;

    for (int i = 0; chanmask >> i != 0; i += 1) {
        if (chanmask & BIT(i)) {
            mask32(data->pdm_pin_clkgates[i / 2], CLK_ENABLE, CLK_ENABLE);
            mask32(data->leap_pdm_feed_clkgates[i / 2], CLK_ENABLE, CLK_ENABLE);
            nhits++;
        }
    }

    printf("CLK: Un-gated clocks of %d PDM channels\n", nhits);
}

void clk_set_pdm_gates(void)
{
    int alc_node = adt_path_offset(adt, "/arm-io/alc0");

    if (alc_node < 0) {
        printf("CLK: Model has no internal microphones, skipping PDM clock init\n");
        return;
    }

    /*
     * We don't need to differentiate between machine models here since Apple
     * seems to always use the same arrangement on all models with a given SoC.
     */
    switch (chip_id) {
        case T8103:
            clk_ungate_pdm_channels(&pdm_clk_data_t8103, BIT(6) | BIT(7) | BIT(9));
            break;

        case T6000 ... T6002:
            clk_ungate_pdm_channels(&pdm_clk_data_t600x, BIT(6) | BIT(7) | BIT(9));
            break;

            // TODO: missing clk_data for the SoCs below
#if 0
    case T8110:
        clk_ungate_pdm_channels(&pdm_clk_data_t8110, BIT(2) | BIT(3) | BIT(5));
        break;

    case T6020 ... T6021:
        clk_ungate_pdm_channels(&pdm_clk_data_t602x, BIT(2) | BIT(3) | BIT(9));
        break;
#endif

        default:
            printf("CLK: Missing SoC PDM clock data\n");
            break;
    }
}

void clk_init(void)
{
    clk_set_mca_muxes();
    clk_set_pdm_gates();
}
