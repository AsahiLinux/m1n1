/* SPDX-License-Identifier: MIT */

#include <stdint.h>

#include "kboot.h"
#include "adt.h"
#include "assert.h"
#include "clk.h"
#include "dapf.h"
#include "devicetree.h"
#include "display.h"
#include "exception.h"
#include "firmware.h"
#include "iodev.h"
#include "isp.h"
#include "kboot_atc.h"
#include "malloc.h"
#include "mcc.h"
#include "memory.h"
#include "pcie.h"
#include "pmgr.h"
#include "sep.h"
#include "sio.h"
#include "smp.h"
#include "tunables.h"
#include "types.h"
#include "usb.h"
#include "utils.h"
#include "xnuboot.h"

#include "libfdt/libfdt.h"

#define MAX_CHOSEN_PARAMS 16

#define MAX_ATC_DEVS 8
#define MAX_CIO_DEVS 8

#define MAX_DISP_MAPPINGS 8

#define MAX_MEM_REGIONS 32

static void *dt = NULL;
static int dt_bufsize = 0;
static void *initrd_start = NULL;
static size_t initrd_size = 0;
static char *chosen_params[MAX_CHOSEN_PARAMS][2];

extern const char *const m1n1_version;

int dt_set_gpu(void *dt);

#define DT_ALIGN 16384

#define bail(...)                                                                                  \
    do {                                                                                           \
        printf(__VA_ARGS__);                                                                       \
        return -1;                                                                                 \
    } while (0)

#define bail_cleanup(...)                                                                          \
    do {                                                                                           \
        printf(__VA_ARGS__);                                                                       \
        ret = -1;                                                                                  \
        goto err;                                                                                  \
    } while (0)

void get_notchless_fb(u64 *fb_base, u64 *fb_height)
{
    *fb_base = cur_boot_args.video.base;
    *fb_height = cur_boot_args.video.height;

    int node = adt_path_offset(adt, "/product");

    if (node < 0) {
        printf("FDT: /product node not found\n");
        return;
    }

    u32 val;

    if ((ADT_GETPROP(adt, node, "partially-occluded-display", &val) < 0 || !val) &&
        (chip_id != T8015 || (board_id != 0x6 && board_id != 0xe))) {
        printf("FDT: No notch detected\n");
        return;
    }

    u64 hfrac = cur_boot_args.video.height * 16 / cur_boot_args.video.width;
    u64 new_height = cur_boot_args.video.width * hfrac / 16;
    if (chip_id == T8015 && (board_id == 0x6 || board_id == 0xe))
        new_height = 2346;

    if (new_height == cur_boot_args.video.height) {
        printf("FDT: Notch detected, but display aspect is already 16:%lu?\n", hfrac);
        return;
    }

    u64 offset = cur_boot_args.video.height - new_height;

    printf("display: Hiding notch, %lux%lu -> %lux%lu (+%lu, 16:%lu)\n", cur_boot_args.video.width,
           cur_boot_args.video.height, cur_boot_args.video.width, new_height, offset, hfrac);

    *fb_base += cur_boot_args.video.stride * offset;
    *fb_height = new_height;
}

static int dt_set_rng_seed_sep(int node)
{
    u64 kaslr_seed;
    uint8_t rng_seed[128]; // same size used by Linux for kexec

    if (sep_get_random(&kaslr_seed, sizeof(kaslr_seed)) != sizeof(kaslr_seed))
        bail("SEP: couldn't get enough random bytes for KASLR seed\n");
    if (sep_get_random(rng_seed, sizeof(rng_seed)) != sizeof(rng_seed))
        bail("SEP: couldn't get enough random bytes for RNG seed\n");

    if (fdt_setprop_u64(dt, node, "kaslr-seed", kaslr_seed))
        bail("FDT: couldn't set kaslr-seed\n");
    if (fdt_setprop(dt, node, "rng-seed", rng_seed, sizeof(rng_seed)))
        bail("FDT: couldn't set rng-seed\n");

    printf("FDT: Passing %ld bytes of KASLR seed and %ld bytes of random seed\n",
           sizeof(kaslr_seed), sizeof(rng_seed));

    return 0;
}

