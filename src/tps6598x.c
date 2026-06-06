/* SPDX-License-Identifier: MIT */

#include "tps6598x.h"
#include "adt.h"
#include "i2c.h"
#include "iodev.h"
#include "malloc.h"
#include "types.h"
#include "utils.h"

#define TPS_REG_CMD1        0x08
#define TPS_REG_DATA1       0x09
#define TPS_REG_INT_EVENT1  0x14
#define TPS_REG_INT_MASK1   0x16
#define TPS_REG_INT_CLEAR1  0x18
#define TPS_REG_POWER_STATE 0x20
#define TPS_CMD_INVALID     0x21434d44 // !CMD

struct tps6598x_dev {
    i2c_dev_t *i2c;
    u8 addr;
};

static tps6598x_dev_t *tps6598x_init(const char *adt_node, const char *addr_prop)
{
    int adt_offset;
    adt_offset = adt_path_offset(adt, adt_node);
    if (adt_offset < 0) {
        printf("tps6598x: Error getting %s node\n", adt_node);
        return NULL;
    }

    const u8 *addr = adt_getprop(adt, adt_offset, addr_prop, NULL);
    if (addr == NULL) {
        printf("tps6598x: Error getting %s %s\n.", adt_node, addr_prop);
        return NULL;
    }

    tps6598x_dev_t *dev = calloc(1, sizeof(*dev));
    if (!dev)
        return NULL;

    dev->addr = *addr;
    return dev;
}

tps6598x_dev_t *tps6598x_init_i2c(const char *adt_node, i2c_dev_t *i2c)
{
    tps6598x_dev_t *dev = tps6598x_init(adt_node, "hpm-iic-addr");
    dev->i2c = i2c;
    return dev;
}

void tps6598x_shutdown(tps6598x_dev_t *dev)
{
    free(dev);
}

static int tps6598x_write_reg(tps6598x_dev_t *dev, const u8 reg, const u8 *data, size_t len)
{
    if (dev->i2c)
        return i2c_smbus_write(dev->i2c, dev->addr, reg, data, len);
    return -1;
}

static int tps6598x_read_reg(tps6598x_dev_t *dev, const u8 reg, u8 *data, size_t len)
{
    if (dev->i2c)
        return i2c_smbus_read(dev->i2c, dev->addr, reg, data, len);
    return -1;
}

int tps6598x_command(tps6598x_dev_t *dev, const char *cmd, const u8 *data_in, size_t len_in,
                     u8 *data_out, size_t len_out)
{
    if (len_in) {
        if (tps6598x_write_reg(dev, TPS_REG_DATA1, data_in, len_in) < 0)
            return -1;
    }

    if (tps6598x_write_reg(dev, TPS_REG_CMD1, (const u8 *)cmd, 4) < 0)
        return -1;

    u32 cmd_status;
    do {
        if (tps6598x_read_reg(dev, TPS_REG_CMD1, (u8 *)&cmd_status, 4) < 0)
            return -1;
        if (cmd_status == TPS_CMD_INVALID)
            return -1;
        udelay(100);
    } while (cmd_status != 0);

    if (len_out) {
        if (tps6598x_read_reg(dev, TPS_REG_DATA1, data_out, len_out) != (ssize_t)len_out)
            return -1;
    }

    return 0;
}

int tps6598x_disable_irqs(tps6598x_dev_t *dev, tps6598x_irq_state_t *state)
{
    size_t read;
    int written;
    static const u8 zeros[CD3218B12_IRQ_WIDTH] = {0x00};
    static const u8 ones[CD3218B12_IRQ_WIDTH] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                                                 0xFF, 0xFF, 0xFF, 0xFF};

    // store IntEvent 1 to restore it later
    read = tps6598x_read_reg(dev, TPS_REG_INT_MASK1, state->int_mask1, sizeof(state->int_mask1));
    if (read != CD3218B12_IRQ_WIDTH) {
        printf("tps6598x: reading TPS_REG_INT_MASK1 failed\n");
        return -1;
    }
    state->valid = 1;

    // mask interrupts and ack all interrupt flags
    written = tps6598x_write_reg(dev, TPS_REG_INT_CLEAR1, ones, sizeof(ones));
    if (written != sizeof(zeros)) {
        printf("tps6598x: writing TPS_REG_INT_CLEAR1 failed, written: %d\n", written);
        return -1;
    }
    written = tps6598x_write_reg(dev, TPS_REG_INT_MASK1, zeros, sizeof(zeros));
    if (written != sizeof(ones)) {
        printf("tps6598x: writing TPS_REG_INT_MASK1 failed, written: %d\n", written);
        return -1;
    }

#ifdef DEBUG
    u8 tmp[CD3218B12_IRQ_WIDTH] = {0x00};
    read = tps6598x_read_reg(dev, TPS_REG_INT_MASK1, tmp, CD3218B12_IRQ_WIDTH);
    if (read != CD3218B12_IRQ_WIDTH)
        printf("tps6598x: failed verification, can't read TPS_REG_INT_MASK1\n");
    else {
        printf("tps6598x: verify: TPS_REG_INT_MASK1 vs. saved IntMask1\n");
        hexdump(tmp, sizeof(tmp));
        hexdump(state->int_mask1, sizeof(state->int_mask1));
    }
#endif
    return 0;
}

int tps6598x_restore_irqs(tps6598x_dev_t *dev, tps6598x_irq_state_t *state)
{
    int written;

    written =
        tps6598x_write_reg(dev, TPS_REG_INT_MASK1, state->int_mask1, sizeof(state->int_mask1));
    if (written != sizeof(state->int_mask1)) {
        printf("tps6598x: restoring TPS_REG_INT_MASK1 failed\n");
        return -1;
    }

#ifdef DEBUG
    int read;
    u8 tmp[CD3218B12_IRQ_WIDTH];
    read = tps6598x_read_reg(dev, TPS_REG_INT_MASK1, tmp, sizeof(tmp));
    if (read != sizeof(tmp))
        printf("tps6598x: failed verification, can't read TPS_REG_INT_MASK1\n");
    else {
        printf("tps6598x: verify saved IntMask1 vs. TPS_REG_INT_MASK1:\n");
        hexdump(state->int_mask1, sizeof(state->int_mask1));
        hexdump(tmp, sizeof(tmp));
    }
#endif

    return 0;
}

int tps6598x_powerup(tps6598x_dev_t *dev)
{
    u8 power_state;

    if (tps6598x_read_reg(dev, TPS_REG_POWER_STATE, &power_state, 1) < 0)
        return -1;

    if (power_state == 0)
        return 0;

    const u8 data = 0;
    tps6598x_command(dev, "SSPS", &data, 1, NULL, 0);

    if (tps6598x_read_reg(dev, TPS_REG_POWER_STATE, &power_state, 1) < 0)
        return -1;

    if (power_state != 0)
        return -1;

    return 0;
}
