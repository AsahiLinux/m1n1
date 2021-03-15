/* SPDX-License-Identifier: MIT */

#ifndef FB_H
#define FB_H

#include "types.h"

typedef struct {
    u32 *ptr;   /* pointer to the start of the framebuffer */
    u32 stride; /* framebuffer stride divided by four (i.e. stride in pixels) */
    u32 depth;  /* framebuffer depth (i.e. bits per pixel) */
    u32 width;  /* width of the framebuffer in pixels */
    u32 height; /* height of the framebuffer in pixels */
} fb_t;

typedef struct {
    u8 r;
    u8 g;
    u8 b;
} rgb_t;

extern fb_t fb;

void fb_init(void);
void fb_blit(u32 x, u32 y, u32 w, u32 h, void *data, u32 stride);
void fb_fill(u32 x, u32 y, u32 w, u32 h, rgb_t color);

void fb_display_logo(void);

#endif
