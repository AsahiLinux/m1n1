/* SPDX-License-Identifier: MIT */

#include "uartproxy.h"
#include "assert.h"
#include "exception.h"
#include "iodev.h"
#include "proxy.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define REQ_SIZE 64

typedef struct {
    u32 _pad;
    u32 type;
    union {
        ProxyRequest prequest;
        struct {
            u64 addr;
            u64 size;
            u32 dchecksum;
        } mrequest;
        u64 features;
    };
    u32 checksum;
} UartRequest;

#define REPLY_SIZE 36

typedef struct {
    u32 type;
    s32 status;
    union {
        ProxyReply preply;
        struct {
            u32 dchecksum;
        } mreply;
        struct uartproxy_msg_start start;
        u64 features;
    };
    u32 checksum;
    u32 _dummy; // Not transferred
} UartReply;

typedef struct {
    u32 type;
    u16 len;
    u16 event_type;
} UartEventHdr;

static_assert(sizeof(UartReply) == (REPLY_SIZE + 4), "Invalid UartReply size");

#define REQ_NOP      0x00AA55FF
#define REQ_PROXY    0x01AA55FF
#define REQ_MEMREAD  0x02AA55FF
#define REQ_MEMWRITE 0x03AA55FF
#define REQ_BOOT     0x04AA55FF
#define REQ_EVENT    0x05AA55FF

#define ST_OK      0
#define ST_BADCMD  -1
#define ST_INVAL   -2
#define ST_XFRERR  -3
#define ST_CSUMERR -4

#define PROXY_FEAT_DISABLE_DATA_CSUMS 0x01
#define PROXY_FEAT_ALL                (PROXY_FEAT_DISABLE_DATA_CSUMS)

static u32 iodev_proxy_buffer[IODEV_MAX];

#define CHECKSUM_INIT     0xDEADBEEF
#define CHECKSUM_FINAL    0xADDEDBAD
#define CHECKSUM_SENTINEL 0xD0DECADE
#define DATA_END_SENTINEL 0xB0CACC10

static bool disable_data_csums = false;

// I just totally pulled this out of my arse
// Noinline so that this can be bailed out by exc_guard = EXC_RETURN
// We assume this function does not use the stack
static u32 __attribute__((noinline)) checksum_block(void *start, u32 length, u32 init)
{
    u32 sum = init;
    u8 *d = (u8 *)start;

    while (length--) {
        sum *= 31337;
        sum += (*d++) ^ 0x5A;
    }
    return sum;
}

static inline u32 checksum_start(void *start, u32 length)
{
    return checksum_block(start, length, CHECKSUM_INIT);
}

static inline u32 checksum_add(void *start, u32 length, u32 sum)
{
    return checksum_block(start, length, sum);
}

static inline u32 checksum_finish(u32 sum)
{
    return sum ^ CHECKSUM_FINAL;
}

static inline u32 checksum(void *start, u32 length)
{
    return checksum_finish(checksum_start(start, length));
}

static u64 data_checksum(void *start, u32 length)
{
    if (disable_data_csums) {
        return CHECKSUM_SENTINEL;
    }

    return checksum(start, length);
}

iodev_id_t uartproxy_iodev;

