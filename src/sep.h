/* SPDX-License-Identifier: MIT */

#ifndef SEP_H
#define SEP_H

#include "asc.h"
#include "types.h"

typedef enum {
    SEP_CAPABILITY_GETRAND = BIT(0),
} sep_capabilities_t;

int sep_init(void);
size_t sep_get_random(void *buffer, size_t len);
sep_capabilities_t sep_get_capabilities(void);

#endif
