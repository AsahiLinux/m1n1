/* SPDX-License-Identifier: MIT */

#ifndef IOVA_H
#define IOVA_H

#include "dart.h"
#include "types.h"

typedef struct iova_domain iova_domain_t;

iova_domain_t *iovad_init(u64 base, u64 limit);
void iovad_shutdown(iova_domain_t *iovad, dart_dev_t *dart);

bool iova_reserve(iova_domain_t *iovad, u64 iova, size_t sz);
u64 iova_alloc(iova_domain_t *iovad, size_t sz);
void iova_free(iova_domain_t *iovad, u64 iova, size_t sz);

#endif
