/* SPDX-License-Identifier: (GPL-2.0-or-later OR BSD-2-Clause) */

#include "adt.h"
#include "xnuboot.h"

/* This API is designed to match libfdt's read-only API */

u32 adt_get_size(void)
{
    return cur_boot_args.devtree_size;
}
