/* SPDX-License-Identifier: MIT */

#include <string.h>

#include "adt.h"
#include "akf.h"
#include "asc.h"
#include "malloc.h"
#include "sep.h"
#include "soc.h"
#include "types.h"
#include "utils.h"

#define SEP_MSG_EP   GENMASK(7, 0)
#define SEP_MSG_CMD  GENMASK(23, 16)
#define SEP_MSG_DATA GENMASK(63, 32)

#define SEP_EP_ROM 0xff

#define SEP_MSG_GETRAND   16
#define SEP_REPLY_GETRAND 116

#define SEP_TIMEOUT 1000

enum sep_mbox_type {
    SEP_MBOX_TYPE_AKF,
    SEP_MBOX_TYPE_ASC,
};

static struct sep_dev {
    enum sep_mbox_type type;
    sep_capabilities_t capabilities;
    union {
        akf_dev_t *akf;
        asc_dev_t *asc;
    };
} *sep_dev;

int sep_init(void)
{
    const char *path = "/arm-io/sep";
    int sep_path[8];

    int node = adt_path_offset_trace(adt, path, sep_path);
    if (node < 0) {
        printf("sep: Error getting sep node %s\n", path);
        return -1;
    }

    u64 base;
    if (adt_get_reg(adt, sep_path, "reg", 0, &base, NULL) < 0) {
        printf("sep: Error getting akf %s base address.\n", path);
        return -1;
    }

    sep_dev = calloc(0, sizeof(*sep_dev));

    if (adt_is_compatible(adt, node, "iop,s5l8960x") || adt_is_compatible(adt, node, "iop,s8000")) {
        sep_dev->type = SEP_MBOX_TYPE_AKF;
    } else {
        sep_dev->type = SEP_MBOX_TYPE_ASC;
    }

    switch (sep_dev->type) {
        case SEP_MBOX_TYPE_AKF:
            sep_dev->akf = akf_init(path);
            break;
        case SEP_MBOX_TYPE_ASC:
            sep_dev->asc = asc_init(path);
            break;
    }

    if (chip_id != S5L8960X && chip_id != T7000 && chip_id != T7001 && chip_id != S8000 &&
        chip_id != S8001 && chip_id != S8003)
        sep_dev->capabilities |= SEP_CAPABILITY_GETRAND;

    return 0;
}

bool sep_send(u64 msg)
{
    switch (sep_dev->type) {
        case SEP_MBOX_TYPE_AKF: {
            const struct akf_message akf_msg = {.msg0 = FIELD_GET(msg, MASK(32)),
                                                .msg1 = FIELD_GET(msg, GENMASK(63, 32))};
            return akf_send(sep_dev->akf, &akf_msg);
        }
        case SEP_MBOX_TYPE_ASC: {
            const struct asc_message asc_msg = {.msg0 = msg};
            return asc_send(sep_dev->asc, &asc_msg);
        }
    }
    __builtin_unreachable();
}

bool sep_recv(u64 *reply)
{
    switch (sep_dev->type) {
        case SEP_MBOX_TYPE_AKF: {
            struct akf_message akf_reply;
            int retval = akf_recv_timeout(sep_dev->akf, &akf_reply, SEP_TIMEOUT);
            *reply =
                FIELD_PREP(MASK(32), akf_reply.msg0) | FIELD_PREP(GENMASK(63, 32), akf_reply.msg1);
            return retval;
        }
        case SEP_MBOX_TYPE_ASC: {
            struct asc_message asc_reply;
            int retval = asc_recv_timeout(sep_dev->asc, &asc_reply, SEP_TIMEOUT);
            *reply = asc_reply.msg0;
            return retval;
        }
    }
    __builtin_unreachable();
}

size_t sep_get_random(void *buffer, size_t len)
{
    if (!(sep_dev->capabilities & SEP_CAPABILITY_GETRAND)) {
        printf("sep: SEP does not support GETRAND\n");
        return 0;
    }

    const u64 msg_getrand =
        FIELD_PREP(SEP_MSG_EP, SEP_EP_ROM) | FIELD_PREP(SEP_MSG_CMD, SEP_MSG_GETRAND);
    int ret;
    size_t done = 0;

    ret = sep_init();
    if (ret)
        return 0;

    while (len) {
        u64 reply;
        u32 rng;
        size_t copy;

        if (!sep_send(msg_getrand))
            return done;
        if (!sep_recv(&reply))
            return done;
        if (FIELD_GET(SEP_MSG_CMD, reply) != SEP_REPLY_GETRAND) {
            printf("SEP: unexpected getrand reply: %016lx\n", reply);
            return done;
        }

        rng = FIELD_GET(SEP_MSG_DATA, reply);
        copy = sizeof(rng);
        if (copy > len)
            copy = len;
        memcpy(buffer, &rng, copy);
        done += copy;
        len -= copy;
        buffer += copy;
    }

    return done;
}

sep_capabilities_t sep_get_capabilities(void)
{
    return sep_dev->capabilities;
}
