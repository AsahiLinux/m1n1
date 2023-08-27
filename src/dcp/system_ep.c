
// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2022 Sven Peter <sven@svenpeter.dev> */

#include <stdbool.h>
#include <string.h>

#include "system_ep.h"
#include "malloc.h"
#include "parser.h"

#include "../afk.h"
#include "../dcp.h"
#include "../types.h"
#include "../utils.h"

#define DCP_SYSTEM_ENDPOINT 0x20
#define TXBUF_LEN           0x4000
#define RXBUF_LEN           0x4000

typedef struct dcp_system_if {
    afk_epic_ep_t *epic;
    dcp_dev_t *dcp;

    afk_epic_service_t *sys_service;
    afk_epic_service_t *powerlog;
} dcp_system_if_t;

static void system_service_init(afk_epic_service_t *service, const char *name, const char *eclass,
                                s64 unit)
{
    UNUSED(name);
    UNUSED(unit);
    dcp_system_if_t *system = (dcp_system_if_t *)service->intf;
    if (strcmp(eclass, "system") == 0) {
        if (system->sys_service) {
            printf("SYSTEM[%p]: system services already started!\n", system);
            return;
        }
        system->sys_service = service;
        service->cookie = system;
    }
}

static void powerlog_service_init(afk_epic_service_t *service, const char *name, const char *eclass,
                                  s64 unit)
{
    UNUSED(name);
    UNUSED(unit);
    dcp_system_if_t *system = (dcp_system_if_t *)service->intf;
    if (strcmp(eclass, "powerlog-service") == 0) {
        if (system->powerlog) {
            printf("SYSTEM[%p]: powerlog service already started!\n", system);
            return;
        }
        system->powerlog = service;
        service->cookie = system;
    }
}

struct OSSerializedInt {
    u32 code; // constant little endian 0xd3
    u32 tag;  // 24 bit size in bits, 8 bit type (constant 4 for integers)
    u64 value;
} PACKED;

int dcp_system_set_property_u64(dcp_system_if_t *system, const char *name, u64 value)
{
    size_t name_len = strlen(name);
    u32 aligned_len = ALIGN_UP(name_len, 4);
    struct OSSerializedInt val = {
        .code = 0xd3,
        .tag = 0x80000000 | (4 << 24) | 64,
        .value = value,
    };
    size_t bfr_len = sizeof(aligned_len) + aligned_len + sizeof(val);

    u8 *bfr = calloc(1, bfr_len);
    if (!bfr)
        return -1;

    memcpy(bfr, &aligned_len, sizeof(aligned_len));
    memcpy(bfr + sizeof(aligned_len), name, name_len);
    memcpy(bfr + sizeof(aligned_len) + aligned_len, &val, sizeof(val));

    afk_epic_service_t *service = system->sys_service;
    if (!service) {
        free(bfr);
        printf("SYSTEM: sys_service-service not started\n");
        return -1;
    }
    int ret = afk_epic_command(service->epic, service->channel, 0x43, bfr, bfr_len, NULL, NULL);

    free(bfr);

    return ret;
}

static const afk_epic_service_ops_t dcp_system_ops[] = {
    {
        .name = "system",
        .init = system_service_init,
    },
    {
        .name = "powerlog-service",
        .init = powerlog_service_init,
    },
    {},
};

dcp_system_if_t *dcp_system_init(dcp_dev_t *dcp)
{
    dcp_system_if_t *system = calloc(1, sizeof(dcp_system_if_t));
    if (!system)
        return NULL;

    system->dcp = dcp;
    system->epic = afk_epic_start_ep(dcp->afk, DCP_SYSTEM_ENDPOINT, dcp_system_ops, true);
    if (!system->epic) {
        // printf("system: failed to initialize EPIC\n");
        goto err_free;
    }

    int err = afk_epic_start_interface(system->epic, system, TXBUF_LEN, RXBUF_LEN);

    if (err < 0 || !system->sys_service) {
        printf("dcp-system: failed to initialize system-service\n");
        goto err_shutdown;
    }

    return system;

err_shutdown:
    afk_epic_shutdown_ep(system->epic);
err_free:
    free(system);
    return NULL;
}

int dcp_system_shutdown(dcp_system_if_t *system)
{
    if (system) {
        afk_epic_shutdown_ep(system->epic);
        free(system);
    }
    return 0;
}
