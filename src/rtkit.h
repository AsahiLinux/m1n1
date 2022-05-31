/* SPDX-License-Identifier: MIT */

#ifndef RTKIT_H
#define RTKIT_H

#include "asc.h"
#include "dart.h"
#include "iova.h"
#include "sart.h"
#include "types.h"

typedef struct rtkit_dev rtkit_dev_t;

struct rtkit_message {
    u8 ep;
    u64 msg;
};

struct rtkit_buffer {
    void *bfr;
    u64 dva;
    size_t sz;
};

rtkit_dev_t *rtkit_init(const char *name, asc_dev_t *asc, dart_dev_t *dart,
                        iova_domain_t *dart_iovad, sart_dev_t *sart);
bool rtkit_quiesce(rtkit_dev_t *rtk);
bool rtkit_sleep(rtkit_dev_t *rtk);
void rtkit_free(rtkit_dev_t *rtk);

bool rtkit_start_ep(rtkit_dev_t *rtk, u8 ep);
bool rtkit_boot(rtkit_dev_t *rtk);

int rtkit_recv(rtkit_dev_t *rtk, struct rtkit_message *msg);
bool rtkit_send(rtkit_dev_t *rtk, const struct rtkit_message *msg);

bool rtkit_map(rtkit_dev_t *rtk, void *phys, size_t sz, u64 *dva);
bool rtkit_unmap(rtkit_dev_t *rtk, u64 dva, size_t sz);

bool rtkit_alloc_buffer(rtkit_dev_t *rtk, struct rtkit_buffer *bfr, size_t sz);
bool rtkit_free_buffer(rtkit_dev_t *rtk, struct rtkit_buffer *bfr);

#endif
