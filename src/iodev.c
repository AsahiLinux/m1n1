/* SPDX-License-Identifier: MIT */

//#define DEBUG_IODEV

#include "iodev.h"
#include "memory.h"
#include "string.h"

#ifdef DEBUG_IODEV
#define dprintf printf
#else
#define dprintf(...)                                                                               \
    do {                                                                                           \
    } while (0)
#endif

#define CONSOLE_BUFFER_SIZE 8192

extern struct iodev iodev_uart;
extern struct iodev iodev_fb;
extern struct iodev iodev_usb_vuart;

struct iodev *iodevs[IODEV_MAX] = {
    [IODEV_UART] = &iodev_uart,
    [IODEV_FB] = &iodev_fb,
    [IODEV_USB_VUART] = &iodev_usb_vuart,
};

char con_buf[CONSOLE_BUFFER_SIZE];
size_t con_wp;
size_t con_rp[IODEV_MAX];

void iodev_register_device(iodev_id_t id, struct iodev *dev)
{
    if (id >= IODEV_MAX)
        return;
    iodevs[id] = dev;
}

struct iodev *iodev_unregister_device(iodev_id_t id)
{
    if (id < IODEV_USB0 || id >= IODEV_MAX)
        return NULL;

    struct iodev *dev = iodevs[id];
    iodevs[id] = NULL;
    return dev;
}

ssize_t iodev_can_read(iodev_id_t id)
{
    if (!iodevs[id] || !iodevs[id]->ops->can_read)
        return 0;

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
    ssize_t ret = iodevs[id]->ops->can_read(iodevs[id]->opaque);
    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
    return ret;
}

bool iodev_can_write(iodev_id_t id)
{
    if (!iodevs[id] || !iodevs[id]->ops->can_write)
        return false;

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
    bool ret = iodevs[id]->ops->can_write(iodevs[id]->opaque);
    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
    return ret;
}

ssize_t iodev_read(iodev_id_t id, void *buf, size_t length)
{
    if (!iodevs[id] || !iodevs[id]->ops->read)
        return -1;

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
    ssize_t ret = iodevs[id]->ops->read(iodevs[id]->opaque, buf, length);
    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
    return ret;
}

ssize_t iodev_write(iodev_id_t id, const void *buf, size_t length)
{
    if (!iodevs[id] || !iodevs[id]->ops->write)
        return -1;

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
    ssize_t ret = iodevs[id]->ops->write(iodevs[id]->opaque, buf, length);
    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
    return ret;
}

ssize_t iodev_queue(iodev_id_t id, const void *buf, size_t length)
{
    if (!iodevs[id] || !iodevs[id]->ops->queue)
        return iodev_write(id, buf, length);

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
    ssize_t ret = iodevs[id]->ops->queue(iodevs[id]->opaque, buf, length);
    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
    return ret;
}

void iodev_flush(iodev_id_t id)
{
    if (!iodevs[id] || !iodevs[id]->ops->flush)
        return;

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
    iodevs[id]->ops->flush(iodevs[id]->opaque);
    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
}

void iodev_lock(iodev_id_t id)
{
    if (!iodevs[id])
        return;

    if (mmu_active())
        spin_lock(&iodevs[id]->lock);
}

void iodev_unlock(iodev_id_t id)
{
    if (!iodevs[id])
        return;

    if (mmu_active())
        spin_unlock(&iodevs[id]->lock);
}

int in_iodev = 0;

static DECLARE_SPINLOCK(console_lock);

void iodev_console_write(const void *buf, size_t length)
{
    bool do_lock = mmu_active();

    if (!do_lock && !is_primary_core()) {
        if (length && iodevs[IODEV_UART]->usage & USAGE_CONSOLE) {
            iodevs[IODEV_UART]->ops->write(iodevs[IODEV_UART]->opaque, "*", 1);
            iodevs[IODEV_UART]->ops->write(iodevs[IODEV_UART]->opaque, buf, length);
        }
        return;
    }

    if (do_lock)
        spin_lock(&console_lock);

    if (in_iodev) {
        if (length && iodevs[IODEV_UART]->usage & USAGE_CONSOLE) {
            iodevs[IODEV_UART]->ops->write(iodevs[IODEV_UART]->opaque, "+", 1);
            iodevs[IODEV_UART]->ops->write(iodevs[IODEV_UART]->opaque, buf, length);
        }
        if (do_lock)
            spin_unlock(&console_lock);
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
    if (do_lock)
        spin_unlock(&console_lock);
}

void iodev_handle_events(iodev_id_t id)
{
    bool do_lock = mmu_active();

    if (do_lock)
        spin_lock(&console_lock);

    if (in_iodev) {
        if (do_lock)
            spin_unlock(&console_lock);
        return;
    }

    in_iodev++;

    if (iodevs[id]->ops->handle_events)
        iodevs[id]->ops->handle_events(iodevs[id]->opaque);

    in_iodev--;

    if (iodev_can_write(id))
        iodev_console_write(NULL, 0);

    if (do_lock)
        spin_unlock(&console_lock);
}

void iodev_console_kick(void)
{
    iodev_console_write(NULL, 0);

    for (iodev_id_t id = 0; id < IODEV_MAX; id++) {
        if (!iodevs[id])
            continue;
        if (!(iodevs[id]->usage & USAGE_CONSOLE))
            continue;

        iodev_handle_events(id);
    }
}

void iodev_console_flush(void)
{
    for (iodev_id_t id = 0; id < IODEV_MAX; id++) {
        if (!iodevs[id])
            continue;
        if (!(iodevs[id]->usage & USAGE_CONSOLE))
            continue;

        iodev_flush(id);
    }
}

void iodev_set_usage(iodev_id_t id, iodev_usage_t usage)
{
    if (iodevs[id])
        iodevs[id]->usage = usage;
}

iodev_usage_t iodev_get_usage(iodev_id_t id)
{
    if (iodevs[id])
        return iodevs[id]->usage;
    return 0;
}

void *iodev_get_opaque(iodev_id_t id)
{
    if (id >= IODEV_MAX || !iodevs[id])
        return NULL;

    return iodevs[id]->opaque;
}
