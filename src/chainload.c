/* SPDX-License-Identifier: MIT */

#include "../build/build_cfg.h"

#include "chainload.h"
#include "adt.h"
#include "malloc.h"
#include "memory.h"
#include "nvme.h"
#include "string.h"
#include "types.h"
#include "utils.h"
#include "xnuboot.h"

#ifdef CHAINLOADING
int rust_load_image(const char *spec, void **image, size_t *size);
#endif

extern u8 _chainload_stub_start[];
extern u8 _chainload_stub_end[];

int chainload_image(void *image, size_t size, char **vars, size_t var_cnt)
{
    u64 new_base = (u64)_base;
    size_t image_size = size;

    printf("chainload: Preparing image...\n");

    // m1n1 variables
    for (size_t i = 0; i < var_cnt; i++)
        image_size += strlen(vars[i]) + 1;

    // pad to end payload
    image_size += 4;
    image_size = ALIGN_UP(image_size, SZ_16K);

    // SEPFW
    size_t sepfw_off = image_size;

    int anode = adt_path_offset(adt, "/chosen/memory-map");
    if (anode < 0) {
        printf("chainload: /chosen/memory-map not found\n");
        return -1;
    }
    u64 sepfw[2];
    if (ADT_GETPROP_ARRAY(adt, anode, "SEPFW", sepfw) < 0) {
        printf("chainload: Failed to find SEPFW\n");
        return -1;
    }

    image_size += sepfw[1];
    image_size = ALIGN_UP(image_size, SZ_16K);

    // Bootargs
    size_t bootargs_off = image_size;
    const size_t bootargs_size = SZ_16K;
    image_size += bootargs_size;

    printf("chainload: Total image size: 0x%lx\n", image_size);

    size_t stub_size = _chainload_stub_end - _chainload_stub_start;

    void *new_image = malloc(image_size + stub_size);

    // Copy m1n1
    memcpy(new_image, image, size);

    // Add vars
    u8 *p = new_image + size;
    for (size_t i = 0; i < var_cnt; i++) {
        size_t len = strlen(vars[i]);

        memcpy(p, vars[i], len);
        p[len] = '\n';
        p += len + 1;
    }

    // Add end padding
    memset(p, 0, 4);

    // Copy SEPFW
    memcpy(new_image + sepfw_off, (void *)sepfw[0], sepfw[1]);

    // Adjust ADT SEPFW address
    sepfw[0] = new_base + sepfw_off;
    if (adt_setprop(adt, anode, "SEPFW", &sepfw, sizeof(sepfw)) < 0) {
        printf("chainload: Failed to set SEPFW prop\n");
        free(new_image);
        return -1;
    }

    // Copy bootargs
    struct boot_args *new_boot_args = new_image + bootargs_off;
    *new_boot_args = cur_boot_args;
    new_boot_args->top_of_kernel_data = new_base + image_size;

    // Copy chainload stub
    void *stub = new_image + image_size;
    memcpy(stub, _chainload_stub_start, stub_size);
    dc_cvau_range(stub, stub_size);
    ic_ivau_range(stub, stub_size);

    // Set up next stage
    next_stage.entry = stub;
    next_stage.args[0] = new_base + bootargs_off;
    next_stage.args[1] = (u64)new_image;
    next_stage.args[2] = new_base;
    next_stage.args[3] = image_size;
    next_stage.args[4] = new_base + 0x800; // m1n1 entrypoint
    next_stage.restore_logo = false;

    return 0;
}

#ifdef CHAINLOADING

int chainload_load(const char *spec, char **vars, size_t var_cnt)
{
    void *image;
    size_t size;
    int ret;

    if (!nvme_init()) {
        printf("chainload: NVME init failed\n");
        return -1;
    }

    ret = rust_load_image(spec, &image, &size);
    nvme_shutdown();
    if (ret < 0)
        return ret;

    return chainload_image(image, size, vars, var_cnt);
}

#else

int chainload_load(const char *spec, char **vars, size_t var_cnt)
{
    UNUSED(spec);
    UNUSED(vars);
    UNUSED(var_cnt);

    printf("Chainloading files not supported in this build!\n");
    return -1;
}

#endif
