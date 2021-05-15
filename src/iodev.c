/* SPDX-License-Identifier: MIT */

//#define DEBUG_IODEV

#include "iodev.h"
#include "string.h"

#ifdef DEBUG_IODEV
#define dprintf printf
#else
#define dprintf(...)                                                                               \
    do {                                                                                           \
    } while (0)
#endif

#define CONSOLE_BUFFER_SIZE SZ_2K

extern struct iodev iodev_uart;
extern struct iodev iodev_fb;
extern struct iodev iodev_usb[];
extern struct iodev iodev_usb_sec[];

struct iodev *iodevs[IODEV_MAX] = {
    [IODEV_UART] = &iodev_uart,           [IODEV_FB] = &iodev_fb,
    [IODEV_USB0] = &iodev_usb[0],         [IODEV_USB1] = &iodev_usb[1],
    [IODEV_USB0_SEC] = &iodev_usb_sec[0], [IODEV_USB1_SEC] = &iodev_usb_sec[1],
};

char con_buf[CONSOLE_BUFFER_SIZE];
size_t con_wp;
size_t con_rp[IODEV_MAX];

bool iodev_can_read(iodev_id_t id)
{
    if (!iodevs[id]->ops->can_read)
        return false;

    return iodevs[id]->ops->can_read(iodevs[id]->opaque);
}

bool iodev_can_write(iodev_id_t id)
{
    if (!iodevs[id]->ops->can_write)
        return false;

    return iodevs[id]->ops->can_write(iodevs[id]->opaque);
}

ssize_t iodev_read(iodev_id_t id, void *buf, size_t length)
{
    if (!iodevs[id]->ops->read)
        return -1;

    return iodevs[id]->ops->read(iodevs[id]->opaque, buf, length);
}

ssize_t iodev_write(iodev_id_t id, const void *buf, size_t length)
{
    if (!iodevs[id]->ops->write)
        return -1;

    return iodevs[id]->ops->write(iodevs[id]->opaque, buf, length);
}

int in_iodev = 0;

void iodev_console_write(const void *buf, size_t length)
{
    if (in_iodev || !is_primary_core()) {
        iodev_write(IODEV_UART, "*", 1);
        iodev_write(IODEV_UART, buf, length);
        return;
    }
    in_iodev++;

    dprintf("  iodev_console_write() wp=%d\n", con_wp);
    for (iodev_id_t id = 0; id < IODEV_MAX; id++) {
        if (!iodevs[id])
            continue;

        if (!(iodevs[id]->usage & USAGE_CONSOLE)) {
            /* Drop buffer */
            con_rp[id] = con_wp + length;
            continue;
        }

        if (!iodev_can_write(id))
            continue;

        if (con_wp > CONSOLE_BUFFER_SIZE)
            con_rp[id] = max(con_wp - CONSOLE_BUFFER_SIZE, con_rp[id]);

        dprintf("  rp=%d\n", con_rp[id]);
        // Flush existing buffer to device if possible
        while (con_rp[id] < con_wp) {
            size_t buf_rp = con_rp[id] % CONSOLE_BUFFER_SIZE;
            size_t block = min(con_wp - con_rp[id], CONSOLE_BUFFER_SIZE - buf_rp);

            dprintf("  write buf %d\n", block);
            ssize_t ret = iodev_write(id, &con_buf[buf_rp], block);

            if (ret <= 0)
                goto next_dev;

            con_rp[id] += ret;
        }

        const u8 *p = buf;
        size_t wrote = 0;

        // Write the current buffer
        while (wrote < length) {
            ssize_t ret = iodev_write(id, p, length - wrote);

            if (ret <= 0)
                goto next_dev;

            con_rp[id] += ret;
            wrote += ret;
            p += ret;
        }

    next_dev:;
    }

    // Update console buffer

    if (length > CONSOLE_BUFFER_SIZE) {
        buf += (length - CONSOLE_BUFFER_SIZE);
        con_wp += (length - CONSOLE_BUFFER_SIZE);
        length = CONSOLE_BUFFER_SIZE;
    }

    while (length) {
        size_t buf_wp = con_wp % CONSOLE_BUFFER_SIZE;
        size_t block = min(length, CONSOLE_BUFFER_SIZE - buf_wp);
        memcpy(&con_buf[buf_wp], buf, block);
        buf += block;
        con_wp += block;
        length -= block;
    }

    in_iodev--;
}

void iodev_handle_events(iodev_id_t id)
{
    if (in_iodev)
        return;

    in_iodev++;

    if (iodevs[id]->ops->handle_events)
        iodevs[id]->ops->handle_events(iodevs[id]->opaque);

    in_iodev--;

    if (iodev_can_write(id))
        iodev_console_flush();
}

void iodev_console_kick(void)
{
    for (iodev_id_t id = 0; id < IODEV_MAX; id++) {
        if (!iodevs[id])
            continue;
        if (!(iodevs[id]->usage & USAGE_CONSOLE))
            continue;

        iodev_handle_events(id);
    }
}
