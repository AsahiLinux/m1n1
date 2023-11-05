/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "aic.h"
#include "iodev.h"
#include "malloc.h"

#define MAGIC          0x000
#define VERSION        0x004
#define DEVID          0x008
#define VENDID         0x00c
#define FEAT_HOST      0x010
#define FEAT_HOST_SEL  0x014
#define FEAT_GUEST     0x020
#define FEAT_GUEST_SEL 0x024

#define QSEL    0x030
#define QMAX    0x034
#define QSIZE   0x038
#define QREADY  0x044
#define QNOTIFY 0x050

#define QDESC      0x080
#define QGUESTAREA 0x090
#define QHOSTAREA  0x0a0

#define IRQ_STATUS  0x060
#define USED_BUFFER BIT(0)
#define CFG_CHANGE  BIT(1)
#define IRQ_ACK     0x064
#define DEV_STATUS  0x070

#define DESC_NEXT  BIT(0)
#define DESC_WRITE BIT(1)

struct availring {
    u16 flags;
    u16 idx;
    u16 ring[];
};

struct usedring {
    u16 flags;
    u16 idx;
    struct {
        u32 id;
        u32 len;
    } ring[];
};

struct desc {
    u64 addr;
    u32 len;
    u16 flags;
    u16 id;
};

struct virtio_q {
    struct virtio_dev *host;
    int idx;
    u32 max;
    u32 size;
    bool ready;
    struct desc *desc;

    u16 avail_seen;
    struct availring *avail;
    struct usedring *used;

    u64 area_regs[(QHOSTAREA + 8 - QDESC) / 4];
};

struct virtio_conf {
    s32 irq;
    u32 devid;
    u64 feats;
    u32 num_qus;
    void *config;
    u64 config_len;
    u8 verbose;
} PACKED;

struct virtio_dev {
    struct virtio_dev *next;
    u64 base;
    int irq;
    int num_qus;
    u32 devid;
    u64 feats;
    uint8_t *config;
    size_t config_len;
    bool verbose;

    u32 feat_host_sel;
    u32 status;
    u32 irqstatus;

    struct virtio_q *currq;
    struct virtio_q qs[];
};

static struct virtio_dev *devlist;

static void notify_avail(struct exc_info *ctx, struct virtio_q *q, int idx)
{
    struct desc *d = &q->desc[idx];
    struct {
        u64 devbase;
        u16 qu;
        u16 idx;
        u32 pad;
        u64 descbase;
    } PACKED info = {
        q->host->base, q->idx, idx, 0, (u64)q->desc,
    };

    if (q->host->verbose)
        printf("virtio @ %lx: available %s buffer at %lx, size %x, flags %x\n", q->host->base,
               (d->flags & DESC_WRITE) ? "device" : "driver", d->addr, d->len, d->flags);

    hv_exc_proxy(ctx, START_HV, HV_VIRTIO, &info);
}

static void notify_buffers(struct exc_info *ctx, struct virtio_dev *dev, u32 qidx)
{
    struct virtio_q *q = &dev->qs[qidx];
    struct availring *avail = q->avail;

    if (qidx >= (u32)dev->num_qus)
        return;

    for (; avail->idx != q->avail_seen; q->avail_seen++)
        notify_avail(ctx, q, avail->ring[q->avail_seen % q->size]);
}

static struct virtio_dev *dev_by_base(u64 base)
{
    struct virtio_dev *dev;

    for (dev = devlist; dev; dev = dev->next)
        if (dev->base == base)
            break;

    return dev;
}

void virtio_put_buffer(u64 base, int qu, u32 id, u32 len)
{
    struct virtio_dev *dev = dev_by_base(base);
    struct virtio_q *q;
    struct usedring *used;

    if (!dev) {
        printf("virtio_put_buffer: no device at %lx\n", base);
        return;
    }

    q = &dev->qs[qu];
    used = q->used;

    used->ring[used->idx % q->size].id = id;
    used->ring[used->idx % q->size].len = len;
    used->idx++;

    dev->irqstatus |= USED_BUFFER;
    aic_set_sw(dev->irq, true);
}

