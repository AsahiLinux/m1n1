// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2022 Sven Peter <sven@svenpeter.dev> */

#include <stdbool.h>
#include <string.h>

#include "dptx_port_ep.h"
#include "dptx_phy.h"
#include "malloc.h"

#include "../afk.h"
#include "../dcp.h"
#include "../types.h"
#include "../utils.h"

#define DCP_DPTX_PORT_ENDPOINT 0x2a

#define TXBUF_LEN 0x4000
#define RXBUF_LEN 0x4000

struct dcpdptx_connection_cmd {
    u32 unk;
    u32 target;
} __attribute__((packed));

struct dcpdptx_hotplug_cmd {
    u8 _pad0[16];
    u32 unk;
} __attribute__((packed));

struct dptxport_apcall_link_rate {
    u32 retcode;
    u8 _unk0[12];
    u32 link_rate;
    u8 _unk1[12];
} __attribute__((packed));

struct dptxport_apcall_lane_count {
    u32 retcode;
    u8 _unk0[12];
    u64 lane_count;
    u8 _unk1[8];
} __attribute__((packed));

struct dptxport_apcall_set_active_lane_count {
    u32 retcode;
    u8 _unk0[12];
    u64 lane_count;
    u8 _unk1[8];
} __attribute__((packed));

struct dptxport_apcall_get_support {
    u32 retcode;
    u8 _unk0[12];
    u32 supported;
    u8 _unk1[12];
} __attribute__((packed));

struct dptxport_apcall_max_drive_settings {
    u32 retcode;
    u8 _unk0[12];
    u32 max_drive_settings[2];
    u8 _unk1[8];
} __attribute__((packed));

struct dptxport_apcall_set_tiled {
    u32 retcode;
};

struct epic_service_call {
    u8 _pad0[2];
    u16 group;
    u32 command;
    u32 data_len;
#define EPIC_SERVICE_CALL_MAGIC 0x69706378
    u32 magic;
    u8 _pad1[48];
} __attribute__((packed));

typedef struct dptx_port {
    bool enabled;
    u32 unit;
    afk_epic_service_t *service;
    dptx_phy_t *phy;
    u32 link_rate, pending_link_rate;
} dptx_port_t;

typedef struct dcp_dptx_if {
    afk_epic_ep_t *epic;
    dcp_dev_t *dcp;
    dptx_phy_t *phy;

    struct dptx_port port[2];
} dcp_dptx_if_t;

static int afk_service_call(afk_epic_service_t *service, u16 group, u32 command, const void *data,
                            size_t data_len, size_t data_pad, void *output, size_t output_len,
                            size_t output_pad)
{
    struct epic_service_call *call;
    void *bfr;
    size_t bfr_len = max(data_len + data_pad, output_len + output_pad) + sizeof(*call);
    int ret;
    u32 retlen;
    size_t rx_len = bfr_len;

    bfr = calloc(bfr_len, 1);
    if (!bfr)
        return -1;

    call = bfr;
    call->group = group;
    call->command = command;
    call->data_len = data_len + data_pad;
    call->magic = EPIC_SERVICE_CALL_MAGIC;

    memcpy(bfr + sizeof(*call), data, data_len);

    ret = afk_epic_command(service->epic, service->channel, SUBTYPE_STD_SERVICE, bfr, bfr_len, bfr,
                           &rx_len);
    if (ret)
        goto out;

    if (call->magic != EPIC_SERVICE_CALL_MAGIC || call->group != group ||
        call->command != command) {
        ret = -1;
        goto out;
    }

    retlen = call->data_len;
    if (output_len < retlen)
        retlen = output_len;
    if (output && output_len) {
        memset(output, 0, output_len);
        memcpy(output, bfr + sizeof(*call), retlen);
    }

out:
    free(bfr);
    return ret;
}

int dptxport_validate_connection(afk_epic_service_t *service, u8 core, u8 atc, u8 die)
{
    struct dcpdptx_connection_cmd cmd, resp;
    int ret;
    u32 target = FIELD_PREP(DCPDPTX_REMOTE_PORT_CORE, core) |
                 FIELD_PREP(DCPDPTX_REMOTE_PORT_DFP, atc) |
                 FIELD_PREP(DCPDPTX_REMOTE_PORT_DIE, die) | DCPDPTX_REMOTE_PORT_CONNECTED;

    cmd.target = target;
    cmd.unk = 0x100;
    ret = afk_service_call(service, 0, 12, &cmd, sizeof(cmd), 40, &resp, sizeof(resp), 40);
    if (ret)
        return ret;

    if (resp.target != target)
        return -1;
    if (resp.unk != 0x100)
        return -1;

    return 0;
}

