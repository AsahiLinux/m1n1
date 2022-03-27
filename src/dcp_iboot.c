/* SPDX-License-Identifier: MIT */

#include "dcp_iboot.h"
#include "afk.h"
#include "assert.h"
#include "malloc.h"
#include "string.h"
#include "utils.h"

#define DCP_IBOOT_ENDPOINT 0x23

#define TXBUF_LEN 0x4000
#define RXBUF_LEN 0x4000

struct txcmd {
    u32 op;
    u32 len;
    u32 unk1;
    u32 unk2;
    u8 payload[];
};

struct rxcmd {
    u32 op;
    u32 len;
    u8 payload[];
};

struct dcp_iboot_if {
    dcp_dev_t *dcp;
    afk_epic_ep_t *epic;
    int channel;

    union {
        u8 txbuf[TXBUF_LEN];
        struct txcmd txcmd;
    };

    union {
        u8 rxbuf[RXBUF_LEN];
        struct rxcmd rxcmd;
    };
};

enum IBootCmd {
    IBOOT_SET_POWER = 2,
    IBOOT_GET_HPD = 3,
    IBOOT_GET_TIMING_MODES = 4,
    IBOOT_GET_COLOR_MODES = 5,
    IBOOT_SET_MODE = 6,
    IBOOT_SWAP_BEGIN = 15,
    IBOOT_SWAP_SET_LAYER = 16,
    IBOOT_SWAP_END = 18,
};

struct get_hpd_resp {
    u8 hpd;
    u8 pad[3];
    u32 timing_cnt;
    u32 color_cnt;
};

struct get_tmode_resp {
    u32 count;
    dcp_timing_mode_t modes[];
};

struct get_cmode_resp {
    u32 count;
    dcp_color_mode_t modes[];
};

struct swap_start_resp {
    u32 unk1, unk2, unk3;
    u32 swap_id;
    u32 unk4;
};

struct swap_set_layer_cmd {
    u32 unk;
    u32 layer_id;
    dcp_layer_t layer;
    dcp_rect_t src;
    dcp_rect_t dst;
    u32 unk2;
} PACKED;

dcp_iboot_if_t *dcp_ib_init(dcp_dev_t *dcp)
{
    dcp_iboot_if_t *iboot = malloc(sizeof(dcp_iboot_if_t));
    if (!iboot)
        return NULL;

    iboot->dcp = dcp;
    iboot->epic = afk_epic_init(dcp->rtkit, DCP_IBOOT_ENDPOINT);
    if (!iboot->epic) {
        printf("dcp-iboot: failed to initialize EPIC\n");
        goto err_free;
    }

    iboot->channel = afk_epic_start_interface(iboot->epic, "disp0-service", TXBUF_LEN, RXBUF_LEN);

    if (iboot->channel < 0) {
        printf("dcp-iboot: failed to initialize disp0 service\n");
        goto err_shutdown;
    }

    return iboot;

err_shutdown:
    afk_epic_shutdown(iboot->epic);
err_free:
    free(iboot);
    return NULL;
}

int dcp_ib_shutdown(dcp_iboot_if_t *iboot)
{
    afk_epic_shutdown(iboot->epic);

    free(iboot);
    return 0;
}

static int dcp_ib_cmd(dcp_iboot_if_t *iboot, int op, size_t in_size)
{
    size_t rxsize = RXBUF_LEN;
    assert(in_size <= TXBUF_LEN - sizeof(struct txcmd));

    iboot->txcmd.op = op;
    iboot->txcmd.len = sizeof(struct txcmd) + in_size;

    return afk_epic_command(iboot->epic, iboot->channel, 0xc0, iboot->txbuf,
                            sizeof(struct txcmd) + in_size, iboot->rxbuf, &rxsize);
}

int dcp_ib_set_power(dcp_iboot_if_t *iboot, bool power)
{
    u32 *pwr = (void *)iboot->txcmd.payload;
    *pwr = power;

    return dcp_ib_cmd(iboot, IBOOT_SET_POWER, 1);
}

int dcp_ib_get_hpd(dcp_iboot_if_t *iboot, int *timing_cnt, int *color_cnt)
{
    struct get_hpd_resp *resp = (void *)iboot->rxcmd.payload;
    int ret = dcp_ib_cmd(iboot, IBOOT_GET_HPD, 0);

    if (ret < 0)
        return ret;

    if (timing_cnt)
        *timing_cnt = resp->timing_cnt;
    if (color_cnt)
        *color_cnt = resp->color_cnt;

    return !!resp->hpd;
}

int dcp_ib_get_timing_modes(dcp_iboot_if_t *iboot, dcp_timing_mode_t **modes)
{
    struct get_tmode_resp *resp = (void *)iboot->rxcmd.payload;
    int ret = dcp_ib_cmd(iboot, IBOOT_GET_TIMING_MODES, 0);

    if (ret < 0)
        return ret;

    *modes = resp->modes;
    return resp->count;
}

int dcp_ib_get_color_modes(dcp_iboot_if_t *iboot, dcp_color_mode_t **modes)
{
    struct get_cmode_resp *resp = (void *)iboot->rxcmd.payload;
    int ret = dcp_ib_cmd(iboot, IBOOT_GET_COLOR_MODES, 0);

    if (ret < 0)
        return ret;

    *modes = resp->modes;
    return resp->count;
}

int dcp_ib_set_mode(dcp_iboot_if_t *iboot, dcp_timing_mode_t *tmode, dcp_color_mode_t *cmode)
{
    struct {
        dcp_timing_mode_t tmode;
        dcp_color_mode_t cmode;
    } *cmd = (void *)iboot->txcmd.payload;

    cmd->tmode = *tmode;
    cmd->cmode = *cmode;
    return dcp_ib_cmd(iboot, IBOOT_SET_MODE, sizeof(*cmd));
}

int dcp_ib_swap_begin(dcp_iboot_if_t *iboot)
{
    struct swap_start_resp *resp = (void *)iboot->rxcmd.payload;
    int ret = dcp_ib_cmd(iboot, IBOOT_SWAP_BEGIN, 0);
    if (ret < 0)
        return ret;

    return resp->swap_id;
}

int dcp_ib_swap_set_layer(dcp_iboot_if_t *iboot, int layer_id, dcp_layer_t *layer,
                          dcp_rect_t *src_rect, dcp_rect_t *dst_rect)
{
    struct swap_set_layer_cmd *cmd = (void *)iboot->txcmd.payload;
    memset(cmd, 0, sizeof(*cmd));
    cmd->layer_id = layer_id;
    cmd->layer = *layer;
    cmd->src = *src_rect;
    cmd->dst = *dst_rect;

    return dcp_ib_cmd(iboot, IBOOT_SWAP_SET_LAYER, sizeof(*cmd));
}

int dcp_ib_swap_end(dcp_iboot_if_t *iboot)
{
    memset(iboot->txcmd.payload, 0, 12);
    return dcp_ib_cmd(iboot, IBOOT_SWAP_END, 12);
}
