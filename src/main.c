/* SPDX-License-Identifier: MIT */

#include "fb.h"
#include "utils.h"
#include "xnuboot.h"

#include "../build/build_tag.h"

void m1n1_main(void)
{
    printf("\n\nm1n1 v%s\n", BUILD_TAG);
    printf("Copyright (C) 2021 The Asahi Linux Contributors\n");
    printf("Licensed under the MIT license\n");

    fb_init();
    fb_display_logo();

    u64 dtaddr = ((u64)cur_boot_args.devtree) - cur_boot_args.virt_base +
                 cur_boot_args.phys_base;

    hexdump((void *)dtaddr, cur_boot_args.devtree_size);

    while (1)
        ;
}