int dptxport_connect(afk_epic_service_t *service, u8 core, u8 atc, u8 die)
{
    struct dcpdptx_connection_cmd cmd = {0}, resp = {0};
    int ret;
    u32 target = FIELD_PREP(DCPDPTX_REMOTE_PORT_CORE, core) |
                 FIELD_PREP(DCPDPTX_REMOTE_PORT_DFP, atc) |
                 FIELD_PREP(DCPDPTX_REMOTE_PORT_DIE, die) | DCPDPTX_REMOTE_PORT_CONNECTED;

    cmd.target = target;
    // cmd.unk = 0x100;
    ret = afk_service_call(service, 0, 11, &cmd, sizeof(cmd), 24, &resp, sizeof(resp), 24);
    if (ret)
        return ret;

    if (resp.target != target)
        return -1;
    if (resp.unk != 0x100)
        return -1;

    return 0;
}

int dptxport_request_display(afk_epic_service_t *service)
{
    return afk_service_call(service, 0, 6, NULL, 0, 16, NULL, 0, 16);
}

int dptxport_release_display(afk_epic_service_t *service)
{
    return afk_service_call(service, 0, 7, NULL, 0, 16, NULL, 0, 16);
}

int dptxport_set_hpd(afk_epic_service_t *service, bool hpd)
{
    struct dcpdptx_hotplug_cmd cmd, resp;
    int ret;

    memset(&cmd, 0, sizeof(cmd));

    if (hpd)
        cmd.unk = 1;

    ret = afk_service_call(service, 8, 8, &cmd, sizeof(cmd), 12, &resp, sizeof(resp), 12);
    if (ret)
        return ret;
    if (resp.unk != 1)
        return -1;
    return 0;
}

static int dptxport_call_get_max_drive_settings(afk_epic_service_t *service, void *reply_,
                                                size_t reply_size)
{
    UNUSED(service);
    struct dptxport_apcall_max_drive_settings *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 0;
    reply->max_drive_settings[0] = 0x3;
    reply->max_drive_settings[1] = 0x3;

    return 0;
}

static int dptxport_call_get_max_link_rate(afk_epic_service_t *service, void *reply_,
                                           size_t reply_size)
{
    UNUSED(service);
    struct dptxport_apcall_link_rate *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 0;
    reply->link_rate = LINK_RATE_HBR3;

    return 0;
}

static int dptxport_call_get_max_lane_count(afk_epic_service_t *service, void *reply_,
                                            size_t reply_size)
{
    UNUSED(service);
    struct dptxport_apcall_lane_count *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 0;
    reply->lane_count = 4;

    return 0;
}

static int dptxport_call_set_active_lane_count(afk_epic_service_t *service, const void *data,
                                               size_t data_size, void *reply_, size_t reply_size)
{
    struct dptx_port *port = service->cookie;
    const struct dptxport_apcall_set_active_lane_count *request = data;
    struct dptxport_apcall_set_active_lane_count *reply = reply_;
    int ret = 0;
    int retcode = 0;

    if (reply_size < sizeof(*reply))
        return -1;
    if (data_size < sizeof(*request))
        return -1;

    u64 lane_count = request->lane_count;

    switch (lane_count) {
        case 0 ... 2:
        case 4:
            ret = dptx_phy_set_active_lane_count(port->phy, lane_count);
            break;
        default:
            printf("DPTX-PORT: set_active_lane_count: invalid lane count:%lu\n", lane_count);
            retcode = 1;
            lane_count = 0;
            break;
    }

    reply->retcode = retcode;
    reply->lane_count = lane_count;

    return ret;
}

static int dptxport_call_get_link_rate(afk_epic_service_t *service, void *reply_, size_t reply_size)
{
    struct dptx_port *port = service->cookie;
    struct dptxport_apcall_link_rate *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 0;
    reply->link_rate = port->link_rate;

    return 0;
}

static int dptxport_call_will_change_link_config(afk_epic_service_t *service)
{
    UNUSED(service);
    return 0;
}

