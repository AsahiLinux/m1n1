/* SPDX-License-Identifier: MIT */

#include "uartproxy.h"
#include "exception.h"
#include "proxy.h"
#include "string.h"
#include "types.h"
#include "uart.h"
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
    };
    u32 checksum;
} UartReply;

#define REQ_NOP      0x00AA55FF
#define REQ_PROXY    0x01AA55FF
#define REQ_MEMREAD  0x02AA55FF
#define REQ_MEMWRITE 0x03AA55FF
#define REQ_BOOT     0x04AA55FF

#define ST_OK     0
#define ST_BADCMD -1
#define ST_INVAL  -2
#define ST_XFRERR -3
#define ST_CRCERR -4

// I just totally pulled this out of my arse
// Noinline so that this can be bailed out by exc_guard = EXC_RETURN
// We assume this function does not use the stack
static u64 __attribute__((noinline)) checksum(void *start, u32 length)
{
    u32 sum = 0xDEADBEEF;
    u8 *d = (u8 *)start;

    while (length--) {
        sum *= 31337;
        sum += (*d++) ^ 0x5A;
    }
    return sum ^ 0xADDEDBAD;
}

void uartproxy_run(void)
{
    int running = 1;
    int c;
    size_t bytes;
    u64 checksum_val;

    UartRequest request;
    UartReply reply = {REQ_BOOT};
    reply.checksum = checksum(&reply, REPLY_SIZE - 4);
    uart_write(&reply, REPLY_SIZE);

    while (running) {
        c = uart_getbyte();
        if (c != 0xFF)
            continue;
        c = uart_getbyte();
        if (c != 0x55)
            continue;
        c = uart_getbyte();
        if (c != 0xAA)
            continue;
        c = uart_getbyte();
        if (c < 0)
            continue;
        memset(&request, 0, sizeof(request));
        request.type = 0x00AA55FF | ((c & 0xff) << 24);
        bytes = uart_read((&request.type) + 1, REQ_SIZE - 4);
        if (bytes != REQ_SIZE - 4)
            continue;
        if (checksum(&(request.type), REQ_SIZE - 4) != request.checksum)
            continue;

        memset(&reply, 0, sizeof(reply));
        reply.type = request.type;
        reply.status = ST_OK;

        switch (request.type) {
            case REQ_NOP:
                break;
            case REQ_PROXY:
                running = proxy_process(&request.prequest, &reply.preply);
                break;
            case REQ_MEMREAD:
                if (request.mrequest.size == 0)
                    break;
                exc_count = 0;
                exc_guard = GUARD_RETURN;
                checksum_val = checksum((void *)request.mrequest.addr, request.mrequest.size);
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
                bytes = uart_read((void *)request.mrequest.addr, request.mrequest.size);
                if (bytes != request.mrequest.size) {
                    reply.status = ST_XFRERR;
                    break;
                }
                checksum_val = checksum((void *)request.mrequest.addr, request.mrequest.size);
                reply.mreply.dchecksum = checksum_val;
                if (reply.mreply.dchecksum != request.mrequest.dchecksum)
                    reply.status = ST_XFRERR;
                break;
            default:
                reply.status = ST_BADCMD;
                break;
        }
        reply.checksum = checksum(&reply, REPLY_SIZE - 4);
        uart_write(&reply, REPLY_SIZE);

        if ((request.type == REQ_MEMREAD) && (reply.status == ST_OK)) {
            uart_write((void *)request.mrequest.addr, request.mrequest.size);
        }
    }
}
