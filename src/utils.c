/* SPDX-License-Identifier: MIT */

#include <assert.h>
#include <stdarg.h>

#include "utils.h"
#include "iodev.h"
#include "smp.h"
#include "types.h"
#include "vsprintf.h"
#include "xnuboot.h"

static char ascii(char s)
{
    if (s < 0x20)
        return '.';
    if (s > 0x7E)
        return '.';
    return s;
}

void hexdump(const void *d, size_t len)
{
    u8 *data;
    size_t i, off;
    data = (u8 *)d;
    for (off = 0; off < len; off += 16) {
        printf("%08lx  ", off);
        for (i = 0; i < 16; i++) {
            if ((i + off) >= len)
                printf("   ");
            else
                printf("%02x ", data[off + i]);
        }

        printf(" ");
        for (i = 0; i < 16; i++) {
            if ((i + off) >= len)
                printf(" ");
            else
                printf("%c", ascii(data[off + i]));
        }
        printf("\n");
    }
}

void regdump(u64 addr, size_t len)
{
    u64 i, off;
    for (off = 0; off < len; off += 32) {
        printf("%016lx  ", addr + off);
        for (i = 0; i < 32; i += 4) {
            printf("%08x ", read32(addr + off + i));
        }
        printf("\n");
    }
}

int snprintf(char *buffer, size_t size, const char *fmt, ...)
{
    va_list args;
    int i;

    va_start(args, fmt);
    i = vsnprintf(buffer, size, fmt, args);
    va_end(args);
    return i;
}

int debug_printf(const char *fmt, ...)
{
    va_list args;
    char buffer[512];
    int i;

    va_start(args, fmt);
    i = vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);

    iodev_console_write(buffer, min(i, (int)(sizeof(buffer) - 1)));

    return i;
}

void __assert_fail(const char *assertion, const char *file, unsigned int line, const char *function)
{
    printf("Assertion failed: '%s' on %s:%d:%s\n", assertion, file, line, function);
    flush_and_reboot();
}

void udelay(u32 d)
{
    u64 delay = ((u64)d) * mrs(CNTFRQ_EL0) / 1000000;
    u64 val = mrs(CNTPCT_EL0);
    while ((mrs(CNTPCT_EL0) - val) < delay)
        ;
    sysop("isb");
}

u64 ticks_to_msecs(u64 ticks)
{
    // NOTE: only accurate if freq is even kHz
    return ticks / (mrs(CNTFRQ_EL0) / 1000);
}

u64 ticks_to_usecs(u64 ticks)
{
    // NOTE: only accurate if freq is even MHz
    return ticks / (mrs(CNTFRQ_EL0) / 1000000);
}

u64 timeout_calculate(u32 usec)
{
    u64 delay = ((u64)usec) * mrs(CNTFRQ_EL0) / 1000000;
    return mrs(CNTPCT_EL0) + delay;
}

bool timeout_expired(u64 timeout)
{
    bool expired = mrs(CNTPCT_EL0) > timeout;
    sysop("isb");
    return expired;
}

void flush_and_reboot(void)
{
    iodev_console_flush();
    reboot();
}

void spin_init(spinlock_t *lock)
{
    lock->lock = -1;
    lock->count = 0;
}

void spin_lock(spinlock_t *lock)
{
    s64 tmp;
    s64 me = smp_id();
    if (__atomic_load_n(&lock->lock, __ATOMIC_ACQUIRE) == me) {
        lock->count++;
        return;
    }

    __asm__ volatile("1:\n"
                     "mov\t%0, -1\n"
                     "2:\n"
                     "\tcasa\t%0, %2, %1\n"
                     "\tcmn\t%0, 1\n"
                     "\tbeq\t3f\n"
                     "\tldxr\t%0, %1\n"
                     "\tcmn\t%0, 1\n"
                     "\tbeq\t2b\n"
                     "\twfe\n"
                     "\tb\t1b\n"
                     "3:"
                     : "=&r"(tmp), "+m"(lock->lock)
                     : "r"(me)
                     : "cc", "memory");

    assert(__atomic_load_n(&lock->lock, __ATOMIC_RELAXED) == me);
    lock->count++;
}

void spin_unlock(spinlock_t *lock)
{
    s64 me = smp_id();
    assert(__atomic_load_n(&lock->lock, __ATOMIC_RELAXED) == me);
    assert(lock->count > 0);
    if (!--lock->count)
        __atomic_store_n(&lock->lock, -1L, __ATOMIC_RELEASE);
}

bool is_heap(void *addr)
{
    u64 p = (u64)addr;
    u64 top_of_kernel_data = (u64)cur_boot_args.top_of_kernel_data;
    u64 top_of_ram = cur_boot_args.mem_size + cur_boot_args.phys_base;

    return p > top_of_kernel_data && p < top_of_ram;
}
