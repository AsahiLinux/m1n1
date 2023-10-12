/* SPDX-License-Identifier: MIT */

#include "afk.h"
#include "assert.h"
#include "malloc.h"
#include "string.h"
#include "utils.h"

#include "dcp/parser.h"

struct afk_rb_hdr {
    u32 bufsz;
    u32 unk;
    u32 _pad1[14];
    u32 rptr;
    u32 _pad2[15];
    u32 wptr;
    u32 _pad3[15];
};

struct afk_rb {
    bool ready;
    struct afk_rb_hdr *hdr;
    void *buf;
    size_t bufsz;
};

enum EPICType {
    TYPE_NOTIFY = 0,
    TYPE_COMMAND = 3,
    TYPE_REPLY = 4,
    TYPE_NOTIFY_ACK = 8,
};

enum EPICCategory {
    CAT_REPORT = 0x00,
    CAT_NOTIFY = 0x10,
    CAT_REPLY = 0x20,
    CAT_COMMAND = 0x30,
};

struct afk_qe {
    u32 magic;
    u32 size;
    u32 channel;
    u32 type;
    u8 data[];
};

struct epic_hdr {
    u8 version;
    u16 seq;
    u8 _pad;
    u32 unk;
    u64 timestamp;
} PACKED;

struct epic_sub_hdr {
    u32 length;
    u8 version;
    u8 category;
    u16 type;
    u64 timestamp;
    u16 seq;
    u8 unk;
    u8 flags;
    u32 inline_len;
} PACKED;

struct epic_announce {
    char name[32];
    u8 props[];
} PACKED;

struct epic_cmd {
    u32 retcode;
    u64 rxbuf;
    u64 txbuf;
    u32 rxlen;
    u32 txlen;
    u8 rxcookie;
    u8 txcookie;
} PACKED;

struct afk_epic {
    rtkit_dev_t *rtk;

    afk_epic_ep_t *endpoint[0x10];
};

#define AFK_MAX_CHANNEL 8

struct afk_epic_ep {
    int ep;
    afk_epic_t *afk;

    struct rtkit_buffer buf;
    u16 tag;

    struct afk_rb tx;
    struct afk_rb rx;

    struct rtkit_buffer txbuf;
    struct rtkit_buffer rxbuf;

    bool started;
    u16 seq;

    u32 num_channels;

    const afk_epic_service_ops_t *ops;
    afk_epic_service_t services[AFK_MAX_CHANNEL];

    void (*recv_handler)(afk_epic_ep_t *epic);
};

enum RBEP_MSG {
    RBEP_INIT = 0x80,
    RBEP_INIT_ACK = 0xa0,
    RBEP_GETBUF = 0x89,
    RBEP_GETBUF_ACK = 0xa1,
    RBEP_INIT_TX = 0x8a,
    RBEP_INIT_RX = 0x8b,
    RBEP_START = 0xa3,
    RBEP_START_ACK = 0x86,
    RBEP_SEND = 0xa2,
    RBEP_RECV = 0x85,
    RBEP_SHUTDOWN = 0xc0,
    RBEP_SHUTDOWN_ACK = 0xc1,
};

#define BLOCK_SHIFT 6
#define QE_MAGIC    ' POI'

#define RBEP_TYPE GENMASK(63, 48)

#define GETBUF_SIZE    GENMASK(31, 16)
#define GETBUF_TAG     GENMASK(15, 0)
#define GETBUF_ACK_DVA GENMASK(47, 0)

#define INITRB_OFFSET GENMASK(47, 32)
#define INITRB_SIZE   GENMASK(31, 16)
#define INITRB_TAG    GENMASK(15, 0)

#define SEND_WPTR GENMASK(31, 0)

#define EPIC_DATA_READY 13

bool afk_rb_init(afk_epic_ep_t *epic, struct afk_rb *rb, u64 base, u64 size)
{
    rb->hdr = epic->buf.bfr + base;

    if (rb->hdr->bufsz + sizeof(*rb->hdr) != size) {
        printf("AFK: ring buffer size mismatch\n");
        return false;
    }

    rb->buf = rb->hdr + 1;
    rb->bufsz = rb->hdr->bufsz;
    rb->ready = true;

    return true;
}

