/* SPDX-License-Identifier: MIT */

#include "display.h"
#include "assert.h"
#include "dcp.h"
#include "dcp_iboot.h"
#include "fb.h"
#include "string.h"
#include "utils.h"
#include "xnuboot.h"

#define DISPLAY_STATUS_DELAY   100
#define DISPLAY_STATUS_RETRIES 20
#define DISPLAY_WAIT_DELAY     10

#define COMPARE(a, b)                                                                              \
    if ((a) > (b)) {                                                                               \
        *best = modes[i];                                                                          \
        continue;                                                                                  \
    } else if ((a) < (b)) {                                                                        \
        continue;                                                                                  \
    }

dcp_dev_t *dcp;
dcp_iboot_if_t *iboot;
u64 fb_dva;

#define abs(x) ((x) >= 0 ? (x) : -(x))

static void display_choose_timing_mode(dcp_timing_mode_t *modes, int cnt, dcp_timing_mode_t *best,
                                       dcp_timing_mode_t *want)
{
    *best = modes[0];

    for (int i = 1; i < cnt; i++) {
        COMPARE(modes[i].valid, best->valid);
        if (want && want->valid) {
            COMPARE(modes[i].width == want->width && modes[i].height == want->height,
                    best->width == want->width && best->height == want->height);
            COMPARE(-abs((long)modes[i].fps - (long)want->fps),
                    -abs((long)best->fps - (long)want->fps));
        }
        COMPARE(modes[i].width <= 1920, best->width <= 1920);
        COMPARE(modes[i].height <= 1200, best->height <= 1200);
        COMPARE(modes[i].fps <= 60 << 16, best->fps <= 60 << 16);
        COMPARE(modes[i].width, best->width);
        COMPARE(modes[i].height, best->height);
        COMPARE(modes[i].fps, best->fps);
    }

    printf("display: timing mode: valid=%d %dx%d %d.%02d Hz\n", best->valid, best->width,
           best->height, best->fps >> 16, ((best->fps & 0xffff) * 100 + 0x7fff) >> 16);
}

static void display_choose_color_mode(dcp_color_mode_t *modes, int cnt, dcp_color_mode_t *best)
{
    *best = modes[0];

    for (int i = 1; i < cnt; i++) {
        COMPARE(modes[i].valid, best->valid);
        COMPARE(modes[i].bpp <= 32, best->bpp <= 32);
        COMPARE(modes[i].bpp, best->bpp);
        COMPARE(-modes[i].colorimetry, -best->colorimetry);
        COMPARE(-modes[i].encoding, -best->encoding);
        COMPARE(-modes[i].eotf, -best->eotf);
    }

    printf("display: color mode: valid=%d colorimetry=%d eotf=%d encoding=%d bpp=%d\n", best->valid,
           best->colorimetry, best->eotf, best->encoding, best->bpp);
}

static int display_start_dcp(void)
{
    if (iboot)
        return 0;

    dcp = dcp_init("/arm-io/dcp", "/arm-io/dart-dcp", "/arm-io/dart-disp0");
    if (!dcp) {
        printf("display: failed to initialize DCP\n");
        return -1;
    }

    // Find the framebuffer DVA
    fb_dva = dart_search(dcp->dart_disp, (void *)cur_boot_args.video.base);
    if (!fb_dva) {
        printf("display: failed to find display DVA\n");
        dcp_shutdown(dcp);
        return -1;
    }

    iboot = dcp_ib_init(dcp);
    if (!iboot) {
        printf("display: failed to initialize DCP iBoot interface\n");
        dcp_shutdown(dcp);
        return -1;
    }

    return 0;
}

int display_parse_mode(const char *config, dcp_timing_mode_t *mode, int *wait_delay)
{
    memset(mode, 0, sizeof(*mode));
    *wait_delay = 0;

    if (!config)
        return 0;

    if (!strncmp(config, "wait", sizeof("wait") - 1)) {
        int delay = 0;
        config += sizeof("wait") - 1;
        if (*config == ':') {
            config += 1;
            for (char c = *config; '0' <= c && c <= '9'; c = *(++config)) {
                delay = (delay * 10) + (c - '0');
            }
        }

        if (delay <= 0) {
            delay = DISPLAY_WAIT_DELAY;
        }

        printf("display: wait enabled (max delay %ds)\n", delay);
        *wait_delay = delay;

        if (*config == ',') {
            config += 1;
        }
    }

    if (!*config || !strcmp(config, "auto"))
        return 0;

    const char *s_w = config;
    const char *s_h = strchr(config, 'x');
    const char *s_fps = strchr(config, '@');

    if (s_w && s_h) {
        mode->width = atol(s_w);
        mode->height = atol(s_h + 1);
        mode->valid = mode->width && mode->height;
    }

    if (s_fps) {
        mode->fps = atol(s_fps + 1) << 16;

        const char *s_fps_frac = strchr(s_fps + 1, '.');
        if (s_fps_frac) {
            // Assumes two decimals...
            mode->fps += (atol(s_fps_frac + 1) << 16) / 100;
        }
    }

    printf("display: want mode: valid=%d %dx%d %d.%02d Hz\n", mode->valid, mode->width,
           mode->height, mode->fps >> 16, ((mode->fps & 0xffff) * 100 + 0x7fff) >> 16);

    return mode->valid;
}

