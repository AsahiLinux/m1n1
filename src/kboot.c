/* SPDX-License-Identifier: MIT */

#include "kboot.h"
#include "adt.h"
#include "assert.h"
#include "dapf.h"
#include "exception.h"
#include "malloc.h"
#include "memory.h"
#include "pcie.h"
#include "sep.h"
#include "smp.h"
#include "types.h"
#include "usb.h"
#include "utils.h"
#include "xnuboot.h"

#include "libfdt/libfdt.h"

#define MAX_CHOSEN_PARAMS 16

#define MAX_ATC_DEVS 8

static void *dt = NULL;
static int dt_bufsize = 0;
static void *initrd_start = NULL;
static size_t initrd_size = 0;
static char *chosen_params[MAX_CHOSEN_PARAMS][2];

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

    if (ADT_GETPROP(adt, node, "partially-occluded-display", &val) < 0 || !val) {
        printf("FDT: No notch detected\n");
        return;
    }

    u64 hfrac = cur_boot_args.video.height * 16 / cur_boot_args.video.width;
    u64 new_height = cur_boot_args.video.width * hfrac / 16;

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
        bail("SEP: couldn't get enough random bytes for KASLR seed");
    if (sep_get_random(rng_seed, sizeof(rng_seed)) != sizeof(rng_seed))
        bail("SEP: couldn't get enough random bytes for RNG seed");

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
    }

    int ipd = adt_path_offset(adt, "/arm-io/spi3/ipd");
    if (ipd < 0) {
        printf("ADT: /arm-io/spi3/ipd not found, no keyboard\n");
    } else {
        u32 len;
        const u8 *kblang = adt_getprop(adt, ipd, "kblang-calibration", &len);
        if (kblang && len >= 2) {
            if (fdt_setprop_u32(dt, node, "asahi,kblang-code", kblang[1]))
                bail("FDT: couldn't set asahi,kblang-code");
        } else {
            printf("ADT: kblang-calibration not found, no keyboard layout\n");
        }
    }

    if (dt_set_rng_seed_sep(node))
        return dt_set_rng_seed_adt(node);

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
    int ret = 0;

    int cpus = fdt_path_offset(dt, "/cpus");
    if (cpus < 0)
        bail("FDT: /cpus node not found in devtree\n");

    uint32_t *pruned_phandles = malloc(MAX_CPUS * sizeof(uint32_t));
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

            fdt32_t *new_phs = malloc(len);
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
} mac_address_devices[] = {
    {
        .alias = "bluetooth0",
        .fdt_property = "local-bd-address",
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
        bail("ADT: Failed to get %s", adt_name);

    fdt_setprop(dt, node, fdt_name, cal_blob, len);
    return 0;
}

static int dt_set_bluetooth(void)
{
    int ret;
    int anode = adt_path_offset(adt, "/arm-io/bluetooth");

    if (anode < 0)
        bail("ADT: /arm-io/bluetooth not found\n");

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

static int dt_set_wifi(void)
{
    int anode = adt_path_offset(adt, "/arm-io/wlan");

    if (anode < 0)
        bail("ADT: /arm-io/wlan not found\n");

    uint8_t info[16];
    if (ADT_GETPROP_ARRAY(adt, anode, "wifi-antenna-sku-info", info) < 0)
        bail("ADT: Failed to get wifi-antenna-sku-info");

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
        bail("ADT: Failed to get wifi-calibration-msf");

    fdt_setprop(dt, node, "brcm,cal-blob", cal_blob, len);

    return 0;
}

static void dt_set_uboot_dm_preloc(int node)
{
    // Tell U-Boot to bind this node early
    fdt_setprop_empty(dt, node, "u-boot,dm-pre-reloc");

    // Make sure the power domains are bound early as well
    int pds_size;
    const fdt32_t *pds = fdt_getprop(dt, node, "power-domains", &pds_size);
    if (!pds)
        return;

    fdt32_t *phandles = malloc(pds_size);
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

struct atc_tunable {
    u32 offset : 24;
    u32 size : 8;
    u32 mask;
    u32 value;
} PACKED;
static_assert(sizeof(struct atc_tunable) == 12, "Invalid atc_tunable size");

struct atc_tunable_info {
    const char *adt_name;
    const char *fdt_name;
    size_t reg_offset;
    size_t reg_size;
    bool required;
};

static const struct atc_tunable_info atc_tunables[] = {
    /* global tunables applied after power on or reset */
    {"tunable_ATC0AXI2AF", "apple,tunable-axi2af", 0x0, 0x4000, true},
    {"tunable_ATC_FABRIC", "apple,tunable-common", 0x45000, 0x4000, true},
    {"tunable_AUS_CMN_TOP", "apple,tunable-common", 0x800, 0x4000, true},
    {"tunable_AUS_CMN_SHM", "apple,tunable-common", 0xa00, 0x4000, true},
    {"tunable_AUSPLL_CORE", "apple,tunable-common", 0x2200, 0x4000, true},
    {"tunable_AUSPLL_TOP", "apple,tunable-common", 0x2000, 0x4000, true},
    {"tunable_CIO3PLL_CORE", "apple,tunable-common", 0x2a00, 0x4000, true},
    {"tunable_CIO3PLL_TOP", "apple,tunable-common", 0x2800, 0x4000, true},
    {"tunable_CIO_CIO3PLL_TOP", "apple,tunable-common", 0x2800, 0x4000, false},
    {"tunable_USB_ACIOPHY_TOP", "apple,tunable-common", 0x0, 0x4000, true},
    /* lane-specific tunables applied after a cable is connected */
    {"tunable_DP_LN0_AUSPMA_TX_TOP", "apple,tunable-lane0-dp", 0xc000, 0x1000, true},
    {"tunable_DP_LN1_AUSPMA_TX_TOP", "apple,tunable-lane1-dp", 0x13000, 0x1000, true},
    {"tunable_USB_LN0_AUSPMA_RX_TOP", "apple,tunable-lane0-usb", 0x9000, 0x1000, true},
    {"tunable_USB_LN0_AUSPMA_RX_EQ", "apple,tunable-lane0-usb", 0xa000, 0x1000, true},
    {"tunable_USB_LN0_AUSPMA_RX_SHM", "apple,tunable-lane0-usb", 0xb000, 0x1000, true},
    {"tunable_USB_LN0_AUSPMA_TX_TOP", "apple,tunable-lane0-usb", 0xc000, 0x1000, true},
    {"tunable_USB_LN1_AUSPMA_RX_TOP", "apple,tunable-lane1-usb", 0x10000, 0x1000, true},
    {"tunable_USB_LN1_AUSPMA_RX_EQ", "apple,tunable-lane1-usb", 0x11000, 0x1000, true},
    {"tunable_USB_LN1_AUSPMA_RX_SHM", "apple,tunable-lane1-usb", 0x12000, 0x1000, true},
    {"tunable_USB_LN1_AUSPMA_TX_TOP", "apple,tunable-lane1-usb", 0x13000, 0x1000, true},
    {"tunable_CIO_LN0_AUSPMA_RX_TOP", "apple,tunable-lane0-cio", 0x9000, 0x1000, true},
    {"tunable_CIO_LN0_AUSPMA_RX_EQ", "apple,tunable-lane0-cio", 0xa000, 0x1000, true},
    {"tunable_CIO_LN0_AUSPMA_RX_SHM", "apple,tunable-lane0-cio", 0xb000, 0x1000, true},
    {"tunable_CIO_LN0_AUSPMA_TX_TOP", "apple,tunable-lane0-cio", 0xc000, 0x1000, true},
    {"tunable_CIO_LN1_AUSPMA_RX_TOP", "apple,tunable-lane1-cio", 0x10000, 0x1000, true},
    {"tunable_CIO_LN1_AUSPMA_RX_EQ", "apple,tunable-lane1-cio", 0x11000, 0x1000, true},
    {"tunable_CIO_LN1_AUSPMA_RX_SHM", "apple,tunable-lane1-cio", 0x12000, 0x1000, true},
    {"tunable_CIO_LN1_AUSPMA_TX_TOP", "apple,tunable-lane1-cio", 0x13000, 0x1000, true},
};

static int dt_append_atc_tunable(int adt_node, int fdt_node,
                                 const struct atc_tunable_info *tunable_info)
{
    u32 tunables_len;
    const struct atc_tunable *tunable_adt =
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
        const struct atc_tunable *tunable = &tunable_adt[j];

        if (tunable->size != 32) {
            printf("kboot: ATC tunable has invalid size %d\n", tunable->size);
            return -1;
        }

        if (tunable->offset % (tunable->size / 8)) {
            printf("kboot: ATC tunable has unaligned offset %x\n", tunable->offset);
            return -1;
        }

        if (tunable->offset + (tunable->size / 8) > tunable_info->reg_size) {
            printf("kboot: ATC tunable has invalid offset %x\n", tunable->offset);
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

static void dt_copy_atc_tunables(const char *adt_path, const char *dt_alias)
{
    int ret;

    int adt_node = adt_path_offset(adt, adt_path);
    if (adt_node < 0)
        return;

    const char *fdt_path = fdt_get_alias(dt, dt_alias);
    if (fdt_path == NULL) {
        printf("FDT: Unable to find alias %s\n", dt_alias);
        return;
    }

    int fdt_node = fdt_path_offset(dt, fdt_path);
    if (fdt_node < 0) {
        printf("FDT: Unable to find path %s for alias %s\n", fdt_path, dt_alias);
        return;
    }

    for (size_t i = 0; i < sizeof(atc_tunables) / sizeof(*atc_tunables); ++i) {
        ret = dt_append_atc_tunable(adt_node, fdt_node, &atc_tunables[i]);
        if (ret)
            goto cleanup;
    }

    return;

cleanup:
    /*
     * USB3 and Thunderbolt won't work if something went wrong. Clean up to make
     * sure we don't leave half-filled properties around so that we can at least
     * try to boot with USB2 support only.
     */
    for (size_t i = 0; i < sizeof(atc_tunables) / sizeof(*atc_tunables); ++i)
        fdt_delprop(dt, fdt_node, atc_tunables[i].fdt_name);

    printf("FDT: Unable to setup ATC tunables for %s - USB3/Thunderbolt will not work\n", adt_path);
}

static int dt_set_atc_tunables(void)
{
    char adt_path[32];
    char fdt_alias[32];

    for (int i = 0; i < MAX_ATC_DEVS; ++i) {
        memset(adt_path, 0, sizeof(adt_path));
        snprintf(adt_path, sizeof(adt_path), "/arm-io/atc-phy%d", i);

        memset(fdt_alias, 0, sizeof(adt_path));
        snprintf(fdt_alias, sizeof(fdt_alias), "atcphy%d", i);

        dt_copy_atc_tunables(adt_path, fdt_alias);
    }

    return 0;
}

#define MAX_RANGES 8

struct ranges_tbl {
    u64 start;
    u64 parent;
    u64 size;
};

static void parse_ranges(int soc, struct ranges_tbl *ranges)
{
    int len;
    const struct fdt_property *ranges_prop = fdt_get_property(dt, soc, "ranges", &len);
    if (ranges_prop && len > 0) {
        int idx = 0;
        int num_entries = len / sizeof(fdt64_t);
        if (num_entries > MAX_RANGES)
            num_entries = MAX_RANGES;

        const fdt64_t *entry = (const fdt64_t *)ranges_prop->data;
        for (int i = 0; i < num_entries; ++i) {
            u64 start = fdt64_ld(entry++);
            u64 parent = fdt64_ld(entry++);
            u64 size = fdt64_ld(entry++);
            if (size) {
                ranges[idx].start = start;
                ranges[idx].parent = parent;
                ranges[idx].size = size;
                idx++;
            }
        }
    }
}

static u64 translate(struct ranges_tbl *ranges, const fdt64_t *reg)
{
    u64 addr = fdt64_ld(reg);
    for (int idx = 0; idx < MAX_RANGES; ++idx) {
        if (ranges[idx].size == 0)
            break;
        if (addr >= ranges[idx].start && addr < ranges[idx].start + ranges[idx].size)
            return ranges[idx].parent - ranges[idx].start + addr;
    }

    return addr;
}

static int dt_disable_missing_devs(const char *adt_prefix, const char *dt_prefix, int max_devs)
{
    int ret = -1;
    int adt_prefix_len = strlen(adt_prefix);
    int dt_prefix_len = strlen(dt_prefix);

    int acnt = 0, phcnt = 0;
    u64 *addrs = malloc(max_devs * sizeof(u64));
    u32 *phandles = malloc(max_devs * sizeof(u32) * 4); // Allow up to 4 extra nodes per device
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
        printf("ADT: missing die-count property handling device as single die device\n");
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
        char path[16] = "/soc";

        if (die_count > 1)
            snprintf(path, sizeof(path), "/soc/die%u", die);

        int soc = fdt_path_offset(dt, path);
        if (soc < 0)
            bail("FDT: %s node not found in devtree\n", path);

        // parse ranges for address translation
        struct ranges_tbl ranges[MAX_RANGES] = {0};
        parse_ranges(soc, ranges);

        /* Disable primary devices */
        fdt_for_each_subnode(node, dt, soc)
        {
            const char *name = fdt_get_name(dt, node, NULL);
            if (strncmp(name, dt_prefix, dt_prefix_len))
                continue;

            const fdt64_t *reg = fdt_getprop(dt, node, "reg", NULL);
            if (!reg)
                bail_cleanup("FDT: failed to get reg property of %s\n", name);

            u64 addr = translate(ranges, reg);

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

            for (int i = 0; i < phcnt; i++) {
                if (phandles[i] != phandle)
                    continue;

                const char *status = fdt_getprop(dt, node, "status", NULL);
                if (status && !strcmp(status, "disabled"))
                    continue;

                printf("FDT: Disabling secondary device %s/%s\n", path, name);

                if (fdt_setprop_string(dt, node, "status", "disabled") < 0)
                    bail_cleanup("FDT: failed to set status property of %s/%s\n", path, name);
                break;
            }
        }
    }

    ret = 0;
err:
    free(phandles);
    free(addrs);

    return ret;
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

    for (int i = 0; i < MAX_CHOSEN_PARAMS; i++) {
        if (!chosen_params[i][0]) {
            chosen_params[i][0] = malloc(strlen(name) + 1);
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
        chosen_params[i][1] = malloc(strlen(value) + 1);
        strcpy(chosen_params[i][1], value);
    }

    return i;
}

int kboot_prepare_dt(void *fdt)
{
    if (dt) {
        free(dt);
        dt = NULL;
    }

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
    if (dt_set_wifi())
        return -1;
    if (dt_set_bluetooth())
        return -1;
    if (dt_set_uboot())
        return -1;
    if (dt_set_atc_tunables())
        return -1;
    if (dt_disable_missing_devs("usb-drd", "usb@", 8))
        return -1;
    if (dt_disable_missing_devs("i2c", "i2c@", 8))
        return -1;

    if (fdt_pack(dt))
        bail("FDT: fdt_pack() failed\n");

    printf("FDT prepared at %p\n", dt);

    return 0;
}

int kboot_boot(void *kernel)
{
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
