
// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2022 Sven Peter <sven@svenpeter.dev> */

#include <stdbool.h>
#include <string.h>

#include "dpav_ep.h"
#include "malloc.h"
#include "parser.h"

#include "../afk.h"
#include "../dcp.h"
#include "../types.h"
#include "../utils.h"

#define DCP_DPAV_ENDPOINT     0x24
#define DCP_DPAV_NUM_SERVICES 4

#define TXBUF_LEN 0x4000
#define RXBUF_LEN 0x4000

typedef struct dcp_dpav_if {
    afk_epic_ep_t *epic;
    dcp_dev_t *dcp;
} dcp_dpav_if_t;

static void dpav_init(afk_epic_service_t *service, const char *name, const char *eclass, s64 unit)
{
    UNUSED(service);
    UNUSED(name);
    UNUSED(eclass);
    UNUSED(unit);
    dprintf("DPAV: init(name='%s', class='%s' unit=%ld:\n", name, eclass, unit);
}

static const afk_epic_service_ops_t dcp_dpav_ops[] = {
    {
        .name = "AppleDCPDPTXController",
        .init = dpav_init,
    },
    {},
};

dcp_dpav_if_t *dcp_dpav_init(dcp_dev_t *dcp)
{
    dcp_dpav_if_t *dpav = calloc(1, sizeof(dcp_dpav_if_t));
    if (!dpav)
        return NULL;

    dpav->dcp = dcp;
    dpav->epic = afk_epic_start_ep(dcp->afk, DCP_DPAV_ENDPOINT, dcp_dpav_ops, true);
    if (!dpav->epic) {
        printf("dpav: failed to initialize EPIC\n");
        goto err_free;
    }

    int err =
        afk_epic_start_interface(dpav->epic, dpav, DCP_DPAV_NUM_SERVICES, TXBUF_LEN, RXBUF_LEN);
    if (err < 0) {
        printf("dpav: failed to initialize DPAV interface\n");
        goto err_shutdown;
    }

    return dpav;

err_shutdown:
    afk_epic_shutdown_ep(dpav->epic);
err_free:
    free(dpav);
    return NULL;
}

int dcp_dpav_shutdown(dcp_dpav_if_t *dpav)
{
    if (dpav) {
        afk_epic_shutdown_ep(dpav->epic);
        free(dpav);
    }
    return 0;
}
