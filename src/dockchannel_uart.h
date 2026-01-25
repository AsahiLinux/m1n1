/* SPDX-License-Identifier: MIT */

#ifndef DOCKCHANNEL_UART_H
#define DOCKCHANNEL_UART_H

#include "types.h"

int dockchannel_uart_init(void);

void dockchannel_uart_putbyte(u8 c);
u8 dockchannel_uart_getbyte(void);

void dockchannel_uart_putchar(u8 c);
u8 dockchannel_uart_getchar(void);

void dockchannel_uart_write(const void *buf, size_t count);
size_t dockchannel_uart_read(void *buf, size_t count);

void dockchannel_uart_puts(const char *s);
int dockchannel_uart_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif
