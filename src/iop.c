#include <string.h>

#include "iop.h"
#include "malloc.h"
#include "utils.h"

// A2I = Application Processor (i.e. we) to I/O Processor (i.e. usually RTKit)

#define APPLE_IOP_CPU_CONTROL     0x44
#define APPLE_IOP_CPU_CONTROL_RUN 0x10

#define APPLE_IOP_A2I_CONTROL       0x8110
#define APPLE_IOP_A2I_CONTROL_FULL  BIT(16)
#define APPLE_IOP_A2I_CONTROL_EMPTY BIT(17)

#define APPLE_IOP_I2A_CONTROL       0x8114
#define APPLE_IOP_I2A_CONTROL_FULL  BIT(16)
#define APPLE_IOP_I2A_CONTROL_EMPTY BIT(17)

#define APPLE_IOP_A2I_MBOX_MSG  0x8800
#define APPLE_IOP_A2I_MBOX_INFO 0x8808
#define APPLE_IOP_I2A_MBOX_MSG  0x8830
#define APPLE_IOP_I2A_MBOX_INFO 0x8838

#define APPLE_RTKIT_EP_MGMT     0
#define APPLE_RTKIT_EP_CRASHLOG 1
#define APPLE_RTKIT_EP_SYSLOG   2
#define APPLE_RTKIT_EP_DEBUG    3
#define APPLE_RTKIT_EP_IOREPORT 4

#define MAX_EPS 0x100

struct iop_dev {
    uintptr_t base;
    void *shmem_paddr;
    uintptr_t shmem_iova;
    size_t shmem_offset;

    bool initialized;

    void *syslog_bfr;
    size_t syslog_sz;

    void *crashlog_bfr;
    size_t crashlog_sz;

    void *ioreport_bfr;
    size_t ioreport_sz;

    DECLARE_BITFIELD(endpoints, MAX_EPS);
};

union iop_msg_info {
    struct {
        u8 ep;
        u8 unk0;
        u16 unk1;
        u32 unk2;
    } msg;
    u64 raw;
};

iop_t *iop_init(uintptr_t base, void *shmem_paddr, uintptr_t shmem_iova)
{
    iop_t *iop = malloc(sizeof(*iop));
    if (!iop)
        return NULL;

    iop->base = base;
    iop->shmem_paddr = shmem_paddr;
    iop->shmem_iova = shmem_iova;
    iop->shmem_offset = 0;
    iop->initialized = false;

    return iop;
}

bool iop_can_send(iop_t *iop)
{
    return !(read32(iop->base + APPLE_IOP_A2I_CONTROL) & APPLE_IOP_A2I_CONTROL_FULL);
}

bool iop_can_recv(iop_t *iop)
{
    return !(read32(iop->base + APPLE_IOP_I2A_CONTROL) & APPLE_IOP_I2A_CONTROL_EMPTY);
}

bool iop_check_send(iop_t *iop)
{
    if (!iop_can_send(iop)) {
        printf("iop: WARNING: unable to send message\n");
        return false;
    }

    return true;
}

void iop_send(iop_t *iop, u64 msg, union iop_msg_info info)
{
    while (!iop_can_send(iop))
        ;

    printf("iop: send: %016lx to ep #0x%02x\n", msg, info.msg.ep);

    write64(iop->base + APPLE_IOP_A2I_MBOX_MSG, msg);
    write64(iop->base + APPLE_IOP_A2I_MBOX_INFO, info.raw);
}

bool iop_recv_raw(iop_t *iop, u64 *msg, union iop_msg_info *info, bool block)
{
    if (block) {
        while (!iop_can_recv(iop))
            ;
    } else {
        if (!iop_can_recv(iop))
            return false;
    }

    *msg = read64(iop->base + APPLE_IOP_I2A_MBOX_MSG);
    info->raw = read64(iop->base + APPLE_IOP_I2A_MBOX_INFO);

    printf("iop: receive: %016lx from ep #0x%02x, %x\n", *msg, info->msg.ep, info->msg.unk0);
    return true;
}

#define MGMT_TYPE GENMASK(59, 52)

#define MGMT_HELLO       1
#define MGMT_HELLO_REPLY 2
#define MGMT_HELLO_TAG   GENMASK(31, 0)

