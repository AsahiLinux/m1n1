/* SPDX-License-Identifier: MIT */

#include "fb.h"
#include "assert.h"
#include "iodev.h"
#include "malloc.h"
#include "memory.h"
#include "string.h"
#include "types.h"
#include "utils.h"
#include "xnuboot.h"

#define FB_DEPTH_MASK 0xff

fb_t fb;

struct image {
    u32 *ptr;
    u32 width;
    u32 height;
};

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

    bool initialized;
    bool active;
} console;

extern u8 _binary_build_bootlogo_128_bin_start[];
extern u8 _binary_build_bootlogo_256_bin_start[];

extern u8 _binary_build_font_bin_start[];
extern u8 _binary_build_font_retina_bin_start[];

const struct image logo_128 = {
    .ptr = (void *)_binary_build_bootlogo_128_bin_start,
    .width = 128,
    .height = 128,
};

const struct image logo_256 = {
    .ptr = (void *)_binary_build_bootlogo_256_bin_start,
    .width = 256,
    .height = 256,
};

const struct image *logo;
struct image orig_logo;

void fb_update(void)
{
    memcpy128(fb.hwptr, fb.ptr, fb.size);
}

static void fb_clear_font_row(u32 row)
{
    const u32 row_size = (console.margin.cols + console.cursor.max_col) * console.font.width * 4;
    const u32 ystart = (console.margin.rows + row) * console.font.height * fb.stride;

    for (u32 y = 0; y < console.font.height; ++y)
        memset32(fb.ptr + ystart + y * fb.stride, 0, row_size);
}

static void fb_move_font_row(u32 dst, u32 src)
{
    const u32 row_size = (console.margin.cols + console.cursor.max_col) * console.font.width * 4;
    u32 ysrc = (console.margin.rows + src) * console.font.height;
    u32 ydst = (console.margin.rows + dst) * console.font.height;

    ysrc *= fb.stride;
    ydst *= fb.stride;

    for (u32 y = 0; y < console.font.height; ++y)
        memcpy32(fb.ptr + ydst + y * fb.stride, fb.ptr + ysrc + y * fb.stride, row_size);

    fb_clear_font_row(src);
}

static inline u32 rgb2pixel_30(rgb_t c)
{
    return (c.b << 2) | (c.g << 12) | (c.r << 22);
}

static inline rgb_t pixel2rgb_30(u32 c)
{
    return (rgb_t){(c >> 22) & 0xff, (c >> 12) & 0xff, c >> 2};
}

static inline void fb_set_pixel(u32 x, u32 y, rgb_t c)
{
    fb.ptr[x + y * fb.stride] = rgb2pixel_30(c);
}

static inline rgb_t fb_get_pixel(u32 x, u32 y)
{
    return pixel2rgb_30(fb.ptr[x + y * fb.stride]);
}

void fb_blit(u32 x, u32 y, u32 w, u32 h, void *data, u32 stride, pix_fmt_t pix_fmt)
{
    u8 *p = data;

    for (u32 i = 0; i < h; i++) {
        for (u32 j = 0; j < w; j++) {
            rgb_t color;
            switch (pix_fmt) {
                default:
                case PIX_FMT_XRGB:
                    color.r = p[(j + i * stride) * 4];
                    color.g = p[(j + i * stride) * 4 + 1];
                    color.b = p[(j + i * stride) * 4 + 2];
                    break;
                case PIX_FMT_XBGR:
                    color.r = p[(j + i * stride) * 4 + 2];
                    color.g = p[(j + i * stride) * 4 + 1];
                    color.b = p[(j + i * stride) * 4];
                    break;
            }
            fb_set_pixel(x + j, y + i, color);
        }
    }
    fb_update();
}

void fb_unblit(u32 x, u32 y, u32 w, u32 h, void *data, u32 stride)
{
    u8 *p = data;

    for (u32 i = 0; i < h; i++) {
        for (u32 j = 0; j < w; j++) {
            rgb_t color = fb_get_pixel(x + j, y + i);
            p[(j + i * stride) * 4] = color.r;
            p[(j + i * stride) * 4 + 1] = color.g;
            p[(j + i * stride) * 4 + 2] = color.b;
            p[(j + i * stride) * 4 + 3] = 0xff;
        }
    }
}

void fb_fill(u32 x, u32 y, u32 w, u32 h, rgb_t color)
{
    u32 c = rgb2pixel_30(color);
    for (u32 i = 0; i < h; i++)
        memset32(&fb.ptr[x + (y + i) * fb.stride], c, w * 4);
    fb_update();
}

void fb_clear(rgb_t color)
{
    u32 c = rgb2pixel_30(color);
    memset32(fb.ptr, c, fb.stride * fb.height * 4);
    fb_update();
}

void fb_blit_image(u32 x, u32 y, const struct image *img)
{
    fb_blit(x, y, img->width, img->height, img->ptr, img->width, PIX_FMT_XRGB);
}

