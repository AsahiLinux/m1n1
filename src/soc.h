/* SPDX-License-Identifier: MIT */

#ifndef __SOC_H__
#define __SOC_H__

#include "../config.h"

#define S5L8960X 0x8960
#define T7000    0x7000
#define T7001    0x7001
#define S8000    0x8000
#define S8001    0x8001
#define S8003    0x8003
#define T8010    0x8010
#define T8011    0x8011
#define T8012    0x8012
#define T8015    0x8015

#define T8103 0x8103
#define T8112 0x8112
#define T8122 0x8122
#define T6000 0x6000
#define T6001 0x6001
#define T6002 0x6002
#define T6020 0x6020
#define T6021 0x6021
#define T6022 0x6022
#define T6030 0x6030
#define T6031 0x6031
#define T6034 0x6034

#ifdef TARGET

#if TARGET == T8103
#define EARLY_UART_BASE 0x235200000
#elif TARGET == T6000 || TARGET == T6001 || TARGET == T6002 || TARGET == T6020 ||                  \
    TARGET == T6021 || TARGET == T6022
#define EARLY_UART_BASE 0x39b200000
#elif TARGET == T8112
#define EARLY_UART_BASE 0x235200000
#elif TARGET == T6034 || TARGET == T6031
#define EARLY_UART_BASE 0x391200000
#elif TARGET == T8015
#define EARLY_UART_BASE 0x22e600000
#elif TARGET == T6030
#define EARLY_UART_BASE 0x289200000
#elif TARGET == T7000 || TARGET == T7001 || TARGET == S8000 || TARGET == S8001 ||                  \
    TARGET == S8003 || TARGET == T8010 || TARGET == T8011
#if TARGET == T7000 && defined(TARGET_BOARD) && TARGET_BOARD == 0x34 // Apple TV HD
#define EARLY_UART_BASE 0x20a0d8000
#else
#define EARLY_UART_BASE 0x20a0c0000
#endif

#elif TARGET == T8012
#define EARLY_UART_BASE 0x20a600000
#elif TARGET == S5L8960X
#define EARLY_UART_BASE 0x20a0a0000
#endif

#endif
#endif
