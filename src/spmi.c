/* SPDX-License-Identifier: MIT */

#include "spmi.h"
#include "adt.h"
#include "malloc.h"

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

struct spmi_regs {
    size_t status_offset;
    size_t cmd_offset;
    size_t reply_offset;

    u32 cmd_extra_mask;
    u32 cmd_active_mask;
    u32 cmd_addr_mask;
    u32 cmd_opcode_mask;

    u32 reply_frame_parity_mask;
    u32 reply_ack_mask;
    u32 reply_addr_mask;
    u32 reply_opcode_mask;

    u32 status_rx_empty_mask;
    u32 status_rx_count_mask;
    u32 status_tx_empty_mask;
    u32 status_tx_count_mask;
};

static const struct spmi_regs regs_gen1 = {
    .status_offset = 0x00,
    .cmd_offset = 0x04,
    .reply_offset = 0x08,

    .cmd_extra_mask = GENMASK(31, 16),
    .cmd_active_mask = BIT(15),
    .cmd_addr_mask = GENMASK(14, 8),
    .cmd_opcode_mask = GENMASK(7, 0),

    .reply_frame_parity_mask = GENMASK(31, 16),
    .reply_ack_mask = BIT(15),
    .reply_addr_mask = GENMASK(14, 8),
    .reply_opcode_mask = GENMASK(7, 0),

    .status_rx_empty_mask = BIT(24),
    .status_rx_count_mask = GENMASK(23, 16),
    .status_tx_empty_mask = BIT(8),
    .status_tx_count_mask = GENMASK(7, 0),
};

static const struct spmi_regs regs_gen4 = {
    .status_offset = 0x200,
    .cmd_offset = 0x210,
    .reply_offset = 0x220,

    .cmd_extra_mask = GENMASK(31, 16),
    .cmd_active_mask = BIT(15),
    .cmd_addr_mask = GENMASK(14, 8),
    .cmd_opcode_mask = GENMASK(7, 0),

    .reply_frame_parity_mask = GENMASK(31, 16),
    .reply_ack_mask = BIT(15),
    .reply_addr_mask = GENMASK(14, 8),
    .reply_opcode_mask = GENMASK(7, 0),

    .status_rx_empty_mask = BIT(30),
    .status_rx_count_mask = GENMASK(23, 16),
    .status_tx_empty_mask = BIT(14),
    .status_tx_count_mask = GENMASK(7, 0),
};

struct spmi_dev {
    uintptr_t base;
    const struct spmi_regs *regs;
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

    s32 gen;
    int ret = ADT_GETPROP(adt, adt_offset, "gen", &gen);
    if (ret == -1) // NotFound
        gen = -1;
    else if (ret < 0) {
        printf("spmi: Error getting %s gen\n", adt_node);
        return NULL;
    }

    spmi_dev_t *dev = calloc(1, sizeof(*dev));
    if (!dev)
        return NULL;

    if (gen >= 4)
        dev->regs = &regs_gen4;
    else // Includes the error case (-1) as old adts don't have the gen property
        dev->regs = &regs_gen1;

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
        if (!(read32(dev->base + dev->regs->status_offset) & dev->regs->status_rx_empty_mask))
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
    if (!(read32(dev->base + dev->regs->status_offset) & dev->regs->status_tx_empty_mask)) {
        printf("spmi: TX FIFO has unsent commands\n");
        return -SPMI_ERR_UNKNOWN;
    }

    while (!(read32(dev->base + dev->regs->status_offset) & dev->regs->status_rx_empty_mask))
        printf("spmi: Leftover RX data: 0x%x\n", read32(dev->base + dev->regs->reply_offset));

    // write command
    write32(dev->base + dev->regs->cmd_offset, FIELD_PREP(dev->regs->cmd_extra_mask, extra) |
                                                   dev->regs->cmd_active_mask |
                                                   FIELD_PREP(dev->regs->cmd_addr_mask, addr) |
                                                   FIELD_PREP(dev->regs->cmd_opcode_mask, opc));

    for (size_t i = 0; i < len_in;) {
        u32 data = 0;
        for (size_t j = 0; (j < 4) && (i < len_in);)
            data |= data_in[i++] << (j++ * 8);
        write32(dev->base + dev->regs->cmd_offset, data);
    }

    // read response
    if (wait_rx_fifo(dev) < 0)
        return -SPMI_ERR_UNKNOWN;
    u32 reply = read32(dev->base + dev->regs->reply_offset);

    if (FIELD_GET(dev->regs->reply_opcode_mask, reply) != opc ||
        FIELD_GET(dev->regs->reply_addr_mask, reply) != addr) {
        printf("spmi: Unexpected SPMI response 0x%x, leftover RX data?\n", reply);
        return -SPMI_ERR_UNKNOWN;
    }

    for (size_t i = 0; i < len_out;) {
        if (read32(dev->base + dev->regs->status_offset) & dev->regs->status_rx_empty_mask) {
            printf("spmi: Reply was shorter than expected\n");
            return -SPMI_ERR_UNKNOWN;
        }
        u32 data = read32(dev->base + dev->regs->reply_offset);
        for (size_t j = 0; (j < 4) && (i < len_out);)
            data_out[i++] = data >> (j++ * 8);
    }

    if (FIELD_GET(dev->regs->reply_frame_parity_mask, reply) != MASK(len_out))
        return -SPMI_ERR_BUS_IO;
    if (!len_out && !(reply & dev->regs->reply_ack_mask))
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
