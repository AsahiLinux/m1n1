/* SPDX-License-Identifier: MIT */

#include "fb.h"
#include "utils.h"
#include "xnuboot.h"

u32 *fb;
int fb_s, fb_w, fb_h, fb_d;
int scale = 1;

static u32 *logo;
static int logo_w, logo_h;

extern char _binary_build_bootlogo_128_bin_start[0];
extern char _binary_build_bootlogo_256_bin_start[0];

void fb_init(void)
{
    fb = (void *)cur_boot_args.video.base;
    fb_s = cur_boot_args.video.stride / 4;
    fb_w = cur_boot_args.video.width;
    fb_h = cur_boot_args.video.height;
    fb_d = cur_boot_args.video.depth & 0xff;
    printf("fb init: %dx%d (%d) [s=%d] @%p\n", fb_w, fb_h, fb_d, fb_s, fb);

    if (cur_boot_args.video.depth & 0x10000) {
        logo = (void *)_binary_build_bootlogo_256_bin_start;
        logo_w = logo_h = 256;
    } else {
        logo = (void *)_binary_build_bootlogo_128_bin_start;
        logo_w = logo_h = 128;
    }
}

static inline uint32_t rgbx_to_rgb30(u32 c)
{
    u8 r = c;
    u8 g = c >> 8;
    u8 b = c >> 16;
    return (b << 2) | (g << 12) | (r << 22);
}

void fb_blit(int x, int y, int w, int h, void *data, int stride)
{
    uint32_t *p = data;

    for (int i = 0; i < h; i++)
        for (int j = 0; j < w; j++)
            fb[x + j + (y + i) * fb_s] = rgbx_to_rgb30(p[j + i * stride]);
}

void fb_fill(int x, int y, int w, int h, u32 color)
{
    for (int i = 0; i < h; i++)
        for (int j = 0; j < w; j++)
            fb[x + j + (y + i) * fb_s] = rgbx_to_rgb30(color);
}

void fb_display_logo(void)
{
    printf("fb: display logo\n");
    fb_blit((fb_w - logo_w) / 2, (fb_h - logo_h) / 2, logo_w, logo_h, logo, logo_w);
}
