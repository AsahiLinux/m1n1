/* SPDX-License-Identifier: MIT */

#ifndef UTILS_H
#define UTILS_H

#include "types.h"

#define printf debug_printf

static inline u32 read32(u64 addr)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]" : "=r"(data) : "r"(addr));
    return data;
}

static inline void write32(u64 addr, u32 data)
{
    __asm__ volatile("str\t%w0, [%1]" : : "r"(data), "r"(addr));
}

static inline u32 set32(u64 addr, u32 set)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstr\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set));
    return data;
}

static inline u32 clear32(u64 addr, u32 clear)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w2\n"
                     "\tstr\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(clear));
    return data;
}

static inline u32 mask32(u64 addr, u32 clear, u32 set)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w3\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstr\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set), "r"(clear));
    return data;
}

static inline u16 read16(u64 addr)
{
    u32 data;
    __asm__ volatile("ldrh\t%w0, [%1]" : "=r"(data) : "r"(addr));
    return data;
}

static inline void write16(u64 addr, u16 data)
{
    __asm__ volatile("strh\t%w0, [%1]" : : "r"(data), "r"(addr));
}

static inline u16 set16(u64 addr, u16 set)
{
    u16 data;
    __asm__ volatile("ldrh\t%w0, [%1]\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrh\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set)

    );
    return data;
}

static inline u16 clear16(u64 addr, u16 clear)
{
    u16 data;
    __asm__ volatile("ldrh\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w2\n"
                     "\tstrh\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(clear));
    return data;
}

static inline u16 mask16(u64 addr, u16 clear, u16 set)
{
    u16 data;
    __asm__ volatile("ldrh\t%w0, [%1]\n"
                     "\tbic\t%w0, %3\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrh\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set), "r"(clear));
    return data;
}

static inline u8 read8(u64 addr)
{
    u32 data;
    __asm__ volatile("ldrb\t%w0, [%1]" : "=r"(data) : "r"(addr));
    return data;
}

static inline void write8(u64 addr, u8 data)
{
    __asm__ volatile("strb\t%w0, [%1]" : : "r"(data), "r"(addr));
}

static inline u8 set8(u64 addr, u8 set)
{
    u8 data;
    __asm__ volatile("ldrb\t%w0, [%1]\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrb\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set));
    return data;
}

static inline u8 clear8(u64 addr, u8 clear)
{
    u8 data;
    __asm__ volatile("ldrb\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w2\n"
                     "\tstrb\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(clear));
    return data;
}

static inline u8 mask8(u64 addr, u8 clear, u8 set)
{
    u8 data;
    __asm__ volatile("ldrb\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w3\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrb\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set), "r"(clear));
    return data;
}

/*
 * These functions are guaranteed to copy by reading from src and writing to dst
 * in <n>-bit units If size is not aligned, the remaining bytes are not copied
 */
void memset32(void *dst, u32 value, u32 size);
void memcpy32(void *dst, void *src, u32 size);
void memset16(void *dst, u16 value, u32 size);
void memcpy16(void *dst, void *src, u32 size);
void memset8(void *dst, u8 value, u32 size);
void memcpy8(void *dst, void *src, u32 size);

void hexdump(const void *d, int len);
void regdump(u64 addr, int len);
int sprintf(char *str, const char *fmt, ...);
int debug_printf(const char *fmt, ...);
void udelay(u32 d);

#endif
