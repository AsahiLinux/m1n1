/* SPDX-License-Identifier: MIT */

#include "utils.h"
#include "types.h"
#include "uart.h"
#include "vsprintf.h"

#include <stdarg.h>

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
        printf("%08x  ", off);
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
        printf("%016x  ", addr + off);
        for (i = 0; i < 32; i += 4) {
            printf("%08x ", read32(addr + off + i));
        }
        printf("\n");
    }
}

int sprintf(char *buffer, const char *fmt, ...)
{
    va_list args;
    int i;

    va_start(args, fmt);
    i = vsprintf(buffer, fmt, args);
    va_end(args);
    return i;
}

int debug_printf(const char *fmt, ...)
{
    va_list args;
    char buffer[512];
    int i;

    va_start(args, fmt);
    i = vsprintf(buffer, fmt, args);
    va_end(args);

    uart_write(buffer, i);

    return i;
}