static int dt_set_rng_seed_adt(int node)
{
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

static int dt_set_chosen(void)
{

    int node = fdt_path_offset(dt, "/chosen");
    if (node < 0)
        bail("FDT: /chosen node not found in devtree\n");

    for (int i = 0; i < MAX_CHOSEN_PARAMS; i++) {
        if (!chosen_params[i][0])
            break;

        const char *name = chosen_params[i][0];
        const char *value = chosen_params[i][1];
        if (fdt_setprop(dt, node, name, value, strlen(value) + 1) < 0)
            bail("FDT: couldn't set chosen.%s property\n", name);
        printf("FDT: %s = '%s'\n", name, value);
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

        u64 fb_base, fb_height;
        get_notchless_fb(&fb_base, &fb_height);
        u64 fb_size = cur_boot_args.video.stride * fb_height;
        u64 fbreg[2] = {cpu_to_fdt64(fb_base), cpu_to_fdt64(fb_size)};
        char fbname[32];

        snprintf(fbname, sizeof(fbname), "framebuffer@%lx", fb_base);

        if (fdt_setprop(dt, fb, "reg", fbreg, sizeof(fbreg)))
            bail("FDT: couldn't set framebuffer.reg property\n");

        if (fdt_set_name(dt, fb, fbname))
            bail("FDT: couldn't set framebuffer name\n");

        if (fdt_setprop_u32(dt, fb, "width", cur_boot_args.video.width))
            bail("FDT: couldn't set framebuffer width\n");

        if (fdt_setprop_u32(dt, fb, "height", fb_height))
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

        // save notch height in the dcp node if present
        if (cur_boot_args.video.height - fb_height) {
            int dcp = fdt_path_offset(dt, "dcp");
            if (dcp >= 0)
                if (fdt_appendprop_u32(dt, dcp, "apple,notch-height",
                                       cur_boot_args.video.height - fb_height))
                    printf("FDT: couldn't set apple,notch-height\n");
        }
    }
    node = fdt_path_offset(dt, "/chosen");
    if (node < 0)
        bail("FDT: /chosen node not found in devtree\n");

    if (is_mac) {
        if (fdt_setprop(dt, node, "asahi,iboot1-version", system_firmware.iboot,
                        strlen(system_firmware.iboot) + 1))
            bail("FDT: couldn't set asahi,iboot1-version\n");

        if (fdt_setprop(dt, node, "asahi,system-fw-version", system_firmware.string,
                        strlen(system_firmware.string) + 1))
            bail("FDT: couldn't set asahi,system-fw-version\n");
    }

    if (fdt_setprop(dt, node, "asahi,iboot2-version", os_firmware.iboot,
                    strlen(os_firmware.iboot) + 1))
        bail("FDT: couldn't set asahi,iboot2-version\n");

    if (fdt_setprop(dt, node, "asahi,os-fw-version", os_firmware.string,
                    strlen(os_firmware.string) + 1))
        bail("FDT: couldn't set asahi,os-fw-version\n");

    if (fdt_setprop(dt, node, "asahi,m1n1-stage2-version", m1n1_version, strlen(m1n1_version) + 1))
        bail("FDT: couldn't set asahi,m1n1-stage2-version\n");

    if (dt_set_rng_seed_sep(node))
        return dt_set_rng_seed_adt(node);

    return 0;
}

static int dt_set_memory(void)
{
    int anode = adt_path_offset(adt, "/chosen");

    if (anode < 0)
        bail("ADT: /chosen not found\n");

    u64 dram_base = 0, dram_size = 0;

    // iOS 12 and below seems to be missing a bunch of stuff...
    if (ADT_GETPROP(adt, anode, "dram-base", &dram_base) < 0) {
        printf("ADT: Failed to get dram-base\n");
        dram_base = 0x800000000;
    }

    if (ADT_GETPROP(adt, anode, "dram-size", &dram_size) < 0) {
        printf("ADT: Failed to get dram-size\n");
        dram_size = mem_size_actual;
    }

    // Tell the kernel our usable memory range. We cannot declare all of DRAM, and just reserve the
    // bottom and top, because the kernel would still map it (and just not use it), which breaks
    // ioremap (e.g. simplefb).

    u64 dram_min = cur_boot_args.phys_base;
    u64 dram_max = cur_boot_args.phys_base + cur_boot_args.mem_size;

    printf("FDT: DRAM at 0x%lx size 0x%lx\n", dram_base, dram_size);
    printf("FDT: Usable memory is 0x%lx..0x%lx (0x%lx)\n", dram_min, dram_max, dram_max - dram_min);

    struct {
        fdt64_t start;
        fdt64_t size;
    } memreg[MAX_MEM_REGIONS] = {{cpu_to_fdt64(dram_min), cpu_to_fdt64(dram_max - dram_min)}};
    int num_regions = 1;

    int resv_node = fdt_path_offset(dt, "/reserved-memory");
    if (resv_node < 0) {
        printf("FDT: '/reserved-memory' not found\n");
    } else {
        int node;

        /* Find all reserved memory nodes */
        fdt_for_each_subnode(node, dt, resv_node)
        {
            const char *name = fdt_get_name(dt, node, NULL);
            const char *status = fdt_getprop(dt, node, "status", NULL);
            if (status && !strcmp(status, "disabled"))
                continue;

            if (fdt_getprop(dt, node, "no-map", NULL))
                continue;

            const fdt64_t *reg = fdt_getprop(dt, node, "reg", NULL);
            if (!reg)
                continue;

            u64 resv_start = fdt64_to_cpu(reg[0]);
            u64 resv_len = fdt64_to_cpu(reg[1]);
            u64 resv_end = resv_start + resv_len;

            if (resv_start < dram_min) {
                if (resv_end > dram_min) {
                    bail("FDT: reserved-memory node %s intersects start of RAM (%lx..%lx "
                         "%lx..%lx)\n",
                         name, resv_start, resv_end, dram_min, dram_max);
                }
            } else if (resv_end > dram_max) {
                if (resv_start < dram_max) {
                    bail("FDT: reserved-memory node %s intersects end of RAM (%lx..%lx %lx..%lx)\n",
                         name, resv_start, resv_end, dram_min, dram_max);
                }
            } else {
                continue;
            }

            if ((resv_start | resv_len) & (get_page_size() - 1)) {
                bail("FDT: reserved-memory node %s not page-aligned, ignoring (%lx..%lx)\n", name,
                     resv_start, resv_end);
                continue;
            }

            printf("FDT: Adding reserved-memory node %s (%lx..%lx) to RAM map\n", name, resv_start,
                   resv_end);

            if (num_regions >= MAX_MEM_REGIONS) {
                bail("FDT: Out of memory regions for reserved-memory\n");
            }

            memreg[num_regions].start = cpu_to_fdt64(resv_start);
            memreg[num_regions++].size = cpu_to_fdt64(resv_len);
        }
    }

    int node = fdt_path_offset(dt, "/memory");
    if (node < 0)
        bail("FDT: /memory node not found in devtree\n");

    if (fdt_setprop(dt, node, "reg", memreg, sizeof(memreg[0]) * num_regions))
        bail("FDT: couldn't set memory.reg property\n");

    return 0;
}

static int dt_set_serial_number(void)
{

    int fdt_root = fdt_path_offset(dt, "/");
    int adt_root = adt_path_offset(adt, "/");

    if (fdt_root < 0)
        bail("FDT: could not open a handle to FDT root.\n");
    if (adt_root < 0)
        bail("ADT: could not open a handle to ADT root.\n");

    u32 sn_len;
    const char *serial_number = adt_getprop(adt, adt_root, "serial-number", &sn_len);
    if (fdt_setprop_string(dt, fdt_root, "serial-number", serial_number))
        bail("FDT: unable to set device serial number!\n");
    printf("FDT: reporting device serial number: %s\n", serial_number);

    return 0;
}

static int dt_set_cpus(void)
{
    int ret = 0;

    int cpus = fdt_path_offset(dt, "/cpus");
    if (cpus < 0)
        bail("FDT: /cpus node not found in devtree\n");

    uint32_t *pruned_phandles = calloc(MAX_CPUS, sizeof(uint32_t));
    size_t pruned = 0;
    if (!pruned_phandles)
        bail("FDT: out of memory\n");

    /* Prune CPU nodes */
    int node, cpu = 0;
    for (node = fdt_first_subnode(dt, cpus); node >= 0;) {
        const char *name = fdt_get_name(dt, node, NULL);
        if (strncmp(name, "cpu@", 4))
            goto next_node;

        if (cpu > MAX_CPUS)
            bail_cleanup("Maximum number of CPUs exceeded, consider increasing MAX_CPUS\n");

        const fdt64_t *prop = fdt_getprop(dt, node, "reg", NULL);
        if (!prop)
            bail_cleanup("FDT: failed to get reg property of CPU\n");

        u64 dt_mpidr = fdt64_ld(prop);

        if (dt_mpidr == (mrs(MPIDR_EL1) & 0xFFFFFF))
            goto next_cpu;

        if (!smp_is_alive(cpu)) {
            printf("FDT: CPU %d is not alive, disabling...\n", cpu);
            pruned_phandles[pruned++] = fdt_get_phandle(dt, node);

            int next = fdt_next_subnode(dt, node);
            fdt_nop_node(dt, node);
            cpu++;
            node = next;
            continue;
        } else {
            printf("FDT: Reserving stack for CPU %d 0x%lx\n", cpu, (uint64_t)secondary_stacks[cpu]);
            fdt_add_mem_rsv(dt, (uint64_t)secondary_stacks[cpu], SECONDARY_STACK_SIZE);
            if (has_el3()) {
                printf("FDT: Reserving EL3 stack for CPU %d 0x%lx\n", cpu,
                       (uint64_t)secondary_stacks_el3[cpu]);
                fdt_add_mem_rsv(dt, (uint64_t)secondary_stacks_el3[cpu], SECONDARY_STACK_SIZE);
            }
        }

        u64 mpidr = smp_get_mpidr(cpu);

        if (dt_mpidr != mpidr)
            bail_cleanup("FDT: DT CPU %d MPIDR mismatch: 0x%lx != 0x%lx\n", cpu, dt_mpidr, mpidr);

        u64 release_addr = smp_get_release_addr(cpu);
        if (fdt_setprop_inplace_u64(dt, node, "cpu-release-addr", release_addr))
            bail_cleanup("FDT: couldn't set cpu-release-addr property\n");

        printf("FDT: CPU %d MPIDR=0x%lx release-addr=0x%lx\n", cpu, mpidr, release_addr);

    next_cpu:
        cpu++;
    next_node:
        node = fdt_next_subnode(dt, node);
    }

    if ((node < 0) && (node != -FDT_ERR_NOTFOUND)) {
        bail_cleanup("FDT: error iterating through CPUs\n");
    }

    /* Prune AIC PMU affinities */
    int aic = fdt_node_offset_by_compatible(dt, -1, "apple,aic");
    if (aic == -FDT_ERR_NOTFOUND)
        aic = fdt_node_offset_by_compatible(dt, -1, "apple,aic2");
    if (aic == -FDT_ERR_NOTFOUND)
        aic = fdt_node_offset_by_compatible(dt, -1, "apple,aic3");
    if (aic < 0)
        bail_cleanup("FDT: Failed to find AIC node\n");

    int affinities = fdt_subnode_offset(dt, aic, "affinities");
    if (affinities < 0) {
        printf("FDT: Failed to find AIC affinities node, ignoring...\n");
    } else {
        int node;
        for (node = fdt_first_subnode(dt, affinities); node >= 0;
             node = fdt_next_subnode(dt, node)) {
            int len;
            const fdt32_t *phs = fdt_getprop(dt, node, "cpus", &len);
            if (!phs)
                bail_cleanup("FDT: Failed to find cpus property under AIC affinity\n");

            fdt32_t *new_phs = calloc(len, 1);
            size_t index = 0;
            size_t count = len / sizeof(fdt32_t);

            for (size_t i = 0; i < count; i++) {
                uint32_t phandle = fdt32_ld(&phs[i]);
                bool prune = false;

                for (size_t j = 0; j < pruned; j++) {
                    if (pruned_phandles[j] == phandle) {
                        prune = true;
                        break;
                    }
                }
                if (!prune)
                    new_phs[index++] = phs[i];
            }

            ret = fdt_setprop(dt, node, "cpus", new_phs, sizeof(fdt32_t) * index);
            free(new_phs);

            if (ret < 0)
                bail_cleanup("FDT: Failed to set cpus property under AIC affinity\n");

            const char *name = fdt_get_name(dt, node, NULL);
            printf("FDT: Pruned %ld/%ld CPU references in [AIC]/affinities/%s\n", count - index,
                   count, name);
        }

        if ((node < 0) && (node != -FDT_ERR_NOTFOUND))
            bail_cleanup("FDT: Error iterating through affinity nodes\n");
    }

    /* Prune CPU-map */
    int cpu_map = fdt_path_offset(dt, "/cpus/cpu-map");
    if (cpu_map < 0) {
        printf("FDT: /cpus/cpu-map node not found in devtree, ignoring...\n");
        free(pruned_phandles);
        return 0;
    }

    int cluster_idx = 0;
    int cluster_node;
    for (cluster_node = fdt_first_subnode(dt, cpu_map); cluster_node >= 0;) {
        const char *name = fdt_get_name(dt, cluster_node, NULL);
        int cpu_idx = 0;

        if (strncmp(name, "cluster", 7))
            goto next_cluster;

        int cpu_node;
        for (cpu_node = fdt_first_subnode(dt, cluster_node); cpu_node >= 0;) {
            const char *cpu_name = fdt_get_name(dt, cpu_node, NULL);

            if (strncmp(cpu_name, "core", 4))
                goto next_map_cpu;

            int len;
            const fdt32_t *cpu_ph = fdt_getprop(dt, cpu_node, "cpu", &len);

            if (!cpu_ph || len != sizeof(*cpu_ph))
                bail_cleanup("FDT: Failed to get cpu prop for /cpus/cpu-map/%s/%s\n", name,
                             cpu_name);

            uint32_t phandle = fdt32_ld(cpu_ph);
            bool prune = false;
            for (size_t i = 0; i < pruned; i++) {
                if (pruned_phandles[i] == phandle) {
                    prune = true;
                    break;
                }
            }

            if (prune) {
                printf("FDT: Pruning /cpus/cpu-map/%s/%s\n", name, cpu_name);

                int next = fdt_next_subnode(dt, cpu_node);
                fdt_nop_node(dt, cpu_node);
                cpu_node = next;
                continue;
            } else {
                char new_name[16];

                snprintf(new_name, 16, "core%d", cpu_idx++);
                fdt_set_name(dt, cpu_node, new_name);
            }
        next_map_cpu:
            cpu_node = fdt_next_subnode(dt, cpu_node);
        }

        if ((cpu_node < 0) && (cpu_node != -FDT_ERR_NOTFOUND))
            bail_cleanup("FDT: Error iterating through CPU nodes\n");

        if (cpu_idx == 0) {
            printf("FDT: Pruning /cpus/cpu-map/%s\n", name);

            int next = fdt_next_subnode(dt, cluster_node);
            fdt_nop_node(dt, cluster_node);
            cluster_node = next;
            continue;
        } else {
            char new_name[16];

            snprintf(new_name, 16, "cluster%d", cluster_idx++);
            fdt_set_name(dt, cluster_node, new_name);
        }
    next_cluster:
        cluster_node = fdt_next_subnode(dt, cluster_node);
    }

    if ((cluster_node < 0) && (cluster_node != -FDT_ERR_NOTFOUND))
        bail_cleanup("FDT: Error iterating through CPU clusters\n");

    return 0;

err:
    free(pruned_phandles);
    return ret;
}

static struct {
    const char *alias;
    const char *fdt_property;
    bool swap;
} mac_address_devices[] = {
    {
        .alias = "bluetooth0",
        .fdt_property = "local-bd-address",
        .swap = true,
    },
    {
        .alias = "ethernet0",
        .fdt_property = "local-mac-address",
    },
    {
        .alias = "wifi0",
        .fdt_property = "local-mac-address",
    },
};

static int dt_set_mac_addresses(void)
{
    int anode = adt_path_offset(adt, "/chosen");

    if (anode < 0)
        bail("ADT: /chosen not found\n");

    for (size_t i = 0; i < sizeof(mac_address_devices) / sizeof(*mac_address_devices); i++) {
        char propname[32];
        snprintf(propname, sizeof(propname), "mac-address-%s", mac_address_devices[i].alias);

        uint8_t addr[6];
        if (ADT_GETPROP_ARRAY(adt, anode, propname, addr) < 0)
            continue;

        if (mac_address_devices[i].swap) {
            for (size_t i = 0; i < sizeof(addr) / 2; ++i) {
                uint8_t tmp = addr[i];
                addr[i] = addr[sizeof(addr) - i - 1];
                addr[sizeof(addr) - i - 1] = tmp;
            }
        }

        const char *path = fdt_get_alias(dt, mac_address_devices[i].alias);
        if (path == NULL)
            continue;

        int node = fdt_path_offset(dt, path);
        if (node < 0)
            continue;

        fdt_setprop(dt, node, mac_address_devices[i].fdt_property, addr, sizeof(addr));
    }

    return 0;
}

static int dt_set_bluetooth_cal(int anode, int node, const char *adt_name, const char *fdt_name)
{
    u32 len;
    const u8 *cal_blob = adt_getprop(adt, anode, adt_name, &len);

    if (!cal_blob || !len)
        bail("ADT: Failed to get %s\n", adt_name);

    fdt_setprop(dt, node, fdt_name, cal_blob, len);
    return 0;
}

static int dt_set_bluetooth(void)
{
    int ret;
    int anode = adt_path_offset(adt, "/arm-io/bluetooth");

    if (anode < 0) {
        /*
         * t8012-based system does not have bluetooth, and on
         * some other devices bluetooth is connected with UART.
         */
        printf("ADT: /arm-io/bluetooth not found\n");
        return 0;
    }

    const char *path = fdt_get_alias(dt, "bluetooth0");
    if (path == NULL)
        return 0;

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        return 0;

    ret = dt_set_bluetooth_cal(anode, node, "bluetooth-taurus-calibration-bf",
                               "brcm,taurus-bf-cal-blob");
    if (ret)
        return ret;

    ret = dt_set_bluetooth_cal(anode, node, "bluetooth-taurus-calibration", "brcm,taurus-cal-blob");
    if (ret)
        return ret;

    return 0;
}

static int dt_set_multitouch(void)
{
    const char *path = fdt_get_alias(dt, "touchbar0");
    if (path == NULL)
        return 0;

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        bail("FDT: alias points at nonexistent node\n");

    const char *adt_touchbar;
    if (fdt_node_check_compatible(dt, 0, "apple,j293") == 0)
        adt_touchbar = "/arm-io/spi0/multi-touch";
    else if (fdt_node_check_compatible(dt, 0, "apple,j493") == 0)
        adt_touchbar = "/arm-io/spi3/touch-bar";
    else
        return 0;

    int anode = adt_path_offset(adt, adt_touchbar);
    if (anode < 0)
        bail("ADT: touchbar node %s not found\n", adt_touchbar);

    u32 len;
    const u8 *cal_blob = adt_getprop(adt, anode, "multi-touch-calibration", &len);
    if (!cal_blob || !len) {
        printf("ADT: Failed to get multi-touch-calibration from %s\n", adt_touchbar);
        return 0;
    }

    fdt_setprop(dt, node, "apple,z2-cal-blob", cal_blob, len);
    return 0;
}

#include "keyboard_types.h"

static int dt_set_ipd(void)
{
    int chosen = fdt_path_offset(dt, "/chosen");
    if (chosen < 0)
        bail("FDT: /chosen node not found in devtree\n");

    int ipd = adt_path_offset(adt, "/arm-io/spi3/ipd");
    if (ipd < 0)
        ipd = adt_path_offset(adt, "/arm-io/dockchannel-mtp/mtp-transport/keyboard");

    if (ipd < 0) {
        printf("ADT: no keyboard found\n");
        return 0;
    }

    u32 len;
    const u8 *kblang = adt_getprop(adt, ipd, "kblang-calibration", &len);
    if (!kblang || len < 2) {
        printf("ADT: kblang-calibration not found, no keyboard layout\n");
        return 0;
    }
    u8 code = kblang[1];

    if (fdt_setprop_u32(dt, chosen, "asahi,kblang-code", code))
        bail("FDT: couldn't set asahi,kblang-code\n");

    const char *path = fdt_get_alias(dt, "keyboard");
    if (path == NULL)
        return 0;

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        bail("FDT: keyboard alias points at nonexistent node\n");

    if (fdt_setprop_u32(dt, node, "apple,keyboard-layout-id", code))
        bail("FDT: couldn't set apple,keyboard-layout-id\n");

    if (code >= ARRAY_SIZE(keyboard_types))
        printf("ADT: kblang code out of range, not setting country code\n");
    else if (fdt_setprop_u32(dt, node, "hid-country-code", keyboard_types[code]))
        bail("FDT: couldn't set hid-country-code\n");

    return 0;
}

#define NVRAM_START    0x700000
#define NVRAM_MAX_SIZE SZ_1M

static int dt_set_nvram(void)
{
    int adt_path[8];
    u64 start, size;

    int anode = adt_path_offset_trace(adt, "/arm-io/spi1/spinor/anvram", adt_path);
    if (anode < 0) {
        printf("ADT: nvram partition not found\n");
        return 0;
    }

    int pp = 0;
    while (adt_path[pp])
        pp++;
    adt_path[pp + 1] = 0;

    int ret = adt_get_reg(adt, adt_path, "reg", 0, &start, &size);
    if (ret < 0) {
        printf("ADT: could not read nvram partition start/size\n");
        return 0;
    }

    if (start != NVRAM_START || size > NVRAM_MAX_SIZE) {

        printf("ADT: unexpected nvram partition start (0x%lx) size (0x%lx)\n", start, size);
        return 0;
    }

    int node = fdt_path_offset(dt, "nvram");
    if (node < 0) {
        printf("DT: nvram alias/partition not found\n");
        return 0;
    }

    fdt32_t reg[2];
    fdt32_st(reg + 0, start);
    fdt32_st(reg + 1, size);
    if (fdt_setprop(dt, node, "reg", reg, sizeof(reg))) {
        printf("FDT: couldn't set nvram.reg\n");
        return 0;
    }

    if (fdt_setprop_string(dt, node, "status", "okay") < 0)
        printf("FDT: failed to enable nvram partition node\n");

    return 0;
}

static int dt_set_wifi(void)
{
    int anode = adt_path_offset(adt, "/arm-io/wlan");

    if (anode < 0) {
        /*
         * t8012-based system does not have wifi, and on some other
         * devices WIFI is connected via an internal EHCI controller.
         */
        printf("ADT: /arm-io/wlan not found\n");
        return 0;
    }

    uint8_t info[16];
    if (ADT_GETPROP_ARRAY(adt, anode, "wifi-antenna-sku-info", info) < 0)
        bail("ADT: Failed to get wifi-antenna-sku-info\n");

    const char *path = fdt_get_alias(dt, "wifi0");
    if (path == NULL)
        return 0;

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        return 0;

    char antenna[8];
    memcpy(antenna, &info[8], sizeof(antenna));
    fdt_setprop_string(dt, node, "apple,antenna-sku", antenna);

    u32 len;
    const u8 *cal_blob = adt_getprop(adt, anode, "wifi-calibration-msf", &len);

    if (!cal_blob || !len)
        bail("ADT: Failed to get wifi-calibration-msf\n");

    fdt_setprop(dt, node, "brcm,cal-blob", cal_blob, len);

    return 0;
}

static void dt_set_uboot_dm_preloc(int node)
{
    // Tell U-Boot to bind this node early
    fdt_setprop_empty(dt, node, "u-boot,dm-pre-reloc");
    fdt_setprop_empty(dt, node, "bootph-all");

    // Make sure the power domains are bound early as well
    int pds_size;
    const fdt32_t *pds = fdt_getprop(dt, node, "power-domains", &pds_size);
    if (!pds)
        return;

    fdt32_t *phandles = calloc(pds_size, 1);
    if (!phandles) {
        printf("FDT: out of memory\n");
        return;
    }
    memcpy(phandles, pds, pds_size);

    for (int i = 0; i < pds_size / 4; i++) {
        node = fdt_node_offset_by_phandle(dt, fdt32_ld(&phandles[i]));
        if (node < 0)
            continue;
        dt_set_uboot_dm_preloc(node);

        // restore node offset after DT update
        node = fdt_node_offset_by_phandle(dt, fdt32_ld(&phandles[i]));
        if (node < 0)
            continue;

        // And make sure the PMGR node is bound early too
        node = fdt_parent_offset(dt, node);
        if (node < 0)
            continue;
        dt_set_uboot_dm_preloc(node);
    }

    free(phandles);
}

static int dt_set_uboot(void)
{
    // Make sure that U-Boot can initialize the serial port in its
    // pre-relocation phase by marking its node and the nodes of the
    // power domains it depends on with a "u-boot,dm-pre-reloc"
    // property.

    const char *path = fdt_get_alias(dt, "serial0");
    if (path == NULL)
        return 0;

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        return 0;

    dt_set_uboot_dm_preloc(node);
    return 0;
}

struct adt_tunable_info {
    const char *adt_name;
    const char *fdt_name;
    size_t reg_offset;
    size_t reg_size;
    bool required;
};

static const struct adt_tunable_info usb4_nhi_tunables[] = {
    {"hi_up_tx_desc_fabric_tunables", "apple,tunable-nhi", 0xf0000, 0x4000, true},
    {"hi_up_tx_data_fabric_tunables", "apple,tunable-nhi", 0xec000, 0x4000, true},
    {"hi_up_rx_desc_fabric_tunables", "apple,tunable-nhi", 0xe8000, 0x4000, true},
    {"hi_up_wr_fabric_tunables", "apple,tunable-nhi", 0xf4000, 0x4000, true},
    {"hi_up_merge_fabric_tunables", "apple,tunable-nhi", 0xf8000, 0x4000, true},
    {"hi_dn_merge_fabric_tunables", "apple,tunable-nhi", 0xfc000, 0x4000, true},
    {"fw_int_ctl_management_tunables", "apple,tunable-nhi", 0x4000, 0x4000, true},
};

static const struct adt_tunable_info usb4_rc_tunables[] = {
    {"top_tunables", "apple,tunable-rc", 0x0, 0x4000, true},
    {"hbw_fabric_tunables", "apple,tunable-rc", 0x4000, 0x4000, true},
    {"lbw_fabric_tunables", "apple,tunable-rc", 0x8000, 0x4000, true},
};

static const struct adt_tunable_info usb4_pcie_adapter_tunables[] = {
    {"pcie_adapter_regs_tunables", "apple,tunable-pcie-adapter", 0x0, 0x4000, true},
};

struct acio_tunable {
    u32 offset;
    u32 size;
    u64 mask;
    u64 value;
} PACKED;
static_assert(sizeof(struct acio_tunable) == 24, "Invalid acio_tunable size");

/*
 * This is *almost* identical to dt_append_atc_tunable except for the different
 * tunable struct and that tunable->size is in bytes instead of bits.
 * If only C had generics that aren't macros :-(
 */
static int dt_append_acio_tunable(int adt_node, int fdt_node,
                                  const struct adt_tunable_info *tunable_info)
{
    u32 tunables_len;
    const struct acio_tunable *tunable_adt =
        adt_getprop(adt, adt_node, tunable_info->adt_name, &tunables_len);

    if (!tunable_adt) {
        printf("ADT: tunable %s not found\n", tunable_info->adt_name);

        if (tunable_info->required)
            return -1;
        else
            return 0;
    }

    if (tunables_len % sizeof(*tunable_adt)) {
        printf("ADT: tunable %s with invalid length %d\n", tunable_info->adt_name, tunables_len);
        return -1;
    }

    u32 n_tunables = tunables_len / sizeof(*tunable_adt);
    for (size_t j = 0; j < n_tunables; j++) {
        const struct acio_tunable *tunable = &tunable_adt[j];

        if (tunable->size != 4) {
            printf("kboot: ACIO tunable has invalid size %d\n", tunable->size);
            return -1;
        }

        if (tunable->offset % tunable->size) {
            printf("kboot: ACIO tunable has unaligned offset %x\n", tunable->offset);
            return -1;
        }

        if (tunable->offset + tunable->size > tunable_info->reg_size) {
            printf("kboot: ACIO tunable has invalid offset %x\n", tunable->offset);
            return -1;
        }

        if (fdt_appendprop_u32(dt, fdt_node, tunable_info->fdt_name,
                               tunable->offset + tunable_info->reg_offset) < 0)
            return -1;
        if (fdt_appendprop_u32(dt, fdt_node, tunable_info->fdt_name, tunable->mask) < 0)
            return -1;
        if (fdt_appendprop_u32(dt, fdt_node, tunable_info->fdt_name, tunable->value) < 0)
            return -1;
    }

    return 0;
}

static int dt_copy_usb4_drom(const char *adt_path, const char *dt_alias)
{
    int adt_node = adt_path_offset(adt, adt_path);
    if (adt_node < 0)
        return -1;

    const char *fdt_path = fdt_get_alias(dt, dt_alias);
    if (fdt_path == NULL)
        bail("FDT: Unable to find alias %s\n", dt_alias);

    int fdt_node = fdt_path_offset(dt, fdt_path);
    if (fdt_node < 0)
        bail("FDT: Unable to find path %s for alias %s\n", fdt_path, dt_alias);

    u32 drom_len;
    const u8 *drom_blob = adt_getprop(adt, adt_node, "thunderbolt-drom", &drom_len);
    if (!drom_blob || !drom_len)
        bail("ADT: Failed to get thunderbolt-drom\n");

    return fdt_setprop(dt, fdt_node, "apple,thunderbolt-drom", drom_blob, drom_len);
}

static int dt_copy_acio_tunables(const char *adt_path, const char *dt_alias,
                                 const struct adt_tunable_info *tunables, size_t n_tunables)
{
    int ret;
    int adt_node = adt_path_offset(adt, adt_path);
    if (adt_node < 0)
        return -1;

    const char *fdt_path = fdt_get_alias(dt, dt_alias);
    if (fdt_path == NULL)
        bail("FDT: Unable to find alias %s\n", dt_alias);

    int fdt_node = fdt_path_offset(dt, fdt_path);
    if (fdt_node < 0)
        bail("FDT: Unable to find path %s for alias %s\n", fdt_path, dt_alias);

    for (size_t i = 0; i < n_tunables; ++i) {
        ret = dt_append_acio_tunable(adt_node, fdt_node, &tunables[i]);
        if (ret)
            bail_cleanup("ADT: unable to convert '%s' tunable", tunables[i].adt_name);
    }

    return 0;

err:
    for (size_t i = 0; i < n_tunables; ++i)
        fdt_delprop(dt, fdt_node, tunables[i].fdt_name);

    return -1;
}

static int dt_set_acio_tunables(void)
{
    char adt_path[32];
    char fdt_alias[32];

    for (int i = 0; i < MAX_CIO_DEVS; ++i) {
        memset(adt_path, 0, sizeof(adt_path));
        snprintf(adt_path, sizeof(adt_path), "/arm-io/acio%d", i);

        memset(fdt_alias, 0, sizeof(fdt_alias));
        snprintf(fdt_alias, sizeof(fdt_alias), "usb4_%d_rc", i);
        dt_copy_acio_tunables(adt_path, fdt_alias, usb4_rc_tunables,
                              sizeof(usb4_rc_tunables) / sizeof(*usb4_rc_tunables));

        memset(fdt_alias, 0, sizeof(fdt_alias));
        snprintf(fdt_alias, sizeof(fdt_alias), "usb4_%d_pcie_adapter", i);
        dt_copy_acio_tunables(adt_path, fdt_alias, usb4_pcie_adapter_tunables,
                              sizeof(usb4_pcie_adapter_tunables) /
                                  sizeof(*usb4_pcie_adapter_tunables));

        memset(fdt_alias, 0, sizeof(fdt_alias));
        snprintf(fdt_alias, sizeof(fdt_alias), "usb4_%d_nhi", i);
        dt_copy_acio_tunables(adt_path, fdt_alias, usb4_nhi_tunables,
                              sizeof(usb4_nhi_tunables) / sizeof(*usb4_nhi_tunables));
        dt_copy_usb4_drom(adt_path, fdt_alias);
    }

    return 0;
}

static const struct adt_tunable_info pciec_tunables[] = {
    {"atc-apcie-debug-tunables", "apple,tunable-debug", 0, 0x2000, true},
    {"atc-apcie-fabric-tunables", "apple,tunable-fabric", 0, 0x4000, true},
    {"atc-apcie-rc-tunables", "apple,tunable-rc", 0, 0x4000, true},
};
static const struct adt_tunable_info pciec_port_tunable = {
    .adt_name = "apcie-config-tunables",
    .fdt_name = "apple,tunable",
    .reg_offset = 0,
    .reg_size = 0x4000,
    .required = true,
};

static int dt_copy_pciec_tunables(const char *adt_path, const char *dt_alias)
{
    int ret;
    int adt_node = adt_path_offset(adt, adt_path);

    if (adt_node < 0)
        return -1;

    const char *fdt_path = fdt_get_alias(dt, dt_alias);
    if (fdt_path == NULL)
        bail("FDT: Unable to find alias %s\n", dt_alias);

    int fdt_node = fdt_path_offset(dt, fdt_path);
    if (fdt_node < 0)
        bail("FDT: Unable to find path %s for alias %s\n", fdt_path, dt_alias);

    int fdt_port_node = fdt_first_subnode(dt, fdt_node);
    if (fdt_port_node < 0)
        bail("FDT: Unable to find port node for %s\n", fdt_path);

    ret = dt_append_acio_tunable(adt_node, fdt_port_node, &pciec_port_tunable);
    if (ret)
        bail_cleanup("PCIEC: unable to convert '%s' tunable", pciec_tunables[0].adt_name);

    for (size_t i = 0; i < sizeof(pciec_tunables) / sizeof(*pciec_tunables); ++i) {
        ret = dt_append_acio_tunable(adt_node, fdt_node, &pciec_tunables[i]);
        if (ret)
            bail_cleanup("PCIEC: unable to convert '%s' tunable", pciec_tunables[i].adt_name);
    }

    return 0;

err:
    for (size_t i = 0; i < sizeof(pciec_tunables) / sizeof(*pciec_tunables); ++i)
        fdt_delprop(dt, fdt_node, pciec_tunables[i].fdt_name);
    fdt_delprop(dt, fdt_port_node, pciec_port_tunable.fdt_name);

    return -1;
}

static int dt_set_pcie_tunables(void)
{
    char adt_path[32];
    char fdt_alias[32];

    for (int i = 0; i < MAX_CIO_DEVS; ++i) {
        memset(adt_path, 0, sizeof(adt_path));
        snprintf(adt_path, sizeof(adt_path), "/arm-io/apciec%d", i);

        memset(fdt_alias, 0, sizeof(adt_path));
        snprintf(fdt_alias, sizeof(fdt_alias), "usb4_%d_pcie", i);

        dt_copy_pciec_tunables(adt_path, fdt_alias);
    }

    return 0;
}

static int dt_get_iommu_node(int node, u32 num)
{
    int len;
    assert(num < 32);
    const void *prop = fdt_getprop(dt, node, "iommus", &len);
    if (!prop || len < 0 || (u32)len < 8 * (num + 1)) {
        printf("FDT: unexpected 'iommus' prop / len %d\n", len);
        return -FDT_ERR_NOTFOUND;
    }

    const fdt32_t *iommus = prop;
    uint32_t phandle = fdt32_ld(&iommus[num * 2]);

    return fdt_node_offset_by_phandle(dt, phandle);
}

static dart_dev_t *dt_init_dart_by_node(int node, u32 num)
{
    int len;
    assert(num < 32);
    const void *prop = fdt_getprop(dt, node, "iommus", &len);
    if (!prop || len < 0 || (u32)len < 8 * (num + 1)) {
        printf("FDT: unexpected 'iommus' prop / len %d\n", len);
        return NULL;
    }

    const fdt32_t *iommus = prop;
    u32 iommu_phandle = fdt32_ld(&iommus[num * 2]);
    u32 iommu_stream = fdt32_ld(&iommus[num * 2 + 1]);

    printf("FDT: iommu phande:%u stream:%u\n", iommu_phandle, iommu_stream);

    return dart_init_fdt(dt, iommu_phandle, iommu_stream, true);
}

static u64 dart_get_mapping(dart_dev_t *dart, const char *path, u64 paddr, size_t size)
{
    u64 iova = dart_search(dart, (void *)paddr);
    if (DART_IS_ERR(iova)) {
        printf("ADT: %s paddr: 0x%lx is not mapped\n", path, paddr);
        return iova;
    }

    u64 pend = (u64)dart_translate(dart, iova + size - 1);
    if (pend != (paddr + size - 1)) {
        printf("ADT: %s is not continuously mapped: 0x%lx\n", path, pend);
        return DART_PTR_ERR;
    }

    return iova;
}

static int dt_device_set_reserved_mem(int node, const char *name, uint32_t phandle, u64 iova,
                                      u64 size)
{
    int ret;

    ret = fdt_appendprop_u32(dt, node, "iommu-addresses", phandle);
    if (ret != 0)
        bail("FDT: could not append phandle to '%s.iommu-addresses' property: %d\n", name, ret);

    ret = fdt_appendprop_u64(dt, node, "iommu-addresses", iova);
    if (ret != 0)
        bail("FDT: could not append iova to '%s.iommu-addresses' property: %d\n", name, ret);

    ret = fdt_appendprop_u64(dt, node, "iommu-addresses", size);
    if (ret != 0)
        bail("FDT: could not append size to '%s.iommu-addresses' property: %d\n", name, ret);

    return 0;
}

static int dt_device_set_reserved_mem_from_dart(int node, dart_dev_t *dart, const char *name,
                                                uint32_t phandle, u64 paddr, u64 size)
{
    u64 iova = dart_get_mapping(dart, name, paddr, size);
    if (DART_IS_ERR(iova)) {
        printf("ADT: no mapping found for '%s' (0x%012lx iova:0x%08lx)\n", name, paddr, iova);
        return 0;
    }

    return dt_device_set_reserved_mem(node, name, phandle, iova, size);
}

static int dt_get_or_add_reserved_mem(const char *node_name, const char *compat, bool nomap,
                                      u64 paddr, size_t size)
{
    int ret;
    int resv_node = fdt_path_offset(dt, "/reserved-memory");
    if (resv_node < 0)
        bail("FDT: '/reserved-memory' not found\n");

    int node = fdt_subnode_offset(dt, resv_node, node_name);
    if (node < 0) {
        node = fdt_add_subnode(dt, resv_node, node_name);
        if (node < 0)
            bail("FDT: failed to add node '%s' to  '/reserved-memory'\n", node_name);

        uint32_t phandle;
        ret = fdt_generate_phandle(dt, &phandle);
        if (ret)
            bail("FDT: failed to generate phandle: %d\n", ret);

        ret = fdt_setprop_u32(dt, node, "phandle", phandle);
        if (ret != 0)
            bail("FDT: couldn't set '%s.phandle' property: %d\n", node_name, ret);
    }

    u64 reg[2] = {cpu_to_fdt64(paddr), cpu_to_fdt64(size)};
    ret = fdt_setprop(dt, node, "reg", reg, sizeof(reg));
    if (ret != 0)
        bail("FDT: couldn't set '%s.reg' property: %d\n", node_name, ret);

    ret = fdt_setprop_string(dt, node, "compatible", compat);
    if (ret != 0)
        bail("FDT: couldn't set '%s.compatible' property: %d\n", node_name, ret);

    if (nomap) {
        ret = fdt_setprop_empty(dt, node, "no-map");
        if (ret != 0)
            bail("FDT: couldn't set '%s.no-map' property: %d\n", node_name, ret);
    }

    return node;
}

static int dt_device_add_mem_region(const char *alias, uint32_t phandle, const char *name)
{
    int ret;
    int dev_node = fdt_path_offset(dt, alias);
    if (dev_node < 0)
        bail("FDT: failed to get node for alias '%s'\n", alias);

    ret = fdt_appendprop_u32(dt, dev_node, "memory-region", phandle);
    if (ret != 0)
        bail("FDT: failed to append to 'memory-region' property\n");

    dev_node = fdt_path_offset(dt, alias);
    if (dev_node < 0)
        bail("FDT: failed to update node for alias '%s'\n", alias);

    if (!name)
        return 0;

    ret = fdt_appendprop_string(dt, dev_node, "memory-region-names", name);
    if (ret != 0)
        bail("FDT: failed to append to 'memory-region-names' property\n");

    return 0;
}

static int dt_set_dcp_firmware(const char *alias)
{
    const char *path = fdt_get_alias(dt, alias);

    if (!path)
        return 0;

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        return 0;

    if (firmware_set_fdt(dt, node, "apple,firmware-version", &os_firmware) < 0)
        bail("FDT: Could not set apple,firmware-version for %s\n", path);

    const struct fw_version_info *compat;

    switch (os_firmware.version) {
        case V12_3_1:
        case V12_4:
            compat = &fw_versions[V12_3];
            break;
        case V13_5B4:
        case V13_5:
        case V13_6_2:
            compat = &fw_versions[V13_5];
            break;
        default:
            compat = &os_firmware;
            break;
    }

    if (firmware_set_fdt(dt, node, "apple,firmware-compat", compat) < 0)
        bail("FDT: Could not set apple,firmware-compat for %s\n", path);

    return 0;
}

struct disp_mapping {
    char region_adt[24];
    char mem_fdt[24];
    bool map_dcp;
    bool map_disp;
    bool map_piodma;
};

struct mem_region {
    u64 paddr;
    u64 size;
};

static int dt_add_reserved_regions(const char *dcp_alias, const char *disp_alias,
                                   const char *piodma_alias, const char *compat,
                                   struct disp_mapping *maps, struct mem_region *region,
                                   u32 num_maps)
{
    int ret = 0;
    dart_dev_t *dart_dcp = NULL, *dart_disp = NULL, *dart_piodma = NULL;
    uint32_t dcp_phandle = 0, disp_phandle = 0, piodma_phandle = 0;

    /* Check for display device aliases, if one is missing assume it is an old DT
     * without display nodes and return without error.
     * Otherwise init each dart and retrieve the node's phandle.
     */
    if (dcp_alias) {
        int dcp_node = fdt_path_offset(dt, dcp_alias);
        if (dcp_node < 0) {
            printf("FDT: could not resolve '%s' alias\n", dcp_alias);
            goto err; // cleanup
        }
        dart_dcp = dt_init_dart_by_node(dcp_node, 0);
        if (!dart_dcp)
            bail_cleanup("FDT: failed to init DART for '%s'\n", dcp_alias);
        dcp_phandle = fdt_get_phandle(dt, dcp_node);
    }

    if (disp_alias) {
        int disp_node = fdt_path_offset(dt, disp_alias);
        if (disp_node < 0) {
            printf("FDT: could not resolve '%s' alias\n", disp_alias);
            goto err; // cleanup
        }
        dart_disp = dt_init_dart_by_node(disp_node, 0);
        if (!dart_disp)
            bail_cleanup("FDT: failed to init DART for '%s'\n", disp_alias);
        disp_phandle = fdt_get_phandle(dt, disp_node);
    }

    if (piodma_alias) {
        int piodma_node = fdt_path_offset(dt, piodma_alias);
        if (piodma_node < 0) {
            printf("FDT: could not resolve '%s' alias\n", piodma_alias);
            goto err; // cleanup
        }

        dart_piodma = dt_init_dart_by_node(piodma_node, 0);
        if (!dart_piodma)
            bail_cleanup("FDT: failed to init DART for '%s'\n", piodma_alias);
        piodma_phandle = fdt_get_phandle(dt, piodma_node);
    }

    for (unsigned i = 0; i < num_maps; i++) {
        const char *name = maps[i].mem_fdt;
        char node_name[64];

        snprintf(node_name, sizeof(node_name), "%s@%lx", name, region[i].paddr);
        int mem_node =
            dt_get_or_add_reserved_mem(node_name, compat, true, region[i].paddr, region[i].size);
        if (mem_node < 0)
            goto err;

        uint32_t mem_phandle = fdt_get_phandle(dt, mem_node);

        if (maps[i].map_dcp && dart_dcp) {
            ret = dt_device_set_reserved_mem_from_dart(mem_node, dart_dcp, node_name, dcp_phandle,
                                                       region[i].paddr, region[i].size);
            if (ret != 0)
                goto err;
        }
        if (maps[i].map_disp && dart_disp) {
            ret = dt_device_set_reserved_mem_from_dart(mem_node, dart_disp, node_name, disp_phandle,
                                                       region[i].paddr, region[i].size);
            if (ret != 0)
                goto err;
        }
        if (maps[i].map_piodma && dart_piodma) {
            ret = dt_device_set_reserved_mem_from_dart(
                mem_node, dart_piodma, node_name, piodma_phandle, region[i].paddr, region[i].size);
            if (ret != 0)
                goto err;
        }

        /* modify device nodes after filling /reserved-memory to avoid
         * reloading mem_node's offset */
        if (maps[i].map_dcp && dcp_alias) {
            ret = dt_device_add_mem_region(dcp_alias, mem_phandle, maps[i].mem_fdt);
            if (ret < 0)
                goto err;
        }
        if (maps[i].map_disp && disp_alias) {
            ret = dt_device_add_mem_region(disp_alias, mem_phandle, maps[i].mem_fdt);
            if (ret < 0)
                goto err;
        }
        if (maps[i].map_piodma && piodma_alias) {
            ret = dt_device_add_mem_region(piodma_alias, mem_phandle, maps[i].mem_fdt);
            if (ret < 0)
                goto err;
        }
    }

    /* enable dart-disp0, it is disabled in device tree to avoid resetting
     * it and breaking display scanout when booting with old m1n1 which
     * does not lock dart-disp0.
     */
    if (disp_alias) {
        int disp_node = fdt_path_offset(dt, disp_alias);

        int dart_disp0 = dt_get_iommu_node(disp_node, 0);
        if (dart_disp0 < 0)
            bail_cleanup("FDT: failed to find 'dart-disp0'\n");

        if (fdt_setprop_string(dt, dart_disp0, "status", "okay") < 0)
            bail_cleanup("FDT: failed to enable 'dart-disp0'\n");
    }
    /* enable dcp* */
    int dcp_node = fdt_path_offset(dt, dcp_alias);
    if (dcp_node < 0 || fdt_setprop_string(dt, dcp_node, "status", "okay") < 0)
        bail_cleanup("FDT: failed to enable '%s'\n", dcp_alias);

err:
    if (dart_dcp)
        dart_shutdown(dart_dcp);
    if (dart_disp)
        dart_shutdown(dart_disp);
    if (dart_piodma)
        dart_shutdown(dart_piodma);

    return ret;
}

static int dt_carveout_reserved_regions(const char *dcp_alias, const char *disp_alias,
                                        const char *piodma_alias, struct disp_mapping *maps,
                                        u32 num_maps)
{
    int ret = 0;

    struct mem_region region[MAX_DISP_MAPPINGS];

    assert(num_maps <= MAX_DISP_MAPPINGS);

    // return early if dcp_alias does not exists
    if (!fdt_get_alias(dt, dcp_alias))
        return 0;

    ret = dt_set_dcp_firmware(dcp_alias);
    if (ret)
        return ret;

    int node = adt_path_offset(adt, "/chosen/carveout-memory-map");
    if (node < 0)
        bail("ADT: '/chosen/carveout-memory-map' not found\n");

    /* read physical addresses of reserved memory regions */
    /* do this up front to avoid errors after modifying the DT */
    for (unsigned i = 0; i < num_maps; i++) {

        int ret;
        u64 phys_map[2];
        struct disp_mapping *map = &maps[i];
        const char *name = map->region_adt;

        ret = ADT_GETPROP_ARRAY(adt, node, name, phys_map);
        if (ret != sizeof(phys_map))
            bail("ADT: could not get carveout memory '%s'\n", name);
        if (!phys_map[0] || !phys_map[1])
            bail("ADT: carveout memory '%s'\n", name);

        region[i].paddr = phys_map[0];
        region[i].size = phys_map[1];
    }

    return dt_add_reserved_regions(dcp_alias, disp_alias, piodma_alias, "apple,asc-mem", maps,
                                   region, num_maps);
}

static struct disp_mapping disp_reserved_regions_vram[] = {
    // boot framebuffer, mapped to dart-disp0 sid 0 and dart-dcp sid 0/5
    {"vram", "framebuffer", true, true, false},
};

static int dt_vram_reserved_region(const char *dcp_alias, const char *disp_alias)
{
    int ret = 0;
    int adt_path[4];
    struct mem_region region;

    // return early if dcp_alias does not exists
    if (!fdt_get_alias(dt, dcp_alias))
        return 0;

    int node = adt_path_offset_trace(adt, "/vram", adt_path);

    if (node < 0)
        bail("ADT: '/vram' not found\n");

    int pp = 0;
    while (adt_path[pp])
        pp++;
    adt_path[pp + 1] = 0;

    ret = adt_get_reg(adt, adt_path, "reg", 0, &region.paddr, &region.size);
    if (ret < 0)
        bail("ADT: failed to read /vram/reg\n");

    return dt_add_reserved_regions(dcp_alias, disp_alias, NULL, "framebuffer",
                                   disp_reserved_regions_vram, &region, 1);
}

static int dt_reserve_asc_firmware(const char *adt_path, const char *adt_path_alt,
                                   const char *fdt_path, bool remap, u64 base)
{
    int ret = 0;

    int fdt_node = fdt_path_offset(dt, fdt_path);
    if (fdt_node < 0) {
        printf("FDT: '%s' not found\n", fdt_path);
        return 0;
    }

    int node = adt_path_offset(adt, adt_path);
    if (node < 0 && adt_path_alt)
        node = adt_path_offset(adt, adt_path_alt);
    if (node < 0)
        bail("ADT: '%s' not found\n", adt_path);

    uint32_t dev_phandle = fdt_get_phandle(dt, fdt_node);
    if (!dev_phandle) {
        ret = fdt_generate_phandle(dt, &dev_phandle);
        if (!ret)
            ret = fdt_setprop_u32(dt, fdt_node, "phandle", dev_phandle);
        if (ret != 0)
            bail("FDT: couldn't set '%s.phandle' property: %d\n", fdt_path, ret);
    }

    const struct adt_segment_ranges *seg;
    u32 segments_len;

    seg = adt_getprop(adt, node, "segment-ranges", &segments_len);
    unsigned int num_maps = segments_len / sizeof(*seg);

    for (unsigned i = 0; i < num_maps; i++) {
        u64 iova = (remap ? seg->remap : seg->iova) | base;

        char node_name[64];
        snprintf(node_name, sizeof(node_name), "asc-firmware@%lx", seg->phys);

        size_t seg_size = seg->size;
        if (seg->size & (SZ_16K - 1)) {
            printf("ADT: segment %s uses non 16k aligned size: 0x%06zx\n", node_name, seg_size);
            seg_size = ALIGN_UP(seg_size, SZ_16K);
        }

        int mem_node =
            dt_get_or_add_reserved_mem(node_name, "apple,asc-mem", true, seg->phys, seg_size);
        if (mem_node < 0)
            return ret;
        uint32_t mem_phandle = fdt_get_phandle(dt, mem_node);

        ret = dt_device_set_reserved_mem(mem_node, node_name, dev_phandle, iova, seg_size);
        if (ret < 0)
            return ret;

        ret = dt_device_add_mem_region(fdt_path, mem_phandle, NULL);
        if (ret < 0)
            return ret;

        seg++;
    }

    return 0;
}

static const char dcpext_aliases[][8] = {
    "dcpext",  "dcpext0", "dcpext1", "dcpext2", "dcpext3",
    "dcpext4", "dcpext5", "dcpext6", "dcpext7",
};

static int dt_reserve_dcpext_firmware(void)
{
    /* reserve asc for all  */
    for (size_t n = 0; n < ARRAY_SIZE(dcpext_aliases); n++) {
        const char *dcpext_alias = dcpext_aliases[n];
        char adt_path[48];

        snprintf(adt_path, sizeof(adt_path) - 1, "/arm-io/%s/iop-%s-nub", dcpext_alias,
                 dcpext_alias);
        adt_path[sizeof(adt_path) - 1] = '\0';

        if (adt_path_offset(adt, adt_path) < 0)
            continue;

        int dcpext_node = fdt_path_offset(dt, dcpext_alias);
        if (dcpext_node < 0)
            continue;

        int ret = dt_reserve_asc_firmware(adt_path, NULL, dcpext_alias, true, 0);
        if (ret < 0)
            bail("FDT: reserving ASC firmware for %s failed!\n", dcpext_alias);

        ret = dt_set_dcp_firmware(dcpext_alias);
        if (ret)
            continue;

        // refresh dcpext_node
        dcpext_node = fdt_path_offset(dt, dcpext_alias);
        if ((dcpext_node < 0) || (fdt_setprop_string(dt, dcpext_node, "status", "okay") < 0))
            printf("FDT: failed to enable '%s'\n", dcpext_alias);
    }

    return 0;
}

static struct disp_mapping disp_reserved_regions_t8103[] = {
    {"region-id-50", "dcp_data", true, false, false},
    {"region-id-57", "region57", true, false, false},
    // The 2 following regions are mapped in dart-dcp sid 0 and dart-disp0 sid 0 and 4
    {"region-id-94", "region94", true, true, false},
    {"region-id-95", "region95", true, false, true},
};

static struct disp_mapping dcpext_reserved_regions_t8103[] = {
    {"region-id-73", "dcpext_data", true, false, false},
    {"region-id-74", "region74", true, false, false},
};

static struct disp_mapping disp_reserved_regions_t8112[] = {
    {"region-id-49", "asc-firmware", true, false, false},
    {"region-id-50", "dcp_data", true, false, false},
    {"region-id-57", "region57", true, false, false},
    // The 2 following regions are mapped in dart-dcp sid 5 and dart-disp0 sid 0 and 4
    {"region-id-94", "region94", true, true, false},
    {"region-id-95", "region95", true, false, true},
};

static struct disp_mapping disp_reserved_regions_t600x[] = {
    {"region-id-50", "dcp_data", true, false, false},
    {"region-id-57", "region57", true, false, false},
    // The 2 following regions are mapped in dart-dcp sid 0 and dart-disp0 sid 0 and 4
    {"region-id-94", "region94", true, true, false},
    {"region-id-95", "region95", true, false, true},
    // used on M1 Pro/Max/Ultra, mapped to dcp and disp0
    {"region-id-157", "region157", true, true, false},
};

#define MAX_DCPEXT 8

static struct disp_mapping dcpext_reserved_regions_t600x[MAX_DCPEXT][2] = {
    {
        {"region-id-73", "dcpext0_data", true, false, false},
        {"region-id-74", "", true, false, false},
    },
    {
        {"region-id-88", "dcpext1_data", true, false, false},
        {"region-id-89", "region89", true, false, false},
    },
    {
        {"region-id-111", "dcpext2_data", true, false, false},
        {"region-id-112", "region112", true, false, false},
    },
    {
        {"region-id-119", "dcpext3_data", true, false, false},
        {"region-id-120", "region120", true, false, false},
    },
    {
        {"region-id-127", "dcpext4_data", true, false, false},
        {"region-id-128", "region128", true, false, false},
    },
    {
        {"region-id-135", "dcpext5_data", true, false, false},
        {"region-id-136", "region136", true, false, false},
    },
    {
        {"region-id-143", "dcpext6_data", true, false, false},
        {"region-id-144", "region144", true, false, false},
    },
    {
        {"region-id-151", "dcpext7_data", true, false, false},
        {"region-id-152", "region152", true, false, false},
    },
};

static struct disp_mapping disp_reserved_regions_t602x[] = {
    {"region-id-49", "asc-firmware", true, false, false},
    {"region-id-50", "dcp_data", true, false, false},
    {"region-id-57", "region57", true, false, false},
    // The 2 following regions are mapped in dart-dcp sid 0 and dart-disp0 sid 0 and 4
    {"region-id-94", "region94", true, true, false},
    {"region-id-95", "region95", true, false, true},
    // used on M1 Pro/Max/Ultra, mapped to dcp and disp0
    {"region-id-157", "region157", true, true, false},
};

static int dt_set_display(void)
{
    /* lock dart-disp0 to prevent old software from resetting it */
    dart_lock_adt("/arm-io/dart-disp0", 0);

    /* Add "/reserved-memory" nodes with iommu mapping and link them to their
     * devices. The memory is already excluded from useable RAM so these nodes
     * are only required to inform the OS about the existing mappings.
     * Required for disp0, dcp and all dcpext.
     * Checks for dcp* / disp*_piodma / disp* aliases and fails silently if
     * they are missing. */

    int ret = 0;

    if (!fdt_node_check_compatible(dt, 0, "apple,t8103")) {
        ret = dt_carveout_reserved_regions("dcp", "disp0", "disp0_piodma",
                                           disp_reserved_regions_t8103,
                                           ARRAY_SIZE(disp_reserved_regions_t8103));
        if (ret)
            return ret;

        ret = dt_carveout_reserved_regions("dcpext", NULL, NULL, dcpext_reserved_regions_t8103,
                                           ARRAY_SIZE(dcpext_reserved_regions_t8103));
    } else if (!fdt_node_check_compatible(dt, 0, "apple,t8112")) {
        ret = dt_carveout_reserved_regions("dcp", "disp0", "disp0_piodma",
                                           disp_reserved_regions_t8112,
                                           ARRAY_SIZE(disp_reserved_regions_t8112));
        if (ret)
            return ret;
    } else if (!fdt_node_check_compatible(dt, 0, "apple,t6000") ||
               !fdt_node_check_compatible(dt, 0, "apple,t6001") ||
               !fdt_node_check_compatible(dt, 0, "apple,t6002")) {
        ret = dt_carveout_reserved_regions("dcp", "disp0", "disp0_piodma",
                                           disp_reserved_regions_t600x,
                                           ARRAY_SIZE(disp_reserved_regions_t600x));
        if (ret)
            return ret;

        if (os_firmware.version >= V13_5) {
            for (int n = 0; n < MAX_DCPEXT && ret == 0; n++) {
                char dcpext_alias[16];

                snprintf(dcpext_alias, sizeof(dcpext_alias), "dcpext%d", n);
                ret = dt_carveout_reserved_regions(dcpext_alias, NULL, NULL,
                                                   dcpext_reserved_regions_t600x[n],
                                                   ARRAY_SIZE(dcpext_reserved_regions_t600x[n]));
            }
        }
    } else if (!fdt_node_check_compatible(dt, 0, "apple,t6020") ||
               !fdt_node_check_compatible(dt, 0, "apple,t6021")) {
        ret = dt_carveout_reserved_regions("dcp", "disp0", "disp0_piodma",
                                           disp_reserved_regions_t602x,
                                           ARRAY_SIZE(disp_reserved_regions_t602x));
        if (ret)
            return ret;
    } else if (!fdt_node_check_compatible(dt, 0, "apple,t6022")) {
        /* noop */
    } else {
        printf("FDT: unknown compatible, skip display reserved-memory setup\n");
        return 0;
    }
    if (ret)
        return ret;

    /*
     * Ignore errors for dcpext firmware reservation, nodes should be disabled
     * if the reservation fails allowing basic operation with just dcp.
     */
    if (!fdt_node_check_compatible(dt, 0, "apple,t8112") ||
        !fdt_node_check_compatible(dt, 0, "apple,t6020") ||
        !fdt_node_check_compatible(dt, 0, "apple,t6021") ||
        !fdt_node_check_compatible(dt, 0, "apple,t6022"))
        dt_reserve_dcpext_firmware();

    const display_config_t *disp_cfg = display_get_config();

    if (disp_cfg)
        return dt_vram_reserved_region(disp_cfg->dcp_alias, "disp0");
    else
        return dt_vram_reserved_region("dcp", "disp0");
}

static int dt_set_sep(void)
{
    const char *path = fdt_get_alias(dt, "sep");
    if (path == NULL) {
        printf("FDT: sep alias not found in devtree\n");
        return 0;
    }

    int anode_mmap = adt_path_offset(adt, "/chosen/memory-map");
    if (anode_mmap < 0)
        bail("ADT: /chosen/memory-map not found \n");

    u64 phys_map[2];
    size_t ret = ADT_GETPROP_ARRAY(adt, anode_mmap, "SEPFW", phys_map);
    if (ret != sizeof(phys_map))
        bail("ADT: could not get sepfw memory\n");

    const char *node_name = "sep-firmware";
    int mem_node =
        dt_get_or_add_reserved_mem(node_name, "apple,asc-mem", false, phys_map[0], phys_map[1]);
    if (mem_node < 0)
        bail("FDT: failed to reserve sepfw");

    uint32_t mem_phandle = fdt_get_phandle(dt, mem_node);
    ret = dt_device_add_mem_region(path, mem_phandle, "sepfw");
    if (ret < 0)
        bail("FDT: failed to add sepfw region");

    int node = fdt_path_offset(dt, path);
    if (node < 0)
        bail("FDT: sep not not found in devtree\n");

    int anode_manifest = adt_path_offset(adt, "/chosen/boot-object-manifests");
    if (anode_manifest < 0)
        bail("ADT: /chosen/boot-object-manifests not found \n");

    ret = ADT_GETPROP_ARRAY(adt, anode_manifest, "lpol", phys_map);
    if (ret != sizeof(phys_map))
        bail("ADT: could not get local policy\n");
    fdt_setprop(dt, node, "local-policy-manifest", (void *)phys_map[0], phys_map[1]);

    ret = ADT_GETPROP_ARRAY(adt, anode_manifest, "ibot", phys_map);
    if (ret != sizeof(phys_map))
        bail("ADT: could not get iboot manifest\n");
    fdt_setprop(dt, node, "iboot-manifest", (void *)phys_map[0], phys_map[1]);

    return 0;
}

static int dt_set_sio_fwdata(const char *adt_path, const char *fdt_alias)
{
    int node = fdt_path_offset(dt, fdt_alias);
    if (node < 0) {
        printf("FDT: '%s' node not found\n", fdt_alias);
        return 0;
    }

    int phandle = fdt_get_phandle(dt, node);
    uint32_t max_phandle;
    int ret = fdt_find_max_phandle(dt, &max_phandle);
    if (ret)
        bail("FDT: failed to get max phandle: %d\n", ret);

    if (!phandle) {
        phandle = ++max_phandle;
        ret = fdt_setprop_u32(dt, node, "phandle", phandle);
        if (ret != 0)
            bail("FDT: couldn't set '%s.phandle' property: %d\n", fdt_alias, ret);
    }

    struct sio_data *siodata = sio_setup_fwdata(adt_path);
    if (!siodata)
        bail("FDT: failed to set up SIO(%s) firmware data\n", adt_path);

    for (int i = 0; i < siodata->num_fwdata; i++) {
        struct sio_mapping *mapping = &siodata->fwdata[i];

        char node_name[64];
        snprintf(node_name, sizeof(node_name), "sio-firmware-data@%lx", mapping->phys);

        int mem_node = dt_get_or_add_reserved_mem(node_name, "apple,asc-mem", true, mapping->phys,
                                                  mapping->size);
        if (mem_node < 0)
            return ret;
        uint32_t mem_phandle = fdt_get_phandle(dt, mem_node);

        int ret =
            dt_device_set_reserved_mem(mem_node, node_name, phandle, mapping->iova, mapping->size);
        if (ret < 0)
            return ret;

        ret = dt_device_add_mem_region(fdt_alias, mem_phandle, NULL);
        if (ret < 0)
            return ret;
    }

    node = fdt_path_offset(dt, fdt_alias);
    if (node < 0)
        bail_cleanup("FDT: '%s' not found\n", fdt_alias);

    for (int i = 0; i < siodata->num_fwparams; i++) {
        struct sio_fwparam *param = &siodata->fwparams[i];

        if (fdt_appendprop_u32(dt, node, "apple,sio-firmware-params", param->key))
            bail_cleanup("FDT: couldn't append to SIO parameters\n");

        if (fdt_appendprop_u32(dt, node, "apple,sio-firmware-params", param->value))
            bail_cleanup("FDT: couldn't append to SIO parameters\n");
    }

err:
    free(siodata);
    return 0;
}

static int dt_setup_sio(void)
{
    static const char *sio_names[2] = {"sio", "sio1"};

    for (size_t i = 0; i < ARRAY_SIZE(sio_names); i++) {

        int node = fdt_path_offset(dt, sio_names[i]);
        if (node < 0)
            continue;

        char adt_path[16];
        snprintf(adt_path, sizeof(adt_path), "/arm-io/%s", sio_names[i]);

        if (dt_reserve_asc_firmware(adt_path, NULL, sio_names[i], true, 0))
            continue;
        if (dt_set_sio_fwdata(adt_path, sio_names[i]))
            continue;

        node = fdt_path_offset(dt, sio_names[i]);
        fdt_setprop_string(dt, node, "status", "okay");
    }

    return 0;
}

struct isp_segment_ranges {
    u64 phys;
    u64 iova;
    u64 remap;
    u32 size;
    u32 unk;
} PACKED;

static int dt_set_isp_fwdata(void)
{
    const char *fdt_path = "isp";
    int ret = 0;

    u64 phys, iova, size;

    int fdt_node = fdt_path_offset(dt, fdt_path);
    if (fdt_node < 0) {
        printf("FDT: '%s' not found\n", fdt_path);
        return 0;
    }

    if (firmware_set_fdt(dt, fdt_node, "apple,firmware-version", &os_firmware) < 0)
        bail("FDT: Could not set apple,firmware-version for %s\n", fdt_path);

    const struct fw_version_info *compat;

    switch (os_firmware.version) {
        case V13_6_2:
            compat = &fw_versions[V13_5];
            break;
        default:
            compat = &os_firmware;
            break;
    }

    if (firmware_set_fdt(dt, fdt_node, "apple,firmware-compat", compat) < 0)
        bail("FDT: Could not set apple,firmware-compat for %s\n", fdt_path);

    if (isp_get_heap(&phys, &iova, &size)) {
        const char *status = fdt_getprop(dt, fdt_node, "status", NULL);

        if (!status || strcmp(status, "disabled")) {
            printf("FDT: ISP enabled but not initialized, disabling\n");
            if (fdt_setprop_string(dt, fdt_node, "status", "disabled") < 0)
                bail("FDT: failed to set status property of ISP\n");
        }

        return 0;
    }

    int adt_node = adt_path_offset(adt, "/arm-io/isp");
    if (adt_node < 0)
        adt_node = adt_path_offset(adt, "/arm-io/isp0");
    if (adt_node < 0)
        return 0;

    uint32_t dev_phandle = fdt_get_phandle(dt, fdt_node);
    if (!dev_phandle) {
        ret = fdt_generate_phandle(dt, &dev_phandle);
        if (!ret)
            ret = fdt_setprop_u32(dt, fdt_node, "phandle", dev_phandle);
        if (ret != 0)
            bail("FDT: couldn't set '%s.phandle' property: %d\n", fdt_path, ret);
    }

    int mem_node = dt_get_or_add_reserved_mem("isp-heap", "apple,asc-mem", true, phys, size);
    if (mem_node < 0)
        return ret;

    ret = dt_device_set_reserved_mem(mem_node, "isp-heap", dev_phandle, iova, size);
    if (ret < 0)
        return ret;

    return 0;
}

static int dt_disable_missing_devs(const char *adt_prefix, const char *dt_prefix, int max_devs)
{
    int ret = -1;
    int adt_prefix_len = strlen(adt_prefix);
    int dt_prefix_len = strlen(dt_prefix);

    int acnt = 0, phcnt = 0;
    u64 *addrs = calloc(max_devs, sizeof(u64));
    u32 *phandles = calloc(max_devs * 5, sizeof(u32)); // Allow up to 5 extra nodes per device
    if (!addrs || !phandles)
        bail_cleanup("FDT: out of memory\n");

    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io", path);
    if (node < 0)
        bail_cleanup("ADT: /arm-io not found\n");

    int pp = 0;
    while (path[pp])
        pp++;
    path[pp + 1] = 0;

    u32 die_count;
    if (ADT_GETPROP(adt, node, "die-count", &die_count) < 0) {
        die_count = 1;
    }
    if (die_count > 8) {
        printf("ADT: limiting die-count from %u to 8\n", die_count);
        die_count = 8;
    }

    /* Find ADT registers */
    ADT_FOREACH_CHILD(adt, node)
    {
        const char *name = adt_get_name(adt, node);
        if (strncmp(name, adt_prefix, adt_prefix_len))
            continue;

        path[pp] = node;
        if (adt_get_reg(adt, path, "reg", 0, &addrs[acnt++], NULL) < 0)
            bail_cleanup("Error getting /arm-io/%s regs\n", name);
    }

    for (u32 die = 0; die < die_count; ++die) {
        char path[32] = "/soc";

        if (die_count > 1) {
            // pre-linux submission multi-die path
            // can probably removed the next time someone read this comment.
            snprintf(path, sizeof(path), "/soc/die%u", die);
            int die_node = fdt_path_offset(dt, path);
            if (die_node < 0) {
                /* this should use aliases for the soc nodes */
                u64 die_unit_addr = die * PMGR_DIE_OFFSET + 0x200000000;
                snprintf(path, sizeof(path), "/soc@%lx", die_unit_addr);
            }
        }

        int soc = fdt_path_offset(dt, path);
        if (soc < 0)
            bail("FDT: %s node not found in devtree\n", path);

        // parse ranges for address translation
        struct dt_ranges_tbl ranges[DT_MAX_RANGES] = {0};
        dt_parse_ranges(dt, soc, ranges);

        /* Disable primary devices */
        fdt_for_each_subnode(node, dt, soc)
        {
            const char *name = fdt_get_name(dt, node, NULL);
            if (strncmp(name, dt_prefix, dt_prefix_len))
                continue;

            const fdt64_t *reg = fdt_getprop(dt, node, "reg", NULL);
            if (!reg)
                bail_cleanup("FDT: failed to get reg property of %s\n", name);

            u64 addr = dt_translate(ranges, reg);

            int i;
            for (i = 0; i < acnt; i++)
                if (addrs[i] == addr)
                    break;
            if (i < acnt)
                continue;

            int iommus_size;
            const fdt32_t *iommus = fdt_getprop(dt, node, "iommus", &iommus_size);
            if (iommus) {
                if (iommus_size & 7 || iommus_size > 4 * 8) {
                    printf("FDT: bad iommus property for %s/%s\n", path, name);
                } else {
                    for (int i = 0; i < iommus_size / 8; i++)
                        phandles[phcnt++] = fdt32_ld(&iommus[i * 2]);
                }
            }

            int phys_size;
            const fdt32_t *phys = fdt_getprop(dt, node, "phys", &phys_size);
            if (phys) {
                if (phys_size & 7 || phys_size > 4 * 8) {
                    printf("FDT: bad phys property for %s/%s\n", path, name);
                } else {
                    for (int i = 0; i < phys_size / 8; i++)
                        phandles[phcnt++] = fdt32_ld(&phys[i * 2]);
                }
            }

            int port = fdt_subnode_offset(dt, node, "port");
            if (port >= 0) {
                int endpoint = fdt_subnode_offset(dt, port, "endpoint");
                if (endpoint >= 0) {
                    const fdt32_t *remote_endpoint =
                        fdt_getprop(dt, endpoint, "remote-endpoint", NULL);
                    if (remote_endpoint) {
                        phandles[phcnt++] = fdt32_ld(remote_endpoint);
                    }
                }
            }

            const char *status = fdt_getprop(dt, node, "status", NULL);
            if (!status || strcmp(status, "disabled")) {
                printf("FDT: Disabling missing device %s/%s\n", path, name);

                if (fdt_setprop_string(dt, node, "status", "disabled") < 0)
                    bail_cleanup("FDT: failed to set status property of %s/%s\n", path, name);
            }
        }

        /* Disable secondary devices */
        fdt_for_each_subnode(node, dt, soc)
        {
            const char *name = fdt_get_name(dt, node, NULL);
            u32 phandle = fdt_get_phandle(dt, node);
            if (!phandle)
                continue;

            for (int i = 0; i < phcnt; i++) {
                if (phandles[i] != phandle)
                    continue;

                phandles[i] = 0;

                const char *status = fdt_getprop(dt, node, "status", NULL);
                if (status && !strcmp(status, "disabled"))
                    continue;

                printf("FDT: Disabling secondary device %s/%s (%d)\n", path, name, phandle);

                if (fdt_setprop_string(dt, node, "status", "disabled") < 0)
                    bail_cleanup("FDT: failed to set status property of %s/%s\n", path, name);
            }
        }
    }

    for (int i = 0; i < phcnt; i++) {
        if (!phandles[i])
            continue;

        int node = fdt_node_offset_by_phandle(dt, phandles[i]);
        if (node < 0)
            bail_cleanup("FDT: failed to find secondary phandle %d\n", phandles[i]);

        const char *name = fdt_get_name(dt, node, NULL);

        // Should be usb-pd/connector/ports/port/endpoint
        if (!strcmp(name, "endpoint")) {
            for (int i = 0; i < 4; i++)
                if (node >= 0)
                    node = fdt_parent_offset(dt, node);
            if (node < 0) {
                printf("FDT: failed to walk up from endpoint phandle %d\n", phandles[i]);
                continue;
            }
            name = fdt_get_name(dt, node, NULL);
            if (strncmp(name, "usb-pd", 6)) {
                printf("FDT: unexpected secondary device %s walking up from endpoint\n", name);
                continue;
            }
        } else {
            printf("FDT: unexpected secondary device %s (%d)\n", name, phandles[i]);
            continue;
        }

        const char *status = fdt_getprop(dt, node, "status", NULL);
        if (status && !strcmp(status, "disabled"))
            continue;

        printf("FDT: Disabling secondary device %s\n", name);

        if (fdt_setprop_string(dt, node, "status", "disabled") < 0)
            bail_cleanup("FDT: failed to set status property of %s\n", name);
        break;
    }

    ret = 0;
err:
    free(phandles);
    free(addrs);

    return ret;
}

static int dt_transfer_virtios(void)
{
    int path[3];
    path[0] = adt_path_offset(adt, "/arm-io/");
    if (path[0] < 0)
        bail("ADT: /arm-io not found\n");

    int aic = fdt_node_offset_by_compatible(dt, -1, "apple,aic");
    if (aic == -FDT_ERR_NOTFOUND)
        aic = fdt_node_offset_by_compatible(dt, -1, "apple,aic2");
    if (aic == -FDT_ERR_NOTFOUND)
        aic = fdt_node_offset_by_compatible(dt, -1, "apple,aic3");
    if (aic < 0)
        bail("FDT: failed to find AIC node\n");

    u32 aic_phandle = fdt_get_phandle(dt, aic);
    const fdt32_t *ic_prop = fdt_getprop(dt, aic, "#interrupt-cells", NULL);
    u32 intcells = 0;
    if (ic_prop)
        intcells = fdt32_ld(ic_prop);
    if (intcells < 3 || intcells > 4)
        bail("FDT: bad '#interrupt-cells' on AIC node (%d)\n", intcells);

    for (u32 i = 0; i < 16; i++) {
        char name[16], fullname[32];
        snprintf(name, sizeof(name) - 1, "virtio%d", i);

        path[1] = adt_subnode_offset(adt, path[0], name);
        if (path[1] < 0)
            break;
        path[2] = 0;

        u64 addr, size;
        if (adt_get_reg(adt, path, "reg", 0, &addr, &size) < 0)
            bail("ADT: error getting /arm-io/%s regs\n", name);

        u32 irq;
        ADT_GETPROP(adt, path[1], "interrupts", &irq);

        snprintf(fullname, sizeof(fullname) - 1, "virtio@%lx", addr);
        printf("FDT: Adding %s found in ADT\n", name);

        int fnode = fdt_add_subnode(dt, 0, fullname);
        if (fnode < 0)
            bail("FDT: failed to create %s\n", fullname);

        if (fdt_setprop_string(dt, fnode, "compatible", "virtio,mmio"))
            bail("FDT: couldn't set %s.compatible\n", fullname);

        fdt64_t reg[2];
        fdt64_st(reg + 0, addr);
        fdt64_st(reg + 1, size);
        if (fdt_setprop(dt, fnode, "reg", reg, sizeof(reg)))
            bail("FDT: couldn't set %s.reg\n", fullname);

        if (fdt_setprop_u32(dt, fnode, "interrupt-parent", aic_phandle))
            bail("FDT: couldn't set %s.interrupt-parent\n", fullname);

        fdt32_t intprop[4];
        fdt32_st(intprop + 0, 0); // AIC_IRQ
        fdt32_st(intprop + 1, 0);
        fdt32_st(intprop + intcells - 2, irq);
        fdt32_st(intprop + intcells - 1, 4); // IRQ_TYPE_LEVEL_HIGH
        if (fdt_setprop(dt, fnode, "interrupts", intprop, 4 * intcells))
            bail("FDT: couldn't set %s.interrupts\n", fullname);
    }

    return 0;
}

void kboot_set_initrd(void *start, size_t size)
{
    initrd_start = start;
    initrd_size = size;
}

int kboot_set_chosen(const char *name, const char *value)
{
    int i = 0;

    if (!name)
        return -1;

    for (i = 0; i < MAX_CHOSEN_PARAMS; i++) {
        if (!chosen_params[i][0]) {
            chosen_params[i][0] = calloc(strlen(name) + 1, 1);
            strcpy(chosen_params[i][0], name);
            break;
        }

        if (!strcmp(name, chosen_params[i][0])) {
            free(chosen_params[i][1]);
            chosen_params[i][1] = NULL;
            break;
        }
    }

    if (i >= MAX_CHOSEN_PARAMS)
        return -1;

    if (value) {
        chosen_params[i][1] = calloc(strlen(value) + 1, 1);
        strcpy(chosen_params[i][1], value);
    }

    return i;
}

#define LOGBUF_SIZE SZ_16K

struct {
    void *buffer;
    size_t wp;
} logbuf;

static bool log_console_iodev_can_write(void *opaque)
{
    UNUSED(opaque);
    return !!logbuf.buffer;
}

static ssize_t log_console_iodev_write(void *opaque, const void *buf, size_t len)
{
    UNUSED(opaque);

    if (!logbuf.buffer)
        return 0;

    ssize_t wrote = 0;
    size_t remain = LOGBUF_SIZE - logbuf.wp;
    while (remain < len) {
        memcpy(logbuf.buffer + logbuf.wp, buf, remain);
        logbuf.wp = 0;
        wrote += remain;
        buf += remain;
        len -= remain;
        remain = LOGBUF_SIZE;
    }
    memcpy(logbuf.buffer + logbuf.wp, buf, len);
    wrote += len;
    logbuf.wp = (logbuf.wp + len) % LOGBUF_SIZE;

    return wrote;
}

const struct iodev_ops iodev_log_ops = {
    .can_write = log_console_iodev_can_write,
    .write = log_console_iodev_write,
};

struct iodev iodev_log = {
    .ops = &iodev_log_ops,
    .usage = USAGE_CONSOLE,
    .lock = SPINLOCK_INIT,
};

static int dt_setup_mtd_phram(void)
{
    char node_name[64];
    snprintf(node_name, sizeof(node_name), "flash@%lx", (u64)adt);

    int node = dt_get_or_add_reserved_mem(node_name, "phram", false, (u64)adt,
                                          ALIGN_UP(cur_boot_args.devtree_size, SZ_16K));

    if (node > 0) {
        int ret = fdt_setprop_string(dt, node, "label", "adt");
        if (ret)
            bail("FDT: failed to setup ADT MTD phram label\n");
    }

    // init memory backed iodev for console log
    logbuf.buffer = (void *)top_of_memory_alloc(LOGBUF_SIZE);
    if (!logbuf.buffer)
        bail("FDT: failed to allocate m1n1 log buffer\n");

    snprintf(node_name, sizeof(node_name), "flash@%lx", (u64)logbuf.buffer);
    node = dt_get_or_add_reserved_mem(node_name, "phram", false, (u64)logbuf.buffer, SZ_16K);

    if (node > 0) {
        int ret = fdt_setprop_string(dt, node, "label", "m1n1_stage2.log");
        if (ret)
            bail("FDT: failed to setup m1n1 log MTD phram label\n");
    }

    return 0;
}

int kboot_prepare_dt(void *fdt)
{
    if (dt) {
        free(dt);
        dt = NULL;
    }

    /* Need to init ISP early to carve out heap */
    isp_init();

    dt_bufsize = fdt_totalsize(fdt);
    assert(dt_bufsize);

    dt_bufsize += 6 * SZ_16K; // Add 96K of buffer for modifications
    dt = memalign(DT_ALIGN, dt_bufsize);

    if (fdt_open_into(fdt, dt, dt_bufsize) < 0)
        bail("FDT: fdt_open_into() failed\n");

    if (fdt_add_mem_rsv(dt, (u64)dt, dt_bufsize))
        bail("FDT: couldn't add reservation for the devtree\n");

    if (fdt_add_mem_rsv(dt, (u64)_base, ((u64)_end) - ((u64)_base)))
        bail("FDT: couldn't add reservation for m1n1\n");

    /* setup console log buffer early to cpature as much log as possible */
    dt_setup_mtd_phram();

    if (dt_set_chosen())
        return -1;
    if (dt_set_serial_number())
        return -1;
    if (dt_set_cpus())
        return -1;
    if (dt_set_mac_addresses())
        return -1;
    if (dt_set_wifi())
        return -1;
    if (dt_set_bluetooth())
        return -1;
    if (dt_set_uboot())
        return -1;
    if (kboot_setup_atc(dt))
        return -1;
    if (dt_set_acio_tunables())
        return -1;
    if (dt_set_pcie_tunables())
        return -1;
    if (dt_set_display())
        return -1;
    if (dt_set_gpu(dt))
        return -1;
    if (dt_set_multitouch())
        return -1;
    if (dt_set_sep())
        return -1;
    if (dt_set_nvram())
        return -1;
    if (dt_set_ipd())
        return -1;
    if (dt_disable_missing_devs("usb-drd", "usb@", 8))
        return -1;
    if (dt_disable_missing_devs("i2c", "i2c@", 8))
        return -1;
    if (dt_setup_sio())
        return -1;
    if (dt_reserve_asc_firmware("/arm-io/isp", "/arm-io/isp0", "isp", false, isp_iova_base()))
        return -1;
    if (dt_set_isp_fwdata())
        return -1;
#ifndef RELEASE
    if (dt_transfer_virtios())
        return 1;
#endif

    /*
     * Set the /memory node late since we might be allocating from the top of memory
     * in one of the above devicetree prep functions, and we want an up-to-date value
     * for the usable memory span to make it into the devicetree.
     */
    if (dt_set_memory())
        return -1;

    if (fdt_pack(dt))
        bail("FDT: fdt_pack() failed\n");

    u32 dt_remain = dt_bufsize - fdt_totalsize(dt);
    if (dt_remain < SZ_16K)
        printf("FDT: free dt buffer space low, %u bytes left\n", dt_remain);

    printf("FDT prepared at %p\n", dt);

    return 0;
}

int kboot_boot(void *kernel)
{
    mcc_enable_cache();
    tunables_apply_static();
    clk_init();

    usb_init();
    pcie_init();
    dapf_init_all();

    printf("Setting SMP mode to WFE...\n");
    smp_set_wfe_mode(true);
    printf("Preparing to boot kernel at %p with fdt at %p\n", kernel, dt);

    next_stage.entry = kernel;
    next_stage.args[0] = (u64)dt;
    next_stage.args[1] = 0;
    next_stage.args[2] = 0;
    next_stage.args[3] = 0;
    next_stage.args[4] = 0;
    next_stage.restore_logo = false;

    return 0;
}
