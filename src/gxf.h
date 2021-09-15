/* SPDX-License-Identifier: MIT */

#ifndef __GXF_H__
#define __GXF_H__

#include "types.h"

#define GL_STACK_SIZE 0x10000

#ifndef __ASSEMBLER__

bool gxf_enabled(void);
bool in_gl12(void);

void gxf_init(void);

uint64_t gl1_call(void *func, uint64_t a, uint64_t b, uint64_t c, uint64_t d);
uint64_t gl2_call(void *func, uint64_t a, uint64_t b, uint64_t c, uint64_t d);

#endif

#endif
