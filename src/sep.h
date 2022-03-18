/* SPDX-License-Identifier: MIT */

#ifndef SEP_H
#define SEP_H

#include "asc.h"
#include "types.h"

int sep_init(void);
size_t sep_get_random(void *buffer, size_t len);

#endif
