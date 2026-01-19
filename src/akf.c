/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "akf.h"
#include "malloc.h"
#include "string.h"
#include "utils.h"

// seperated from asc due to different message format
// CPU start stop: The relvant registers do exist however it is inconsistent
// across peripherals. Since it is unlikely that anything other than SEP
// would be dealt with here it's best to leave start/stop registers alone.

#define AKF_V1_OFF 0x1000
#define AKF_V2_OFF 0x4000

#define AKF_MBOX_CONTROL_FULL  BIT(16)
#define AKF_MBOX_CONTROL_EMPTY BIT(17)

#define AKF_MBOX_SET 0x0
#define AKF_MBOX_CLR 0x4

#define AKF_MBOX_A2I_CONTROL 0x8
#define AKF_MBOX_A2I_SEND0   0x10
#define AKF_MBOX_A2I_SEND1   0x14
#define AKF_MBOX_A2I_RECV0   0x18
#define AKF_MBOX_A2I_RECV1   0x1c

#define AKF_MBOX_I2A_CONTROL 0x20
#define AKF_MBOX_I2A_SEND0   0x30
#define AKF_MBOX_I2A_SEND1   0x34
#define AKF_MBOX_I2A_RECV0   0x38
#define AKF_MBOX_I2A_RECV1   0x3c

struct akf_dev {
    uintptr_t base;
    int iop_node;
};

akf_dev_t *akf_init(const char *path)
{
    int akf_path[8];
    int node = adt_path_offset_trace(adt, path, akf_path);
    if (node < 0) {
        printf("akf: Error getting akf node %s\n", path);
        return NULL;
    }

    u64 base;
    if (adt_get_reg(adt, akf_path, "reg", 0, &base, NULL) < 0) {
        printf("akf: Error getting akf %s base address.\n", path);
        return NULL;
    }

    akf_dev_t *akf = calloc(1, sizeof(*akf));
    if (!akf)
        return NULL;

    if (adt_is_compatible(adt, node, "iop,s5l8960x")) {
        akf->base = base + AKF_V1_OFF;
    } else if (adt_is_compatible(adt, node, "iop,s8000")) {
        akf->base = base + AKF_V2_OFF;
    } else {
        printf("akf: Unsupported compatible\n");
        goto out_free;
    }

    akf->iop_node = node;

    return akf;

out_free:
    free(akf);
    return NULL;
}

void akf_free(akf_dev_t *akf)
{
    free(akf);
}

int akf_get_iop_node(akf_dev_t *akf)
{
    return akf->iop_node;
}

bool akf_can_recv(akf_dev_t *akf)
{
    return !(read32(akf->base + AKF_MBOX_I2A_CONTROL) & AKF_MBOX_CONTROL_EMPTY);
}

bool akf_recv(akf_dev_t *akf, struct akf_message *msg)
{
    if (!akf_can_recv(akf))
        return false;

    msg->msg0 = read32(akf->base + AKF_MBOX_I2A_RECV0);
    msg->msg1 = read32(akf->base + AKF_MBOX_I2A_RECV1);
    dma_rmb();

    return true;
}

bool akf_recv_timeout(akf_dev_t *akf, struct akf_message *msg, u32 delay_usec)
{
    u64 timeout = timeout_calculate(delay_usec);
    while (!timeout_expired(timeout)) {
        if (akf_recv(akf, msg))
            return true;
    }
    return false;
}

bool akf_can_send(akf_dev_t *akf)
{
    return !(read32(akf->base + AKF_MBOX_A2I_CONTROL) & AKF_MBOX_CONTROL_FULL);
}

bool akf_send(akf_dev_t *akf, const struct akf_message *msg)
{
    if (poll32(akf->base + AKF_MBOX_A2I_CONTROL, AKF_MBOX_CONTROL_FULL, 0, 200000)) {
        printf("akf: A2I mailbox full for 200ms. Is the akf stuck?");
        return false;
    }

    dma_wmb();
    write32(akf->base + AKF_MBOX_A2I_SEND0, msg->msg0);
    write32(akf->base + AKF_MBOX_A2I_SEND1, msg->msg1);

    return true;
}