static bool handle_virtio(struct exc_info *ctx, u64 addr, u64 *val, bool write, int width)
{
    struct virtio_dev *dev;
    struct virtio_q *q;
    UNUSED(ctx);
    UNUSED(width);

    dev = dev_by_base(addr & ~0xfff);
    if (!dev)
        return false;

    addr &= 0xfff;

    if (write) {
        if (dev->verbose)
            printf("virtio @ %lx: W 0x%lx <- 0x%lx (%d)\n", dev->base, addr, *val, width);

        switch (addr) {
            case DEV_STATUS:
                dev->status = *val;
                break;
            case QSEL:
                if (((int)*val) <= dev->num_qus)
                    dev->currq = &dev->qs[*val];
                else
                    dev->currq = NULL;
                break;
            case QNOTIFY:
                notify_buffers(ctx, dev, *val);
                break;
            case FEAT_HOST_SEL:
                dev->feat_host_sel = *val;
                break;
            case IRQ_ACK:
                dev->irqstatus &= ~(*val);
                if (!dev->irqstatus)
                    aic_set_sw(dev->irq, false);
                break;
        }

        q = dev->currq;
        if (!q)
            return true;

        switch (addr) {
            case QSIZE:
                q->size = *val;
                break;
            case QREADY:
                q->ready = *val & 1;
                break;
            case QDESC ... QHOSTAREA + 4:
                addr -= QDESC;
                addr /= 4;
                q->area_regs[addr] = *val;

                q->desc = (void *)(q->area_regs[1] << 32 | q->area_regs[0]);
                q->avail = (void *)(q->area_regs[5] << 32 | q->area_regs[4]);
                q->used = (void *)(q->area_regs[9] << 32 | q->area_regs[8]);
                break;
        }
    } else {
        switch (addr) {
            case MAGIC:
                *val = 0x74726976;
                break;
            case VERSION:
                *val = 2;
                break;
            case DEVID:
                *val = dev->devid;
                break;
            case DEV_STATUS:
                *val = dev->status;
                break;
            case FEAT_HOST:
                *val = dev->feats >> (dev->feat_host_sel * 32);
                break;
            case IRQ_STATUS:
                *val = dev->irqstatus;
                break;
            case 0x100 ... 0x1000:
                if (addr - 0x100 < dev->config_len)
                    *val = dev->config[addr - 0x100];
                else
                    *val = 0;
                break;
            default:
                q = dev->currq;
                if (!q) {
                    *val = 0;
                    goto rdone;
                }
        }

        switch (addr) {
            case QMAX:
                *val = q->max;
                break;
            case QREADY:
                *val = q->ready;
                break;
        }
    rdone:
        if (dev->verbose)
            printf("virtio @ %lx: R 0x%lx -> 0x%lx (%d)\n", dev->base, addr, *val, width);
    };

    return true;
}

void hv_map_virtio(u64 base, struct virtio_conf *conf)
{
    struct virtio_dev *dev;
    int i;

    dev = calloc(1, sizeof(*dev) + sizeof(struct virtio_q) * conf->num_qus);
    dev->num_qus = conf->num_qus;
    dev->base = base;
    dev->irq = conf->irq;
    dev->devid = conf->devid;
    dev->currq = NULL;
    dev->feats = conf->feats | BIT(32); /* always set: VIRTIO_F_VERSION_1 */
    dev->config = conf->config;
    dev->config_len = conf->config_len;
    dev->verbose = conf->verbose;
    for (i = 0; i < dev->num_qus; i++) {
        dev->qs[i].host = dev;
        dev->qs[i].idx = i;
        dev->qs[i].max = 256;
        dev->qs[i].avail_seen = 0;
        dev->qs[i].ready = 0;
    }

    if (devlist)
        dev->next = devlist;
    devlist = dev;

    hv_map_hook(base, handle_virtio, 0x1000);
}
