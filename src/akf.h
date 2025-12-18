/* SPDX-License-Identifier: MIT */

#ifndef AKF_H
#define AKF_H

#include "types.h"

struct akf_message {
    u32 msg0;
    u32 msg1;
};

typedef struct akf_dev akf_dev_t;

akf_dev_t *akf_init(const char *path);
void akf_free(akf_dev_t *akf);

int akf_get_iop_node(akf_dev_t *akf);

bool akf_can_recv(akf_dev_t *akf);
bool akf_can_send(akf_dev_t *akf);

bool akf_recv(akf_dev_t *akf, struct akf_message *msg);
bool akf_recv_timeout(akf_dev_t *akf, struct akf_message *msg, u32 delay_usec);
bool akf_send(akf_dev_t *akf, const struct akf_message *msg);

#endif
