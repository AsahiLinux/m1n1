/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "i2c.h"
#include "malloc.h"
#include "pmgr.h"
#include "types.h"
#include "utils.h"

#define PASEMI_FIFO_TX       0x00
#define PASEMI_TX_FLAG_READ  BIT(10)
#define PASEMI_TX_FLAG_STOP  BIT(9)
#define PASEMI_TX_FLAG_START BIT(8)

#define PASEMI_FIFO_RX       0x04
#define PASEMI_RX_FLAG_EMPTY BIT(8)

#define PASEMI_STATUS            0x14
#define PASEMI_STATUS_XFER_BUSY  BIT(28)
#define PASEMI_STATUS_XFER_ENDED BIT(27)

#define PASEMI_CONTROL          0x1c
#define PASEMI_CONTROL_CLEAR_RX BIT(10)
#define PASEMI_CONTROL_CLEAR_TX BIT(9)

struct i2c_dev {
    uintptr_t base;
};

i2c_dev_t *i2c_init(const char *adt_node)
{
    int adt_path[8];
    int adt_offset;
    adt_offset = adt_path_offset_trace(adt, adt_node, adt_path);
    if (adt_offset < 0) {
        printf("i2c: Error getting %s node\n", adt_node);
        return NULL;
    }

    u64 base;
    if (adt_get_reg(adt, adt_path, "reg", 0, &base, NULL) < 0) {
        printf("i2c: Error getting %s regs\n", adt_node);
        return NULL;
    }

    if (pmgr_adt_power_enable(adt_node)) {
        printf("i2c: Error enabling power for %s\n", adt_node);
        return NULL;
    }

    i2c_dev_t *dev = malloc(sizeof(*dev));
    if (!dev)
        return NULL;

    dev->base = base;
    return dev;
}

void i2c_shutdown(i2c_dev_t *dev)
{
    free(dev);
}

static void i2c_clear_fifos(i2c_dev_t *dev)
{
    set32(dev->base + PASEMI_CONTROL, PASEMI_CONTROL_CLEAR_TX | PASEMI_CONTROL_CLEAR_RX);
}

static void i2c_clear_status(i2c_dev_t *dev)
{
    write32(dev->base + PASEMI_STATUS, 0xffffffff);
}

static void i2c_xfer_start_read(i2c_dev_t *dev, u8 addr, size_t len)
{
    write32(dev->base + PASEMI_FIFO_TX, PASEMI_TX_FLAG_START | (addr << 1) | 1);
    write32(dev->base + PASEMI_FIFO_TX, PASEMI_TX_FLAG_READ | PASEMI_TX_FLAG_STOP | len);
}

static size_t i2c_xfer_read(i2c_dev_t *dev, u8 *bfr, size_t len)
{
    for (size_t i = 0; i < len; ++i) {
        u32 timeout = 5000;
        u32 val;

        do {
            val = read32(dev->base + PASEMI_FIFO_RX);
            if (!(val & PASEMI_RX_FLAG_EMPTY))
                break;
            udelay(10);
        } while (--timeout);

        if (val & PASEMI_RX_FLAG_EMPTY) {
            printf("i2c: timeout while reading (got %lu, expected %lu bytes)\n", i, len);
            return i;
        }

        bfr[i] = val;
    }

    return len;
}

static int i2c_xfer_write(i2c_dev_t *dev, u8 addr, u32 start, u32 stop, const u8 *bfr, size_t len)
{
    if (start)
        write32(dev->base + PASEMI_FIFO_TX, PASEMI_TX_FLAG_START | (addr << 1));

    for (size_t i = 0; i < len; ++i) {
        u32 data = bfr[i];
        if (i == (len - 1) && stop)
            data |= PASEMI_TX_FLAG_STOP;

        write32(dev->base + PASEMI_FIFO_TX, data);
    }

    if (!stop)
        return 0;

    if (poll32(dev->base + PASEMI_STATUS, PASEMI_STATUS_XFER_BUSY, 0, 50000)) {
        printf(
            "i2c: timeout while waiting for PASEMI_STATUS_XFER_BUSY to clear after write xfer\n");
        return -1;
    }

    return 0;
}

int i2c_smbus_read(i2c_dev_t *dev, u8 addr, u8 reg, u8 *bfr, size_t len)
{
    int ret = -1;

    i2c_clear_fifos(dev);
    i2c_clear_status(dev);

    if (i2c_xfer_write(dev, addr, 1, 0, &reg, 1))
        goto err;

    i2c_xfer_start_read(dev, addr, len + 1);
    u8 len_reply;
    if (i2c_xfer_read(dev, &len_reply, 1) != 1)
        goto err;

    if (len_reply < len)
        printf("i2c: want to read %ld bytes from addr %d but can only read %d\n", len, addr,
               len_reply);
    if (len_reply > len)
        printf("i2c: want to read %ld bytes from addr %d but device wants to send %d\n", len, addr,
               len_reply);

    ret = i2c_xfer_read(dev, bfr, min(len, len_reply));

err:
    if (poll32(dev->base + PASEMI_STATUS, PASEMI_STATUS_XFER_BUSY, 0, 50000)) {
        printf("i2c: timeout while waiting for PASEMI_STATUS_XFER_BUSY to clear after read xfer\n");
        return -1;
    }

    return ret;
}

int i2c_smbus_write(i2c_dev_t *dev, u8 addr, u8 reg, const u8 *bfr, size_t len)
{
    i2c_clear_fifos(dev);
    i2c_clear_status(dev);

    if (i2c_xfer_write(dev, addr, 1, 0, &reg, 1))
        return -1;

    u8 len_send = len;
    if (i2c_xfer_write(dev, addr, 0, 0, &len_send, 1))
        return -1;
    if (i2c_xfer_write(dev, addr, 0, 1, bfr, len))
        return -1;

    return len_send;
}

int i2c_smbus_read32(i2c_dev_t *dev, u8 addr, u8 reg, u32 *val)
{
    u8 bfr[4];
    if (i2c_smbus_read(dev, addr, reg, bfr, 4) != 4)
        return -1;

    *val = (bfr[0]) | (bfr[1] << 8) | (bfr[2] << 16) | (bfr[3] << 24);
    return 0;
}

int i2c_smbus_read16(i2c_dev_t *dev, u8 addr, u8 reg, u16 *val)
{
    u8 bfr[2];
    if (i2c_smbus_read(dev, addr, reg, bfr, 2) != 2)
        return -1;

    *val = (bfr[0]) | (bfr[1] << 8);
    return 0;
}

int i2c_smbus_write32(i2c_dev_t *dev, u8 addr, u8 reg, u32 val)
{
    u8 bfr[4];

    bfr[0] = val;
    bfr[1] = val >> 8;
    bfr[2] = val >> 16;
    bfr[3] = val >> 24;

    return i2c_smbus_write(dev, addr, reg, bfr, 4);
}

int i2c_smbus_read8(i2c_dev_t *dev, u8 addr, u8 reg, u8 *val)
{
    if (i2c_smbus_read(dev, addr, reg, val, 1) != 1)
        return -1;
    return 0;
}
