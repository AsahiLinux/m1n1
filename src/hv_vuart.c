/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "iodev.h"
#include "uart_regs.h"

bool handle_vuart(u64 addr, u64 *val, bool write, int width)
{
    UNUSED(width);
    static bool newline = true;
    addr &= 0xfff;

    if (write) {
        switch (addr) {
            case UTXH: {
                uint8_t b = *val;
                if (newline) {
                    iodev_console_write("EL1> ", 5);
                    newline = false;
                }
                if (b == '\n')
                    newline = true;
                iodev_console_write(&b, 1);
                break;
            }
        }
    } else {
        switch (addr) {
            case UTRSTAT:
                *val = 0x02;
                break;
            default:
                *val = 0;
                break;
        }
    }

    // printf("HV: vuart(0x%lx, 0x%lx, %d, %d)\n", addr, *val, write, width);

    return true;
}

void hv_map_vuart(u64 base)
{
    hv_map_hook(base, handle_vuart, 0x1000);
}
