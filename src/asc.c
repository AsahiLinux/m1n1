/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "asc.h"
#include "malloc.h"
#include "utils.h"

#define ASC_CPU_CONTROL       0x44
#define ASC_CPU_CONTROL_START 0x10

#define ASC_MBOX_CONTROL_FULL  BIT(16)
#define ASC_MBOX_CONTROL_EMPTY BIT(17)

#define ASC_MBOX_A2I_CONTROL 0x110
#define ASC_MBOX_A2I_SEND0   0x800
#define ASC_MBOX_A2I_SEND1   0x808
#define ASC_MBOX_A2I_RECV0   0x810
#define ASC_MBOX_A2I_RECV1   0x818

#define ASC_MBOX_I2A_CONTROL 0x114
#define ASC_MBOX_I2A_SEND0   0x820
#define ASC_MBOX_I2A_SEND1   0x828
#define ASC_MBOX_I2A_RECV0   0x830
#define ASC_MBOX_I2A_RECV1   0x838

#define ASC_MBOX_A2I_CONTROL_T8015 0x108
#define ASC_MBOX_I2A_CONTROL_T8015 0x10c

#define ASC_CPU_CONTROL_T8015       0x0
#define ASC_CPU_CONTROL_START_T8015 0x1

struct asc_ops {
    bool (*send)(asc_dev_t *asc, const struct asc_message *msg);
    bool (*recv)(asc_dev_t *asc, struct asc_message *msg);
    bool (*can_recv)(asc_dev_t *asc);
    bool (*can_send)(asc_dev_t *asc);
    void (*cpu_start)(asc_dev_t *asc);
    void (*cpu_stop)(asc_dev_t *asc);
    bool (*cpu_running)(asc_dev_t *asc);
};

struct asc_dev {
    uintptr_t cpu_base;
    uintptr_t base;
    const struct asc_ops *ops;
    int iop_node;
};

static void ascwrap_v4_cpu_start(asc_dev_t *asc)
{
    set32(asc->cpu_base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);
}

static void ascwrap_v4_cpu_stop(asc_dev_t *asc)
{
    clear32(asc->cpu_base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);
}

static bool ascwrap_v4_cpu_running(asc_dev_t *asc)
{
    return read32(asc->cpu_base + ASC_CPU_CONTROL) & ASC_CPU_CONTROL_START;
}

static bool ascwrap_v4_send(asc_dev_t *asc, const struct asc_message *msg)
{
    bool can_send = false;
    u64 timeout = timeout_calculate(200000);
    while (!timeout_expired(timeout))
        if ((can_send = asc_can_send(asc)))
            break;

    if (!can_send) {
        printf("asc: A2I mailbox full for 200ms. Is the ASC stuck?");
        return false;
    }

    dma_wmb();
    write64(asc->base + ASC_MBOX_A2I_SEND0, msg->msg0);
    write64(asc->base + ASC_MBOX_A2I_SEND1, msg->msg1);

    // printf("sent msg: %lx %x\n", msg->msg0, msg->msg1);
    return true;
}

static bool ascwrap_v4_recv(asc_dev_t *asc, struct asc_message *msg)
{
    if (!asc_can_recv(asc))
        return false;

    msg->msg0 = read64(asc->base + ASC_MBOX_I2A_RECV0);
    msg->msg1 = (u32)read64(asc->base + ASC_MBOX_I2A_RECV1);
    dma_rmb();

    // printf("received msg: %lx %x\n", msg->msg0, msg->msg1);

    return true;
}

static bool ascwrap_v4_can_recv(asc_dev_t *asc)
{
    return !(read32(asc->base + ASC_MBOX_I2A_CONTROL) & ASC_MBOX_CONTROL_EMPTY);
}

static bool ascwrap_v4_can_send(asc_dev_t *asc)
{
    return !(read32(asc->base + ASC_MBOX_A2I_CONTROL) & ASC_MBOX_CONTROL_FULL);
}

const struct asc_ops ascwrap_v4_ops = {
    .send = &ascwrap_v4_send,
    .recv = &ascwrap_v4_recv,
    .can_send = &ascwrap_v4_can_send,
    .can_recv = &ascwrap_v4_can_recv,
    .cpu_start = &ascwrap_v4_cpu_start,
    .cpu_stop = &ascwrap_v4_cpu_stop,
    .cpu_running = &ascwrap_v4_cpu_running,
};

static bool t8015_can_recv(asc_dev_t *asc)
{
    return !(read32(asc->base + ASC_MBOX_I2A_CONTROL_T8015) & ASC_MBOX_CONTROL_EMPTY);
}

static bool t8015_can_send(asc_dev_t *asc)
{
    return !(read32(asc->base + ASC_MBOX_A2I_CONTROL_T8015) & ASC_MBOX_CONTROL_FULL);
}

