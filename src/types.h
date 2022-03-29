/* SPDX-License-Identifier: MIT */

#ifndef TYPES_H
#define TYPES_H

#ifndef __ASSEMBLER__

#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

typedef int8_t s8;
typedef int16_t s16;
typedef int32_t s32;
typedef int64_t s64;

typedef u64 uintptr_t;
typedef s64 ptrdiff_t;

typedef s64 ssize_t;

#endif

#define UNUSED(x)  (void)(x)
#define ALIGNED(x) __attribute__((aligned(x)))
#define PACKED     __attribute__((packed))

#define STACK_ALIGN(type, name, cnt, alignment)                                                    \
    u8 _al__##name[((sizeof(type) * (cnt)) + (alignment) +                                         \
                    (((sizeof(type) * (cnt)) % (alignment)) > 0                                    \
                         ? ((alignment) - ((sizeof(type) * (cnt)) % (alignment)))                  \
                         : 0))];                                                                   \
    type *name =                                                                                   \
        (type *)(((u32)(_al__##name)) + ((alignment) - (((u32)(_al__##name)) & ((alignment)-1))))

#define HAVE_PTRDIFF_T 1
#define HAVE_UINTPTR_T 1
#define UPTRDIFF_T     uintptr_t

#define SZ_2K  (1 << 11)
#define SZ_4K  (1 << 12)
#define SZ_16K (1 << 14)
#define SZ_1M  (1 << 20)
#define SZ_32M (1 << 25)

#ifdef __ASSEMBLER__

#define sys_reg(op0, op1, CRn, CRm, op2) s##op0##_##op1##_c##CRn##_c##CRm##_##op2

#else

#define sys_reg(op0, op1, CRn, CRm, op2) , _S, op0, op1, CRn, CRm, op2

#endif

#endif
