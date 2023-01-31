// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2021 Alyssa Rosenzweig <alyssa@rosenzweig.io> */

#ifndef __APPLE_DCP_PARSER_H__
#define __APPLE_DCP_PARSER_H__

#include "../types.h"

struct dcp_parse_ctx {
    void *blob;
    u32 pos, len;
};

int parse(void *blob, size_t size, struct dcp_parse_ctx *ctx);

int parse_epic_service_init(struct dcp_parse_ctx *handle, char **name, char **class, s64 *unit);

#endif
