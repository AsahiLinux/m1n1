/* SPDX-License-Identifier: MIT */

#ifndef __CHAINLOAD_H__
#define __CHAINLOAD_H__

#include <stdbool.h>
#include <stddef.h>

int do_chainload(void);

extern size_t prepare_chainload(void);
extern bool chainload_get_bytes(void *buf, size_t buf_size);

#endif
