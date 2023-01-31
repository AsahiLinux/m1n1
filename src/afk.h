/* SPDX-License-Identifier: MIT */

#ifndef DCP_AFK_H
#define DCP_AFK_H

#include <stddef.h>

#include "rtkit.h"

#define MAX_PENDING_CMDS 8

typedef struct afk_epic_ep afk_epic_ep_t;

typedef struct afk_epic_service_ops afk_epic_service_ops_t;

enum EPICMessage {
    CODE_ANNOUNCE = 0x30,
    CODE_STD_SERVICE = 0xc0,
};

struct epic_cmd_info {
    u16 code;

    void *rxbuf;
    void *txbuf;
    u64 rxbuf_dma;
    u64 txbuf_dma;
    size_t rxlen;
    size_t txlen;

    u32 retcode;
    bool done;
    bool free_on_ack;
};

typedef struct afk_epic_service {
    const afk_epic_service_ops_t *ops;
    afk_epic_ep_t *epic;
    void *intf;

    struct epic_cmd_info cmds[MAX_PENDING_CMDS];
    u8 cmd_tag;

    u32 channel;
    bool enabled;

    u16 seq;

    void *cookie;
} afk_epic_service_t;

typedef struct afk_epic_service_ops {
    const char name[32];

    bool (*init)(afk_epic_service_t *service, u8 *props, size_t props_size);
    int (*call)(afk_epic_service_t *service, u32 idx, const void *data, size_t data_size,
                void *reply, size_t reply_size);
} afk_epic_service_ops_t;

afk_epic_ep_t *afk_epic_init(rtkit_dev_t *rtkit, int endpoint);
int afk_epic_shutdown(afk_epic_ep_t *epic);

int afk_epic_start_channel(afk_epic_ep_t *epic, const afk_epic_service_ops_t *ops, void *intf,
                           const char *name);
int afk_epic_start_interface(afk_epic_ep_t *epic, const afk_epic_service_ops_t *ops, void *intf,
                             const char *name, size_t insize, size_t outsize);
int afk_epic_command(afk_epic_ep_t *epic, int channel, u16 sub_seq, u16 code, void *txbuf,
                     size_t txsize, void *rxbuf, size_t *rxsize);

int afk_epic_report(afk_epic_ep_t *epic, int channel, u32 type, u16 sub_seq, void *payload,
                    size_t payload_size);

#endif
