/* SPDX-License-Identifier: MIT */

#ifndef __SPMI_H__
#define __SPMI_H__

#include "types.h"
#include "utils.h"

#define SPMI_ERR_UNKNOWN       1
#define SPMI_ERR_BUS_IO        2
#define SPMI_ERR_INVALID_PARAM 3

typedef struct spmi_dev spmi_dev_t;

spmi_dev_t *spmi_init(const char *adt_node);
void spmi_shutdown(spmi_dev_t *dev);

int spmi_reg0_write(spmi_dev_t *dev, u8 addr, u8 value);

int spmi_ext_read(spmi_dev_t *dev, u8 addr, u8 reg, u8 *bfr, size_t len);
int spmi_ext_write(spmi_dev_t *dev, u8 addr, u8 reg, const u8 *bfr, size_t len);

int spmi_ext_read_long(spmi_dev_t *dev, u8 addr, u16 reg, u8 *bfr, size_t len);
int spmi_ext_write_long(spmi_dev_t *dev, u8 addr, u16 reg, const u8 *bfr, size_t len);

int spmi_send_reset(spmi_dev_t *dev, u8 addr);
int spmi_send_sleep(spmi_dev_t *dev, u8 addr);
int spmi_send_shutdown(spmi_dev_t *dev, u8 addr);
int spmi_send_wakeup(spmi_dev_t *dev, u8 addr);

#endif
