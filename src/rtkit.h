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

rtkit_dev_t *rtkit_init(const char *name, asc_dev_t *asc, dart_dev_t *dart,
                        iova_domain_t *dart_iovad, sart_dev_t *sart);
bool rtkit_shutdown(rtkit_dev_t *rtk);
void rtkit_free(rtkit_dev_t *rtk);

bool rtkit_start_ep(rtkit_dev_t *rtk, u8 ep);
bool rtkit_boot(rtkit_dev_t *rtk);

bool rtkit_recv(rtkit_dev_t *rtk, struct rtkit_message *msg);
bool rtkit_send(rtkit_dev_t *rtk, const struct rtkit_message *msg);

#endif
