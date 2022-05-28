/* SPDX-License-Identifier: MIT */

#ifndef DART_H
#define DART_H

#include "types.h"

typedef struct dart_dev dart_dev_t;

dart_dev_t *dart_init(uintptr_t base, u8 device, bool keep_pts);
dart_dev_t *dart_init_adt(const char *path, int instance, int device, bool keep_pts);
int dart_setup_pt_region(dart_dev_t *dart, const char *path, int device);
int dart_map(dart_dev_t *dart, uintptr_t iova, void *bfr, size_t len);
void dart_unmap(dart_dev_t *dart, uintptr_t iova, size_t len);
void dart_free_l2(dart_dev_t *dart, uintptr_t iova);
void *dart_translate(dart_dev_t *dart, uintptr_t iova);
u64 dart_search(dart_dev_t *dart, void *paddr);
s64 dart_find_iova(dart_dev_t *dart, s64 start, size_t len);
void dart_shutdown(dart_dev_t *dart);

#endif