static int dptxport_call_did_change_link_config(afk_epic_service_t *service)
{
    UNUSED(service);
    // struct dptx_port *dptx = service->intf;
    // int ret = 0;

    mdelay(100);
    // dispext0,0 -> atcph1,dpphy
    // mux_control_select(dptx->mux, 0);

    return 0;
}

static int dptxport_call_set_link_rate(afk_epic_service_t *service, const void *data,
                                       size_t data_size, void *reply_, size_t reply_size)
{
    dptx_port_t *port = service->cookie;
    const struct dptxport_apcall_link_rate *request = data;
    struct dptxport_apcall_link_rate *reply = reply_;
    u32 link_rate, phy_link_rate;
    bool phy_set_rate = false;

    if (reply_size < sizeof(*reply))
        return -1;
    if (data_size < sizeof(*request))
        return -1;

    link_rate = request->link_rate;

    switch (link_rate) {
        case LINK_RATE_RBR:
            phy_link_rate = 1620;
            phy_set_rate = true;
            break;
        case LINK_RATE_HBR:
            phy_link_rate = 2700;
            phy_set_rate = true;
            break;
        case LINK_RATE_HBR2:
            phy_link_rate = 5400;
            phy_set_rate = true;
            break;
        case LINK_RATE_HBR3:
            phy_link_rate = 8100;
            phy_set_rate = true;
            break;
        case 0:
            phy_link_rate = 0;
            phy_set_rate = true;
            break;
        default:
            printf("DPTXPort: Unsupported link rate 0x%x requested\n", link_rate);
            link_rate = 0;
            phy_set_rate = false;
            break;
    }

    if (phy_set_rate) {
        dptx_phy_set_link_rate(port->phy, phy_link_rate);

        port->link_rate = port->pending_link_rate = link_rate;
    }

    // dptx->pending_link_rate = link_rate;
    reply->retcode = 0;
    reply->link_rate = link_rate;

    return 0;
}

static int dptxport_call_get_supports_hpd(afk_epic_service_t *service, void *reply_,
                                          size_t reply_size)
{
    UNUSED(service);
    struct dptxport_apcall_get_support *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 0;
    reply->supported = 0;
    return 0;
}

static int dptxport_call_get_supports_downspread(afk_epic_service_t *service, void *reply_,
                                                 size_t reply_size)
{
    UNUSED(service);
    struct dptxport_apcall_get_support *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 0;
    reply->supported = 0;
    return 0;
}

static int dptxport_call_set_tiled_display_hint(afk_epic_service_t *service, void *reply_,
                                                size_t reply_size)
{
    UNUSED(service);
    struct dptxport_apcall_set_tiled *reply = reply_;

    if (reply_size < sizeof(*reply))
        return -1;

    reply->retcode = 1;
    return 0;
}

static int dptxport_call(afk_epic_service_t *service, u32 idx, const void *data, size_t data_size,
                         void *reply, size_t reply_size)
{
    dcp_dptx_if_t *dptx = (dcp_dptx_if_t *)service->intf;

    switch (idx) {
        case DPTX_APCALL_WILL_CHANGE_LINKG_CONFIG:
            return dptxport_call_will_change_link_config(service);
        case DPTX_APCALL_DID_CHANGE_LINK_CONFIG:
            return dptxport_call_did_change_link_config(service);
        case DPTX_APCALL_GET_MAX_LINK_RATE:
            return dptxport_call_get_max_link_rate(service, reply, reply_size);
        case DPTX_APCALL_GET_LINK_RATE:
            return dptxport_call_get_link_rate(service, reply, reply_size);
        case DPTX_APCALL_SET_LINK_RATE:
            return dptxport_call_set_link_rate(service, data, data_size, reply, reply_size);
        case DPTX_APCALL_GET_MAX_LANE_COUNT:
            return dptxport_call_get_max_lane_count(service, reply, reply_size);
        case DPTX_APCALL_SET_ACTIVE_LANE_COUNT:
            return dptxport_call_set_active_lane_count(service, data, data_size, reply, reply_size);
        case DPTX_APCALL_GET_SUPPORTS_HPD:
            return dptxport_call_get_supports_hpd(service, reply, reply_size);
        case DPTX_APCALL_GET_SUPPORTS_DOWN_SPREAD:
            return dptxport_call_get_supports_downspread(service, reply, reply_size);
        case DPTX_APCALL_GET_MAX_DRIVE_SETTINGS:
            return dptxport_call_get_max_drive_settings(service, reply, reply_size);
        case DPTX_APCALL_SET_TILED_DISPLAY_HINTS:
            memcpy(reply, data, min(reply_size, data_size));
            return dptxport_call_set_tiled_display_hint(service, reply, reply_size);
        case DPTX_APCALL_ACTIVATE:
            dptx_phy_activate(dptx->phy);
            memcpy(reply, data, min(reply_size, data_size));
            if (reply_size > 4)
                memset(reply, 0, 4);
            return 0;
        default:
            /* just try to ACK and hope for the best... */
            dprintf("DPTXPort: unhandled call %d\n", idx);
            // fallthrough
        /* we can silently ignore and just ACK these calls */
        case DPTX_APCALL_DEACTIVATE:
        case DPTX_APCALL_SET_DRIVE_SETTINGS:
        case DPTX_APCALL_GET_DRIVE_SETTINGS:
            memcpy(reply, data, min(reply_size, data_size));
            if (reply_size > 4)
                memset(reply, 0, 4);
            return 0;
    }
}

