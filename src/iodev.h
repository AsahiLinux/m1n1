/* SPDX-License-Identifier: MIT */

#ifndef IODEV_H
#define IODEV_H

#include "types.h"
#include "utils.h"

typedef enum _iodev_id_t {
    IODEV_UART,
    IODEV_FB,
    IODEV_USB0,
    IODEV_USB1,
    IODEV_USB0_SEC,
    IODEV_USB1_SEC,
    IODEV_MAX,
} iodev_id_t;

typedef enum _iodev_usage_t {
    USAGE_CONSOLE = BIT(0),
    USAGE_UARTPROXY = BIT(1),
} iodev_usage_t;

struct iodev_ops {
    bool (*can_read)(void *opaque);
    bool (*can_write)(void *opaque);
    ssize_t (*read)(void *opaque, void *buf, size_t length);
    ssize_t (*write)(void *opaque, const void *buf, size_t length);
    ssize_t (*queue)(void *opaque, const void *buf, size_t length);
    void (*flush)(void *opaque);
    void (*handle_events)(void *opaque);
};

struct iodev {
    const struct iodev_ops *ops;

    iodev_usage_t usage;
    void *opaque;
};

extern struct iodev *iodevs[IODEV_MAX];

bool iodev_can_read(iodev_id_t id);
bool iodev_can_write(iodev_id_t id);
ssize_t iodev_read(iodev_id_t id, void *buf, size_t length);
ssize_t iodev_write(iodev_id_t id, const void *buf, size_t length);
ssize_t iodev_queue(iodev_id_t id, const void *buf, size_t length);
void iodev_flush(iodev_id_t id);
void iodev_handle_events(iodev_id_t id);

void iodev_console_write(const void *buf, size_t length);
void iodev_console_kick(void);
void iodev_console_flush(void);

static inline void iodev_set_usage(iodev_id_t id, iodev_usage_t usage)
{
    iodevs[id]->usage = usage;
}

#endif
