/* SPDX-License-Identifier: MIT */

#define AIC_REG_SIZE     0x8000
#define AIC_INFO         0x0004
#define AIC_WHOAMI       0x2000
#define AIC_EVENT        0x2004
#define AIC_IPI_SEND     0x2008
#define AIC_IPI_ACK      0x200c
#define AIC_IPI_MASK_SET 0x2024
#define AIC_IPI_MASK_CLR 0x2028
#define AIC_TARGET_CPU   0x3000
#define AIC_SW_SET       0x4000
#define AIC_SW_CLR       0x4080
#define AIC_MASK_SET     0x4100
#define AIC_MASK_CLR     0x4180

#define AIC_CPU_IPI_SET(cpu)      (0x5008 + ((cpu) << 7))
#define AIC_CPU_IPI_CLR(cpu)      (0x500c + ((cpu) << 7))
#define AIC_CPU_IPI_MASK_SET(cpu) (0x5024 + ((cpu) << 7))
#define AIC_CPU_IPI_MASK_CLR(cpu) (0x5028 + ((cpu) << 7))

#define AIC2_INFO1   0x0004
#define AIC2_INFO2   0x0008
#define AIC2_INFO3   0x000c
#define AIC2_LATENCY 0x0204
#define AIC2_IRQ_CFG 0x2000

#define AIC2_IRQ_CFG_TARGET GENMASK(3, 0)

#define AIC_INFO_NR_HW GENMASK(15, 0)

#define AIC2_INFO1_NR_IRQ   GENMASK(15, 0)
#define AIC2_INFO1_LAST_DIE GENMASK(27, 24)

#define AIC2_INFO3_MAX_IRQ GENMASK(15, 0)
#define AIC2_INFO3_MAX_DIE GENMASK(27, 24)

#define AIC_EVENT_DIE  GENMASK(31, 24)
#define AIC_EVENT_TYPE GENMASK(23, 16)
#define AIC_EVENT_NUM  GENMASK(15, 0)

#define AIC_EVENT_TYPE_HW   1
#define AIC_EVENT_TYPE_IPI  4
#define AIC_EVENT_IPI_OTHER 1
#define AIC_EVENT_IPI_SELF  2

#define AIC_IPI_SEND_CPU(cpu) BIT(cpu)

#define AIC_IPI_OTHER BIT(0)
#define AIC_IPI_SELF  BIT(31)

#define AIC1_MAX_IRQ   0x400
#define AIC_MAX_HW_NUM (0x80 * 32) // max_irq of the M1 Max
