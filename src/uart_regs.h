/* SPDX-License-Identifier: MIT */

#define ULCON    0x000
#define UCON     0x004
#define UFCON    0x008
#define UTRSTAT  0x010
#define UFSTAT   0x018
#define UTXH     0x020
#define URXH     0x024
#define UBRDIV   0x028
#define UFRACVAL 0x02c

#define UCON_TXTHRESH_ENA BIT(13)
#define UCON_RXTHRESH_ENA BIT(12)
#define UCON_RXTO_ENA     BIT(9)
#define UCON_TXMODE       GENMASK(3, 2)
#define UCON_RXMODE       GENMASK(1, 0)

#define UCON_MODE_OFF 0
#define UCON_MODE_IRQ 1

#define UTRSTAT_RXTO     BIT(9)
#define UTRSTAT_TXTHRESH BIT(5)
#define UTRSTAT_RXTHRESH BIT(4)
#define UTRSTAT_TXE      BIT(2)
#define UTRSTAT_TXBE     BIT(1)
#define UTRSTAT_RXD      BIT(0)

#define UFSTAT_TXFULL BIT(9)
#define UFSTAT_RXFULL BIT(8)
#define UFSTAT_TXCNT  GENMASK(7, 4)
#define UFSTAT_RXCNT  GENMASK(3, 0)
