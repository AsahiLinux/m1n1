/* SPDX-License-Identifier: MIT */

#include "asc.h"
#include "dart.h"
#include "iova.h"
#include "malloc.h"
#include "rtkit.h"
#include "sart.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define rtkit_printf(...)                                                                          \
    do {                                                                                           \
        debug_printf("rtkit(%s): ", rtk->name);                                                    \
        debug_printf(__VA_ARGS__);                                                                 \
    } while (0)

#define RTKIT_EP_MGMT     0
#define RTKIT_EP_CRASHLOG 1
#define RTKIT_EP_SYSLOG   2
#define RTKIT_EP_DEBUG    3
#define RTKIT_EP_IOREPORT 4

#define MGMT_TYPE GENMASK(59, 52)

#define MGMT_PWR_STATE GENMASK(15, 0)

#define MSG_BUFFER_REQUEST      1
#define MSG_BUFFER_REQUEST_SIZE GENMASK(51, 44)
#define MSG_BUFFER_REQUEST_IOVA GENMASK(41, 0)

#define MGMT_MSG_HELLO        1
#define MGMT_MSG_HELLO_ACK    2
#define MGMT_MSG_HELLO_MINVER GENMASK(15, 0)
#define MGMT_MSG_HELLO_MAXVER GENMASK(31, 16)

#define MGMT_MSG_IOP_PWR_STATE     6
#define MGMT_MSG_IOP_PWR_STATE_ACK 7

#define MGMT_MSG_EPMAP        8
#define MGMT_MSG_EPMAP_DONE   BIT(51)
#define MGMT_MSG_EPMAP_BASE   GENMASK(34, 32)
#define MGMT_MSG_EPMAP_BITMAP GENMASK(31, 0)

#define MGMT_MSG_EPMAP_REPLY      8
#define MGMT_MSG_EPMAP_REPLY_DONE BIT(51)
#define MGMT_MSG_EPMAP_REPLY_MORE BIT(0)

#define MGMT_MSG_AP_PWR_STATE     0xb
#define MGMT_MSG_AP_PWR_STATE_ACK 0xb

#define MGMT_MSG_START_EP      5
#define MGMT_MSG_START_EP_IDX  GENMASK(39, 32)
#define MGMT_MSG_START_EP_FLAG BIT(1)

#define RTKIT_MIN_VERSION 11
#define RTKIT_MAX_VERSION 12

enum rtkit_power_state {
    RTKIT_POWER_OFF = 0x00,
    RTKIT_POWER_SLEEP = 0x01,
    RTKIT_POWER_ON = 0x20,
};

struct rtkit_buffer {
    void *bfr;
    u64 iova;
    size_t sz;
};

struct rtkit_dev {
    char *name;

    asc_dev_t *asc;
    dart_dev_t *dart;
    iova_domain_t *dart_iovad;
    sart_dev_t *sart;

    enum rtkit_power_state iop_power;
    enum rtkit_power_state ap_power;

    struct rtkit_buffer syslog_bfr;
    struct rtkit_buffer crashlog_bfr;
    struct rtkit_buffer ioreport_bfr;
};

rtkit_dev_t *rtkit_init(const char *name, asc_dev_t *asc, dart_dev_t *dart,
                        iova_domain_t *dart_iovad, sart_dev_t *sart)
{
    if (dart && sart) {
        printf("rtkit: Cannot use both SART and DART simultaneously\n");
        return NULL;
    }

    if (dart && !dart_iovad) {
        printf("rtkit: if DART is used iovad is already required\n");
        return NULL;
    }

    rtkit_dev_t *rtk = malloc(sizeof(*rtk));
    if (!rtk)
        return NULL;
    memset(rtk, 0, sizeof(*rtk));

    size_t name_len = strlen(name);
    rtk->name = malloc(name_len + 1);
    if (!rtk->name)
        goto out_free_rtk;
    strcpy(rtk->name, name);

    rtk->asc = asc;
    rtk->dart = dart;
    rtk->dart_iovad = dart_iovad;
    rtk->sart = sart;
    rtk->iop_power = RTKIT_POWER_OFF;
    rtk->ap_power = RTKIT_POWER_OFF;

    return rtk;

out_free_rtk:
    free(rtk);
    return NULL;
}

