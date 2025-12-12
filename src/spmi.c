/* SPDX-License-Identifier: MIT */

#include "spmi.h"
#include "adt.h"
#include "malloc.h"

#define SPMI_STATUS 0x00
#define SPMI_CMD    0x04
#define SPMI_REPLY  0x08

#define SPMI_CMD_EXTRA  GENMASK(31, 16)
#define SPMI_CMD_ACTIVE BIT(15)
#define SPMI_CMD_ADDR   GENMASK(14, 8)
#define SPMI_CMD_OPCODE GENMASK(7, 0)

#define SPMI_REPLY_FRAME_PARITY GENMASK(31, 16)
#define SPMI_REPLY_ACK          BIT(15)
#define SPMI_REPLY_ADDR         GENMASK(14, 8)
#define SPMI_REPLY_OPCODE       GENMASK(7, 0)

#define SPMI_STATUS_RX_EMPTY BIT(24)
#define SPMI_STATUS_RX_COUNT GENMASK(23, 16)
#define SPMI_STATUS_TX_EMPTY BIT(8)
#define SPMI_STATUS_TX_COUNT GENMASK(7, 0)

#define SPMI_OPC_RESET    0x10
#define SPMI_OPC_SLEEP    0x11
#define SPMI_OPC_SHUTDOWN 0x12
#define SPMI_OPC_WAKEUP   0x13

#define SPMI_OPC_SLAVE_DESC 0x1c

#define SPMI_OPC_EXT_WRITE  0x00
#define SPMI_OPC_EXT_READ   0x20
#define SPMI_OPC_EXT_WRITEL 0x30
#define SPMI_OPC_EXT_READL  0x38
#define SPMI_OPC_WRITE      0x40
#define SPMI_OPC_READ       0x60
#define SPMI_OPC_ZERO_WRITE 0x80

struct spmi_dev {
    uintptr_t base;
};

spmi_dev_t *spmi_init(const char *adt_node)
{
    int adt_path[8];
    int adt_offset;
    adt_offset = adt_path_offset_trace(adt, adt_node, adt_path);
    if (adt_offset < 0) {
        printf("spmi: Error getting %s node\n", adt_node);
        return NULL;
    }

    u64 base;
    if (adt_get_reg(adt, adt_path, "reg", 0, &base, NULL) < 0) {
        printf("spmi: Error getting %s regs\n", adt_node);
        return NULL;
    }

    spmi_dev_t *dev = calloc(1, sizeof(*dev));
    if (!dev)
        return NULL;

    dev->base = base;
    return dev;
}

void spmi_shutdown(spmi_dev_t *dev)
{
    free(dev);
}

static int wait_rx_fifo(spmi_dev_t *dev)
{
    for (size_t i = 0; i < 1000; i++) {
        if (!(read32(dev->base + SPMI_STATUS) & SPMI_STATUS_RX_EMPTY))
            return 0;
        udelay(10);
    }
    printf("spmi: Timeout waiting for RX data\n");
    return -1;
}

