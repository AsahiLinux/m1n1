/* SPDX-License-Identifier: MIT */

#ifndef UTILS_H
#define UTILS_H

#include "cpu_regs.h"
#include "soc.h"
#include "types.h"

#define printf(...) debug_printf(__VA_ARGS__)

#ifdef DEBUG
#define dprintf(...) debug_printf(__VA_ARGS__)
#else
#define dprintf(...)                                                                               \
    do {                                                                                           \
    } while (0)
#endif

#define ARRAY_SIZE(s) (sizeof(s) / sizeof((s)[0]))

#define ALIGN_UP(x, a)   (((x) + ((a) - 1)) & ~((a) - 1))
#define ALIGN_DOWN(x, a) ((x) & ~((a) - 1))

#define min(a, b) (((a) < (b)) ? (a) : (b))
#define max(a, b) (((a) > (b)) ? (a) : (b))

#define USEC_PER_SEC 1000000L

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

static inline u64 writeread64(u64 addr, u64 data)
{
    write64(addr, data);
    return read64(addr);
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

static inline u32 writeread32(u64 addr, u32 data)
{
    write32(addr, data);
    return read32(addr);
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

static inline u16 writeread16(u64 addr, u16 data)
{
    write16(addr, data);
    return read16(addr);
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

static inline u8 writeread8(u64 addr, u8 data)
{
    write8(addr, data);
    return read8(addr);
}

static inline void write64_lo_hi(u64 addr, u64 val)
{
    write32(addr, val);
    write32(addr + 4, val >> 32);
}

#define _concat(a, _1, b, ...) a##b

#define _sr_tkn_S(_0, _1, op0, op1, CRn, CRm, op2) s##op0##_##op1##_c##CRn##_c##CRm##_##op2

#define _sr_tkn(a) a

#define sr_tkn(...) _concat(_sr_tkn, __VA_ARGS__, )(__VA_ARGS__)

#define __mrs(reg)                                                                                 \
    ({                                                                                             \
        u64 val;                                                                                   \
        __asm__ volatile("mrs\t%0, " #reg : "=r"(val));                                            \
        val;                                                                                       \
    })
#define _mrs(reg) __mrs(reg)

#define __msr(reg, val)                                                                            \
    ({                                                                                             \
        u64 __val = (u64)val;                                                                      \
        __asm__ volatile("msr\t" #reg ", %0" : : "r"(__val));                                      \
    })
#define _msr(reg, val) __msr(reg, val)

#define mrs(reg)      _mrs(sr_tkn(reg))
#define msr(reg, val) _msr(sr_tkn(reg), val)
#define msr_sync(reg, val)                                                                         \
    ({                                                                                             \
        _msr(sr_tkn(reg), val);                                                                    \
        sysop("isb");                                                                              \
    })

#define reg_clr(reg, bits)      _msr(sr_tkn(reg), _mrs(sr_tkn(reg)) & ~(bits))
#define reg_set(reg, bits)      _msr(sr_tkn(reg), _mrs(sr_tkn(reg)) | bits)
#define reg_mask(reg, clr, set) _msr(sr_tkn(reg), (_mrs(sr_tkn(reg)) & ~(clr)) | set)

#define reg_clr_sync(reg, bits)                                                                    \
    ({                                                                                             \
        reg_clr(sr_tkn(reg), bits);                                                                \
        sysop("isb");                                                                              \
    })
#define reg_set_sync(reg, bits)                                                                    \
    ({                                                                                             \
        reg_set(sr_tkn(reg), bits);                                                                \
        sysop("isb");                                                                              \
    })
#define reg_mask_sync(reg, clr, set)                                                               \
    ({                                                                                             \
        reg_mask(sr_tkn(reg), clr, set);                                                           \
        sysop("isb");                                                                              \
    })

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

#define dma_mb()  sysop("dmb osh")
#define dma_rmb() sysop("dmb oshld")
#define dma_wmb() sysop("dmb oshst")

extern u32 board_id, chip_id;
static inline bool has_ecores(void)
{
    return !(chip_id == S5L8960X || chip_id == T7000 || chip_id == T7001 || chip_id == S8000 ||
             chip_id == S8001 || chip_id == S8003);
}

static inline int is_ecore(void)
{
    return has_ecores() && !(mrs(MPIDR_EL1) & (1 << 16));
}

static inline int in_el2(void)
{
    return (mrs(CurrentEL) >> 2) == 2;
}

static inline int in_el3(void)
{
    return (mrs(CurrentEL) >> 2) == 3;
}

static inline int has_el3(void)
{
    return !!(mrs(ID_AA64PFR0_EL1) & 0xf000);
}

static inline int has_el2(void)
{
    return !!(mrs(ID_AA64PFR0_EL1) & 0xf00);
}

static inline bool is_16k(void)
{
    return ((mrs(ID_AA64MMFR0_EL1) >> 20) & 0xf) == 0x1;
}

extern int boot_cpu_idx;
extern u64 boot_cpu_mpidr;
static inline int is_boot_cpu(void)
{
    return boot_cpu_idx == -1 || boot_cpu_mpidr == mrs(MPIDR_EL1);
}

static inline size_t get_page_size(void)
{
    return is_16k() ? 16384 : 4096;
}

extern char _base[];
extern char _rodata_end[];
extern char _end[];
extern char _payload_start[];
extern char _payload_end[];

/*
 * These functions are guaranteed to copy by reading from src and writing to dst
 * in <n>-bit units If size is not aligned, the remaining bytes are not copied
 */
void memcpy128(void *dst, void *src, size_t size);
void memset64(void *dst, u64 value, size_t size);
void memcpy64(void *dst, void *src, size_t size);
void memset32(void *dst, u32 value, size_t size);
void memcpy32(void *dst, void *src, size_t size);
void memset16(void *dst, u16 value, size_t size);
void memcpy16(void *dst, void *src, size_t size);
void memset8(void *dst, u8 value, size_t size);
void memcpy8(void *dst, void *src, size_t size);

void get_simd_state(void *state);
void put_simd_state(void *state);

void hexdump(const void *d, size_t len);
void regdump(u64 addr, size_t len);
int snprintf(char *str, size_t size, const char *fmt, ...);
int debug_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void udelay(u32 d);

static inline u64 get_ticks(void)
{
    return mrs(CNTPCT_EL0);
}
u64 ticks_to_msecs(u64 ticks);
u64 ticks_to_usecs(u64 ticks);

void reboot(void) __attribute__((noreturn));
void flush_and_reboot(void) __attribute__((noreturn));

u64 timeout_calculate(u32 usec);
bool timeout_expired(u64 timeout);

#define SPINLOCK_ALIGN 64

typedef struct {
    s64 lock;
    int count;
} spinlock_t ALIGNED(SPINLOCK_ALIGN);

// 18.1.6 vs 18.1.1 diff
// clang-format off
#define SPINLOCK_INIT       {-1, 0}
// clang-format on
#define DECLARE_SPINLOCK(n) spinlock_t n = SPINLOCK_INIT;

void spin_init(spinlock_t *lock);
void spin_lock(spinlock_t *lock);
void spin_unlock(spinlock_t *lock);

#define mdelay(m) udelay((m) * 1000)

#define panic(fmt, ...)                                                                            \
    do {                                                                                           \
        debug_printf(fmt, ##__VA_ARGS__);                                                          \
        flush_and_reboot();                                                                        \
    } while (0)

static inline int poll32(u64 addr, u32 mask, u32 target, u32 timeout)
{
    while (--timeout > 0) {
        u32 value = read32(addr) & mask;
        if (value == target)
            return 0;
        udelay(1);
    }

    return -1;
}

typedef u64(generic_func)(u64, u64, u64, u64, u64);

struct vector_args {
    generic_func *entry;
    u64 args[5];
    bool restore_logo;
};

extern u32 board_id, chip_id;

extern bool is_mac;
extern bool cpufeat_actlr_el2, cpufeat_fast_ipi, cpufeat_mmu_sprr;
extern bool cpufeat_global_sleep, cpufeat_workaround_cyclone_cache;

extern struct vector_args next_stage;
extern u64 boot_flags, mem_size_actual;

void cpu_sleep(bool deep) __attribute__((noreturn));
void deep_wfi(void);

bool is_heap(void *addr);
bool supports_arch_retention(void);
bool supports_gxf(void);
bool supports_pan(void);
u64 top_of_memory_alloc(size_t size);

#endif
