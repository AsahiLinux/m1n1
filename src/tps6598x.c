/* SPDX-License-Identifier: MIT */

#include "tps6598x.h"
#include "adt.h"
#include "i2c.h"
#include "iodev.h"
#include "malloc.h"
#include "spmi.h"
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

#define TPS_SPMI_REG_SELECT 0x00
#define TPS_SPMI_REG_SIZE   0x1f
#define TPS_SPMI_REG_DATA   0x20

// Write to TPS_SPMI_REG_SELECT with MSB=1 will
// trigger selection of register with the 7-bit address
#define TPS_SPMI_REG_SELECT_TRIG BIT(7)

struct tps6598x_dev {
    i2c_dev_t *i2c;
    spmi_dev_t *spmi;
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

tps6598x_dev_t *tps6598x_init_spmi(const char *adt_node, spmi_dev_t *spmi)
{
    tps6598x_dev_t *dev = tps6598x_init(adt_node, "reg");
    dev->spmi = spmi;

    if (spmi_send_wakeup(dev->spmi, dev->addr) < 0)
        return NULL;
    mdelay(10);

    return dev;
}

void tps6598x_shutdown(tps6598x_dev_t *dev)
{
    if (dev->spmi)
        spmi_send_shutdown(dev->spmi, dev->addr);
    free(dev);
}

static int tps6598x_spmi_select_reg(tps6598x_dev_t *dev, const u8 reg)
{
    u8 val = ~reg;
    if (spmi_reg0_write(dev->spmi, dev->addr, reg) < 0)
        return -1;

    while (val != reg) {
        if (spmi_ext_read(dev->spmi, dev->addr, TPS_SPMI_REG_SELECT, &val, 1) < 0)
            return -1;
        if (val == reg)
            break;
        if (val != (reg | TPS_SPMI_REG_SELECT_TRIG)) // Selection in progress
            return -1;
        mdelay(1);
    }
    return 0;
}

static int tps6598x_write_reg(tps6598x_dev_t *dev, const u8 reg, const u8 *data, size_t len)
{
    if (dev->i2c)
        return i2c_smbus_write(dev->i2c, dev->addr, reg, data, len);

    if (dev->spmi) {
        if (tps6598x_spmi_select_reg(dev, reg) < 0)
            return -1;
        if (spmi_ext_write(dev->spmi, dev->addr, TPS_SPMI_REG_DATA, data, len) < 0)
            return -1;
        return len;
    }

    return -1;
}

static int tps6598x_read_reg(tps6598x_dev_t *dev, const u8 reg, u8 *data, size_t len)
{
    if (dev->i2c)
        return i2c_smbus_read(dev->i2c, dev->addr, reg, data, len);

    if (dev->spmi) {
        if (tps6598x_spmi_select_reg(dev, reg) < 0)
            return -1;
        if (spmi_ext_read(dev->spmi, dev->addr, TPS_SPMI_REG_DATA, data, len) < 0)
            return -1;
        return len;
    }

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

int tps6598x_cmd_status(tps6598x_dev_t *dev, const char *cmd)
{
    u32 cmd_status;

    if (tps6598x_read_reg(dev, TPS_REG_CMD1, (u8 *)&cmd_status, 4) < 0) {
        printf("tps6598x: read status for cmd: %s failed\n", cmd);
        return -1;
    }
    if (cmd_status == TPS_CMD_INVALID) {
        printf("tps6598x: cmd %s status invalid\n", cmd);
        return -1;
    }
    if (cmd_status) {
        printf("tps6598x: cmd %s status 0x%x\n", cmd, cmd_status);
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

    ret = tps6598x_read_reg(dev, TPS_REG_MODE, (u8 *)&mode, 4);
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

int tps6598x_foreach_hpm(hpm_match_t *match, hpm_action_t *action, void *data)
{
    char hpm_path[64] = {0};
    char i2c_path[64] = {0};
    int node;
    int ret;
    bool stop = false;    // Whether we should stop iteration after a non-zero action return value
    bool matched = false; // Whether we found any matching hpms at all; used for return value

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

        ret = snprintf(i2c_path, sizeof(i2c_path), "/arm-io/%s", adt_get_name(adt, node));
        if (ret < 0 || (size_t)ret >= sizeof(i2c_path))
            continue;

        i2c_dev_t *i2c = NULL;

        int it = mngr_node;
        ADT_FOREACH_CHILD(adt, it)
        {
            if (!adt_is_compatible(adt, it, "usbc,cd3217"))
                continue;

            const char *name = adt_get_name(adt, it);

            ret = snprintf(hpm_path, sizeof(hpm_path), "/arm-io/%s/%s/%s", adt_get_name(adt, node),
                           adt_get_name(adt, mngr_node), name);
            if (ret < 0 || (size_t)ret >= sizeof(hpm_path))
                continue;

            if (!match(hpm_path, data))
                continue;
            matched = true;

            if (!i2c) {
                i2c = i2c_init(i2c_path);
                if (!i2c) {
                    printf("tps6598x: i2c_init failed for %s.\n", i2c_path);
                    break; // skip to the next i2c bus
                }
            }

            tps6598x_dev_t *tps = tps6598x_init_i2c(hpm_path, i2c);
            if (!tps) {
                printf("tps6598x: init failed for %s.\n", hpm_path);
                continue; // try the next hpm on this bus
            }

            ret = action(hpm_path, tps, data);

            tps6598x_shutdown(tps);

            if (ret != 0) {
                stop = true; // The action indicated end of iteration: Do not iterate another bus
                break;
            }
        }
        if (i2c)
            i2c_shutdown(i2c);
        if (stop)
            return ret;
    }

    if (!matched) {
        // No hpms matched: Indicate this as error through the return value
        return -1;
    }

    return 0;
}

static int tps6598x_enable_debugusb_one(char *hpm_path, tps6598x_dev_t *tps, void *)
{
    printf("tps6598x: enable debugusb for %s\n", hpm_path);

    if (tps6598x_powerup(tps) < 0) {
        printf("tps6598x_enable_debugusb: tps6598x_powerup failed for %s.\n", hpm_path);
        tps6598x_shutdown(tps);
        return -1;
    }

    tps6598x_enter_kis(tps);

    return 1; // stop iterating
}

static bool tps6598x_is_dfu(char *hpm_path, void *)
{
    size_t len = strlen(hpm_path);
    if (len < 4)
        return false;
    return !strcmp(hpm_path + len - 4, "hpm0");
}

int tps6598x_enable_debugusb(void)
{
    int ret = tps6598x_foreach_hpm(tps6598x_is_dfu, tps6598x_enable_debugusb_one, NULL);
    if (ret < 0) {
        printf("tps6598x_enable_debugusb failed (node not found?)\n");
        return ret;
    }
    return 0;
}
