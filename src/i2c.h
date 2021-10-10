/* SPDX-License-Identifier: MIT */

#ifndef I2C_H
#define I2C_H

#include "types.h"

typedef struct i2c_dev i2c_dev_t;

i2c_dev_t *i2c_init(const char *adt_node);
void i2c_shutdown(i2c_dev_t *dev);

int i2c_smbus_read(i2c_dev_t *dev, u8 addr, u8 reg, u8 *bfr, size_t len);
int i2c_smbus_write(i2c_dev_t *dev, u8 addr, u8 reg, const u8 *bfr, size_t len);

int i2c_smbus_read32(i2c_dev_t *dev, u8 addr, u8 reg, u32 *val);
int i2c_smbus_write32(i2c_dev_t *dev, u8 addr, u8 reg, u32 val);

int i2c_smbus_read16(i2c_dev_t *dev, u8 addr, u8 reg, u16 *val);
int i2c_smbus_read8(i2c_dev_t *dev, u8 addr, u8 reg, u8 *val);

#endif
