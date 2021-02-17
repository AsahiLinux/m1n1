/* SPDX-License-Identifier: MIT */

#ifndef __DART_H__
#define __DART_H__

#include "types.h"

void dart_shutdown_device(uintptr_t base, u8 device);
void dart_shutdown(uintptr_t base);
void dart_init(uintptr_t base);

void dart_map_page(uintptr_t base, u8 device, u64 vaddr, u64 paddr);
void dart_unmap_page(uintptr_t base, u8 device, u64 vaddr);

void dart_map(uintptr_t base, u8 device, u64 vaddr, u64 paddr, u64 size);
void dart_unmap(uintptr_t base, u8 device, u64 vaddr, u64 size);

void dart_enable_device(uintptr_t base, u8 device);
void dart_disable_device(uintptr_t base, u8 device);

#endif
