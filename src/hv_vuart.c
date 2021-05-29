/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "uart_regs.h"

static iodev_id_t vuart_iodev;

bool handle_vuart(u64 addr, u64 *val, bool write, int width)
{
    UNUSED(width);
    addr &= 0xfff;

    if (write) {
        switch (addr) {
            case UTXH: {
                uint8_t b = *val;
                if (iodev_can_write(vuart_iodev))
                    iodev_write(vuart_iodev, &b, 1);
                break;
            }
        }
    } else {
        switch (addr) {
            case UTRSTAT:
                *val = 0x06;
                break;
            default:
                *val = 0;
                break;
        }
    }

    // printf("HV: vuart(0x%lx, 0x%lx, %d, %d)\n", addr, *val, write, width);

    return true;
}

void hv_map_vuart(u64 base, iodev_id_t iodev)
{
    hv_map_hook(base, handle_vuart, 0x1000);
    vuart_iodev = iodev;
}
