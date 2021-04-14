/* SPDX-License-Identifier: MIT */

#ifndef USB_H
#define USB_H

#include "types.h"
#include "usb_dwc3.h"

dwc3_dev_t *usb_bringup(u32 idx);

#endif
