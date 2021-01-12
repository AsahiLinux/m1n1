/* SPDX-License-Identifier: MIT */

#ifndef UART_H
#define UART_H

void uart_init(void);

void uart_putc(u8 c);
u8 uart_getc(void);

void uart_write(const void *buf, size_t count);

void uart_puts(const char *s);

#endif
