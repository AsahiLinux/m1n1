#include "ringbuffer.h"
#include "malloc.h"
#include "types.h"

ringbuffer_t *ringbuffer_alloc(size_t len)
{
    ringbuffer_t *bfr = malloc(sizeof(*bfr));
    if (!bfr)
        return NULL;

    bfr->buffer = malloc(len);
    if (!bfr->buffer) {
        free(bfr);
        return NULL;
    }

    bfr->read = 0;
    bfr->write = 0;
    bfr->len = len;

    return bfr;
}

void ringbuffer_free(ringbuffer_t *bfr)
{
    if (bfr)
        free(bfr->buffer);
    free(bfr);
}

size_t ringbuffer_read(u8 *target, size_t len, ringbuffer_t *bfr)
{
    size_t read;

    for (read = 0; read < len; ++read) {
        if (bfr->read == bfr->write)
            break;

        *target = bfr->buffer[bfr->read];
        target++;

        bfr->read++;
        bfr->read %= bfr->len;
    }

    return read;
}

size_t ringbuffer_write(const u8 *src, size_t len, ringbuffer_t *bfr)
{
    size_t written;

    for (written = 0; written < len; ++written) {
        if (((bfr->write + 1) % bfr->len) == bfr->read)
            break;

        bfr->buffer[bfr->write] = *src;
        src++;

        bfr->write++;
        bfr->write %= bfr->len;
    }

    return written;
}

size_t ringbuffer_get_used(ringbuffer_t *bfr)
{
    size_t read = bfr->read;
    size_t write = bfr->write;

    if (write < read)
        write += bfr->len;

    return write - read;
}

size_t ringbuffer_get_free(ringbuffer_t *bfr)
{
    return bfr->len - ringbuffer_get_used(bfr);
}