static int afk_epic_poll(afk_epic_t *afk, int endpoint, bool block)
{
    int ret;
    struct rtkit_message msg;

    while ((ret = rtkit_recv(afk->rtk, &msg)) == 0)
        if (!block)
            break;

    if (ret < 0) {
        printf("EPIC: rtkit_recv failed!\n");
        return ret;
    }

    if (ret == 0) {
        return 0;
    }

    if (msg.ep < 0x20 || msg.ep >= 0x30 || !afk->endpoint[msg.ep - 0x20]) {
        printf("EPIC: received message for unexpected endpoint 0x%02x\n", msg.ep);
        return 0;
    }

    afk_epic_ep_t *epic = afk->endpoint[msg.ep - 0x20];
    if (!epic) {
        printf("EPIC: received message for idle endpoint 0x%02x\n", msg.ep);
        return 0;
    }

    int type = FIELD_GET(RBEP_TYPE, msg.msg);
    u64 base, size, tag;
    switch (type) {
        case RBEP_INIT_ACK:
            break;

        case RBEP_GETBUF:
            size = FIELD_GET(GETBUF_SIZE, msg.msg) << BLOCK_SHIFT;
            epic->tag = FIELD_GET(GETBUF_TAG, msg.msg);
            if (!rtkit_alloc_buffer(epic->afk->rtk, &epic->buf, size)) {
                printf("EPIC: failed to allocate buffer\n");
                return -1;
            }
            msg.msg = (FIELD_PREP(RBEP_TYPE, RBEP_GETBUF_ACK) |
                       FIELD_PREP(GETBUF_ACK_DVA, epic->buf.dva));
            if (!rtkit_send(epic->afk->rtk, &msg)) {
                printf("EPIC: failed to send buffer address\n");
                return -1;
            }
            break;

        case RBEP_INIT_TX:
        case RBEP_INIT_RX:
            base = FIELD_GET(INITRB_OFFSET, msg.msg) << BLOCK_SHIFT;
            size = FIELD_GET(INITRB_SIZE, msg.msg) << BLOCK_SHIFT;
            tag = FIELD_GET(INITRB_TAG, msg.msg);
            if (tag != epic->tag) {
                printf("EPIC: wrong tag (0x%x != 0x%lx)\n", epic->tag, tag);
                return -1;
            }

            struct afk_rb *rb;
            if (type == RBEP_INIT_RX)
                rb = &epic->rx;
            else
                rb = &epic->tx;

            if (!afk_rb_init(epic, rb, base, size))
                return -1;

            if (epic->rx.ready && epic->tx.ready) {
                msg.msg = FIELD_PREP(RBEP_TYPE, RBEP_START);
                if (!rtkit_send(epic->afk->rtk, &msg)) {
                    printf("EPIC: failed to send start\n");
                    return -1;
                }
            }
            break;

        case RBEP_RECV: {
            dma_rmb();
            struct afk_rb *rb = &epic->rx;
            if (rb->hdr->rptr != rb->hdr->wptr) {
                if (endpoint == epic->ep)
                    return EPIC_DATA_READY;
                else if (epic->recv_handler)
                    epic->recv_handler(epic);
            }
            break;
        }
        case RBEP_START_ACK:
            epic->started = true;
            break;

        case RBEP_SHUTDOWN_ACK:
            epic->started = false;
            break;

        default:
            printf("EPIC: received unknown message type 0x%x\n", type);
            return 0;
            break;
    }

    return 0;
}

static int afk_epic_rx(afk_epic_ep_t *epic, struct afk_qe **qe)
{
    struct afk_rb *rb = &epic->rx;
    u32 rptr = rb->hdr->rptr;
    struct afk_qe *hdr = rb->buf + rptr;

    if (hdr->magic != QE_MAGIC) {
        printf("EPIC: bad queue entry magic!\n");
        return -1;
    }

    if (rptr + hdr->size > rb->bufsz) {
        rptr = 0;
        hdr = rb->buf + rptr;
        if (hdr->magic != QE_MAGIC) {
            printf("EPIC: bad queue entry magic!\n");
            return -1;
        }
        rb->hdr->rptr = rptr;
    }

    *qe = hdr;

    return 1;
}

