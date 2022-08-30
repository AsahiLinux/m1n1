/* SPDX-License-Identifier: MIT */

#ifndef IODEV_H
#define IODEV_H

#include "types.h"
#include "utils.h"

#define USB_IODEV_COUNT 8

typedef enum _iodev_id_t {
    IODEV_UART,
    IODEV_FB,
    IODEV_USB_VUART,
    IODEV_USB0,
    IODEV_MAX = IODEV_USB0 + USB_IODEV_COUNT,
} iodev_id_t;

typedef enum _iodev_usage_t {
    USAGE_CONSOLE = BIT(0),
    USAGE_UARTPROXY = BIT(1),
} iodev_usage_t;

struct iodev_ops {
    ssize_t (*can_read)(void *opaque);
    bool (*can_write)(void *opaque);
    ssize_t (*read)(void *opaque, void *buf, size_t length);
    ssize_t (*write)(void *opaque, const void *buf, size_t length);
    ssize_t (*queue)(void *opaque, const void *buf, size_t length);
    void (*flush)(void *opaque);
    void (*handle_events)(void *opaque);
};

struct iodev {
    const struct iodev_ops *ops;

    spinlock_t lock;
    iodev_usage_t usage;
    void *opaque;
};

void iodev_register_device(iodev_id_t id, struct iodev *dev);
struct iodev *iodev_unregister_device(iodev_id_t id);

ssize_t iodev_can_read(iodev_id_t id);
bool iodev_can_write(iodev_id_t id);
ssize_t iodev_read(iodev_id_t id, void *buf, size_t length);
ssize_t iodev_write(iodev_id_t id, const void *buf, size_t length);
ssize_t iodev_queue(iodev_id_t id, const void *buf, size_t length);
void iodev_flush(iodev_id_t id);
void iodev_handle_events(iodev_id_t id);
void iodev_lock(iodev_id_t id);
void iodev_unlock(iodev_id_t id);

void iodev_console_write(const void *buf, size_t length);
void iodev_console_kick(void);
void iodev_console_flush(void);

iodev_usage_t iodev_get_usage(iodev_id_t id);
void iodev_set_usage(iodev_id_t id, iodev_usage_t usage);
void *iodev_get_opaque(iodev_id_t id);

#endif
