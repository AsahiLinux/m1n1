/* SPDX-License-Identifier: MIT */

#ifndef DCP_AFK_H
#define DCP_AFK_H

#include "rtkit.h"
#include "types.h"

typedef struct afk_epic afk_epic_t;
typedef struct afk_epic_ep afk_epic_ep_t;

typedef struct afk_epic_service_ops afk_epic_service_ops_t;

afk_epic_t *afk_epic_init(rtkit_dev_t *rtkit);
int afk_epic_shutdown(afk_epic_t *afk);

afk_epic_ep_t *afk_epic_start_ep(afk_epic_t *afk, int endpoint, bool notify);
int afk_epic_shutdown_ep(afk_epic_ep_t *epic);

int afk_epic_work(afk_epic_t *afk, int endpoint);
int afk_epic_start_interface(afk_epic_ep_t *epic, char *name, size_t insize, size_t outsize);
int afk_epic_command(afk_epic_ep_t *epic, int channel, u16 sub_type, void *txbuf, size_t txsize,
                     void *rxbuf, size_t *rxsize);

#endif