static void dptxport_init(afk_epic_service_t *service, const char *name, const char *eclass,
                          s64 unit)
{
    dcp_dptx_if_t *dptx = (dcp_dptx_if_t *)service->intf;

    if (strcmp(name, "dcpdptx-port-epic"))
        return;
    if (strcmp(eclass, "AppleDCPDPTXRemotePort"))
        return;

    switch (unit) {
        case 0:
        case 1:
            if (dptx->port[unit].enabled) {
                printf("DPTXPort: unit %ld already exists\n", unit);
                return;
            }
            dptx->port[unit].unit = unit;
            dptx->port[unit].service = service;
            dptx->port[unit].enabled = true;
            service->cookie = (void *)&dptx->port[unit];
            break;
        default:
            printf("DPTXPort: invalid unit %ld\n", unit);
            return;
    }
}

static const afk_epic_service_ops_t dcp_dptx_ops[] = {
    {
        .name = "AppleDCPDPTXRemotePort",
        .init = dptxport_init,
        .call = dptxport_call,
    },
    {},
};

int dcp_dptx_connect(dcp_dptx_if_t *dptx, dptx_phy_t *phy, u32 die, u32 port)
{
    if (port > 1)
        return -1;
    if (!dptx->port[port].service) {
        printf("DPTXPort: port %u not initialized. enabled:%d\n", port, dptx->port[port].enabled);
        return -1;
    }

    dptx->port[port].phy = dptx->phy = phy;

    dptxport_connect(dptx->port[port].service, 0, dptx_phy_dcp_output(phy), die);
    dptxport_request_display(dptx->port[port].service);

    return 0;
}

int dcp_dptx_hpd(dcp_dptx_if_t *dptx, u32 port, bool hpd)
{
    if (!dptx->port[port].service)
        return -1;

    dptxport_set_hpd(dptx->port[port].service, hpd);

    return 0;
}

int dcp_dptx_disconnect(dcp_dptx_if_t *dptx, u32 port)
{
    dptxport_release_display(dptx->port[port].service);
    dptxport_set_hpd(dptx->port[port].service, false);

    return 0;
}

dcp_dptx_if_t *dcp_dptx_init(dcp_dev_t *dcp, u32 num_dptxports)
{
    dcp_dptx_if_t *dptx = calloc(1, sizeof(dcp_dptx_if_t));
    if (!dptx)
        return NULL;

    dptx->dcp = dcp;
    dptx->epic = afk_epic_start_ep(dcp->afk, DCP_DPTX_PORT_ENDPOINT, dcp_dptx_ops, true);
    if (!dptx->epic) {
        printf("dcp-dptx: failed to initialize EPIC\n");
        goto err_free;
    }

    int err = afk_epic_start_interface(dptx->epic, dptx, num_dptxports, TXBUF_LEN, RXBUF_LEN);
    if (err < 0) {
        printf("dcp-dptx: failed to initialize DPTXRemotePort interface\n");
        goto err_shutdown;
    }

    return dptx;

err_shutdown:
    afk_epic_shutdown_ep(dptx->epic);
err_free:
    free(dptx);
    return NULL;
}

int dcp_dptx_shutdown(dcp_dptx_if_t *dptx)
{
    if (dptx) {
        afk_epic_shutdown_ep(dptx->epic);
        free(dptx);
    }
    return 0;
}
