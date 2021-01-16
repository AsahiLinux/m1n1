/* SPDX-License-Identifier: MIT */

#ifndef TYPES_H
#define TYPES_H

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

#define ALIGNED(x) __attribute__((aligned(x)))
#define PACKED __attribute__((packed))

#define STACK_ALIGN(type, name, cnt, alignment)                                \
    u8 _al__##name[(                                                           \
        (sizeof(type) * (cnt)) + (alignment) +                                 \
        (((sizeof(type) * (cnt)) % (alignment)) > 0                            \
             ? ((alignment) - ((sizeof(type) * (cnt)) % (alignment)))          \
             : 0))];                                                           \
    type *name =                                                               \
        (type *)(((u32)(_al__##name)) +                                        \
                 ((alignment) - (((u32)(_al__##name)) & ((alignment)-1))))

#define INT_MAX ((int)0x7fffffff)
#define UINT_MAX ((unsigned int)0xffffffff)

#define LONG_MAX ((long)0x7fffffffffffffffl)
#define ULONG_MAX ((unsigned long)0xfffffffffffffffful)

#define LLONG_MAX LONG_MAX
#define ULLONG_MAX ULLONG_MAX

#define HAVE_PTRDIFF_T 1
#define HAVE_UINTPTR_T 1
#define UPTRDIFF_T uintptr_t

#endif
