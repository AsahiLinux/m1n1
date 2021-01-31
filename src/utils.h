/* SPDX-License-Identifier: MIT */

#ifndef UTILS_H
#define UTILS_H

#include "types.h"

#define printf debug_printf

static inline u64 read64(u64 addr)
{
    u64 data;
    __asm__ volatile("ldr\t%0, [%1]" : "=r"(data) : "r"(addr) : "memory");
    return data;
}

static inline void write64(u64 addr, u64 data)
{
    __asm__ volatile("str\t%0, [%1]" : : "r"(data), "r"(addr) : "memory");
}

static inline u64 set64(u64 addr, u64 set)
{
    u64 data;
    __asm__ volatile("ldr\t%0, [%1]\n"
                     "\torr\t%0, %0, %2\n"
                     "\tstr\t%0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set)
                     : "memory");
    return data;
}

static inline u64 clear64(u64 addr, u64 clear)
{
    u64 data;
    __asm__ volatile("ldr\t%0, [%1]\n"
                     "\tbic\t%0, %0, %2\n"
                     "\tstr\t%0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(clear)
                     : "memory");
    return data;
}

static inline u64 mask64(u64 addr, u64 clear, u64 set)
{
    u64 data;
    __asm__ volatile("ldr\t%0, [%1]\n"
                     "\tbic\t%0, %0, %3\n"
                     "\torr\t%0, %0, %2\n"
                     "\tstr\t%0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set), "r"(clear)
                     : "memory");
    return data;
}

static inline u32 read32(u64 addr)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]" : "=r"(data) : "r"(addr) : "memory");
    return data;
}

static inline void write32(u64 addr, u32 data)
{
    __asm__ volatile("str\t%w0, [%1]" : : "r"(data), "r"(addr) : "memory");
}

static inline u32 set32(u64 addr, u32 set)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstr\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set)
                     : "memory");
    return data;
}

static inline u32 clear32(u64 addr, u32 clear)
{
    u32 data;
    __asm__ volatile("ldr\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w2\n"
                     "\tstr\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(clear)
                     : "memory");
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
                     : "r"(addr), "r"(set), "r"(clear)
                     : "memory");
    return data;
}

static inline u16 read16(u64 addr)
{
    u32 data;
    __asm__ volatile("ldrh\t%w0, [%1]" : "=r"(data) : "r"(addr) : "memory");
    return data;
}

static inline void write16(u64 addr, u16 data)
{
    __asm__ volatile("strh\t%w0, [%1]" : : "r"(data), "r"(addr) : "memory");
}

static inline u16 set16(u64 addr, u16 set)
{
    u16 data;
    __asm__ volatile("ldrh\t%w0, [%1]\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrh\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set)
                     : "memory"

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
                     : "r"(addr), "r"(clear)
                     : "memory");
    return data;
}

static inline u16 mask16(u64 addr, u16 clear, u16 set)
{
    u16 data;
    __asm__ volatile("ldrh\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w3\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrh\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set), "r"(clear)
                     : "memory");
    return data;
}

static inline u8 read8(u64 addr)
{
    u32 data;
    __asm__ volatile("ldrb\t%w0, [%1]" : "=r"(data) : "r"(addr) : "memory");
    return data;
}

static inline void write8(u64 addr, u8 data)
{
    __asm__ volatile("strb\t%w0, [%1]" : : "r"(data), "r"(addr) : "memory");
}

static inline u8 set8(u64 addr, u8 set)
{
    u8 data;
    __asm__ volatile("ldrb\t%w0, [%1]\n"
                     "\torr\t%w0, %w0, %w2\n"
                     "\tstrb\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(set)
                     : "memory");
    return data;
}

static inline u8 clear8(u64 addr, u8 clear)
{
    u8 data;
    __asm__ volatile("ldrb\t%w0, [%1]\n"
                     "\tbic\t%w0, %w0, %w2\n"
                     "\tstrb\t%w0, [%1]"
                     : "=&r"(data)
                     : "r"(addr), "r"(clear)
                     : "memory");
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
                     : "r"(addr), "r"(set), "r"(clear)
                     : "memory");
    return data;
}

#define sys_reg(op0, op1, CRn, CRm, op2) s##op0##_##op1##_c##CRn##_c##CRm##_##op2

#define _mrs(reg)                                                                                  \
    ({                                                                                             \
        u64 val;                                                                                   \
        __asm__ volatile("mrs\t%0, " #reg : "=r"(val));                                            \
        val;                                                                                       \
    })
#define mrs(reg) _mrs(reg)

#define _msr(reg, val)                                                                             \
    ({                                                                                             \
        u64 __val = (u64)val;                                                                      \
        __asm__ volatile("msr\t" #reg ", %0" : : "r"(__val));                                      \
    })
#define msr(reg, val) _msr(reg, val)

#define sysop(op) __asm__ volatile(op ::: "memory")

#define cacheop(op, val) ({ __asm__ volatile(op ", %0" : : "r"(val) : "memory"); })

#define ic_ialluis() sysop("ic ialluis")
#define ic_iallu()   sysop("ic iallu")
#define ic_iavau(p)  cacheop("ic ivau", p)
#define dc_ivac(p)   cacheop("dc ivac", p)
#define dc_isw(p)    cacheop("dc isw", p)
#define dc_csw(p)    cacheop("dc csw", p)
#define dc_cisw(p)   cacheop("dc cisw", p)
#define dc_zva(p)    cacheop("dc zva", p)
#define dc_cvac(p)   cacheop("dc cvac", p)
#define dc_cvau(p)   cacheop("dc cvau", p)
#define dc_civac(p)  cacheop("dc civac", p)

static inline int is_ecore(void)
{
    return !(mrs(MPIDR_EL1) & (1 << 16));
}

extern char _base[0];
extern char _payload_start[];
extern char _payload_end[];

/*
 * These functions are guaranteed to copy by reading from src and writing to dst
 * in <n>-bit units If size is not aligned, the remaining bytes are not copied
 */
void memset64(void *dst, u64 value, size_t size);
void memcpy64(void *dst, void *src, size_t size);
void memset32(void *dst, u32 value, size_t size);
void memcpy32(void *dst, void *src, size_t size);
void memset16(void *dst, u16 value, size_t size);
void memcpy16(void *dst, void *src, size_t size);
void memset8(void *dst, u8 value, size_t size);
void memcpy8(void *dst, void *src, size_t size);

void hexdump(const void *d, size_t len);
void regdump(u64 addr, size_t len);
int sprintf(char *str, const char *fmt, ...);
int debug_printf(const char *fmt, ...);
void udelay(u32 d);
void reboot(void) __attribute__((noreturn));

#define panic(fmt, ...)                                                                            \
    do {                                                                                           \
        debug_printf(fmt, ##__VA_ARGS__);                                                          \
        reboot();                                                                                  \
    } while (0)

#endif
