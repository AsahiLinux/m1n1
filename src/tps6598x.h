/* SPDX-License-Identifier: MIT */

#ifndef TPS6598X_H
#define TPS6598X_H

#include "i2c.h"
#include "spmi.h"
#include "types.h"

typedef struct tps6598x_dev tps6598x_dev_t;

tps6598x_dev_t *tps6598x_init_i2c(const char *adt_path, i2c_dev_t *i2c);
tps6598x_dev_t *tps6598x_init_spmi(const char *adt_path, spmi_dev_t *spmi);
void tps6598x_shutdown(tps6598x_dev_t *dev);

int tps6598x_command(tps6598x_dev_t *dev, const char *cmd, const u8 *data_in, size_t len_in,
                     u8 *data_out, size_t len_out);
int tps6598x_powerup(tps6598x_dev_t *dev);

typedef bool(hpm_match_t)(char *hpm_path, void *data);
typedef int(hpm_action_t)(char *hpm_path, tps6598x_dev_t *tps, void *data);
int tps6598x_foreach_hpm(hpm_match_t *match, hpm_action_t *action, void *data);

int tps6598x_enter_kis(tps6598x_dev_t *dev);
int tps6598x_enable_debugusb(void);

#define CD3218B12_IRQ_WIDTH 9

typedef struct tps6598x_irq_state {
    u8 int_mask1[CD3218B12_IRQ_WIDTH];
    bool valid;
} tps6598x_irq_state_t;

int tps6598x_disable_irqs(tps6598x_dev_t *dev, tps6598x_irq_state_t *state);
int tps6598x_restore_irqs(tps6598x_dev_t *dev, tps6598x_irq_state_t *state);

#endif
