/* SPDX-License-Identifier: MIT */

#ifndef TPS6598X_H
#define TPS6598X_H

#include "i2c.h"
#include "types.h"

typedef struct tps6598x_dev tps6598x_dev_t;

tps6598x_dev_t *tps6598x_init(const char *adt_path, i2c_dev_t *i2c);
void tps6598x_shutdown(tps6598x_dev_t *dev);

int tps6598x_command(tps6598x_dev_t *dev, const char *cmd, const u8 *data_in, size_t len_in,
                     u8 *data_out, size_t len_out);
int tps6598x_powerup(tps6598x_dev_t *dev);

#endif
