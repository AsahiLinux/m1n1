#ifndef RINGBUFFER_H
#define RINGBUFFER_H

#include "types.h"

typedef struct {
    u8 *buffer;
    size_t len;
    size_t read;
    size_t write;
} ringbuffer_t;

ringbuffer_t *ringbuffer_alloc(size_t len);
void ringbuffer_free(ringbuffer_t *bfr);

size_t ringbuffer_read(u8 *target, size_t len, ringbuffer_t *bfr);
size_t ringbuffer_write(const u8 *src, size_t len, ringbuffer_t *bfr);

size_t ringbuffer_get_used(ringbuffer_t *bfr);
size_t ringbuffer_get_free(ringbuffer_t *bfr);

#endif
