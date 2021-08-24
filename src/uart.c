/* SPDX-License-Identifier: MIT */

#include <stdarg.h>

#include "uart.h"
#include "iodev.h"
#include "types.h"
#include "uart_regs.h"
#include "utils.h"
#include "vsprintf.h"

#define UART_CLOCK 24000000

#define UART_BASE 0x235200000L

void *pxx = uart_init;

void uart_init(void)
{
    /* keep UART config from iBoot */
}

void uart_putbyte(u8 c)
{
    while (!(read32(UART_BASE + UTRSTAT) & UTRSTAT_TXBE))
        ;

    write32(UART_BASE + UTXH, c);
}

u8 uart_getbyte(void)
{
    while (!(read32(UART_BASE + UTRSTAT) & UTRSTAT_RXD))
        ;

    return read32(UART_BASE + URXH);
}

void uart_putchar(u8 c)
{
    if (c == '\n')
        uart_putbyte('\r');

    uart_putbyte(c);
}

u8 uart_getchar(void)
{
    return uart_getbyte();
}

void uart_puts(const char *s)
{
    while (*s)
        uart_putchar(*(s++));

    uart_putchar('\n');
}

void uart_write(const void *buf, size_t count)
{
    const u8 *p = buf;

    while (count--)
        uart_putbyte(*p++);
}

size_t uart_read(void *buf, size_t count)
{
    u8 *p = buf;
    size_t recvd = 0;

    while (count--) {
        *p++ = uart_getbyte();
        recvd++;
    }

    return recvd;
}

void uart_setbaud(int baudrate)
{
    uart_flush();
    write32(UART_BASE + UBRDIV, ((UART_CLOCK / baudrate + 7) / 16) - 1);
}

void uart_flush(void)
{
    while (!(read32(UART_BASE + UTRSTAT) & UTRSTAT_TXE))
        ;
}

void uart_clear_irqs(void)
{
    write32(UART_BASE + UTRSTAT, UTRSTAT_TXTHRESH | UTRSTAT_RXTHRESH | UTRSTAT_RXTO);
}

int uart_printf(const char *fmt, ...)
{
    va_list args;
    char buffer[512];
    int i;

    va_start(args, fmt);
    i = vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);

    uart_write(buffer, min(i, (int)(sizeof(buffer) - 1)));

    return i;
}

static bool uart_iodev_can_write(void *opaque)
{
    UNUSED(opaque);
    return true;
}

static ssize_t uart_iodev_can_read(void *opaque)
{
    UNUSED(opaque);
    return (read32(UART_BASE + UTRSTAT) & UTRSTAT_RXD) ? 1 : 0;
}

static ssize_t uart_iodev_read(void *opaque, void *buf, size_t len)
{
    UNUSED(opaque);
    return uart_read(buf, len);
}

static ssize_t uart_iodev_write(void *opaque, const void *buf, size_t len)
{
    UNUSED(opaque);
    uart_write(buf, len);
    return len;
}

static struct iodev_ops iodev_uart_ops = {
    .can_read = uart_iodev_can_read,
    .can_write = uart_iodev_can_write,
    .read = uart_iodev_read,
    .write = uart_iodev_write,
};

struct iodev iodev_uart = {
    .ops = &iodev_uart_ops,
    .usage = USAGE_CONSOLE | USAGE_UARTPROXY,
};
