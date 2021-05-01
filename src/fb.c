/* SPDX-License-Identifier: MIT */

#include "fb.h"
#include "assert.h"
#include "iodev.h"
#include "string.h"
#include "types.h"
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

static struct {
    struct {
        u8 *ptr;
        u32 width;
        u32 height;
    } font;

    struct {
        u32 row;
        u32 col;

        u32 max_row;
        u32 max_col;
    } cursor;

    struct {
        u32 rows;
        u32 cols;
    } margin;

    int initialized;
} console = {.initialized = 0};

extern u8 _binary_build_bootlogo_128_bin_start[];
extern u8 _binary_build_bootlogo_256_bin_start[];

extern u8 _binary_build_font_bin_start[];
extern u8 _binary_build_font_retina_bin_start[];

static void fb_clear_font_row(u32 row)
{
    const u32 row_size = (console.margin.cols + console.cursor.max_col) * console.font.width * 4;
    const u32 ystart = (console.margin.rows + row) * console.font.height * fb.stride;

    for (u32 y = 0; y < console.font.height; ++y)
        memset(fb.ptr + ystart + y * fb.stride, 0, row_size);
}

static void fb_move_font_row(u32 dst, u32 src)
{
    const u32 row_size = (console.margin.cols + console.cursor.max_col) * console.font.width * 4;
    u32 ysrc = (console.margin.rows + src) * console.font.height;
    u32 ydst = (console.margin.rows + dst) * console.font.height;

    ysrc *= fb.stride;
    ydst *= fb.stride;

    for (u32 y = 0; y < console.font.height; ++y)
        memcpy(fb.ptr + ydst + y * fb.stride, fb.ptr + ysrc + y * fb.stride, row_size);

    fb_clear_font_row(src);
}

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
        console.font.ptr = _binary_build_font_retina_bin_start;
        console.font.width = 16;
        console.font.height = 32;
    } else {
        logo.ptr = (void *)_binary_build_bootlogo_128_bin_start;
        logo.width = logo.height = 128;
        console.font.ptr = _binary_build_font_bin_start;
        console.font.width = 8;
        console.font.height = 16;
    }

    console.margin.rows = 2;
    console.margin.cols = 4;
    console.cursor.col = 0;
    console.cursor.row = 0;

    console.cursor.max_row = (fb.height / console.font.height) - 2 * console.margin.rows;
    console.cursor.max_col =
        ((fb.width - logo.width) / 2) / console.font.width - 2 * console.margin.cols;

    console.initialized = 1;

    for (u32 row = 0; row < console.cursor.max_row; ++row)
        fb_clear_font_row(row);

    printf("fb console: max rows %d, max cols %d\n", console.cursor.max_row,
           console.cursor.max_col);
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

static rgb_t font_get_pixel(u8 c, u32 x, u32 y)
{
    c -= 0x20;
    u8 v =
        console.font.ptr[c * console.font.width * console.font.height + y * console.font.width + x];

    rgb_t col = {.r = v, .g = v, .b = v};
    return col;
}

static void fb_putbyte(u8 c)
{
    u32 x = (console.margin.cols + console.cursor.col) * console.font.width;
    u32 y = (console.margin.rows + console.cursor.row) * console.font.height;

    for (u32 i = 0; i < console.font.height; i++)
        for (u32 j = 0; j < console.font.width; j++)
            fb_set_pixel(x + j, y + i, font_get_pixel(c, j, i));
}

static void fb_putchar(u8 c)
{
    if (c == '\r') {
        console.cursor.col = 0;
    } else if (c == '\n') {
        console.cursor.row++;
        console.cursor.col = 0;
    } else if (c >= 0x20 && c < 0x7f) {
        fb_putbyte(c);
        console.cursor.col++;
    } else {
        fb_putbyte('?');
        console.cursor.col++;
    }

    if (console.cursor.col == console.cursor.max_col) {
        console.cursor.row++;
        console.cursor.col = 0;
    }

    if (console.cursor.row == console.cursor.max_row)
        fb_console_scroll(1);
}

void fb_console_scroll(u32 n)
{
    u32 row = 0;
    n = min(n, console.cursor.row);
    for (; row < console.cursor.max_row - n; ++row)
        fb_move_font_row(row, row + n);
    for (; row < console.cursor.max_row; ++row)
        fb_clear_font_row(row);
    console.cursor.row -= n;
}

void fb_console_reserve_lines(u32 n)
{
    if ((console.cursor.max_row - console.cursor.row) <= n)
        fb_console_scroll(1 + n - (console.cursor.max_row - console.cursor.row));
}

ssize_t fb_console_write(const char *bfr, size_t len)
{
    ssize_t wrote = 0;

    if (!console.initialized)
        return 0;

    while (len--) {
        fb_putchar(*bfr++);
        wrote++;
    }

    return wrote;
}

static bool fb_console_iodev_can_write(void *opaque)
{
    UNUSED(opaque);
    return console.initialized;
}

static ssize_t fb_console_iodev_write(void *opaque, const void *buf, size_t len)
{
    UNUSED(opaque);
    return fb_console_write(buf, len);
}

const struct iodev_ops iodev_fb_ops = {
    .can_write = fb_console_iodev_can_write,
    .write = fb_console_iodev_write,
};

struct iodev iodev_fb = {
    .ops = &iodev_fb_ops,
    .usage = USAGE_CONSOLE,
};
