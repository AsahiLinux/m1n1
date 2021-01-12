/* SPDX-License-Identifier: MIT */

#ifndef FB_H
#define FB_H

#include "types.h"

extern u32 *fb;
extern int fb_s, fb_w, fb_h;

void fb_init(void);
void fb_blit(int x, int y, int w, int h, void *data, int stride);
void fb_fill(int x, int y, int w, int h, u32 color);

void fb_display_logo(void);

#endif
