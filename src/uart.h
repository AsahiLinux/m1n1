/* SPDX-License-Identifier: MIT */

#ifndef UART_H
#define UART_H

#include "types.h"

int uart_init(void);

void uart_putbyte(u8 c);
u8 uart_getbyte(void);

void uart_putchar(u8 c);
u8 uart_getchar(void);

void uart_write(const void *buf, size_t count);
size_t uart_read(void *buf, size_t count);

void uart_puts(const char *s);

void uart_setbaud(int baudrate);

void uart_flush(void);

void uart_clear_irqs(void);

int uart_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif
