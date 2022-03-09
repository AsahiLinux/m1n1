/* SPDX-License-Identifier: MIT */

#ifndef ASC_H
#define ASC_H

#include "types.h"

struct asc_message {
    u64 msg0;
    u32 msg1;
};

typedef struct asc_dev asc_dev_t;

asc_dev_t *asc_init(const char *path);
void asc_free(asc_dev_t *asc);

int asc_get_iop_node(asc_dev_t *asc);

void asc_cpu_start(asc_dev_t *asc);
void asc_cpu_stop(asc_dev_t *asc);

bool asc_can_recv(asc_dev_t *asc);
bool asc_can_send(asc_dev_t *asc);

bool asc_recv(asc_dev_t *asc, struct asc_message *msg);
bool asc_recv_timeout(asc_dev_t *asc, struct asc_message *msg, u32 delay_usec);
bool asc_send(asc_dev_t *asc, const struct asc_message *msg);

#endif
