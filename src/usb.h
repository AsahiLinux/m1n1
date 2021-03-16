/* SPDX-License-Identifier: MIT */

#ifndef USB_H
#define USB_H

#include "types.h"
#include "usb_dwc3.h"

extern dwc3_dev_t *usb_dwc3_port0;
extern dwc3_dev_t *usb_dwc3_port1;

int usb_init(void);
void usb_shutdown(void);

void usb_console_write(const char *bfr, size_t len);

#endif
