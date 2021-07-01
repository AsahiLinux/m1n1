/* SPDX-License-Identifier: MIT */

#include "kboot.h"
#include "adt.h"
#include "assert.h"
#include "cpio.h"
#include "exception.h"
#include "malloc.h"
#include "memory.h"
#include "pcie.h"
#include "smp.h"
#include "types.h"
#include "usb.h"
#include "utils.h"
#include "xnuboot.h"

#include "libfdt/libfdt.h"

static void *dt = NULL;
static int dt_bufsize = 0;
static char *bootargs = NULL;
static void *initrd_start = NULL;
static size_t initrd_size = 0;

#define DT_ALIGN     16384
#define INITRD_ALIGN 65536

#define bail(...)                                                                                  \
    do {                                                                                           \
        printf(__VA_ARGS__);                                                                       \
        return -1;                                                                                 \
    } while (0)

static int dt_set_chosen(void)
{

    int node = fdt_path_offset(dt, "/chosen");
    if (node < 0)
        bail("FDT: /chosen node not found in devtree\n");

    if (bootargs) {
        if (fdt_setprop(dt, node, "bootargs", bootargs, strlen(bootargs) + 1) < 0)
            bail("FDT: couldn't set chosen.bootargs property\n");

        printf("FDT: bootargs = '%s'\n", bootargs);
    }

    if (initrd_start && initrd_size) {
        if (fdt_setprop_u64(dt, node, "linux,initrd-start", (u64)initrd_start))
            bail("FDT: couldn't set chosen.linux,initrd-start property\n");

        u64 end = ((u64)initrd_start) + initrd_size;
        if (fdt_setprop_u64(dt, node, "linux,initrd-end", end))
            bail("FDT: couldn't set chosen.linux,initrd-end property\n");

        if (fdt_add_mem_rsv(dt, (u64)initrd_start, initrd_size))
            bail("FDT: couldn't add reservation for the initrd\n");

        printf("FDT: initrd at %p size 0x%lx\n", initrd_start, initrd_size);
    }

    if (cur_boot_args.video.base) {
        int fb = fdt_path_offset(dt, "/chosen/framebuffer");
        if (fb < 0)
            bail("FDT: /chosen node not found in devtree\n");

        u64 fb_base = cur_boot_args.video.base;
        u64 fb_size = cur_boot_args.video.stride * cur_boot_args.video.height;
        u64 fbreg[2] = {cpu_to_fdt64(fb_base), cpu_to_fdt64(fb_size)};
        char fbname[32];

        sprintf(fbname, "framebuffer@%lx", fb_base);

        if (fdt_setprop(dt, fb, "reg", fbreg, sizeof(fbreg)))
            bail("FDT: couldn't set framebuffer.reg property\n");

        if (fdt_set_name(dt, fb, fbname))
            bail("FDT: couldn't set framebuffer name\n");

        if (fdt_setprop_u32(dt, fb, "width", cur_boot_args.video.width))
            bail("FDT: couldn't set framebuffer width\n");

        if (fdt_setprop_u32(dt, fb, "height", cur_boot_args.video.height))
            bail("FDT: couldn't set framebuffer height\n");

        if (fdt_setprop_u32(dt, fb, "stride", cur_boot_args.video.stride))
            bail("FDT: couldn't set framebuffer stride\n");

        const char *format = NULL;

        switch (cur_boot_args.video.depth & 0xff) {
            case 32:
                format = "x8r8g8b8";
                break;
            case 30:
                format = "x2r10g10b10";
                break;
            case 16:
                format = "r5g6b5";
                break;
            default:
                printf("FDT: unsupported fb depth %lu, not enabling\n", cur_boot_args.video.depth);
                return 0; // Do not error out, but don't set the FB
        }

        if (fdt_setprop_string(dt, fb, "format", format))
            bail("FDT: couldn't set framebuffer format\n");

        fdt_delprop(dt, fb, "status"); // may fail if it does not exist

        printf("FDT: %s base 0x%lx size 0x%lx\n", fbname, fb_base, fb_size);

        // We do not need to reserve the framebuffer, as it will be excluded from the usable RAM
        // range already.
    }

    int anode = adt_path_offset(adt, "/chosen");

    if (anode < 0)
        bail("ADT: /chosen not found\n");

    const uint8_t *random_seed;
    u32 seed_length;

    random_seed = adt_getprop(adt, anode, "random-seed", &seed_length);
    if (random_seed) {
        printf("ADT: %d bytes of random seed available\n", seed_length);

        if (seed_length >= sizeof(u64)) {
            u64 kaslr_seed;

            memcpy(&kaslr_seed, random_seed, sizeof(kaslr_seed));

            // Ideally we would throw away the kaslr_seed part of random_seed
            // and avoid reusing it. However, Linux wants 64 bytes of bootloader
            // random seed to consider its CRNG initialized, which is exactly
            // how much iBoot gives us. This probably doesn't matter, since
            // that entropy is going to get shuffled together and Linux makes
            // sure to clear the FDT randomness after using it anyway, but just
            // in case let's mix in a few bits from our own KASLR base to make
            // kaslr_seed unique.

            kaslr_seed ^= (u64)cur_boot_args.virt_base;

            if (fdt_setprop_u64(dt, node, "kaslr-seed", kaslr_seed))
                bail("FDT: couldn't set kaslr-seed\n");

            printf("FDT: KASLR seed initialized\n");
        } else {
            printf("ADT: not enough random data for kaslr-seed\n");
        }

        if (seed_length) {
            if (fdt_setprop(dt, node, "rng-seed", random_seed, seed_length))
                bail("FDT: couldn't set rng-seed\n");

            printf("FDT: Passing %d bytes of random seed\n", seed_length);
        }
    } else {
        printf("ADT: no random-seed available!\n");
    }

    return 0;
}