void rtkit_free(rtkit_dev_t *rtk)
{
    free(rtk->name);
    free(rtk);
}

bool rtkit_send(rtkit_dev_t *rtk, const struct rtkit_message *msg)
{
    struct asc_message asc_msg;

    asc_msg.msg0 = msg->msg;
    asc_msg.msg1 = msg->ep;

    return asc_send(rtk->asc, &asc_msg);
}

static bool rtkit_handle_buffer_request(rtkit_dev_t *rtk, struct rtkit_message *msg,
                                        struct rtkit_buffer *bfr)
{
    size_t n_4kpages = FIELD_GET(MSG_BUFFER_REQUEST_SIZE, msg->msg);
    size_t sz = n_4kpages << 12;
    u64 addr = FIELD_GET(MSG_BUFFER_REQUEST_IOVA, msg->msg);

    if (addr) {
        rtkit_printf("buffer request but buffer already exists\n");
        return false;
    }

    bfr->bfr = memalign(SZ_16K, sz);
    if (!bfr->bfr) {
        rtkit_printf("unable to allocate %zu buffer\n", sz);
        return false;
    }

    bfr->sz = sz;

    if (rtk->sart) {
        if (!sart_add_allowed_region(rtk->sart, bfr->bfr, sz))
            goto error;

        bfr->iova = (u64)bfr->bfr;
    } else if (rtk->dart) {
        bfr->iova = iova_alloc(rtk->dart_iovad, sz);
        if (!bfr->iova)
            goto error;

        if (dart_map(rtk->dart, bfr->iova, bfr->bfr, sz) < 0)
            goto error;
    } else {
        rtkit_printf("TODO: implement no IOMMU buffers\n");
        goto error;
    }

    struct asc_message reply;
    reply.msg1 = msg->ep;
    reply.msg0 = FIELD_PREP(MGMT_TYPE, MSG_BUFFER_REQUEST);
    reply.msg0 |= FIELD_PREP(MSG_BUFFER_REQUEST_SIZE, n_4kpages);
    reply.msg0 |= FIELD_PREP(MSG_BUFFER_REQUEST_IOVA, bfr->iova);

    if (!asc_send(rtk->asc, &reply)) {
        rtkit_printf("unable to send buffer reply\n");
        goto error;
    }

    return true;

error:
    if (bfr->iova && rtk->dart_iovad)
        iova_free(rtk->dart_iovad, bfr->iova, sz);
    free(bfr->bfr);
    bfr->bfr = NULL;
    bfr->sz = 0;
    bfr->iova = 0;
    return false;
}

bool rtkit_recv(rtkit_dev_t *rtk, struct rtkit_message *msg)
{
    struct asc_message asc_msg;

    while (asc_recv(rtk->asc, &asc_msg)) {
        if (asc_msg.msg1 >= 0x100) {
            rtkit_printf("WARNING: received message for invalid endpoint %x >= 0x100\n",
                         asc_msg.msg1);
            return false;
        }

        msg->msg = asc_msg.msg0;
        msg->ep = (u8)asc_msg.msg1;

        /* if this is an app message we can just forwad it to the caller */
        if (msg->ep >= 0x20)
            return true;

        u32 msgtype = FIELD_GET(MGMT_TYPE, msg->msg);
        switch (msg->ep) {
            case RTKIT_EP_MGMT:
                switch (msgtype) {
                    case MGMT_MSG_IOP_PWR_STATE_ACK:
                        rtk->iop_power = FIELD_GET(MGMT_PWR_STATE, msg->msg);
                        break;
                    case MGMT_MSG_AP_PWR_STATE_ACK:
                        rtk->ap_power = FIELD_GET(MGMT_PWR_STATE, msg->msg);
                        break;
                    default:
                        rtkit_printf("unknown management message %x\n", msgtype);
                }
                break;
            case RTKIT_EP_SYSLOG:
                switch (msgtype) {
                    case MSG_BUFFER_REQUEST:
                        rtkit_handle_buffer_request(rtk, msg, &rtk->syslog_bfr);
                        break;
                    default:
                        rtkit_printf("unknown syslog message %x\n", msgtype);
                }
                break;
            case RTKIT_EP_CRASHLOG:
                switch (msgtype) {
                    case MSG_BUFFER_REQUEST:
                        rtkit_handle_buffer_request(rtk, msg, &rtk->crashlog_bfr);
                        break;
                    default:
                        rtkit_printf("unknown crashlog message %x\n", msgtype);
                }
                break;
            case RTKIT_EP_IOREPORT:
                switch (msgtype) {
                    case MSG_BUFFER_REQUEST:
                        rtkit_handle_buffer_request(rtk, msg, &rtk->ioreport_bfr);
                        break;
                    /* unknown but must be ACKed */
                    case 0x8:
                    case 0xc:
                        if (!rtkit_send(rtk, msg))
                            rtkit_printf("unable to ACK unknown ioreport message\n");
                        break;
                    default:
                        rtkit_printf("unknown ioreport message %x\n", msgtype);
                }
                break;
            default:
                rtkit_printf("message to unknown system endpoint 0x%02x: %lx\n", msg->ep, msg->msg);
        }
    }

    return false;
}

