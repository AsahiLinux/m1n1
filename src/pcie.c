/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "pcie.h"
#include "pmgr.h"
#include "tunables.h"
#include "utils.h"

/*
 * The ADT uses 17 register sets:
 *
 * 0:  90000000 00000006 10000000 00000000  ECAM
 * 1:  80000000 00000006 00040000 00000000  RC
 * 2:  80080000 00000006 00090000 00000000  PHY
 * 3:  800c0000 00000006 00020000 00000000  PHY IP
 * 4:  8c000000 00000006 00004000 00000000  AXI
 * 5:  3d2bc000 00000000 00001000 00000000  fuses
 * 6:  81000000 00000006 00008000 00000000  port 0
 * 7:  81010000 00000006 00001000 00000000
 * 8:  80084000 00000006 00004000 00000000  port 0 PHY
 * 9:  800c8000 00000006 00016610 00000000
 * 10: 82000000 00000006 00008000 00000000  port 1
 * 11: 82010000 00000006 00001000 00000000
 * 12: 80088000 00000006 00004000 00000000  port 1 PHY
 * 13: 800d0000 00000006 00006000 00000000
 * 14: 83000000 00000006 00008000 00000000  port 2
 * 15: 83010000 00000006 00001000 00000000
 * 16: 8008c000 00000006 00004000 00000000  port 2 PHY
 * 17: 800d8000 00000006 00006000 00000000
 */

/* PHY registers */

#define APCIE_PHY_CTRL         0x000
#define APCIE_PHY_CTRL_CLK0REQ BIT(0)
#define APCIE_PHY_CTRL_CLK1REQ BIT(1)
#define APCIE_PHY_CTRL_CLK0ACK BIT(2)
#define APCIE_PHY_CTRL_CLK1ACK BIT(3)
#define APCIE_PHY_CTRL_RESET   BIT(7)

/* Port registers */

#define APCIE_PORT_APPCLK    0x800
#define APCIE_PORT_APPCLK_EN BIT(0)

#define APCIE_PORT_STATUS     0x804
#define APCIE_PORT_STATUS_RUN BIT(0)

#define APCIE_PORT_RESET     0x814
#define APCIE_PORT_RESET_DIS BIT(0)

/* DesignWare PCIe Core registers */

#define DWC_DBI_RO_WR    0x8bc
#define DWC_DBI_RO_WR_EN BIT(0)

struct fuse_bits {
    u16 src_reg;
    u16 tgt_reg;
    u8 src_bit;
    u8 tgt_bit;
    u8 width;
};

struct fuse_bits pcie_fuse_bits[] = {
    {0x0084, 0x6238, 4, 0, 6},   {0x0084, 0x6220, 10, 14, 3}, {0x0084, 0x62a4, 13, 17, 2},
    {0x0418, 0x522c, 27, 9, 2},  {0x0418, 0x522c, 13, 12, 3}, {0x0418, 0x5220, 18, 14, 3},
    {0x0418, 0x52a4, 21, 17, 2}, {0x0418, 0x522c, 23, 16, 5}, {0x0418, 0x5278, 23, 20, 3},
    {0x0418, 0x5018, 31, 2, 1},  {0x041c, 0x1204, 0, 2, 5},   {}};

static bool pcie_initialized = false;
static u64 rc_base;
static u64 phy_base;
static u64 phy_ip_base;
static u64 fuse_base;
static u32 port_count;
static u64 port_base[8];

