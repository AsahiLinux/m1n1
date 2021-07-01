/* SPDX-License-Identifier: MIT */

#ifndef CPIO_H
#define CPIO_H

#include "types.h"
#include "utils.h"

struct cpio;

struct cpio *cpio_init(void);
int cpio_add_file(struct cpio *c, const char *name, const u8 *bfr, size_t sz);
int cpio_add_dir(struct cpio *c, const char *name);
size_t cpio_get_size(struct cpio *c);
size_t cpio_finalize(struct cpio *c, u8 *bfr, size_t bfr_size);
void cpio_free(struct cpio *c);

#endif
