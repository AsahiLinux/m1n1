/* SPDX-License-Identifier: MIT */

#include "assert.h"
#include "fb.h"
#include "string.h"
#include "utils.h"
#include "xnuboot.h"

#define FB_DEPTH_FLAG_RETINA 0x10000
#define FB_DEPTH_MASK        0xff

fb_t fb;

static struct {
    u32 *ptr;
    u32 width;
    u32 height;
} logo;

extern u8 _binary_build_bootlogo_128_bin_start[];
extern u8 _binary_build_bootlogo_256_bin_start[];

extern u8 _binary_build_font_bin_start[];
extern u8 _binary_build_font_retina_bin_start[];

void fb_init(void)
{
    fb.ptr = (void *)cur_boot_args.video.base;
    fb.stride = cur_boot_args.video.stride / 4;
    fb.width = cur_boot_args.video.width;
    fb.height = cur_boot_args.video.height;
    fb.depth = cur_boot_args.video.depth & FB_DEPTH_MASK;
    printf("fb init: %dx%d (%d) [s=%d] @%p\n", fb.width, fb.height, fb.depth, fb.stride, fb.ptr);

    if (cur_boot_args.video.depth & FB_DEPTH_FLAG_RETINA) {
        logo.ptr = (void *)_binary_build_bootlogo_256_bin_start;
        logo.width = logo.height = 256;
    } else {
        logo.ptr = (void *)_binary_build_bootlogo_128_bin_start;
        logo.width = logo.height = 128;
    }
}

static void fb_set_pixel(u32 x, u32 y, rgb_t c)
{
    fb.ptr[x + y * fb.stride] = (c.b << 2) | (c.g << 12) | (c.r << 22);
}

void fb_blit(u32 x, u32 y, u32 w, u32 h, void *data, u32 stride)
{
    u8 *p = data;

    for (u32 i = 0; i < h; i++) {
        for (u32 j = 0; j < w; j++) {
            rgb_t color = {.r = p[(j + i * stride) * 4],
                           .g = p[(j + i * stride) * 4 + 1],
                           .b = p[(j + i * stride) * 4 + 2]};
            fb_set_pixel(x + j, y + i, color);
        }
    }
}

void fb_fill(u32 x, u32 y, u32 w, u32 h, rgb_t color)
{
    for (u32 i = 0; i < h; i++)
        for (u32 j = 0; j < w; j++)
            fb_set_pixel(x + j, y + i, color);
}

void fb_display_logo(void)
{
    printf("fb: display logo\n");
    fb_blit((fb.width - logo.width) / 2, (fb.height - logo.height) / 2, logo.width, logo.height,
            logo.ptr, logo.width);
}
