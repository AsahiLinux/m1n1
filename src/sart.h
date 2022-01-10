/* SPDX-License-Identifier: MIT */

#ifndef SART_H
#define SART_H

#include "types.h"

typedef struct sart_dev sart_dev_t;

sart_dev_t *sart_init(const char *adt_path);
void sart_free(sart_dev_t *asc);

bool sart_add_allowed_region(sart_dev_t *sart, void *paddr, size_t sz);
bool sart_remove_allowed_region(sart_dev_t *sart, void *paddr, size_t sz);

#endif
