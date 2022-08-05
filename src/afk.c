/* SPDX-License-Identifier: MIT */

#include "afk.h"
#include "assert.h"
#include "malloc.h"
#include "string.h"
#include "utils.h"

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
    u32 rptr;
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

enum EPICMessage {
    CODE_ANNOUNCE = 0x30,
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
    u16 code;
    u64 timestamp;
    u16 seq;
    u16 unk;
    u32 unk2;
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
} PACKED;

struct afk_epic_ep {
    int ep;
    rtkit_dev_t *rtk;

    struct rtkit_buffer buf;
    u16 tag;

    struct afk_rb tx;
    struct afk_rb rx;

    struct rtkit_buffer txbuf;
    struct rtkit_buffer rxbuf;

    bool started;
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

static int afk_epic_poll(afk_epic_ep_t *epic)
{
    int ret;
    struct rtkit_message msg;

    while ((ret = rtkit_recv(epic->rtk, &msg)) == 0)
        ;

    if (ret < 0) {
        printf("EPIC: rtkit_recv failed!\n");
        return ret;
    }

    if (msg.ep != epic->ep) {
        printf("EPIC: received message for unexpected endpoint %d\n", msg.ep);
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
            if (!rtkit_alloc_buffer(epic->rtk, &epic->buf, size)) {
                printf("EPIC: failed to allocate buffer\n");
                return -1;
            }
            msg.msg = (FIELD_PREP(RBEP_TYPE, RBEP_GETBUF_ACK) |
                       FIELD_PREP(GETBUF_ACK_DVA, epic->buf.dva));
            if (!rtkit_send(epic->rtk, &msg)) {
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
                if (!rtkit_send(epic->rtk, &msg)) {
                    printf("EPIC: failed to send start\n");
                    return -1;
                }
            }
            break;

        case RBEP_RECV:
            return 1;

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
    int ret;
    struct afk_rb *rb = &epic->rx;

    u32 rptr = rb->hdr->rptr;

    while (rptr == rb->hdr->wptr) {
        do {
            ret = afk_epic_poll(epic);
            if (ret < 0)
                return ret;
        } while (ret == 0);
        dma_rmb();
    }

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

    if (wptr < rptr && (wptr + sizeof(struct afk_qe) > rptr)) {
        printf("EPIC: TX ring buffer is full\n");
        return -1;
    }

    hdr->magic = QE_MAGIC;
    hdr->channel = channel;
    hdr->type = type;
    hdr->size = size;

    wptr += sizeof(struct afk_qe);

    if (size > rb->bufsz - wptr) {
        if (rptr < sizeof(struct afk_qe)) {
            printf("EPIC: TX ring buffer is full\n");
            return -1;
        }
        *(struct afk_qe *)rb->buf = *hdr;
        hdr = rb->buf;
        wptr = sizeof(struct afk_qe);
    }

    if (wptr < rptr && (wptr + size > rptr)) {
        printf("EPIC: TX ring buffer is full\n");
        return -1;
    }

    wptr += size;
    wptr = ALIGN_UP(wptr, 1 << BLOCK_SHIFT);

    memcpy(hdr + 1, data, size);

    dma_mb();
    rb->hdr->wptr = wptr;
    dma_wmb();

    struct rtkit_message msg = {
        epic->ep,
        FIELD_PREP(RBEP_TYPE, RBEP_SEND) | FIELD_PREP(SEND_WPTR, wptr),
    };

    if (!rtkit_send(epic->rtk, &msg)) {
        printf("EPIC: failed to send TX WPTR message\n");
        return -1;
    }

    return 1;
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
    assert(rptr < rb->bufsz);
    if (rptr == rb->bufsz)
        rptr = 0;
    rb->hdr->rptr = rptr;
}

int afk_epic_command(afk_epic_ep_t *epic, int channel, u16 code, void *txbuf, size_t txsize,
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
    msg.hdr.seq = 0;
    msg.sub.length = sizeof(msg.cmd);
    msg.sub.version = 3;
    msg.sub.category = CAT_COMMAND;
    msg.sub.code = code;
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

        if (sub->category != CAT_REPLY || sub->code != code) {
            printf("EPIC: got unexpected message %02x:%04x during command\n", sub->category,
                   sub->code);
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

    assert(*rxsize >= rcmd->rxlen);
    *rxsize = rcmd->rxlen;

    if (rxsize && *rxsize && rcmd->rxbuf)
        memcpy(rxbuf, epic->rxbuf.bfr, *rxsize);

    afk_epic_rx_ack(epic);

    return 0;
}

afk_epic_ep_t *afk_epic_init(rtkit_dev_t *rtk, int endpoint)
{
    afk_epic_ep_t *epic = malloc(sizeof(afk_epic_ep_t));
    if (!epic)
        return NULL;

    memset(epic, 0, sizeof(*epic));
    epic->ep = endpoint;
    epic->rtk = rtk;

    if (!rtkit_start_ep(rtk, endpoint)) {
        printf("EPIC: failed to start endpoint %d\n", endpoint);
        goto err;
    }

    struct rtkit_message msg = {endpoint, FIELD_PREP(RBEP_TYPE, RBEP_INIT)};
    if (!rtkit_send(rtk, &msg)) {
        printf("EPIC: failed to send init message\n");
        goto err;
    }

    while (!epic->started) {
        int ret = afk_epic_poll(epic);
        if (ret < 0)
            break;
        else if (ret > 0)
            printf("EPIC: received unexpected message during init\n");
    }

    return epic;

err:
    free(epic);
    return NULL;
}

int afk_epic_shutdown(afk_epic_ep_t *epic)
{
    struct rtkit_message msg = {epic->ep, FIELD_PREP(RBEP_TYPE, RBEP_SHUTDOWN)};
    if (!rtkit_send(epic->rtk, &msg)) {
        printf("EPIC: failed to send shutdown message\n");
        return -1;
    }

    while (epic->started) {
        int ret = afk_epic_poll(epic);
        if (ret < 0)
            break;
    }

    rtkit_free_buffer(epic->rtk, &epic->buf);
    rtkit_free_buffer(epic->rtk, &epic->rxbuf);
    rtkit_free_buffer(epic->rtk, &epic->txbuf);

    free(epic);
    return 0;
}

int afk_epic_start_interface(afk_epic_ep_t *epic, char *name, size_t txsize, size_t rxsize)
{
    int channel = -1;
    struct afk_qe *msg;
    struct epic_announce *announce;

    for (int tries = 0; tries < 20; tries += 1) {

        int ret = afk_epic_rx(epic, &msg);
        if (ret < 0)
            return ret;

        if (msg->type != TYPE_NOTIFY) {
            printf("EPIC: got unexpected message type %d during iface start\n", msg->type);
            afk_epic_rx_ack(epic);
            continue;
        }

        struct epic_hdr *hdr = (void *)(msg + 1);
        struct epic_sub_hdr *sub = (void *)(hdr + 1);

        if (sub->category != CAT_REPORT || sub->code != CODE_ANNOUNCE) {
            printf("EPIC: got unexpected message %02x:%04x during iface start\n", sub->category,
                   sub->code);
            afk_epic_rx_ack(epic);
            continue;
        }

        announce = (void *)(sub + 1);

        if (strncmp(name, announce->name, sizeof(announce->name))) {
            printf("EPIC: ignoring channel %d: %s\n", msg->channel, announce->name);
            afk_epic_rx_ack(epic);
            continue;
        }

        channel = msg->channel;
        break;
    }

    if (channel == -1) {
        printf("EPIC: too many unexpected messages, giving up\n");
        return -1;
    }

    if (!rtkit_alloc_buffer(epic->rtk, &epic->rxbuf, rxsize)) {
        printf("EPIC: failed to allocate rx buffer\n");
        return -1;
    }

    if (!rtkit_alloc_buffer(epic->rtk, &epic->txbuf, txsize)) {
        printf("EPIC: failed to allocate tx buffer\n");
        return -1;
    }

    printf("EPIC: started interface %d (%s)\n", msg->channel, announce->name);

    afk_epic_rx_ack(epic);

    return channel;
}
