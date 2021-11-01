/* SPDX-License-Identifier: MIT */

#ifndef __SOC_H__
#define __SOC_H__

#include "../config.h"

#define T8103 0x8103
#define T6000 0x6000
#define T6001 0x6001

#ifdef TARGET

#if TARGET == T8103
#define EARLY_UART_BASE 0x235200000
#elif TARGET == T6000 || TARGET == T6001
#define EARLY_UART_BASE 0x39b200000
#endif

#endif
#endif
