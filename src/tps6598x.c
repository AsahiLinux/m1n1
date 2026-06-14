/* SPDX-License-Identifier: MIT */

#include "tps6598x.h"
#include "adt.h"
#include "i2c.h"
#include "iodev.h"
#include "malloc.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define TPS_REG_MODE        0x03
#define TPS_REG_CMD1        0x08
#define TPS_REG_DATA1       0x09
#define TPS_REG_INT_EVENT1  0x14
#define TPS_REG_INT_MASK1   0x16
#define TPS_REG_INT_CLEAR1  0x18
#define TPS_REG_POWER_STATE 0x20
#define TPS_CMD_INVALID     0x444d4321 // !CMD as LE u32
#define TPS_MODE_DBMA       ((u32)'D' | ((u32)'B' << 8) | ((u32)'M' << 16) | ((u32)'a' << 24))

struct tps6598x_dev {
    i2c_dev_t *i2c;
    u8 addr;
};

tps6598x_dev_t *tps6598x_init(const char *adt_node, i2c_dev_t *i2c)
{
    int adt_offset;
    adt_offset = adt_path_offset(adt, adt_node);
    if (adt_offset < 0) {
        printf("tps6598x: Error getting %s node\n", adt_node);
        return NULL;
    }

    const u8 *iic_addr = adt_getprop(adt, adt_offset, "hpm-iic-addr", NULL);
    if (iic_addr == NULL) {
        printf("tps6598x: Error getting %s hpm-iic-addr\n.", adt_node);
        return NULL;
    }

    tps6598x_dev_t *dev = calloc(1, sizeof(*dev));
    if (!dev)
        return NULL;

    dev->i2c = i2c;
    dev->addr = *iic_addr;
    return dev;
}

void tps6598x_shutdown(tps6598x_dev_t *dev)
{
    free(dev);
}

int tps6598x_command(tps6598x_dev_t *dev, const char *cmd, const u8 *data_in, size_t len_in,
                     u8 *data_out, size_t len_out)
{
    if (len_in) {
        if (i2c_smbus_write(dev->i2c, dev->addr, TPS_REG_DATA1, data_in, len_in) < 0)
            return -1;
    }

    if (i2c_smbus_write(dev->i2c, dev->addr, TPS_REG_CMD1, (const u8 *)cmd, 4) < 0)
        return -1;

    u32 cmd_status;
    do {
        if (i2c_smbus_read32(dev->i2c, dev->addr, TPS_REG_CMD1, &cmd_status))
            return -1;
        if (cmd_status == TPS_CMD_INVALID)
            return -1;
        udelay(100);
    } while (cmd_status != 0);

    if (len_out) {
        if (i2c_smbus_read(dev->i2c, dev->addr, TPS_REG_DATA1, data_out, len_out) !=
            (ssize_t)len_out)
            return -1;
    }

    return 0;
}

