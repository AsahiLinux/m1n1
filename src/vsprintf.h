/* SPDX-License-Identifier: MIT */

#ifndef VSPRINTF_H
#define VSPRINTF_H

#include <stdarg.h>

int vsprintf(char *buf, const char *fmt, va_list args);
int vsnprintf(char *buf, size_t size, const char *fmt, va_list args);

#endif
