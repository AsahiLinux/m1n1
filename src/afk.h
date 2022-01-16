/* SPDX-License-Identifier: MIT */

#ifndef DCP_AFK_H
#define DCP_AFK_H

#include "rtkit.h"

typedef struct afk_epic_ep afk_epic_ep_t;

afk_epic_ep_t *afk_epic_init(rtkit_dev_t *rtkit, int endpoint);
int afk_epic_shutdown(afk_epic_ep_t *epic);

int afk_epic_start_interface(afk_epic_ep_t *epic, char *name, size_t insize, size_t outsize);
int afk_epic_command(afk_epic_ep_t *epic, int channel, u16 code, void *txbuf, size_t txsize,
                     void *rxbuf, size_t *rxsize);

#endif