static int afk_epic_tx(afk_epic_ep_t *epic, u32 channel, u32 type, void *data, size_t size)
{
    struct afk_rb *rb = &epic->tx;

    u32 rptr = rb->hdr->rptr;
    u32 wptr = rb->hdr->wptr;
    struct afk_qe *hdr = rb->buf + wptr;
    size_t buf_advance = ALIGN_UP(sizeof(struct afk_qe) + size, 1 << BLOCK_SHIFT);

    if (wptr < rptr && buf_advance >= rptr - wptr)
        goto buffer_full;
    if (wptr >= rptr) {
        bool fits_above_wptr =
            (buf_advance < rb->bufsz - wptr) || (buf_advance == rb->bufsz - wptr && rptr != 0);

        if (!fits_above_wptr && buf_advance >= rptr)
            goto buffer_full;
    }

    hdr->magic = QE_MAGIC;
    hdr->channel = channel;
    hdr->type = type;
    hdr->size = size;

    wptr += sizeof(struct afk_qe);

    if (size > rb->bufsz - wptr) {
        *(struct afk_qe *)rb->buf = *hdr;
        hdr = rb->buf;
        wptr = sizeof(struct afk_qe);
    }

    wptr += size;
    wptr = ALIGN_UP(wptr, 1 << BLOCK_SHIFT);
    if (wptr >= rb->bufsz)
        wptr = 0;

    memcpy(hdr + 1, data, size);

    dma_mb();
    rb->hdr->wptr = wptr;
    dma_wmb();

    struct rtkit_message msg = {
        epic->ep,
        FIELD_PREP(RBEP_TYPE, RBEP_SEND) | FIELD_PREP(SEND_WPTR, wptr),
    };

    if (!rtkit_send(epic->afk->rtk, &msg)) {
        printf("EPIC: failed to send TX WPTR message\n");
        return -1;
    }

    return 1;

buffer_full:
    printf("EPIC: TX ring buffer is full\n");
    return -1;
}

static void afk_epic_rx_ack(afk_epic_ep_t *epic)
{
    struct afk_rb *rb = &epic->rx;
    u32 rptr = rb->hdr->rptr;
    struct afk_qe *hdr = rb->buf + rptr;

    if (hdr->magic != QE_MAGIC) {
        printf("EPIC: bad queue entry magic!\n");
    }

    dma_mb();

    rptr = ALIGN_UP(rptr + sizeof(*hdr) + hdr->size, 1 << BLOCK_SHIFT);
    assert(rptr <= rb->bufsz);
    if (rptr == rb->bufsz)
        rptr = 0;
    rb->hdr->rptr = rptr;
}

int afk_epic_work(afk_epic_t *afk, int endpoint)
{
    int i = 0;

    while (i < 0x10) {
        afk_epic_ep_t *cur = afk->endpoint[i++];
        if (cur) {
            struct afk_rb *rb = &cur->rx;
            if (rb->hdr->rptr != rb->hdr->wptr) {
                if (cur->ep == endpoint) {
                    return EPIC_DATA_READY;
                }
                if (cur->recv_handler)
                    cur->recv_handler(cur);
                else {
                    struct afk_qe *rmsg;
                    // will net block
                    int ret = afk_epic_rx(cur, &rmsg);
                    if (ret < 0) {
                        return ret;
                    }
                    dprintf("EPIC[0x%02x]: ignoring message type %d\n", cur->ep, rmsg->type);
                    afk_epic_rx_ack(cur);
                }
            }
        }
        if (rtkit_can_recv(afk->rtk)) {
            int ret = afk_epic_poll(afk, endpoint, false);
            if (ret < 0 || ret == EPIC_DATA_READY)
                return ret;
            i = 0;
            continue;
        }
    }

    return 0;
}

static afk_epic_service_t *afk_epic_find_service(afk_epic_ep_t *epic, u32 channel)
{
    for (u32 i = 0; i < epic->num_channels; i++)
        if (epic->services[i].enabled && epic->services[i].channel == channel)
            return &epic->services[i];

    return NULL;
}

struct epic_std_service_ap_call {
    u32 unk0;
    u32 unk1;
    u32 type;
    u32 len;
    u32 magic;
    u8 _unk[48];
} PACKED;

