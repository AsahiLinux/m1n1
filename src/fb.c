/* SPDX-License-Identifier: MIT */

#include <assert.h>

#include "fb.h"
#include "smp.h"
#include "string.h"
#include "utils.h"
#include "xnuboot.h"

#define FB_DEPTH_FLAG_RETINA 0x10000
#define FB_DEPTH_MASK        0xff

#define CONSOLE_MAX_ROWS 60
#define CONSOLE_MAX_COLS 80

fb_t fb;

typedef struct {
    u32 row;
    u32 col;
} console_pos_t;

static struct {
    u32 *ptr;
    u32 width;
    u32 height;
} logo;

static struct {
    u32 initialized;
    console_pos_t cursor;
    u32 row_offset;
    u8 text[CONSOLE_MAX_ROWS][CONSOLE_MAX_COLS];
} console = {.initialized = 0, .cursor = {.row = 0, .col = 0}, .row_offset = 0, .text = {{0}}};

extern u8 _binary_build_bootlogo_128_bin_start[];
extern u8 _binary_build_bootlogo_256_bin_start[];

extern u8 _binary_build_font_bin_start[];

static const rgb_t color_black = {.r = 0, .g = 0, .b = 0};

static void fb_console_blit_all(void);

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

    console.initialized = 1;
    fb_console_blit_all();
}

static void fb_set_pixel(u32 x, u32 y, rgb_t c)
{
    fb.ptr[x + y * fb.stride] = (c.b << 2) | (c.g << 12) | (c.r << 22);
}

static u32 fb_console_get_row(u32 row)
{
    return (row + console.row_offset) % CONSOLE_MAX_ROWS;
}

static rgb_t font_get_pixel(u8 c, u32 x, u32 y)
{
    c -= 0x20;
    u8 *ptr = &_binary_build_font_bin_start[c * 512 + (y * 8 + x) * 4];

    rgb_t col = {.r = *ptr++, .g = *ptr++, .b = *ptr++};
    return col;
}

static void fb_console_blit_char(console_pos_t pos)
{
    u32 x = 30 + pos.col * 8;
    u32 y = 50 + pos.row * 16;
    u8 c = console.text[fb_console_get_row(pos.row)][pos.col];

    if (!console.initialized)
        return;

    if (c == '\0') {
        fb_fill(x, y, 8, 16, color_black);
    } else {
        for (int i = 0; i < 16; i++)
            for (int j = 0; j < 8; j++)
                fb_set_pixel(x + j, y + i, font_get_pixel(c, j, i));
    }
}

static void fb_console_blit_row(u32 row)
{
    console_pos_t pos = {.row = row, .col = 0};

    while (pos.col < CONSOLE_MAX_COLS) {
        fb_console_blit_char(pos);
        pos.col++;
    }
}

static void fb_console_blit_all(void)
{
    for (u32 row = 0; row < CONSOLE_MAX_ROWS; ++row)
        fb_console_blit_row(row);
}

static void fb_console_putbyte(u8 c)
{
    if (console.cursor.col >= CONSOLE_MAX_COLS)
        return;

    console.text[fb_console_get_row(console.cursor.row)][console.cursor.col] = c;
    fb_console_blit_char(console.cursor);

    console.cursor.col++;
}

static void fb_check_scroll(void)
{
    if (console.cursor.row < CONSOLE_MAX_ROWS)
        return;

    memset(console.text[fb_console_get_row(0)], 0, CONSOLE_MAX_COLS);
    console.row_offset = (console.row_offset + 1) % CONSOLE_MAX_ROWS;
    console.cursor.row--;

    assert(console.cursor.row < CONSOLE_MAX_ROWS);

    fb_console_blit_all();
}

void fb_console_putc(u8 c)
{
    if (!smp_is_primary())
        return;

    if (c == '\n') {
        console.cursor.row++;
        console.cursor.col = 0;
    } else if (c == '\r') {
        console.cursor.col = 0;
    } else if (c >= 0x20 && c <= 0x7e) {
        fb_console_putbyte(c);
    } else {
        fb_console_putbyte('?');
    }

    fb_check_scroll();
}

void fb_console_write(const void *buf, size_t count)
{
    const u8 *p = buf;

    while (count--)
        fb_console_putc(*p++);
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