const struct asc_ops t8015_ans2_ops = {
    .send = &ascwrap_v4_send,
    .recv = &ascwrap_v4_recv,
    .can_send = &t8015_can_send,
    .can_recv = &t8015_can_recv,
    .cpu_start = &ascwrap_v4_cpu_start,
    .cpu_stop = &ascwrap_v4_cpu_stop,
    .cpu_running = &ascwrap_v4_cpu_running,
};

static bool t8015_cpu_running(asc_dev_t *asc)
{
    if (!asc->cpu_base)
        return true;

    return read32(asc->cpu_base + ASC_CPU_CONTROL_T8015) & ASC_CPU_CONTROL_START_T8015;
}

static void t8015_cpu_start(asc_dev_t *asc)
{
    if (!asc->cpu_base)
        return;

    set32(asc->cpu_base + ASC_CPU_CONTROL_T8015, ASC_CPU_CONTROL_START_T8015);
}

static void t8015_cpu_stop(asc_dev_t *asc)
{
    if (!asc->cpu_base)
        return;

    clear32(asc->cpu_base + ASC_CPU_CONTROL_T8015, ASC_CPU_CONTROL_START_T8015);
}

const struct asc_ops t8015_ops = {
    .send = &ascwrap_v4_send,
    .recv = &ascwrap_v4_recv,
    .can_send = &t8015_can_send,
    .can_recv = &t8015_can_recv,
    .cpu_start = &t8015_cpu_start,
    .cpu_stop = &t8015_cpu_stop,
    .cpu_running = &t8015_cpu_running,
};

asc_dev_t *asc_init(const char *path)
{
    int asc_path[8];
    int node = adt_path_offset_trace(adt, path, asc_path);
    if (node < 0) {
        printf("asc: Error getting ASC node %s\n", path);
        return NULL;
    }

    u64 base;
    if (adt_get_reg(adt, asc_path, "reg", 0, &base, NULL) < 0) {
        printf("asc: Error getting ASC %s base address.\n", path);
        return NULL;
    }

    asc_dev_t *asc = calloc(1, sizeof(*asc));
    if (!asc)
        return NULL;

    if (adt_is_compatible(adt, node, "iop-pmp,t8015") ||
        adt_is_compatible(adt, node, "iop,t8015")) {
        // there is also a iop-gfx,t8015 but how that works is unknown
        asc->base = base + 0x8000;
        asc->ops = &t8015_ops;

        if (adt_get_reg(adt, asc_path, "reg", 2, (u64 *)&asc->cpu_base, NULL) < 0)
            asc->cpu_base = 0;

    } else if (adt_is_compatible(adt, node, "iop-ans2,t8015")) {
        asc->base = base + 0x8000;
        asc->ops = &t8015_ans2_ops;

        if (adt_get_reg(adt, asc_path, "reg", 1, (u64 *)&asc->cpu_base, NULL) < 0) {
            printf("asc: Error getting T8015 ANS2 %s CPU base address.\n", path);
            goto out_free;
        }
    } else if (adt_is_compatible(adt, node, "iop,ascwrap-v4") ||
               adt_is_compatible(adt, node, "iop-sep,ascwrap-v4")) {
        asc->cpu_base = base;
        asc->base = base + 0x8000;
        asc->ops = &ascwrap_v4_ops;
    } else {
        printf("asc: Unsupported compatible\n");
        goto out_free;
    }

    asc->iop_node = adt_first_child_offset(adt, node);

    return asc;

out_free:
    free(asc);
    return NULL;
}

void asc_free(asc_dev_t *asc)
{
    free(asc);
}

int asc_get_iop_node(asc_dev_t *asc)
{
    return asc->iop_node;
}

void asc_cpu_start(asc_dev_t *asc)
{
    asc->ops->cpu_start(asc);
}

void asc_cpu_stop(asc_dev_t *asc)
{
    asc->ops->cpu_stop(asc);
}

bool asc_cpu_running(asc_dev_t *asc)
{
    return asc->ops->cpu_running(asc);
}

bool asc_can_recv(asc_dev_t *asc)
{
    return asc->ops->can_recv(asc);
}

bool asc_recv(asc_dev_t *asc, struct asc_message *msg)
{
    return asc->ops->recv(asc, msg);
}

bool asc_recv_timeout(asc_dev_t *asc, struct asc_message *msg, u32 delay_usec)
{
    u64 timeout = timeout_calculate(delay_usec);
    while (!timeout_expired(timeout)) {
        if (asc_recv(asc, msg))
            return true;
    }
    return false;
}

bool asc_can_send(asc_dev_t *asc)
{
    return asc->ops->can_send(asc);
}

bool asc_send(asc_dev_t *asc, const struct asc_message *msg)
{
    return asc->ops->send(asc, msg);
}