#define MGMT_EPMAP        8
#define MGMT_EPMAP_LAST   BIT(51)
#define MGMT_EPMAP_BASE   GENMASK(34, 32)
#define MGMT_EPMAP_BITMAP GENMASK(31, 0)

#define MGMT_EPMAP_REPLY      8
#define MGMT_EPMAP_REPLY_MORE BIT(0)

#define MGMT_STARTEP      5
#define MGMT_STARTEP_EP   GENMASK(39, 32)
#define MGMT_STARTEP_FLAG BIT(1)

#define MGMT_BOOT_DONE     7
#define MGMT_BOOT_DONE_UNK GENMASK(15, 0)

#define MGMT_BOOT_DONE2 0xb

static void iop_handle_mgmt(iop_t *iop, u64 msg)
{
    u8 type = FIELD_GET(MGMT_TYPE, msg);
    union iop_msg_info reply_info;
    u64 reply_msg;

    memset(&reply_info, 0, sizeof(reply_info));
    reply_info.msg.ep = 0;

    switch (type) {
        case MGMT_HELLO:
            printf("iop: mgmt: HELLO\n");
            if (!iop_check_send(iop))
                return;
            reply_msg = FIELD_PREP(MGMT_HELLO_TAG, FIELD_GET(MGMT_HELLO_TAG, msg));
            reply_msg |= FIELD_PREP(MGMT_TYPE, MGMT_HELLO_REPLY);
            iop_send(iop, reply_msg, reply_info);
            break;

        case MGMT_EPMAP:
            for (int i = 0; i < 32; ++i) {
                if (FIELD_GET(MGMT_EPMAP_BITMAP, msg) & BIT(i))
                    BIT_SET(iop->endpoints, 32 * FIELD_GET(MGMT_EPMAP_BASE, msg) + i);
            }

            reply_msg = FIELD_PREP(MGMT_TYPE, MGMT_EPMAP_REPLY);
            reply_msg |= FIELD_PREP(MGMT_EPMAP_BASE, FIELD_GET(MGMT_EPMAP_BASE, msg));
            if (msg & MGMT_EPMAP_LAST)
                reply_msg |= MGMT_EPMAP_LAST;
            else
                reply_msg |= MGMT_EPMAP_REPLY_MORE;
            iop_send(iop, reply_msg, reply_info);

            if (msg & MGMT_EPMAP_LAST) {
                for_each_set_bit(ep, iop->endpoints, MAX_EPS)
                {
                    if (ep == 0)
                        continue;
                    reply_msg = FIELD_PREP(MGMT_TYPE, MGMT_STARTEP);
                    reply_msg |= FIELD_PREP(MGMT_STARTEP_EP, ep);
                    reply_msg |= MGMT_STARTEP_FLAG;
                    iop_send(iop, reply_msg, reply_info);
                }
            }
            break;
        case MGMT_BOOT_DONE:
            reply_msg = FIELD_PREP(MGMT_TYPE, 0xb);
            reply_msg |= FIELD_PREP(MGMT_BOOT_DONE_UNK, 0x20);
            iop_send(iop, reply_msg, reply_info);
            break;

        case MGMT_BOOT_DONE2:
            iop->initialized = true;
            break;
        default:
            printf("iop: unknown MGMT message: %016lx (type: 0x%08x)\n", msg, type);
    }
}

#define COMMON_REQUEST_BUFFER      1
#define COMMON_REQUEST_BUFFER_SIZE GENMASK(51, 44)
#define COMMON_REQUEST_BUFFER_IOVA GENMASK(39, 0)

static void iop_handle_buffer(iop_t *iop, const char *name, u8 ep, u64 msg, void **bfr, size_t *sz)
{
    union iop_msg_info reply_info;
    u64 reply_msg;

    size_t bfr_sz;
    uintptr_t bfr_iova;

    memset(&reply_info, 0, sizeof(reply_info));
    reply_info.msg.ep = ep;

    bfr_sz = FIELD_GET(COMMON_REQUEST_BUFFER_SIZE, msg) << 12;
    bfr_iova = iop->shmem_iova + iop->shmem_offset;
    *bfr = iop->shmem_paddr + iop->shmem_offset;
    *sz = bfr_sz;
    iop->shmem_offset += bfr_sz;

    printf("iop: %s: buffer at %p (iova: %lx) with size #0x%lx\n", name, *bfr, bfr_iova, bfr_sz);
    reply_msg = FIELD_PREP(MGMT_TYPE, COMMON_REQUEST_BUFFER);
    reply_msg |= FIELD_PREP(COMMON_REQUEST_BUFFER_SIZE, bfr_sz >> 12);
    reply_msg |= FIELD_PREP(COMMON_REQUEST_BUFFER_IOVA, bfr_iova);
    iop_send(iop, reply_msg, reply_info);
}

