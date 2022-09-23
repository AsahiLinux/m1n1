/* SPDX-License-Identifier: MIT */

#ifndef DART_H
#define DART_H

#include "types.h"

#define DART_PTR_ERR     BIT(63)
#define DART_IS_ERR(val) FIELD_GET(DART_PTR_ERR, val)

typedef struct dart_dev dart_dev_t;

enum dart_type_t {
    DART_T8020,
    DART_T8110,
    DART_T6000,
};

dart_dev_t *dart_init(uintptr_t base, u8 device, bool keep_pts, enum dart_type_t type);
dart_dev_t *dart_init_adt(const char *path, int instance, int device, bool keep_pts);
void dart_lock_adt(const char *path, int instance);
dart_dev_t *dart_init_fdt(void *dt, u32 phandle, int device, bool keep_pts);
int dart_setup_pt_region(dart_dev_t *dart, const char *path, int device);
int dart_map(dart_dev_t *dart, uintptr_t iova, void *bfr, size_t len);
void dart_unmap(dart_dev_t *dart, uintptr_t iova, size_t len);
void dart_free_l2(dart_dev_t *dart, uintptr_t iova);
void *dart_translate(dart_dev_t *dart, uintptr_t iova);
u64 dart_search(dart_dev_t *dart, void *paddr);
u64 dart_find_iova(dart_dev_t *dart, s64 start, size_t len);
void dart_shutdown(dart_dev_t *dart);

#endif
