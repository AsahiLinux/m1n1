/* SPDX-License-Identifier: MIT */

#include <string.h>

#include "asc.h"
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

static asc_dev_t *sep_asc = NULL;

int sep_init(void)
{
    if (!sep_asc)
        sep_asc = asc_init("/arm-io/sep");
    if (!sep_asc)
        return -1;
    return 0;
}

size_t sep_get_random(void *buffer, size_t len)
{
    const struct asc_message msg_getrand = {.msg0 = FIELD_PREP(SEP_MSG_EP, SEP_EP_ROM) |
                                                    FIELD_PREP(SEP_MSG_CMD, SEP_MSG_GETRAND)};
    int ret;
    size_t done = 0;

    ret = sep_init();
    if (ret)
        return 0;

    while (len) {
        struct asc_message reply;
        u32 rng;
        size_t copy;

        if (!asc_send(sep_asc, &msg_getrand))
            return done;
        if (!asc_recv_timeout(sep_asc, &reply, SEP_TIMEOUT))
            return done;
        if (FIELD_GET(SEP_MSG_CMD, reply.msg0) != SEP_REPLY_GETRAND) {
            printf("SEP: unexpected getrand reply: %016lx\n", reply.msg0);
            return done;
        }

        rng = FIELD_GET(SEP_MSG_DATA, reply.msg0);
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
