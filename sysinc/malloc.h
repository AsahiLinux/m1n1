/* SPDX-License-Identifier: MIT */

#ifndef MALLOC_H
#define MALLOC_H

#include <stddef.h>

void *malloc(size_t);
void free(void *);
void *calloc(size_t, size_t);
void *realloc(void *, size_t);
void *realloc_in_place(void *, size_t);
void *memalign(size_t, size_t);
int posix_memalign(void **, size_t, size_t);

#endif