static int afk_epic_handle_std_service(afk_epic_ep_t *epic, int channel, u8 category, u16 sub_seq,
                                       void *payload, size_t payload_size)
{
    afk_epic_service_t *service = afk_epic_find_service(epic, channel);

    if (service && service->ops->call && category == CAT_NOTIFY) {
        struct epic_std_service_ap_call *call = payload;
        size_t call_size;
        void *reply;
        int ret;

        if (payload_size < sizeof(*call))
            return -1;

        call_size = call->len;
        if (payload_size < sizeof(*call) + call_size)
            return -1;

        if (!service->ops->call)
            return 0;
        reply = calloc(payload_size, 1);
        if (!reply)
            return -1;

        ret = service->ops->call(service, call->type, payload + sizeof(*call), call_size,
                                 reply + sizeof(*call), call_size);
        if (ret) {
            free(reply);
            return ret;
        }

        memcpy(reply, call, sizeof(*call));

        size_t tx_size = sizeof(struct epic_hdr) + sizeof(struct epic_sub_hdr) + payload_size;
        void *msg = calloc(tx_size, 1);

        struct epic_hdr *hdr = msg;
        struct epic_sub_hdr *sub = msg + sizeof(struct epic_hdr);

        hdr->version = 2;
        hdr->seq = epic->seq++;

        sub->length = payload_size;
        sub->version = 4;
        sub->category = CAT_REPLY;
        sub->type = SUBTYPE_STD_SERVICE;
        sub->seq = sub_seq; // service->seq++;
        sub->flags = 0x08;
        sub->inline_len = payload_size - 4;

        memcpy(msg + sizeof(struct epic_hdr) + sizeof(struct epic_sub_hdr), reply, payload_size);

        afk_epic_tx(epic, channel, TYPE_NOTIFY_ACK, msg, tx_size);
        free(reply);
        free(msg);

        return 0;
    }

    dprintf("AFK: channel %d received unhandled standard service message: %x\n", channel, category);

    return -1;
}

int afk_epic_command(afk_epic_ep_t *epic, int channel, u16 sub_type, void *txbuf, size_t txsize,
                     void *rxbuf, size_t *rxsize)
{
    struct {
        struct epic_hdr hdr;
        struct epic_sub_hdr sub;
        struct epic_cmd cmd;
    } PACKED msg;

    assert(txsize <= epic->txbuf.sz);
    assert(!rxsize || *rxsize <= epic->rxbuf.sz);

    memset(&msg, 0, sizeof(msg));

    msg.hdr.version = 2;
    msg.hdr.seq = epic->seq++;
    msg.sub.length = sizeof(msg.cmd);
    msg.sub.version = 4;
    msg.sub.category = CAT_COMMAND;
    msg.sub.type = sub_type;
    msg.sub.seq = 0;
    msg.cmd.txbuf = epic->txbuf.dva;
    msg.cmd.txlen = txsize;
    msg.cmd.rxbuf = epic->rxbuf.dva;
    msg.cmd.rxlen = rxsize ? *rxsize : 0;

    memcpy(epic->txbuf.bfr, txbuf, txsize);

    int ret = afk_epic_tx(epic, channel, TYPE_COMMAND, &msg, sizeof msg);
    if (ret < 0) {
        printf("EPIC: failed to transmit command\n");
        return ret;
    }

    struct afk_qe *rmsg;
    struct epic_cmd *rcmd;

    while (true) {
        ret = afk_epic_work(epic->afk, epic->ep);
        if (ret < 0)
            return ret;
        else if (ret != EPIC_DATA_READY)
            continue;
        // will not block
        ret = afk_epic_rx(epic, &rmsg);
        if (ret < 0)
            return ret;

        if (rmsg->type != TYPE_REPLY && rmsg->type != TYPE_NOTIFY) {
            printf("EPIC: got unexpected message type %d during command\n", rmsg->type);
            afk_epic_rx_ack(epic);
            continue;
        }

        struct epic_hdr *hdr = (void *)(rmsg + 1);
        struct epic_sub_hdr *sub = (void *)(hdr + 1);

        if (sub->category == CAT_NOTIFY && sub->type == SUBTYPE_STD_SERVICE) {
            void *payload = rmsg->data + sizeof(struct epic_hdr) + sizeof(struct epic_sub_hdr);
            size_t payload_size =
                rmsg->size - sizeof(struct epic_hdr) - sizeof(struct epic_sub_hdr);
            afk_epic_rx_ack(epic);
            afk_epic_handle_std_service(epic, channel, sub->category, sub->seq, payload,
                                        payload_size);
            continue;
        } else if (sub->category != CAT_REPLY || sub->type != sub_type) {
            printf("EPIC: got unexpected message %02x:%04x during command\n", sub->category,
                   sub->type);
            afk_epic_rx_ack(epic);
            continue;
        }

        rcmd = (void *)(sub + 1);
        break;
    }

    if (rcmd->retcode != 0) {
        printf("EPIC: IOP returned 0x%x\n", rcmd->retcode);
        afk_epic_rx_ack(epic);
        return rcmd->retcode; // should be negative already
    }

    if (rxsize) {
        assert(*rxsize >= rcmd->rxlen);
        *rxsize = rcmd->rxlen;

        if (*rxsize && rcmd->rxbuf)
            memcpy(rxbuf, epic->rxbuf.bfr, *rxsize);
    }

    afk_epic_rx_ack(epic);

    return 0;
}

