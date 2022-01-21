/* SPDX-License-Identifier: MIT */

#ifndef NVME_H
#define NVME_H

#include "types.h"

bool nvme_init(void);
void nvme_shutdown(void);

bool nvme_flush(u32 nsid);
bool nvme_read(u32 nsid, u64 lba, void *buffer);

#endif