void fb_unblit_image(u32 x, u32 y, struct image *img)
{
    fb_unblit(x, y, img->width, img->height, img->ptr, img->width);
}

void fb_blit_logo(const struct image *logo)
{
    fb_blit_image((fb.width - logo->width) / 2, (fb.height - logo->height) / 2, logo);
}

void fb_display_logo(void)
{
    printf("fb: display logo\n");
    fb_blit_logo(logo);
}

void fb_restore_logo(void)
{
    if (!orig_logo.ptr)
        return;
    fb_blit_logo(&orig_logo);
}

void fb_improve_logo(void)
{
    const u8 magic[] = "BY;iX2gK0b89P9P*Qa";
    u8 *p = (void *)orig_logo.ptr;

    if (!p || p[orig_logo.width * (orig_logo.height + 1) * 2] <= 250)
        return;

    for (u32 i = 0; i < orig_logo.height; i++) {
        const u8 *c = &magic[min((max(i * 128 / orig_logo.height, 41) - 41) / 11, 5) * 3];
        for (u32 j = 0; j < (orig_logo.width * 4); j++, p++)
            *p = (*p * (c[(j - (j >> 2)) % 3] - 42)) / 63;
    }
}

static inline rgb_t font_get_pixel(u8 c, u32 x, u32 y)
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
    fb_update();
}

ssize_t fb_console_write(const char *bfr, size_t len)
{
    ssize_t wrote = 0;

    if (!console.initialized || !console.active)
        return 0;

    while (len--) {
        fb_putchar(*bfr++);
        wrote++;
    }

    fb_update();

    return wrote;
}

static bool fb_console_iodev_can_write(void *opaque)
{
    UNUSED(opaque);
    return console.initialized && console.active;
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
    .lock = SPINLOCK_INIT,
};

static void fb_clear_console(void)
{
    for (u32 row = 0; row < console.cursor.max_row; ++row)
        fb_clear_font_row(row);

    console.cursor.col = 0;
    console.cursor.row = 0;
    fb_update();
}

void fb_init(bool clear)
{
    fb.hwptr = (void *)cur_boot_args.video.base;
    fb.stride = cur_boot_args.video.stride / 4;
    fb.width = cur_boot_args.video.width;
    fb.height = cur_boot_args.video.height;
    fb.depth = cur_boot_args.video.depth & FB_DEPTH_MASK;
    fb.size = cur_boot_args.video.stride * cur_boot_args.video.height;
    printf("fb init: %dx%d (%d) [s=%d] @%p\n", fb.width, fb.height, fb.depth, fb.stride, fb.hwptr);

    mmu_add_mapping(cur_boot_args.video.base, cur_boot_args.video.base, ALIGN_UP(fb.size, 0x4000),
                    MAIR_IDX_NORMAL_NC, PERM_RW);

    fb.ptr = malloc(fb.size);
    memcpy(fb.ptr, fb.hwptr, fb.size);

    if (cur_boot_args.video.depth & FB_DEPTH_FLAG_RETINA) {
        logo = &logo_256;
        console.font.ptr = _binary_build_font_retina_bin_start;
        console.font.width = 16;
        console.font.height = 32;
    } else {
        logo = &logo_128;
        console.font.ptr = _binary_build_font_bin_start;
        console.font.width = 8;
        console.font.height = 16;
    }

    if (!orig_logo.ptr) {
        orig_logo = *logo;
        orig_logo.ptr = malloc(orig_logo.width * orig_logo.height * 4);
        fb_unblit_image((fb.width - orig_logo.width) / 2, (fb.height - orig_logo.height) / 2,
                        &orig_logo);
    }

    if (clear)
        memset32(fb.ptr, 0, fb.size);

    console.margin.rows = 2;
    console.margin.cols = 4;
    console.cursor.col = 0;
    console.cursor.row = 0;

    console.cursor.max_row = (fb.height / console.font.height) - 2 * console.margin.rows;
    console.cursor.max_col =
        ((fb.width - logo->width) / 2) / console.font.width - 2 * console.margin.cols;

    console.initialized = true;
    console.active = false;

    fb_clear_console();

    printf("fb console: max rows %d, max cols %d\n", console.cursor.max_row,
           console.cursor.max_col);
}

void fb_set_active(bool active)
{
    console.active = active;
    if (active)
        iodev_console_kick();
}

void fb_shutdown(bool restore_logo)
{
    if (!console.initialized)
        return;

    console.active = false;
    console.initialized = false;
    fb_clear_console();
    if (restore_logo) {
        fb_restore_logo();
        free(orig_logo.ptr);
        orig_logo.ptr = NULL;
    }
    free(fb.ptr);
}

void fb_reinit(void)
{
    if (!console.initialized)
        return;

    fb_shutdown(false);
    fb_init(true);
    fb_display_logo();
}