static void afk_epic_notify_handler(afk_epic_ep_t *epic)
{
    struct afk_qe *rmsg;
    // will not block
    int ret = afk_epic_rx(epic, &rmsg);
    if (ret < 0)
        return;

    if (rmsg->type != TYPE_NOTIFY) {
        dprintf("EPIC[0x%02x]: got unexpected message type %d in %s\n", epic->ep, rmsg->type,
                __func__);
        afk_epic_rx_ack(epic);
        return;
    }

    struct epic_hdr *hdr = (void *)(rmsg + 1);
    struct epic_sub_hdr *sub = (void *)(hdr + 1);

    if (sub->category == CAT_NOTIFY && sub->type == SUBTYPE_STD_SERVICE) {
        void *payload = rmsg->data + sizeof(struct epic_hdr) + sizeof(struct epic_sub_hdr);
        size_t payload_size = rmsg->size - sizeof(struct epic_hdr) - sizeof(struct epic_sub_hdr);
        afk_epic_handle_std_service(epic, rmsg->channel, sub->category, sub->seq, payload,
                                    payload_size);
    } else {
        dprintf("EPIC[0x%02x]: %s: rx: Ch %u, Type:0x%02x sub cat:%x type:%x \n", epic->ep,
                __func__, rmsg->channel, rmsg->type, sub->category, sub->type);
    }

    afk_epic_rx_ack(epic);
}

afk_epic_ep_t *afk_epic_start_ep(afk_epic_t *afk, int endpoint, const afk_epic_service_ops_t *ops,
                                 bool notify)
{
    afk_epic_ep_t *epic = malloc(sizeof(afk_epic_ep_t));
    if (!epic)
        return NULL;

    memset(epic, 0, sizeof(*epic));
    epic->ep = endpoint;
    epic->afk = afk;
    epic->ops = ops;
    afk->endpoint[endpoint - 0x20] = epic;

    if (notify)
        epic->recv_handler = afk_epic_notify_handler;

    if (!rtkit_start_ep(epic->afk->rtk, endpoint)) {
        printf("EPIC: failed to start endpoint %d\n", endpoint);
        goto err;
    }

    struct rtkit_message msg = {endpoint, FIELD_PREP(RBEP_TYPE, RBEP_INIT)};
    if (!rtkit_send(epic->afk->rtk, &msg)) {
        printf("EPIC: failed to send init message\n");
        goto err;
    }

    while (!epic->started) {
        int ret = afk_epic_poll(epic->afk, endpoint, true);
        if (ret < 0)
            break;
        else if (ret > 0)
            printf("EPIC: received unexpected message during init\n");
    }

    return epic;

err:
    afk->endpoint[endpoint - 0x20] = NULL;
    free(epic);
    return NULL;
}

int afk_epic_shutdown_ep(afk_epic_ep_t *epic)
{
    struct rtkit_message msg = {epic->ep, FIELD_PREP(RBEP_TYPE, RBEP_SHUTDOWN)};
    if (!rtkit_send(epic->afk->rtk, &msg)) {
        printf("EPIC: failed to send shutdown message\n");
        return -1;
    }

    while (epic->started) {
        int ret = afk_epic_poll(epic->afk, epic->ep, true);
        if (ret < 0)
            break;
    }

    rtkit_free_buffer(epic->afk->rtk, &epic->buf);
    rtkit_free_buffer(epic->afk->rtk, &epic->rxbuf);
    rtkit_free_buffer(epic->afk->rtk, &epic->txbuf);

    epic->afk->endpoint[epic->ep - 0x20] = NULL;

    free(epic);
    return 0;
}

static const afk_epic_service_ops_t *afk_match_service(afk_epic_ep_t *ep, const char *name)
{
    const afk_epic_service_ops_t *ops;

    if (!name[0])
        return NULL;
    if (!ep->ops)
        return NULL;

    for (ops = ep->ops; ops->name[0]; ops++) {
        if (strcmp(ops->name, name))
            continue;

        return ops;
    }

    return NULL;
}

