/* SPDX-License-Identifier: MIT */

#ifndef __SOC_H__
#define __SOC_H__

#include "../config.h"

#define T8103 0x8103
#define T8112 0x8112
#define T8122 0x8122
#define T6000 0x6000
#define T6001 0x6001
#define T6002 0x6002
#define T6020 0x6020
#define T6030 0x6030
#define T6021 0x6021
#define T6022 0x6022
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
#endif

#endif
#endif
