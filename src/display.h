/* SPDX-License-Identifier: MIT */

#ifndef DISPLAY_H
#define DISPLAY_H

#include "types.h"

typedef enum _dcp_shutdown_mode {
    DCP_QUIESCED = 0,
    DCP_SLEEP_IF_EXTERNAL = 1,
    DCP_SLEEP = 2,
} dcp_shutdown_mode;

extern bool display_is_external;

int display_init(void);
int display_start_dcp(void);
int display_configure(const char *config);
void display_shutdown(dcp_shutdown_mode mode);

#endif