int tps6598x_cmd_status(tps6598x_dev_t *dev, const char *cmd)
{
    u32 cmd_status;

    if (i2c_smbus_read32(dev->i2c, dev->addr, TPS_REG_CMD1, &cmd_status)) {
        printf("tps6598x: i2c_smbus_read32 cmd: %s failed\n", cmd);
        return -1;
    }
    if (cmd_status == TPS_CMD_INVALID) {
        printf("tps6598x: i2c_smbus_read32 cmd: %s status invalid\n", cmd);
        return -1;
    }
    if (cmd_status) {
        printf("tps6598x: i2c_smbus_read32 cmd: %s status 0x%x\n", cmd, cmd_status);
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
    read = i2c_smbus_read(dev->i2c, dev->addr, TPS_REG_INT_MASK1, state->int_mask1,
                          sizeof(state->int_mask1));
    if (read != CD3218B12_IRQ_WIDTH) {
        printf("tps6598x: reading TPS_REG_INT_MASK1 failed\n");
        return -1;
    }
    state->valid = 1;

    // mask interrupts and ack all interrupt flags
    written = i2c_smbus_write(dev->i2c, dev->addr, TPS_REG_INT_CLEAR1, ones, sizeof(ones));
    if (written != sizeof(zeros)) {
        printf("tps6598x: writing TPS_REG_INT_CLEAR1 failed, written: %d\n", written);
        return -1;
    }
    written = i2c_smbus_write(dev->i2c, dev->addr, TPS_REG_INT_MASK1, zeros, sizeof(zeros));
    if (written != sizeof(ones)) {
        printf("tps6598x: writing TPS_REG_INT_MASK1 failed, written: %d\n", written);
        return -1;
    }

#ifdef DEBUG
    u8 tmp[CD3218B12_IRQ_WIDTH] = {0x00};
    read = i2c_smbus_read(dev->i2c, dev->addr, TPS_REG_INT_MASK1, tmp, CD3218B12_IRQ_WIDTH);
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

    written = i2c_smbus_write(dev->i2c, dev->addr, TPS_REG_INT_MASK1, state->int_mask1,
                              sizeof(state->int_mask1));
    if (written != sizeof(state->int_mask1)) {
        printf("tps6598x: restoring TPS_REG_INT_MASK1 failed\n");
        return -1;
    }

#ifdef DEBUG
    int read;
    u8 tmp[CD3218B12_IRQ_WIDTH];
    read = i2c_smbus_read(dev->i2c, dev->addr, TPS_REG_INT_MASK1, tmp, sizeof(tmp));
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

    if (i2c_smbus_read8(dev->i2c, dev->addr, TPS_REG_POWER_STATE, &power_state))
        return -1;

    if (power_state == 0)
        return 0;

    const u8 data = 0;
    tps6598x_command(dev, "SSPS", &data, 1, NULL, 0);

    if (i2c_smbus_read8(dev->i2c, dev->addr, TPS_REG_POWER_STATE, &power_state))
        return -1;

    if (power_state != 0)
        return -1;

    return 0;
}

int tps6598x_enter_kis(tps6598x_dev_t *dev)
{
    u32 target_len = 0;
    const u8 *target = adt_getprop(adt, 0, "target-type", &target_len);
    u8 key[4] = {0};
    const u8 key_null[4] = {0, 0, 0, 0};
    const u8 vdm[] = {0x06, 0x46, 0x82, 0x01};
    u32 mode = 0;
    u8 out = 0;
    u8 en = 1;
    int ret;

    if (target_len < 4)
        return -1;

    // reverse the key
    for (int i = 0; i < 4; i++)
        key[i] = target[3 - i];

    // check status and soft reset if it fails
    if (tps6598x_cmd_status(dev, "LOCK")) {
        tps6598x_command(dev, "Gaid", NULL, 0, NULL, 0);
        mdelay(20);
    }

    ret = tps6598x_command(dev, "LOCK", key, 4, (u8 *)&out, 1);
    if (ret || (out & 0xf)) {
        printf("tps6598x_enter_kis: Failed to unlock using '%.4s': ret=%d result=0x%hhx\n", key,
               ret, out & 0xf);
        return -1;
    }

    ret = tps6598x_command(dev, "DBMa", &en, 1, &out, 1);
    if (ret || (out & 0xf)) {
        printf("tps6598x_enter_kis: DBMa cmd failed: ret=%d result=0x%hhx\n", ret, out & 0xf);
        return -1;
    }

    ret = i2c_smbus_read32(dev->i2c, dev->addr, TPS_REG_MODE, &mode);
    if (mode != TPS_MODE_DBMA) {
        printf("tps6598x_enter_kis: Failed to enter DBMa mode, mode=0x%08x\n", mode);
        return -1;
    }

    ret = tps6598x_command(dev, "DVEn", vdm, sizeof(vdm), &out, 1);
    if (ret || (out & 0xf)) {
        printf("tps6598x_enter_kis: DVEn cmd failed: ret=%d result=0x%hhx\n", ret, out & 0xf);
        return -1;
    }

    en = 0;
    tps6598x_command(dev, "DBMa", &en, 1, NULL, 0);
    tps6598x_command(dev, "LOCK", key_null, 4, NULL, 0);

    return ret;
}

int tps6598x_enable_debugusb(void)
{
    char hpm_path[64] = {0};
    char i2c_path[64] = {0};
    bool found = false;
    int node;
    int ret;

    node = adt_path_offset(adt, "/arm-io");
    if (node < 0)
        return -1;

    ADT_FOREACH_CHILD(adt, node)
    {
        int mngr_node;

        if (!adt_is_compatible(adt, node, "i2c,s5l8940x"))
            continue;

        mngr_node = adt_first_child_offset(adt, node);
        if (mngr_node < 0 || !adt_is_compatible(adt, mngr_node, "usbc,manager"))
            continue;

        int it = mngr_node;
        ADT_FOREACH_CHILD(adt, it)
        {
            if (!adt_is_compatible(adt, it, "usbc,cd3217"))
                continue;

            const char *name = adt_get_name(adt, it);
            if (strcmp(name, "hpm0"))
                continue;

            ret = snprintf(i2c_path, sizeof(i2c_path), "/arm-io/%s", adt_get_name(adt, node));
            if (ret < 0 || (size_t)ret >= sizeof(i2c_path))
                continue;
            ret = snprintf(hpm_path, sizeof(hpm_path), "/arm-io/%s/%s/%s", adt_get_name(adt, node),
                           adt_get_name(adt, mngr_node), name);
            if (ret < 0 || (size_t)ret >= sizeof(hpm_path))
                continue;

            found = true;
        }
        if (found)
            break;
    }
    if (!found) {
        printf("tps6598x_enable_debugusb: i2c / hpm node not found\n");
        return -1;
    }

    printf("tps6598x: enable debugusb for %s\n", hpm_path);

    i2c_dev_t *i2c = i2c_init(i2c_path);
    if (!i2c) {
        printf("tps6598x_enable_debugusb: i2c_init failed for %s.\n", i2c_path);
        return -1;
    }

    tps6598x_dev_t *tps = tps6598x_init(hpm_path, i2c);
    if (!tps) {
        printf("tps6598x_enable_debugusb: tps6598x_init failed for %s.\n", hpm_path);
        return -1;
    }

    if (tps6598x_powerup(tps) < 0) {
        printf("tps6598x_enable_debugusb: tps6598x_powerup failed for %s.\n", hpm_path);
        tps6598x_shutdown(tps);
        return -1;
    }

    tps6598x_enter_kis(tps);

    tps6598x_shutdown(tps);

    i2c_shutdown(i2c);

    return 0;
}
