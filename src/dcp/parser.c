// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2021 Alyssa Rosenzweig <alyssa@rosenzweig.io> */

#include "malloc.h"
#include "parser.h"
#include "string.h"

#include "../utils.h"

#define DCP_PARSE_HEADER 0xd3

enum dcp_parse_type {
    DCP_TYPE_DICTIONARY = 1,
    DCP_TYPE_ARRAY = 2,
    DCP_TYPE_INT64 = 4,
    DCP_TYPE_STRING = 9,
    DCP_TYPE_BLOB = 10,
    DCP_TYPE_BOOL = 11
};

struct dcp_parse_tag {
    unsigned int size : 24;
    enum dcp_parse_type type : 5;
    unsigned int padding : 2;
    bool last : 1;
} __packed;

static void *parse_bytes(struct dcp_parse_ctx *ctx, size_t count)
{
    void *ptr = ctx->blob + ctx->pos;

    if (ctx->pos + count > ctx->len)
        return NULL;

    ctx->pos += count;
    return ptr;
}

static u32 *parse_u32(struct dcp_parse_ctx *ctx)
{
    return parse_bytes(ctx, sizeof(u32));
}

static struct dcp_parse_tag *parse_tag(struct dcp_parse_ctx *ctx)
{
    struct dcp_parse_tag *tag;

    /* Align to 32-bits */
    ctx->pos = ALIGN_UP(ctx->pos, 4);

    tag = parse_bytes(ctx, sizeof(struct dcp_parse_tag));

    if (!tag)
        return NULL;

    if (tag->padding)
        return NULL;

    return tag;
}

static struct dcp_parse_tag *parse_tag_of_type(struct dcp_parse_ctx *ctx, enum dcp_parse_type type)
{
    struct dcp_parse_tag *tag = parse_tag(ctx);

    if (!tag)
        return NULL;

    if (tag->type != type)
        return NULL;

    return tag;
}

static int skip(struct dcp_parse_ctx *handle)
{
    struct dcp_parse_tag *tag = parse_tag(handle);
    int ret = 0;
    int i;

    if (!tag)
        return -1;

    switch (tag->type) {
        case DCP_TYPE_DICTIONARY:
            for (i = 0; i < tag->size; ++i) {
                ret |= skip(handle); /* key */
                ret |= skip(handle); /* value */
            }

            return ret;

        case DCP_TYPE_ARRAY:
            for (i = 0; i < tag->size; ++i)
                ret |= skip(handle);

            return ret;

        case DCP_TYPE_INT64:
            handle->pos += sizeof(s64);
            return 0;

        case DCP_TYPE_STRING:
        case DCP_TYPE_BLOB:
            handle->pos += tag->size;
            return 0;

        case DCP_TYPE_BOOL:
            return 0;

        default:
            return -1;
    }
}

/* Caller must free the result */
static char *parse_string(struct dcp_parse_ctx *handle)
{
    struct dcp_parse_tag *tag = parse_tag_of_type(handle, DCP_TYPE_STRING);
    const char *in;
    char *out;

    if (!tag)
        return NULL;

    in = parse_bytes(handle, tag->size);
    if (!in)
        return NULL;

    out = malloc(tag->size + 1);

    memcpy(out, in, tag->size);
    out[tag->size] = '\0';
    return out;
}

static int parse_int(struct dcp_parse_ctx *handle, s64 *value)
{
    void *tag = parse_tag_of_type(handle, DCP_TYPE_INT64);
    s64 *in;

    if (!tag)
        return -1;

    in = parse_bytes(handle, sizeof(s64));

    if (!in)
        return -1;

    memcpy(value, in, sizeof(*value));
    return 0;
}

// currently unused
#if 0
static int parse_bool(struct dcp_parse_ctx *handle, bool *b)
{
    struct dcp_parse_tag *tag = parse_tag_of_type(handle, DCP_TYPE_BOOL);

    if (!tag)
        return -1;

    *b = !!tag->size;
    return 0;
}
#endif

struct iterator {
    struct dcp_parse_ctx *handle;
    u32 idx, len;
};

static int iterator_begin(struct dcp_parse_ctx *handle, struct iterator *it, bool dict)
{
    struct dcp_parse_tag *tag;
    enum dcp_parse_type type = dict ? DCP_TYPE_DICTIONARY : DCP_TYPE_ARRAY;

    *it = (struct iterator){.handle = handle, .idx = 0};

    tag = parse_tag_of_type(it->handle, type);
    if (!tag)
        return -1;

    it->len = tag->size;
    return 0;
}

#define dcp_parse_foreach_in_array(handle, it)                                                     \
    for (iterator_begin(handle, &it, false); it.idx < it.len; ++it.idx)
#define dcp_parse_foreach_in_dict(handle, it)                                                      \
    for (iterator_begin(handle, &it, true); it.idx < it.len; ++it.idx)

int parse(void *blob, size_t size, struct dcp_parse_ctx *ctx)
{
    u32 *header;

    *ctx = (struct dcp_parse_ctx){
        .blob = blob,
        .len = size,
        .pos = 0,
    };

    header = parse_u32(ctx);
    if (!header)
        return -1;

    if (*header != DCP_PARSE_HEADER)
        return -1;

    return 0;
}

int parse_epic_service_init(struct dcp_parse_ctx *handle, char **name, char **class, s64 *unit)
{
    int ret = 0;
    struct iterator it;
    bool parsed_unit = false;
    bool parsed_name = false;
    bool parsed_class = false;

    *name = NULL;
    *class = NULL;

    dcp_parse_foreach_in_dict(handle, it)
    {
        char *key = parse_string(it.handle);

        if (!key) {
            ret = -1;
            break;
        }

        if (!strcmp(key, "EPICName")) {
            *name = parse_string(it.handle);
            if (!*name)
                ret = -1;
            else
                parsed_name = true;
        } else if (!strcmp(key, "EPICProviderClass")) {
            *class = parse_string(it.handle);
            if (!*class)
                ret = -1;
            else
                parsed_class = true;
        } else if (!strcmp(key, "EPICUnit")) {
            ret = parse_int(it.handle, unit);
            if (!ret)
                parsed_unit = true;
        } else {
            skip(it.handle);
        }

        free(key);
        if (ret)
            break;
    }

    if (!parsed_unit || !parsed_name || !parsed_class)
        ret = -1;

    if (ret) {
        if (*name) {
            free(*name);
            *name = NULL;
        }
        if (*class) {
            free(*class);
            *class = NULL;
        }
    }

    return ret;
}