static void iop_handle_crashlog(iop_t *iop, u64 msg)
{
    u8 type = FIELD_GET(MGMT_TYPE, msg);

    switch (type) {
        case COMMON_REQUEST_BUFFER:
            iop_handle_buffer(iop, "crashlog", APPLE_RTKIT_EP_CRASHLOG, msg, &iop->crashlog_bfr,
                              &iop->crashlog_sz);
            break;
        default:
            printf("iop: unknown crashlog message: %016lx (type: 0x%08x)\n", msg, type);
    }
}

static void iop_handle_syslog(iop_t *iop, u64 msg)
{
    u8 type = FIELD_GET(MGMT_TYPE, msg);

    switch (type) {
        case COMMON_REQUEST_BUFFER:
            iop_handle_buffer(iop, "syslog", APPLE_RTKIT_EP_SYSLOG, msg, &iop->syslog_bfr,
                              &iop->syslog_sz);
            break;
        default:
            printf("iop: unknown syslog message: %016lx (type: 0x%08x)\n", msg, type);
    }
}

static void iop_handle_debug(iop_t *iop, u64 msg)
{
    UNUSED(iop);
    u8 type = FIELD_GET(MGMT_TYPE, msg);
    printf("iop: unknown debug message: %016lx (type: 0x%08x)\n", msg, type);
}

static void iop_handle_ioreport(iop_t *iop, u64 msg)
{
    u8 type = FIELD_GET(MGMT_TYPE, msg);
    union iop_msg_info reply_info;
    u64 reply_msg;

    memset(&reply_info, 0, sizeof(reply_info));
    reply_info.msg.ep = APPLE_RTKIT_EP_IOREPORT;

    switch (type) {
        case 0x8:
            reply_msg = FIELD_PREP(MGMT_TYPE, 0x8);
            iop_send(iop, reply_msg, reply_info);
            break;
        case COMMON_REQUEST_BUFFER:
            iop_handle_buffer(iop, "ioreport", APPLE_RTKIT_EP_IOREPORT, msg, &iop->ioreport_bfr,
                              &iop->ioreport_sz);
            break;
        default:
            printf("iop: unknown ioreport message: %016lx (type: 0x%08x)\n", msg, type);
    }
}

bool iop_recv(iop_t *iop, u64 *_msg, union iop_msg_info *_info, bool block)
{
    u64 msg;
    union iop_msg_info info;
    bool did_recv = true;

    while (did_recv) {
        did_recv = iop_recv_raw(iop, &msg, &info, block);
        if (!did_recv)
            continue;
        switch (info.msg.ep) {
            case APPLE_RTKIT_EP_MGMT:
                iop_handle_mgmt(iop, msg);
                break;
            case APPLE_RTKIT_EP_CRASHLOG:
                iop_handle_crashlog(iop, msg);
                break;
            case APPLE_RTKIT_EP_SYSLOG:
                iop_handle_syslog(iop, msg);
                break;
            case APPLE_RTKIT_EP_DEBUG:
                iop_handle_debug(iop, msg);
                break;
            case APPLE_RTKIT_EP_IOREPORT:
                iop_handle_ioreport(iop, msg);
                break;
            default:
                *_msg = msg;
                *_info = info;
                return true;
        }
    }

    return false;
}

void iop_boot(iop_t *iop)
{
    u64 msg;
    union iop_msg_info info;
    bool did_recv = false;

    set32(iop->base + APPLE_IOP_CPU_CONTROL, APPLE_IOP_CPU_CONTROL_RUN);

    while (!iop->initialized) {
        did_recv = iop_recv(iop, &msg, &info, false);

        if (!did_recv)
            continue;
        switch (info.msg.ep) {
            default:
                printf("iop: message to unknown ep #0x%02x during boot\n", info.msg.ep);
                break;
        }
    }
}