static int dt_set_memory(void)
{
    int anode = adt_path_offset(adt, "/chosen");

    if (anode < 0)
        bail("ADT: /chosen not found\n");

    u64 dram_base, dram_size;

    if (ADT_GETPROP(adt, anode, "dram-base", &dram_base) < 0)
        bail("ADT: Failed to get dram-base\n");
    if (ADT_GETPROP(adt, anode, "dram-size", &dram_size) < 0)
        bail("ADT: Failed to get dram-size\n");

    // Tell the kernel our usable memory range. We cannot declare all of DRAM, and just reserve the
    // bottom and top, because the kernel would still map it (and just not use it), which breaks
    // ioremap (e.g. simplefb).

    u64 dram_min = cur_boot_args.phys_base;
    u64 dram_max = cur_boot_args.phys_base + cur_boot_args.mem_size;

    printf("FDT: DRAM at 0x%lx size 0x%lx\n", dram_base, dram_size);
    printf("FDT: Usable memory is 0x%lx..0x%lx (0x%lx)\n", dram_min, dram_max, dram_max - dram_min);

    u64 memreg[2] = {cpu_to_fdt64(dram_min), cpu_to_fdt64(dram_max - dram_min)};

    int node = fdt_path_offset(dt, "/memory");
    if (node < 0)
        bail("FDT: /memory node not found in devtree\n");

    if (fdt_setprop(dt, node, "reg", memreg, sizeof(memreg)))
        bail("FDT: couldn't set memory.reg property\n");

    return 0;
}

static int dt_set_cpus(void)
{
    int cpus = fdt_path_offset(dt, "/cpus");
    if (cpus < 0)
        bail("FDT: /cpus node not found in devtree\n");

    int node, cpu = 0;
    fdt_for_each_subnode(node, dt, cpus)
    {
        const fdt64_t *prop = fdt_getprop(dt, node, "reg", NULL);
        if (!prop)
            bail("FDT: failed to get reg property of CPU\n");

        u64 dt_mpidr = fdt64_ld(prop);

        if (dt_mpidr == (mrs(MPIDR_EL1) & 0xFFFFFF))
            goto next;

        if (!smp_is_alive(cpu)) {
            printf("FDT: CPU %d is not alive, disabling...\n", cpu);
            if (fdt_setprop_string(dt, node, "status", "disabled"))
                bail("FDT: couldn't set status property\n");
            goto next;
        }

        u64 mpidr = smp_get_mpidr(cpu);

        if (dt_mpidr != mpidr)
            bail("FDT: DT CPU %d MPIDR mismatch: 0x%lx != 0x%lx\n", cpu, dt_mpidr, mpidr);

        u64 release_addr = smp_get_release_addr(cpu);
        if (fdt_setprop_u64(dt, node, "cpu-release-addr", release_addr))
            bail("FDT: couldn't set cpu-release-addr property\n");

        printf("FDT: CPU %d MPIDR=0x%lx release-addr=0x%lx\n", cpu, mpidr, release_addr);

    next:
        cpu++;
    }

    if ((node < 0) && (node != -FDT_ERR_NOTFOUND)) {
        bail("FDT: error iterating through CPUs\n");
    }

    return 0;
}

static const char *aliases[] = {
    "bluetooth0",
    "ethernet0",
    "wifi0",
};