bool rtkit_start_ep(rtkit_dev_t *rtk, u8 ep)
{
    struct asc_message msg;

    msg.msg0 = FIELD_PREP(MGMT_TYPE, MGMT_MSG_START_EP);
    msg.msg0 |= MGMT_MSG_START_EP_FLAG;
    msg.msg0 |= FIELD_PREP(MGMT_MSG_START_EP_IDX, ep);
    msg.msg1 = RTKIT_EP_MGMT;

    if (!asc_send(rtk->asc, &msg)) {
        rtkit_printf("unable to start endpoint 0x%02x\n", ep);
        return false;
    }

    return true;
}

bool rtkit_boot(rtkit_dev_t *rtk)
{
    struct asc_message msg;

    /* can be sent unconditionally to wake up a possibly sleeping IOP */
    msg.msg0 =
        FIELD_PREP(MGMT_TYPE, MGMT_MSG_IOP_PWR_STATE) | FIELD_PREP(MGMT_PWR_STATE, RTKIT_POWER_ON);
    msg.msg1 = RTKIT_EP_MGMT;
    if (!asc_send(rtk->asc, &msg)) {
        rtkit_printf("unable to send wakeup message\n");
        return false;
    }

    if (!asc_recv_timeout(rtk->asc, &msg, USEC_PER_SEC)) {
        rtkit_printf("did not receive HELLO\n");
        return false;
    }

    if (msg.msg1 != RTKIT_EP_MGMT) {
        rtkit_printf("expected HELLO but got message for EP 0x%x", msg.msg1);
        return false;
    }

    u32 msgtype;
    msgtype = FIELD_GET(MGMT_TYPE, msg.msg0);
    if (msgtype != MGMT_MSG_HELLO) {
        rtkit_printf("expected HELLO but got message with type 0x%02x", msgtype);

        return false;
    }

    u32 min_ver, max_ver, want_ver;
    min_ver = FIELD_GET(MGMT_MSG_HELLO_MINVER, msg.msg0);
    max_ver = FIELD_GET(MGMT_MSG_HELLO_MAXVER, msg.msg0);
    want_ver = min(RTKIT_MAX_VERSION, max_ver);

    if (min_ver > RTKIT_MIN_VERSION || max_ver < RTKIT_MAX_VERSION) {
        rtkit_printf("supported versions [%d,%d] must overlap versions [%d,%d]\n",
                     RTKIT_MIN_VERSION, RTKIT_MAX_VERSION, min_ver, max_ver);
        return false;
    }

    rtkit_printf("booting with version %d\n", want_ver);

    msg.msg0 = FIELD_PREP(MGMT_TYPE, MGMT_MSG_HELLO_ACK);
    msg.msg0 |= FIELD_PREP(MGMT_MSG_HELLO_MINVER, want_ver);
    msg.msg0 |= FIELD_PREP(MGMT_MSG_HELLO_MAXVER, want_ver);
    msg.msg1 = RTKIT_EP_MGMT;
    if (!asc_send(rtk->asc, &msg)) {
        rtkit_printf("couldn't send HELLO ack\n");
        return false;
    }

    bool has_crashlog = false;
    bool has_debug = false;
    bool has_ioreport = false;
    bool has_syslog = false;
    bool got_epmap = false;
    while (!got_epmap) {
        if (!asc_recv_timeout(rtk->asc, &msg, USEC_PER_SEC)) {
            rtkit_printf("couldn't receive message while waiting for endpoint map\n");
            return false;
        }

        if (msg.msg1 != RTKIT_EP_MGMT) {
            rtkit_printf("expected management message while waiting for endpoint map but got "
                         "message for endpoint 0x%x\n",
                         msg.msg1);
            return false;
        }

        msgtype = FIELD_GET(MGMT_TYPE, msg.msg0);
        if (msgtype != MGMT_MSG_EPMAP) {
            rtkit_printf("expected endpoint map message but got 0x%x instead\n", msgtype);
            return false;
        }

        u32 bitmap = FIELD_GET(MGMT_MSG_EPMAP_BITMAP, msg.msg0);
        u32 base = FIELD_GET(MGMT_MSG_EPMAP_BASE, msg.msg0);
        for (unsigned int i = 0; i < 32; i++) {
            if (bitmap & (1U << i)) {
                u8 ep_idx = 32 * base + i;

                if (ep_idx >= 0x20)
                    continue;
                switch (ep_idx) {
                    case RTKIT_EP_CRASHLOG:
                        has_crashlog = true;
                        break;
                    case RTKIT_EP_DEBUG:
                        has_debug = true;
                        break;
                    case RTKIT_EP_IOREPORT:
                        has_ioreport = true;
                        break;
                    case RTKIT_EP_SYSLOG:
                        has_syslog = true;
                        break;
                    case RTKIT_EP_MGMT:
                        break;
                    default:
                        rtkit_printf("unknown system endpoint 0x%02x\n", ep_idx);
                }
            }
        }

        if (msg.msg0 & MGMT_MSG_EPMAP_DONE)
            got_epmap = true;

        msg.msg0 = FIELD_PREP(MGMT_TYPE, MGMT_MSG_EPMAP_REPLY);
        msg.msg0 |= FIELD_PREP(MGMT_MSG_EPMAP_BASE, base);
        if (got_epmap)
            msg.msg0 |= MGMT_MSG_EPMAP_REPLY_DONE;
        else
            msg.msg0 |= MGMT_MSG_EPMAP_REPLY_MORE;

        msg.msg1 = RTKIT_EP_MGMT;

        if (!asc_send(rtk->asc, &msg)) {
            rtkit_printf("couldn't reply to endpoint map\n");
            return false;
        }
    }

    /* start all required system endpoints */
    if (has_debug && !rtkit_start_ep(rtk, RTKIT_EP_DEBUG))
        return false;
    if (has_crashlog && !rtkit_start_ep(rtk, RTKIT_EP_CRASHLOG))
        return false;
    if (has_syslog && !rtkit_start_ep(rtk, RTKIT_EP_SYSLOG))
        return false;
    if (has_ioreport && !rtkit_start_ep(rtk, RTKIT_EP_IOREPORT))
        return false;

    while (rtk->iop_power != RTKIT_POWER_ON) {
        struct rtkit_message rtk_msg;
        if (rtkit_recv(rtk, &rtk_msg)) {
            rtkit_printf("unexpected message to non-system endpoint 0x%02x during boot: %lx\n",
                         rtk_msg.ep, rtk_msg.msg);
            continue;
        }
    }

    /*
     * normally we'd send a AP power state message now but that enables the syslog.
     * we can get away without this message and keep the syslog disabled at least for
     * NVMe / ANS.
     */
    return true;
}

bool rtkit_shutdown(rtkit_dev_t *rtk)
{
    struct asc_message msg;
    msg.msg0 = FIELD_PREP(MGMT_TYPE, MGMT_MSG_IOP_PWR_STATE) |
               FIELD_PREP(MGMT_PWR_STATE, RTKIT_POWER_SLEEP);
    msg.msg1 = RTKIT_EP_MGMT;
    if (!asc_send(rtk->asc, &msg)) {
        rtkit_printf("unable to send shutdown message\n");
        return false;
    }

    while (rtk->iop_power != RTKIT_POWER_SLEEP) {
        struct rtkit_message rtk_msg;
        if (rtkit_recv(rtk, &rtk_msg)) {
            rtkit_printf("unexpected message to non-system endpoint 0x%02x during shutdown: %lx\n",
                         rtk_msg.ep, rtk_msg.msg);
            continue;
        }
    }

    return true;
}
