/* SPDX-License-Identifier: MIT */

#ifndef SART_H
#define SART_H

#include "types.h"

bool sart_allow_dma(uintptr_t sart_base, void *paddr, size_t sz);

#endif