static int dt_set_mac_addresses(void)
{
    int anode = adt_path_offset(adt, "/chosen");

    if (anode < 0)
        bail("ADT: /chosen not found\n");

    for (size_t i = 0; i < sizeof(aliases) / sizeof(*aliases); i++) {
        char propname[32];
        sprintf(propname, "mac-address-%s", aliases[i]);

        uint8_t addr[6];
        if (ADT_GETPROP_ARRAY(adt, anode, propname, addr) < 0)
            continue;

        const char *path = fdt_get_alias(dt, aliases[i]);
        if (path == NULL)
            continue;

        int node = fdt_path_offset(dt, path);
        if (node < 0)
            continue;

        fdt_setprop(dt, node, "local-mac-address", addr, sizeof(addr));
    }

    return 0;
}

void kboot_set_initrd(void *start, size_t size)
{
    initrd_start = start;
    initrd_size = size;
}

void kboot_set_bootargs(const char *ba)
{
    if (bootargs)
        free(bootargs);

    if (!ba) {
        bootargs = NULL;
        return;
    }

    bootargs = malloc(strlen(ba) + 1);
    strcpy(bootargs, ba);
}

int kboot_prepare_dt(void *fdt)
{
    if (dt) {
        free(dt);
        dt = NULL;
    }

    if (kboot_prepare_fw() < 0)
        bail("FDT: couldn't prepare firmware.");

    dt_bufsize = fdt_totalsize(fdt);
    assert(dt_bufsize);

    dt_bufsize += 64 * 1024; // Add 64K of buffer for modifications
    dt = memalign(DT_ALIGN, dt_bufsize);

    if (fdt_open_into(fdt, dt, dt_bufsize) < 0)
        bail("FDT: fdt_open_into() failed\n");

    if (fdt_add_mem_rsv(dt, (u64)dt, dt_bufsize))
        bail("FDT: couldn't add reservation for the devtree\n");

    if (fdt_add_mem_rsv(dt, (u64)_base, ((u64)_end) - ((u64)_base)))
        bail("FDT: couldn't add reservation for m1n1\n");

    if (dt_set_chosen())
        return -1;
    if (dt_set_memory())
        return -1;
    if (dt_set_cpus())
        return -1;
    if (dt_set_mac_addresses())
        return -1;

    if (fdt_pack(dt))
        bail("FDT: fdt_pack() failed\n");

    printf("FDT prepared at %p\n", dt);

    return 0;
}

static int kboot_prepare_sepfw(struct cpio *c)
{
    int adt_path[8];
    int adt_offset;
    adt_offset = adt_path_offset_trace(adt, "/chosen/memory-map", adt_path);
    if (adt_offset < 0) {
        printf("kboot: Error getting /chosen/memory-map node\n");
        return -1;
    }

    u64 base;
    u64 sz;
    if (adt_get_reg(adt, adt_path, "SEPFW", 0, &base, &sz) < 0) {
        printf("kboot: Error getting SEPFW\n");
        return -1;
    }

    if (cpio_add_file(c, "lib/firmware/apple/sepfw.bin", (const u8 *)base, sz) < 0) {
        printf("kboot: unable to add lib/firmware/apple/sepfw.bin\n");
        return -1;
    }

    return 0;
}

int kboot_prepare_fw(void)
{
    struct cpio *c = cpio_init();
    u8 *cpio_start = NULL;
    u8 *new_initrd_start = NULL;
    size_t cpio_size = 0;
    u32 new_initrd_size = 0;

    if (cpio_add_dir(c, "lib") < 0)
        goto err;
    if (cpio_add_dir(c, "lib/firmware") < 0)
        goto err;
    if (cpio_add_dir(c, "lib/firmware/apple") < 0)
        goto err;

    if (kboot_prepare_sepfw(c) < 0)
        printf("kboot: no SEPFW found.\n");

    cpio_size = cpio_get_size(c);
    new_initrd_size = cpio_size + ALIGN_UP(initrd_size, 4);
    new_initrd_start = memalign(INITRD_ALIGN, new_initrd_size);
    if (!new_initrd_start) {
        printf("kboot: couldn't allocate initrd buffer\n");
        goto err;
    }

    memcpy(new_initrd_start, initrd_start, initrd_size);

    cpio_start = new_initrd_start + ALIGN_UP(initrd_size, 4);
    size_t res = cpio_finalize(c, cpio_start, cpio_size);
    if (res != cpio_size) {
        printf("kboot: unexpected cpio_finalize size: %lu should be %lu\n", res, cpio_size);
        goto err;
    }

    initrd_start = new_initrd_start;
    initrd_size = new_initrd_size;
    cpio_free(c);

    return 0;

err:
    free(new_initrd_start);
    cpio_free(c);
    return -1;
}

int kboot_boot(void *kernel)
{
    usb_init();
    pcie_init();

    printf("Preparing to boot kernel at %p with fdt at %p\n", kernel, dt);

    next_stage.entry = kernel;
    next_stage.args[0] = (u64)dt;
    next_stage.args[1] = 0;
    next_stage.args[2] = 0;
    next_stage.args[3] = 0;

    return 0;
}