static int raw_command(spmi_dev_t *dev, u8 addr, u8 opc, u16 extra, const u8 *data_in,
                       size_t len_in, u8 *data_out, size_t len_out)
{
    if (addr != (addr & MASK(4))) {
        printf("spmi: Invalid slave address %u\n", addr);
        return -SPMI_ERR_INVALID_PARAM;
    }
    if (len_out > 16) {
        printf("spmi: Invalid out size %lu\n", len_out);
        return -SPMI_ERR_INVALID_PARAM;
    }

    // ensure FIFOs are in the correct state
    if (!(read32(dev->base + SPMI_STATUS) & SPMI_STATUS_TX_EMPTY)) {
        printf("spmi: TX FIFO has unsent commands\n");
        return -SPMI_ERR_UNKNOWN;
    }

    while (!(read32(dev->base + SPMI_STATUS) & SPMI_STATUS_RX_EMPTY))
        printf("spmi: Leftover RX data: 0x%x\n", read32(dev->base + SPMI_REPLY));

    // write command
    write32(dev->base + SPMI_CMD, FIELD_PREP(SPMI_CMD_EXTRA, extra) | SPMI_CMD_ACTIVE |
                                      FIELD_PREP(SPMI_CMD_ADDR, addr) |
                                      FIELD_PREP(SPMI_CMD_OPCODE, opc));

    for (size_t i = 0; i < len_in;) {
        u32 data = 0;
        for (size_t j = 0; (j < 4) && (i < len_in);)
            data |= data_in[i++] << (j++ * 8);
        write32(dev->base + SPMI_CMD, data);
    }

    // read response
    if (wait_rx_fifo(dev) < 0)
        return -SPMI_ERR_UNKNOWN;
    u32 reply = read32(dev->base + SPMI_REPLY);

    if (FIELD_GET(SPMI_REPLY_OPCODE, reply) != opc || FIELD_GET(SPMI_REPLY_ADDR, reply) != addr) {
        printf("spmi: Unexpected SPMI response 0x%x, leftover RX data?\n", reply);
        return -SPMI_ERR_UNKNOWN;
    }

    for (size_t i = 0; i < len_out;) {
        if (read32(dev->base + SPMI_STATUS) & SPMI_STATUS_RX_EMPTY) {
            printf("spmi: Reply was shorter than expected\n");
            return -SPMI_ERR_UNKNOWN;
        }
        u32 data = read32(dev->base + SPMI_REPLY);
        for (size_t j = 0; (j < 4) && (i < len_out);)
            data_out[i++] = data >> (j++ * 8);
    }

    if (FIELD_GET(SPMI_REPLY_FRAME_PARITY, reply) != MASK(len_out))
        return -SPMI_ERR_BUS_IO;
    if (!len_in && !(reply & SPMI_REPLY_ACK))
        return -SPMI_ERR_BUS_IO;
    return 0;
}

int spmi_send_reset(spmi_dev_t *dev, u8 addr)
{
    return raw_command(dev, addr, SPMI_OPC_RESET, 0, NULL, 0, NULL, 0);
}

int spmi_send_sleep(spmi_dev_t *dev, u8 addr)
{
    return raw_command(dev, addr, SPMI_OPC_SLEEP, 0, NULL, 0, NULL, 0);
}

int spmi_send_shutdown(spmi_dev_t *dev, u8 addr)
{
    return raw_command(dev, addr, SPMI_OPC_SHUTDOWN, 0, NULL, 0, NULL, 0);
}

int spmi_send_wakeup(spmi_dev_t *dev, u8 addr)
{
    return raw_command(dev, addr, SPMI_OPC_WAKEUP, 0, NULL, 0, NULL, 0);
}

int spmi_reg0_write(spmi_dev_t *dev, u8 addr, u8 value)
{
    if (value != (value & MASK(7))) {
        printf("spmi: Invalid reg 0 value %u\n", value);
        return -SPMI_ERR_INVALID_PARAM;
    }
    return raw_command(dev, addr, SPMI_OPC_ZERO_WRITE | value, value << 8, NULL, 0, NULL, 0);
}

int spmi_ext_read(spmi_dev_t *dev, u8 addr, u8 reg, u8 *bfr, size_t len)
{
    if (len < 1 || len > 16) {
        printf("spmi: Invalid size for extended read\n");
        return -SPMI_ERR_INVALID_PARAM;
    }
    return raw_command(dev, addr, SPMI_OPC_EXT_READ | (len - 1), reg, NULL, 0, bfr, len);
}

int spmi_ext_write(spmi_dev_t *dev, u8 addr, u8 reg, const u8 *bfr, size_t len)
{
    if (len < 1 || len > 16) {
        printf("spmi: Invalid size for extended write\n");
        return -SPMI_ERR_INVALID_PARAM;
    }
    return raw_command(dev, addr, SPMI_OPC_EXT_WRITE | (len - 1), reg, bfr, len, NULL, 0);
}

int spmi_ext_read_long(spmi_dev_t *dev, u8 addr, u16 reg, u8 *bfr, size_t len)
{
    if (len < 1 || len > 8) {
        printf("spmi: Invalid size for extended read long\n");
        return -SPMI_ERR_INVALID_PARAM;
    }
    return raw_command(dev, addr, SPMI_OPC_EXT_READL | (len - 1), reg, NULL, 0, bfr, len);
}

int spmi_ext_write_long(spmi_dev_t *dev, u8 addr, u16 reg, const u8 *bfr, size_t len)
{
    if (len < 1 || len > 8) {
        printf("spmi: Invalid size for extended write long\n");
        return -SPMI_ERR_INVALID_PARAM;
    }
    return raw_command(dev, addr, SPMI_OPC_EXT_WRITEL | (len - 1), reg, bfr, len, NULL, 0);
}