int afk_epic_start_interface(afk_epic_ep_t *epic, void *intf, int expected, size_t txsize,
                             size_t rxsize)
{
    int services = 0;
    struct afk_qe *msg;
    struct epic_announce *announce;

    /* consume messages for other endpoints, syslog or ioreport might be noisy
     * at startup */
    while (1) {
        int ret = afk_epic_work(epic->afk, epic->ep);
        if (ret < 0)
            return ret;
        if (ret == EPIC_DATA_READY)
            break;
    }

    for (int tries = 0; tries < 500; tries += 1) {
        s64 epic_unit = -1;
        char *epic_name = NULL;
        char *epic_class = NULL;
        const char *service_name = NULL;

        int ret = afk_epic_work(epic->afk, epic->ep);
        if (ret < 0)
            return ret;
        else if (ret != EPIC_DATA_READY)
            continue;

        ret = afk_epic_rx(epic, &msg);
        if (ret < 0)
            return ret;

        if (msg->type != TYPE_NOTIFY && msg->type != TYPE_REPLY) {
            dprintf("AFK[ep:%02x]: got unexpected message type %d during iface start\n", epic->ep,
                    msg->type);
            afk_epic_rx_ack(epic);
            continue;
        }

        struct epic_hdr *hdr = (void *)(msg + 1);
        struct epic_sub_hdr *sub = (void *)(hdr + 1);

        if (sub->category != CAT_REPORT || sub->type != SUBTYPE_ANNOUNCE) {
            dprintf("AFK[ep:%02x]: got unexpected message %02x:%04x during iface start\n", epic->ep,
                    sub->category, sub->type);
            afk_epic_rx_ack(epic);
            continue;
        }

        if (epic->num_channels >= AFK_MAX_CHANNEL) {
            printf("AFK[ep:%02x]: Out of free service for service on channel %d\n", epic->ep,
                   msg->channel);
            afk_epic_rx_ack(epic);
            continue;
        }

        announce = (void *)(sub + 1);

        size_t props_size = sub->length - offsetof(struct epic_announce, props);

        if (props_size > 36) {
            struct dcp_parse_ctx ctx;

            int ret = parse(announce->props, props_size, &ctx);
            if (ret) {
                printf("AFK[ep:%02x]: Failed to parse service init props (len=%zu) for %s\n",
                       epic->ep, props_size, announce->name);
                afk_epic_rx_ack(epic);
                continue;
            }
            ret = parse_epic_service_init(&ctx, &epic_name, &epic_class, &epic_unit);
            if (ret) {
                printf("AFK[ep:%02x]: failed to extract init props (len=%zu): %d\n", epic->ep,
                       props_size, ret);
                hexdump(announce->props, props_size);
                afk_epic_rx_ack(epic);
                continue;
            }
            service_name = epic_class;
        } else {
            service_name = announce->name;
        }

        const afk_epic_service_ops_t *ops = afk_match_service(epic, service_name);
        if (!ops) {
            printf("AFK[ep:%02x]: unable to match service %s on channel %d\n", epic->ep,
                   service_name, msg->channel);
            afk_epic_rx_ack(epic);
            continue;
        }

        afk_epic_service_t *service = &epic->services[epic->num_channels++];
        service->enabled = true;
        service->ops = ops;
        service->intf = intf;
        service->epic = epic;
        service->channel = msg->channel;
        service->seq = 0;

        ops->init(service, epic_name, service_name, epic_unit);
        dprintf("AFK[ep:%02x]: new service %s on channel %d\n", epic->ep, service_name,
                msg->channel);
        free(epic_name);
        free(epic_class);

        afk_epic_rx_ack(epic);
        if (++services >= expected)
            break;
    }

    if (!services) {
        printf("AFK[ep:%02x]: too many unexpected messages, giving up\n", epic->ep);
        return -1;
    }

    if (!rtkit_alloc_buffer(epic->afk->rtk, &epic->rxbuf, rxsize)) {
        printf("AFK[ep:%02x]: failed to allocate rx buffer\n", epic->ep);
        return -1;
    }

    if (!rtkit_alloc_buffer(epic->afk->rtk, &epic->txbuf, txsize)) {
        printf("AFK[ep:%02x]: failed to allocate tx buffer\n", epic->ep);
        return -1;
    }

    dprintf("AFK[ep:%02x]: started interface with %d services\n", epic->ep, services);

    return 0;
}

afk_epic_t *afk_epic_init(rtkit_dev_t *rtkit)
{
    afk_epic_t *afk = calloc(sizeof(*afk), 1);

    if (!afk)
        return NULL;

    afk->rtk = rtkit;

    return afk;
}

int afk_epic_shutdown(afk_epic_t *afk)
{

    for (int i = 0; i < 0x10; i++)
        if (afk->endpoint[i])
            afk_epic_shutdown_ep(afk->endpoint[i]);

    free(afk);

    return 0;
}
