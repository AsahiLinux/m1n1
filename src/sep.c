/* SPDX-License-Identifier: MIT */

#include <string.h>

#include "adt.h"
#include "asc.h"
#include "malloc.h"
#include "sep.h"
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
    SEP_MBOX_TYPE_ASC,
};

static struct sep_dev {
    enum sep_mbox_type type;
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
    sep_dev->type = SEP_MBOX_TYPE_ASC;

    switch (sep_dev->type) {
        case SEP_MBOX_TYPE_ASC:
            sep_dev->asc = asc_init(path);
            break;
    }

    return 0;
}

bool sep_send(u64 msg)
{
    switch (sep_dev->type) {
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