int uartproxy_run(struct uartproxy_msg_start *start)
{
    int ret;
    int running = 1;
    size_t bytes;
    u64 checksum_val;
    u64 enabled_features = 0;

    iodev_id_t iodev = IODEV_MAX;

    UartRequest request;
    UartReply reply = {REQ_BOOT};
    if (!start) {
        // Startup notification only goes out via UART
        reply.checksum = checksum(&reply, REPLY_SIZE - 4);
        iodev_write(IODEV_UART, &reply, REPLY_SIZE);
    } else {
        // Exceptions / hooks keep the current iodev
        iodev = uartproxy_iodev;
        reply.start = *start;
        reply.checksum = checksum(&reply, REPLY_SIZE - 4);
        iodev_write(iodev, &reply, REPLY_SIZE);
    }

    while (running) {
        if (!start) {
            // Look for commands from any iodev on startup
            for (iodev = 0; iodev < IODEV_MAX;) {
                u8 b;
                if ((iodev_get_usage(iodev) & USAGE_UARTPROXY)) {
                    iodev_handle_events(iodev);
                    if (iodev_can_read(iodev) && iodev_read(iodev, &b, 1) == 1) {
                        iodev_proxy_buffer[iodev] >>= 8;
                        iodev_proxy_buffer[iodev] |= b << 24;
                        if ((iodev_proxy_buffer[iodev] & 0xffffff) == 0xAA55FF)
                            break;
                    }
                }
                iodev++;
                if (iodev == IODEV_MAX)
                    iodev = 0;
            }
        } else {
            // Stick to the current iodev for exceptions
            do {
                u8 b;
                iodev_handle_events(iodev);
                if (iodev_read(iodev, &b, 1) != 1) {
                    printf("Proxy: iodev read failed, exiting.\n");
                    return -1;
                }
                iodev_proxy_buffer[iodev] >>= 8;
                iodev_proxy_buffer[iodev] |= b << 24;
            } while ((iodev_proxy_buffer[iodev] & 0xffffff) != 0xAA55FF);
        }

        memset(&request, 0, sizeof(request));
        request.type = iodev_proxy_buffer[iodev];
        bytes = iodev_read(iodev, (&request.type) + 1, REQ_SIZE - 4);
        if (bytes != REQ_SIZE - 4)
            continue;

        if (checksum(&(request.type), REQ_SIZE - 4) != request.checksum) {
            memset(&reply, 0, sizeof(reply));
            reply.type = request.type;
            reply.status = ST_CSUMERR;
            reply.checksum = checksum(&reply, REPLY_SIZE - 4);
            iodev_write(iodev, &reply, REPLY_SIZE);
            continue;
        }

        memset(&reply, 0, sizeof(reply));
        reply.type = request.type;
        reply.status = ST_OK;

        uartproxy_iodev = iodev;

        switch (request.type) {
            case REQ_NOP:
                enabled_features = request.features & PROXY_FEAT_ALL;
                if (iodev == IODEV_UART) {
                    // Don't allow disabling checksums on UART
                    enabled_features &= ~PROXY_FEAT_DISABLE_DATA_CSUMS;
                }

                disable_data_csums = enabled_features & PROXY_FEAT_DISABLE_DATA_CSUMS;
                reply.features = enabled_features;
                break;
            case REQ_PROXY:
                ret = proxy_process(&request.prequest, &reply.preply);
                if (ret != 0)
                    running = 0;
                if (ret < 0)
                    printf("Proxy req error: %d\n", ret);
                break;
            case REQ_MEMREAD:
                if (request.mrequest.size == 0)
                    break;
                exc_count = 0;
                exc_guard = GUARD_RETURN;
                checksum_val = data_checksum((void *)request.mrequest.addr, request.mrequest.size);
                exc_guard = GUARD_OFF;
                if (exc_count)
                    reply.status = ST_XFRERR;
                reply.mreply.dchecksum = checksum_val;
                break;
            case REQ_MEMWRITE:
                exc_count = 0;
                exc_guard = GUARD_SKIP;
                if (request.mrequest.size != 0) {
                    // Probe for exception guard
                    // We can't do the whole buffer easily, because we'd drop UART data
                    write8(request.mrequest.addr, 0);
                    write8(request.mrequest.addr + request.mrequest.size - 1, 0);
                }
                exc_guard = GUARD_OFF;
                if (exc_count) {
                    reply.status = ST_XFRERR;
                    break;
                }
                bytes = iodev_read(iodev, (void *)request.mrequest.addr, request.mrequest.size);
                if (bytes != request.mrequest.size) {
                    reply.status = ST_XFRERR;
                    break;
                }
                checksum_val = data_checksum((void *)request.mrequest.addr, request.mrequest.size);
                reply.mreply.dchecksum = checksum_val;
                if (reply.mreply.dchecksum != request.mrequest.dchecksum) {
                    reply.status = ST_XFRERR;
                    break;
                }
                if (disable_data_csums) {
                    // Check the sentinel that should be present after the data
                    u32 sentinel = 0;
                    bytes = iodev_read(iodev, &sentinel, sizeof(sentinel));
                    if (bytes != sizeof(sentinel) || sentinel != DATA_END_SENTINEL) {
                        reply.status = ST_XFRERR;
                        break;
                    }
                }
                break;
            default:
                reply.status = ST_BADCMD;
                break;
        }
        sysop("dsb sy");
        sysop("isb");
        reply.checksum = checksum(&reply, REPLY_SIZE - 4);
        iodev_lock(uartproxy_iodev);
        iodev_queue(iodev, &reply, REPLY_SIZE);

        if ((request.type == REQ_MEMREAD) && (reply.status == ST_OK)) {
            iodev_queue(iodev, (void *)request.mrequest.addr, request.mrequest.size);

            if (disable_data_csums) {
                // Since there is no checksum, put a sentinel after the data so the receiver
                // can check that no packets were lost.
                u32 sentinel = DATA_END_SENTINEL;

                iodev_queue(iodev, &sentinel, sizeof(sentinel));
            }
        }

        iodev_unlock(uartproxy_iodev);
        // Flush all queued data
        iodev_write(iodev, NULL, 0);
        iodev_flush(iodev);
    }

    return ret;
}

void uartproxy_send_event(u16 event_type, void *data, u16 length)
{
    UartEventHdr hdr;
    u32 csum;

    hdr.type = REQ_EVENT;
    hdr.len = length;
    hdr.event_type = event_type;

    if (disable_data_csums) {
        csum = CHECKSUM_SENTINEL;
    } else {
        csum = checksum_start(&hdr, sizeof(UartEventHdr));
        csum = checksum_finish(checksum_add(data, length, csum));
    }
    iodev_lock(uartproxy_iodev);
    iodev_queue(uartproxy_iodev, &hdr, sizeof(UartEventHdr));
    iodev_queue(uartproxy_iodev, data, length);
    iodev_write(uartproxy_iodev, &csum, sizeof(csum));
    iodev_unlock(uartproxy_iodev);
}