int display_wait_connected(dcp_iboot_if_t *iboot, int *timing_cnt, int *color_cnt)
{
    int hpd;

    for (int retries = 0; retries < DISPLAY_STATUS_RETRIES; retries += 1) {
        hpd = dcp_ib_get_hpd(iboot, timing_cnt, color_cnt);
        if ((hpd > 0) && *timing_cnt && *color_cnt) {
            printf("display: waited %d ms for display connected\n", retries * DISPLAY_STATUS_DELAY);
            return 1;
        }

        mdelay(DISPLAY_STATUS_DELAY);
    }

    // hpd is 0 if no display, negative if an error occurred
    return hpd;
}

int display_wait_disconnected(dcp_iboot_if_t *iboot, int wait_delay)
{
    int hpd, timing_cnt, color_cnt;
    int max_retries = wait_delay * 1000 / DISPLAY_STATUS_DELAY;

    for (int retries = 0; retries < max_retries; retries += 1) {
        hpd = dcp_ib_get_hpd(iboot, &timing_cnt, &color_cnt);
        if (hpd < 0) {
            return hpd;
        }

        if (!hpd) {
            printf("display: waited %d ms for display disconnected\n",
                   retries * DISPLAY_STATUS_DELAY);
            return 1;
        }

        mdelay(DISPLAY_STATUS_DELAY);
    }

    return 0;
}

int display_configure(const char *config)
{
    dcp_timing_mode_t want;
    int wait_delay;

    display_parse_mode(config, &want, &wait_delay);

    int ret = display_start_dcp();
    if (ret < 0)
        return ret;

    // Power on
    if ((ret = dcp_ib_set_power(iboot, true)) < 0) {
        printf("display: failed to set power\n");
        return ret;
    }

    // Detect if display is connected
    int timing_cnt, color_cnt;

    if (wait_delay) {
        // Some monitors disconnect when getting out of sleep mode.
        // Wait a bit to see if that happens.
        printf("display: waiting for monitor disconnect\n");
        if ((ret = display_wait_disconnected(iboot, wait_delay)) < 0) {
            printf("display: failed to wait for disconnect\n");
            return -1;
        }

        if (!ret) {
            printf("display: did not disconnect\n");
        }
    }

    /* After boot DCP does not immediately report a connected display. Retry getting display
     * information for 2 seconds.
     */
    if ((ret = display_wait_connected(iboot, &timing_cnt, &color_cnt)) < 0) {
        printf("display: failed to get display status\n");
        return 0;
    }

    printf("display: connected:%d timing_cnt:%d color_cnt:%d\n", ret, timing_cnt, color_cnt);

    if (!ret || !timing_cnt || !color_cnt)
        return 0;

    // Find best modes
    dcp_timing_mode_t *tmodes, tbest;
    if ((ret = dcp_ib_get_timing_modes(iboot, &tmodes)) < 0) {
        printf("display: failed to get timing modes\n");
        return -1;
    }
    assert(ret == timing_cnt);
    display_choose_timing_mode(tmodes, timing_cnt, &tbest, &want);

    dcp_color_mode_t *cmodes, cbest;
    if ((ret = dcp_ib_get_color_modes(iboot, &cmodes)) < 0) {
        printf("display: failed to get color modes\n");
        return -1;
    }
    assert(ret == color_cnt);
    display_choose_color_mode(cmodes, color_cnt, &cbest);

    // Set mode
    if ((ret = dcp_ib_set_mode(iboot, &tbest, &cbest)) < 0) {
        printf("display: failed to set mode\n");
        return -1;
    }

    // Swap!
    int swap_id = ret = dcp_ib_swap_begin(iboot);
    if (swap_id < 0) {
        printf("display: failed to start swap\n");
        return -1;
    }

    dcp_layer_t layer = {
        .planes = {{
            .addr = fb_dva,
            .stride = tbest.width * 4,
            .addr_format = ADDR_PLANAR,
        }},
        .plane_cnt = 1,
        .width = tbest.width,
        .height = tbest.height,
        .surface_fmt = FMT_w30r,
        .colorspace = 2,
        .eotf = EOTF_GAMMA_SDR,
        .transform = XFRM_NONE,
    };

    dcp_rect_t rect = {tbest.width, tbest.height, 0, 0};

    if ((ret = dcp_ib_swap_set_layer(iboot, 0, &layer, &rect, &rect)) < 0) {
        printf("display: failed to set layer\n");
        return -1;
    }

    if ((ret = dcp_ib_swap_end(iboot)) < 0) {
        printf("display: failed to complete swap\n");
        return -1;
    }

    printf("display: swapped! (swap_id=%d)\n", swap_id);

    if (cur_boot_args.video.stride != layer.planes[0].stride ||
        cur_boot_args.video.width != layer.width || cur_boot_args.video.height != layer.height ||
        cur_boot_args.video.depth != 30) {
        cur_boot_args.video.stride = layer.planes[0].stride;
        cur_boot_args.video.width = layer.width;
        cur_boot_args.video.height = layer.height;
        cur_boot_args.video.depth = 30;
        fb_reinit();
    }

    /* Update for python / subsequent stages */
    memcpy((void *)boot_args_addr, &cur_boot_args, sizeof(cur_boot_args));

    return 1;
}

int display_init(void)
{
    if (cur_boot_args.video.width == 640 && cur_boot_args.video.height == 1136) {
        printf("display: Dummy framebuffer found, initializing display\n");

        return display_configure(NULL);
    } else {
        printf("display: Display is already initialized (%ldx%ld)\n", cur_boot_args.video.width,
               cur_boot_args.video.height);
        return 0;
    }
}

void display_shutdown(void)
{
    if (iboot) {
        dcp_ib_shutdown(iboot);
        dcp_shutdown(dcp);
    }
}
