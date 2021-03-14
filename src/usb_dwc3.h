/* SPDX-License-Identifier: MIT */

#ifndef USB_DWC3_H
#define USB_DWC3_H

#include "dart.h"
#include "types.h"

typedef struct dwc3_dev dwc3_dev_t;

dwc3_dev_t *usb_dwc3_init(uintptr_t regs, dart_dev_t *dart);
void usb_dwc3_shutdown(dwc3_dev_t *dev);

void usb_dwc3_handle_events(dwc3_dev_t *dev);

int usb_dwc3_can_read(dwc3_dev_t *dev);
int usb_dwc3_can_write(dwc3_dev_t *dev);

u8 usb_dwc3_getbyte(dwc3_dev_t *dev);
void usb_dwc3_putbyte(dwc3_dev_t *dev, u8 byte);

void usb_dwc3_write(dwc3_dev_t *dev, const void *buf, size_t count);
size_t usb_dwc3_read(dwc3_dev_t *dev, void *buf, size_t count);

#endif