int pcie_init(void)
{
    const char *path = "/arm-io/apcie";
    int adt_path[8];
    int adt_offset;
    u64 port_reg_cnt;

    if (pcie_initialized)
        return 0;

    adt_offset = adt_path_offset_trace(adt, path, adt_path);
    if (adt_offset < 0) {
        printf("pcie: Error getting node %s\n", path);
        return -1;
    }

    if (adt_is_compatible(adt, adt_offset, "apcie,t8103")) {
        port_reg_cnt = 4;
    } else if (adt_is_compatible(adt, adt_offset, "apcie,t6000")) {
        port_reg_cnt = 5;
    } else {
        printf("pcie: Unsupported compatible\n");
        return -1;
    }

    if (ADT_GETPROP(adt, adt_offset, "#ports", &port_count) < 0) {
        printf("pcie: Error getting port count for %s\n", path);
        return -1;
    }

    u64 config_base;
    if (adt_get_reg(adt, adt_path, "reg", 0, &config_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", 0, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", 1, &rc_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", 1, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", 2, &phy_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", 2, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", 3, &phy_ip_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", 3, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", 5, &fuse_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", 5, path);
        return -1;
    }

    if (pmgr_adt_clocks_enable(path)) {
        printf("pcie: Error enabling clocks for %s\n", path);
        return -1;
    }

    if (tunables_apply_local(path, "apcie-axi2af-tunables", 4)) {
        printf("pcie: Error applying %s for %s\n", "apcie-axi2af-tunables", path);
        return -1;
    }
    if (tunables_apply_local(path, "apcie-common-tunables", 1)) {
        printf("pcie: Error applying %s for %s\n", "apcie-common-tunables", path);
        return -1;
    }

    /*
     * Initialize PHY.
     */

    if (tunables_apply_local(path, "apcie-phy-tunables", 2)) {
        printf("pcie: Error applying %s for %s\n", "apcie-phy-tunables", path);
        return -1;
    }

    set32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK0REQ);
    if (poll32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK0ACK, APCIE_PHY_CTRL_CLK0ACK, 50000)) {
        printf("pcie: Timeout enabling PHY CLK0\n");
        return -1;
    }

    set32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK1REQ);
    if (poll32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK1ACK, APCIE_PHY_CTRL_CLK1ACK, 50000)) {
        printf("pcie: Timeout enabling PHY CLK1\n");
        return -1;
    }

    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_RESET);
    udelay(1);

    /* ??? */
    set32(rc_base + 0x24, 1);
    udelay(1);

    /* Apply "fuses". */
    for (int i = 0; pcie_fuse_bits[i].width; i++) {
        u32 fuse;
        fuse = (read32(fuse_base + pcie_fuse_bits[i].src_reg) >> pcie_fuse_bits[i].src_bit);
        mask32(phy_ip_base + pcie_fuse_bits[i].tgt_reg, (1 << pcie_fuse_bits[i].width) - 1,
               fuse << pcie_fuse_bits[i].tgt_bit);
    }

    if (tunables_apply_local(path, "apcie-phy-ip-pll-tunables", 3)) {
        printf("pcie: Error applying %s for %s\n", "apcie-phy-ip-pll-tunables", path);
        return -1;
    }
    if (tunables_apply_local(path, "apcie-phy-ip-auspma-tunables", 3)) {
        printf("pcie: Error applying %s for %s\n", "apcie-phy-ip-auspma-tunables", path);
        return -1;
    }

    int port;
    for (port = 0; port < port_count; port++) {
        char bridge[64];

        printf("pcie: Initializing port %d\n", port);

        /*
         * Initialize RC port.
         */

        sprintf(bridge, "/arm-io/apcie/pci-bridge%d", port);

        if (adt_path_offset(adt, bridge) < 0)
            continue;

        if (adt_get_reg(adt, adt_path, "reg", port * port_reg_cnt + 6, &port_base[port], NULL)) {
            printf("pcie: Error getting reg with index %d for %s\n", port * 4 + 6, path);
            return -1;
        }

        if (tunables_apply_local_addr(bridge, "apcie-config-tunables", port_base[port])) {
            printf("pcie: Error applying %s for %s\n", "apcie-config-tunables", bridge);
            return -1;
        }

        set32(port_base[port] + APCIE_PORT_APPCLK, APCIE_PORT_APPCLK_EN);

        /* PERSTN */
        set32(port_base[port] + APCIE_PORT_RESET, APCIE_PORT_RESET_DIS);

        if (poll32(port_base[port] + APCIE_PORT_STATUS, APCIE_PORT_STATUS_RUN,
                   APCIE_PORT_STATUS_RUN, 250000)) {
            printf("pcie: Port failed to come up on %s\n", bridge);
            return -1;
        }

        /* Make Designware PCIe Core registers writable. */
        set32(config_base + DWC_DBI_RO_WR, DWC_DBI_RO_WR_EN);

        if (tunables_apply_local_addr(bridge, "pcie-rc-tunables", config_base)) {
            printf("pcie: Error applying %s for %s\n", "pcie-rc-tunables", bridge);
            return -1;
        }
        if (tunables_apply_local_addr(bridge, "pcie-rc-gen3-shadow-tunables", config_base)) {
            printf("pcie: Error applying %s for %s\n", "pcie-rc-gen3-shadow-tunables", bridge);
            return -1;
        }
        if (tunables_apply_local_addr(bridge, "pcie-rc-gen4-shadow-tunables", config_base)) {
            printf("pcie: Error applying %s for %s\n", "pcie-rc-gen4-shadow-tunables", bridge);
            return -1;
        }

        /* Make Designware PCIe Core registers readonly. */
        clear32(config_base + DWC_DBI_RO_WR, DWC_DBI_RO_WR_EN);

        /* Move to the next PCIe device on this bus. */
        config_base += (1 << 15);
    }

    pcie_initialized = true;
    printf("pcie: initialized.\n");

    return 0;
}

int pcie_shutdown(void)
{
    if (!pcie_initialized)
        return 0;

    for (int port = 0; port < port_count; port++) {
        clear32(port_base[port] + APCIE_PORT_RESET, APCIE_PORT_RESET_DIS);
        clear32(port_base[port] + APCIE_PORT_APPCLK, APCIE_PORT_APPCLK_EN);
    }

    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_RESET);
    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK1REQ);
    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK0REQ);

    pcie_initialized = false;
    printf("pcie: shutdown.\n");

    return 0;
}
