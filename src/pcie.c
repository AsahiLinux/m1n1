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
 * 6:  81000000 00000006 00008000 00000000  port 0 config
 * 7:  81010000 00000006 00001000 00000000  port 0 LTSSM debug
 * 8:  80084000 00000006 00004000 00000000  port 0 PHY
 * 9:  800c8000 00000006 00016610 00000000  port 0 PHY IP
   <macOS 12.0 RC and later add a per-port Intr2AXI reg here>
 * 10: 82000000 00000006 00008000 00000000  port 1 config
 * 11: 82010000 00000006 00001000 00000000  port 1 LTSSM debug
 * 12: 80088000 00000006 00004000 00000000  port 1 PHY
 * 13: 800d0000 00000006 00006000 00000000  port 1 PHY IP
   <...>
 * 14: 83000000 00000006 00008000 00000000  port 2 config
 * 15: 83010000 00000006 00001000 00000000  port 2 LTSSM debug
 * 16: 8008c000 00000006 00004000 00000000  port 2 PHY
 * 17: 800d8000 00000006 00006000 00000000  port 2 PHY IP
   <...>
 */

/* PHY registers */

#define APCIE_PHY_CTRL         0x000
#define APCIE_PHY_CTRL_CLK0REQ BIT(0)
#define APCIE_PHY_CTRL_CLK1REQ BIT(1)
#define APCIE_PHY_CTRL_CLK0ACK BIT(2)
#define APCIE_PHY_CTRL_CLK1ACK BIT(3)
#define APCIE_PHY_CTRL_RESET   BIT(7)

#define APCIE_PHYIF_CTRL     0x024
#define APCIE_PHYIF_CTRL_RUN BIT(0)

/* PHY common registers */
#define APCIE_PHYCMN_CLK         0x000
#define APCIE_PHYCMN_CLK_MODE    GENMASK(1, 0) /* Guesswork */
#define APCIE_PHYCMN_CLK_MODE_ON 1
#define APCIE_PHYCMN_CLK_100MHZ  BIT(31)

/* Port registers */

#define APCIE_PORT_LINKSTS      0x208
#define APCIE_PORT_LINKSTS_UP   BIT(0)
#define APCIE_PORT_LINKSTS_BUSY BIT(2)
#define APCIE_PORT_LINKSTS_L2   BIT(6)

#define APCIE_PORT_APPCLK    0x800
#define APCIE_PORT_APPCLK_EN BIT(0)

#define APCIE_PORT_STATUS     0x804
#define APCIE_PORT_STATUS_RUN BIT(0)

#define APCIE_PORT_RESET     0x814
#define APCIE_PORT_RESET_DIS BIT(0)

#define APCIE_T602X_PORT_RESET  0x82c
#define APCIE_T602X_PORT_MSIMAP 0x3800

/* PCIe capability registers */
#define PCIE_CAP_BASE    0x70
#define PCIE_LNKCAP      0x0c
#define PCIE_LNKCAP_SLS  GENMASK(3, 0)
#define PCIE_LNKCAP_MLW  GENMASK(9, 4)
#define PCIE_LNKCAP2     0x2c
#define PCIE_LNKCAP2_SLS GENMASK(6, 1)
#define PCIE_LNKCTL2     0x30
#define PCIE_LNKCTL2_TLS GENMASK(3, 0)

/* DesignWare PCIe Core registers */

#define DWC_DBI_RO_WR    0x8bc
#define DWC_DBI_RO_WR_EN BIT(0)

#define DWC_DBI_PORT_LINK_CONTROL        0x710
#define DWC_DBI_PORT_LINK_DLL_LINK_EN    BIT(5)
#define DWC_DBI_PORT_LINK_FAST_LINK_MODE BIT(7)
#define DWC_DBI_PORT_LINK_MODE           GENMASK(21, 16)
#define DWC_DBI_PORT_LINK_MODE_1_LANE    0x1
#define DWC_DBI_PORT_LINK_MODE_2_LANES   0x3
#define DWC_DBI_PORT_LINK_MODE_4_LANES   0x7
#define DWC_DBI_PORT_LINK_MODE_8_LANES   0xf
#define DWC_DBI_PORT_LINK_MODE_16_LANES  0x1f

#define DWC_DBI_LINK_WIDTH_SPEED_CONTROL 0x80c
#define DWC_DBI_LINK_WIDTH               GENMASK(12, 8)
#define DWC_DBI_SPEED_CHANGE             BIT(17)

struct fuse_bits {
    u16 src_reg;
    u16 tgt_reg;
    u8 src_bit;
    u8 tgt_bit;
    u8 width;
};

const struct fuse_bits pcie_fuse_bits_t8103[] = {
    {0x0084, 0x6238, 4, 0, 6},   {0x0084, 0x6220, 10, 14, 3}, {0x0084, 0x62a4, 13, 17, 2},
    {0x0418, 0x522c, 27, 9, 2},  {0x0418, 0x522c, 13, 12, 3}, {0x0418, 0x5220, 18, 14, 3},
    {0x0418, 0x52a4, 21, 17, 2}, {0x0418, 0x522c, 23, 16, 5}, {0x0418, 0x5278, 23, 20, 3},
    {0x0418, 0x5018, 31, 2, 1},  {0x041c, 0x1204, 0, 2, 5},   {},
};

const struct fuse_bits pcie_fuse_bits_t6000[] = {
    {0x004c, 0x1004, 3, 2, 5},   {0x0048, 0x522c, 26, 16, 5}, {0x0048, 0x522c, 29, 9, 2},
    {0x0048, 0x522c, 26, 12, 3}, {0x0048, 0x522c, 26, 16, 5}, {0x0048, 0x52a4, 24, 17, 2},
    {0x004c, 0x5018, 2, 3, 1},   {0x0048, 0x50a4, 14, 17, 2}, {0x0048, 0x62a4, 14, 17, 2},
    {0x0048, 0x6220, 8, 14, 3},  {0x0048, 0x6238, 2, 0, 6},   {},
};

/* clang-format off */
const struct fuse_bits pcie_fuse_bits_t8112[] = {
    {0x0490, 0x6238, 0, 0, 6},   {0x0490, 0x6220, 6, 14, 3},  {0x0490, 0x62a4, 12, 17, 2},
    {0x0490, 0x5018, 14, 2, 1},  {0x0490, 0x5220, 15, 14, 3}, {0x0490, 0x52a4, 18, 17, 2},
    {0x0490, 0x5278, 20, 20, 3}, {0x0490, 0x522c, 23, 12, 3}, {0x0490, 0x522c, 26, 9, 2},
    {0x0490, 0x522c, 28, 16, 4}, {0x0494, 0x522c, 0, 20, 1},  {0x0494, 0x1204, 5, 2, 5},
    {},
};
/* clang-format on */

enum apcie_type {
    APCIE_T81XX = 0,
    APCIE_T602X = 1,
};

struct reg_info {
    enum apcie_type type;
    int shared_reg_count;
    int config_idx;
    int rc_idx;
    int phy_common_idx;
    int phy_idx;
    int phy_ip_idx;
    int axi_idx;
    int fuse_idx;
    bool alt_phy_start;
};

static const struct reg_info regs_t8xxx_t600x = {
    .type = APCIE_T81XX,
    .shared_reg_count = 6,
    .config_idx = 0,
    .rc_idx = 1,
    .phy_common_idx = -1,
    .phy_idx = 2,
    .phy_ip_idx = 3,
    .axi_idx = 4,
    .fuse_idx = 5,
};

static const struct reg_info regs_t602x = {
    .type = APCIE_T602X,
    .shared_reg_count = 8,
    .config_idx = 0,
    .rc_idx = 1,
    // 2 = phy unknown?
    .phy_common_idx = 3,
    .phy_idx = 4,
    .phy_ip_idx = 5,
    .axi_idx = 6,
    .fuse_idx = 7,
};

static bool pcie_initialized = false;
static u64 rc_base;
static u64 phy_common_base;
static u64 phy_base;
static u64 phy_ip_base;
static u64 fuse_base;
static u32 port_count;
static u64 port_base[8];
static u64 port_ltssm_base[8];
static u64 port_phy_base[8];
static u64 port_intr2axi_base[8];
static const struct reg_info *pcie_regs;

int pcie_init(void)
{
    const char *path = "/arm-io/apcie";
    int adt_path[8];
    int adt_offset;
    const struct fuse_bits *fuse_bits;

    if (pcie_initialized)
        return 0;

    adt_offset = adt_path_offset_trace(adt, path, adt_path);
    if (adt_offset < 0) {
        printf("pcie: Error getting node %s\n", path);
        return -1;
    }

    if (adt_is_compatible(adt, adt_offset, "apcie,t8103")) {
        fuse_bits = pcie_fuse_bits_t8103;
        pcie_regs = &regs_t8xxx_t600x;
        printf("pcie: Initializing t8103 PCIe controller\n");
    } else if (adt_is_compatible(adt, adt_offset, "apcie,t6000")) {
        fuse_bits = pcie_fuse_bits_t6000;
        pcie_regs = &regs_t8xxx_t600x;
        printf("pcie: Initializing t6000 PCIe controller\n");
    } else if (adt_is_compatible(adt, adt_offset, "apcie,t8112")) {
        fuse_bits = pcie_fuse_bits_t8112;
        pcie_regs = &regs_t8xxx_t600x;
        printf("pcie: Initializing t8112 PCIe controller\n");
    } else if (adt_is_compatible(adt, adt_offset, "apcie,t6020")) {
        fuse_bits = NULL;
        pcie_regs = &regs_t602x;
        printf("pcie: Initializing t6020 PCIe controller\n");
    } else {
        printf("pcie: Unsupported compatible\n");
        return -1;
    }

    if (ADT_GETPROP(adt, adt_offset, "#ports", &port_count) < 0) {
        printf("pcie: Error getting port count for %s\n", path);
        return -1;
    }

    u64 config_base;
    if (adt_get_reg(adt, adt_path, "reg", pcie_regs->config_idx, &config_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", pcie_regs->config_idx, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", pcie_regs->rc_idx, &rc_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", pcie_regs->rc_idx, path);
        return -1;
    }

    if (pcie_regs->phy_common_idx != -1) {
        if (adt_get_reg(adt, adt_path, "reg", pcie_regs->phy_common_idx, &phy_common_base, NULL)) {
            printf("pcie: Error getting reg with index %d for %s\n", pcie_regs->phy_idx, path);
            return -1;
        }
    } else {
        phy_common_base = 0;
    }

    if (adt_get_reg(adt, adt_path, "reg", pcie_regs->phy_idx, &phy_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", pcie_regs->phy_idx, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", pcie_regs->phy_ip_idx, &phy_ip_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", pcie_regs->phy_ip_idx, path);
        return -1;
    }

    if (adt_get_reg(adt, adt_path, "reg", pcie_regs->fuse_idx, &fuse_base, NULL)) {
        printf("pcie: Error getting reg with index %d for %s\n", pcie_regs->fuse_idx, path);
        return -1;
    }

    u32 reg_len;
    if (!adt_getprop(adt, adt_offset, "reg", &reg_len)) {
        printf("pcie: Error getting reg length for %s\n", path);
        return -1;
    }

    int port_regs = (reg_len / 16) - pcie_regs->shared_reg_count;

    if (port_regs % port_count) {
        printf("pcie: %d port registers do not evenly divide into %d ports\n", port_regs,
               port_count);
        return -1;
    }

    int port_reg_cnt = port_regs / port_count;
    printf("pcie: ADT uses %d reg entries per port\n", port_reg_cnt);

    if (pmgr_adt_power_enable(path)) {
        printf("pcie: Error enabling power for %s\n", path);
        return -1;
    }

    if (tunables_apply_local(path, "apcie-axi2af-tunables", pcie_regs->axi_idx)) {
        printf("pcie: Error applying %s for %s\n", "apcie-axi2af-tunables", path);
        return -1;
    }

    /* ??? */
    write32(rc_base + 0x4, 0);

    if (!adt_getprop(adt, adt_offset, "apcie-common-tunables", NULL)) {
        printf("pcie: No common tunables\n");
    } else if (tunables_apply_local(path, "apcie-common-tunables", pcie_regs->rc_idx)) {
        printf("pcie: Error applying %s for %s\n", "apcie-common-tunables", path);
        return -1;
    }

    /*
     * Initialize PHY.
     */

    if (!adt_getprop(adt, adt_offset, "apcie-phy-tunables", NULL)) {
        printf("pcie: No PHY tunables\n");
    } else if (tunables_apply_local(path, "apcie-phy-tunables", pcie_regs->phy_idx)) {
        printf("pcie: Error applying %s for %s\n", "apcie-phy-tunables", path);
        return -1;
    }

    if (pcie_regs->type == APCIE_T602X) {
        if (poll32(phy_common_base + APCIE_PHYCMN_CLK, APCIE_PHYCMN_CLK_100MHZ,
                   APCIE_PHYCMN_CLK_100MHZ, 250000)) {
            printf("pcie: Reference clock not available\n");
            return -1;
        }
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
    if (pcie_regs->type == APCIE_T81XX) {
        set32(rc_base + APCIE_PHYIF_CTRL, APCIE_PHYIF_CTRL_RUN);
        udelay(1);
    } else if (pcie_regs->type == APCIE_T602X) {
        set32(phy_base + 4, 0x01);
    }

    /* Apply "fuses". */
    for (int i = 0; fuse_bits && fuse_bits[i].width; i++) {
        u32 fuse;
        fuse = (read32(fuse_base + fuse_bits[i].src_reg) >> fuse_bits[i].src_bit);
        fuse &= (1 << fuse_bits[i].width) - 1;
        mask32(phy_ip_base + fuse_bits[i].tgt_reg,
               ((1 << fuse_bits[i].width) - 1) << fuse_bits[i].tgt_bit,
               fuse << fuse_bits[i].tgt_bit);
    }

    if (tunables_apply_local(path, "apcie-phy-ip-pll-tunables", pcie_regs->phy_ip_idx)) {
        printf("pcie: Error applying %s for %s\n", "apcie-phy-ip-pll-tunables", path);
        return -1;
    }
    if (tunables_apply_local(path, "apcie-phy-ip-auspma-tunables", pcie_regs->phy_ip_idx)) {
        printf("pcie: Error applying %s for %s\n", "apcie-phy-ip-auspma-tunables", path);
        return -1;
    }

    if (pcie_regs->type == APCIE_T602X) {
        set32(phy_base + 4, 0x10);
        mask32(phy_common_base + APCIE_PHYCMN_CLK, APCIE_PHYCMN_CLK_MODE,
               FIELD_PREP(APCIE_PHYCMN_CLK_MODE, 1));
        if (poll32(phy_base + 0x8, 1, 1, 250000)) {
            printf("pcie: PHY clock enable timed out\n");
            return -1;
        }
        set32(phy_base + APCIE_PHY_CTRL, 0x300);
        write32(rc_base + 0x54, 0x140);
        write32(rc_base + 0x50, 0x1);
        if (poll32(rc_base + 0x58, 1, 1, 250000)) {
            printf("pcie: Failed to initialize RC thing\n");
            return -1;
        }
        clear32(rc_base + 0x3c, 0x1);
        pmgr_adt_power_disable_index(path, 1);
    }

    for (u32 port = 0; port < port_count; port++) {
        char bridge[64];
        int bridge_offset;

        /*
         * Initialize RC port.
         */

        snprintf(bridge, sizeof(bridge), "/arm-io/apcie/pci-bridge%d", port);

        if ((bridge_offset = adt_path_offset(adt, bridge)) < 0)
            continue;

        printf("pcie: Initializing port %d\n", port);

        if (adt_get_reg(adt, adt_path, "reg", port * port_reg_cnt + pcie_regs->shared_reg_count,
                        &port_base[port], NULL)) {
            printf("pcie: Error getting reg with index %d for %s\n",
                   port * port_reg_cnt + pcie_regs->shared_reg_count, path);
            return -1;
        }

        if (adt_get_reg(adt, adt_path, "reg", port * port_reg_cnt + pcie_regs->shared_reg_count + 1,
                        &port_ltssm_base[port], NULL)) {
            printf("pcie: Error getting reg with index %d for %s\n",
                   port * port_reg_cnt + pcie_regs->shared_reg_count + 1, path);
            return -1;
        }

        if (adt_get_reg(adt, adt_path, "reg", port * port_reg_cnt + pcie_regs->shared_reg_count + 2,
                        &port_phy_base[port], NULL)) {
            printf("pcie: Error getting reg with index %d for %s\n",
                   port * port_reg_cnt + pcie_regs->shared_reg_count + 2, path);
            return -1;
        }

        if (port_reg_cnt >= 5) {
            if (adt_get_reg(adt, adt_path, "reg",
                            port * port_reg_cnt + pcie_regs->shared_reg_count + 4,
                            &port_intr2axi_base[port], NULL)) {
                printf("pcie: Error getting reg with index %d for %s\n",
                       port * port_reg_cnt + pcie_regs->shared_reg_count + 4, path);
                return -1;
            }
        } else {
            port_intr2axi_base[port] = 0;
        }

        if (pcie_regs->type == APCIE_T602X) {
            set32(rc_base + 0x3c, 0x1);

            // ??????
            write32(port_base[port] + 0x10, 0x2);
            write32(port_base[port] + 0x88, 0x110);
            write32(port_base[port] + 0x100, 0xffffffff);
            write32(port_base[port] + 0x148, 0xffffffff);
            write32(port_base[port] + 0x210, 0xffffffff);
            write32(port_base[port] + 0x80, 0x0);
            write32(port_base[port] + 0x84, 0x0);
            write32(port_base[port] + 0x104, 0x7fffffff);
            write32(port_base[port] + 0x124, 0x100);
            write32(port_base[port] + 0x16c, 0x0);
            write32(port_base[port] + 0x13c, 0x10);
            write32(port_base[port] + 0x800, 0x100100);
            write32(port_base[port] + 0x808, 0x1000ff);
            write32(port_base[port] + 0x82c, 0x0);
            for (int i = 0; i < 512; i++)
                write32(port_base[port] + APCIE_T602X_PORT_MSIMAP + 4 * i, 0);
            write32(port_base[port] + 0x397c, 0x0);
            write32(port_base[port] + 0x130, 0x3000000);
            write32(port_base[port] + 0x140, 0x10);
            write32(port_base[port] + 0x144, 0x253770);
            write32(port_base[port] + 0x21c, 0x0);
            write32(port_base[port] + 0x834, 0x0);
        }

        if (tunables_apply_local_addr(bridge, "apcie-config-tunables", port_base[port])) {
            printf("pcie: Error applying %s for %s\n", "apcie-config-tunables", bridge);
            return -1;
        }

        set32(port_base[port] + APCIE_PORT_APPCLK, APCIE_PORT_APPCLK_EN);

        if (pcie_regs->type == APCIE_T602X) {
            clear32(port_phy_base[port] + APCIE_PHY_CTRL,
                    APCIE_PHY_CTRL_CLK0REQ | APCIE_PHY_CTRL_CLK1REQ);

            set32(port_phy_base[port] + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK0REQ);
            if (poll32(port_phy_base[port] + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK0ACK,
                       APCIE_PHY_CTRL_CLK0ACK, 50000)) {
                printf("pcie: Timeout enabling PHY CLK0\n");
                return -1;
            }

            set32(port_phy_base[port] + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK1REQ);
            if (poll32(port_phy_base[port] + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK1ACK,
                       APCIE_PHY_CTRL_CLK1ACK, 50000)) {
                printf("pcie: Timeout enabling PHY CLK1\n");
                return -1;
            }

            clear32(port_phy_base[port] + APCIE_PHY_CTRL, 0x4000);
            set32(port_phy_base[port] + APCIE_PHY_CTRL, 0x200);
            set32(port_phy_base[port] + APCIE_PHY_CTRL, 0x400);

            set32(port_base[port] + APCIE_T602X_PORT_RESET, APCIE_PORT_RESET_DIS);
        } else {
            /* PERSTN */
            set32(port_base[port] + APCIE_PORT_RESET, APCIE_PORT_RESET_DIS);
        }

        if (poll32(port_base[port] + APCIE_PORT_STATUS, APCIE_PORT_STATUS_RUN,
                   APCIE_PORT_STATUS_RUN, 250000)) {
            printf("pcie: Port failed to come up on %s\n", bridge);
            return -1;
        }

        if (poll32(port_base[port] + APCIE_PORT_LINKSTS, APCIE_PORT_LINKSTS_BUSY, 0, 250000)) {
            printf("pcie: Port failed to become idle on %s\n", bridge);
            return -1;
        }

        /* Do it again? */
        if (pcie_regs->type == APCIE_T602X) {
            clear32(port_base[port] + APCIE_T602X_PORT_RESET, APCIE_PORT_RESET_DIS);
            set32(port_base[port] + APCIE_T602X_PORT_RESET, APCIE_PORT_RESET_DIS);

            if (poll32(port_base[port] + APCIE_PORT_LINKSTS, APCIE_PORT_LINKSTS_BUSY, 0, 250000)) {
                printf("pcie: Port failed to become idle on %s\n", bridge);
                return -1;
            }

            udelay(1000);

            write32(port_ltssm_base[port] + 0x10, 0x2);
            write32(port_ltssm_base[port] + 0x1c, 0x4);
            set32(port_ltssm_base[port] + 0x20, 0x2);
            write32(port_ltssm_base[port] + 0x14, 0x1);
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

        u32 max_speed;
        if (ADT_GETPROP(adt, bridge_offset, "maximum-link-speed", &max_speed) >= 0) {
            /* Some devices override "maximum-link-speed" in the device child nodes.
             * The property used for the link speed seems to be ad-hoc made up.
             * The 10 GB ethernet adapter uses "target-link-speed" and the SD card
             * reader uses "expected-link-speed". Assume that PCIe link speed override
             * resides in the first (only?) child node.
             */
            if (max_speed == 1) {
                int np = adt_first_child_offset(adt, bridge_offset);
                if (np >= 0) {
                    int target_speed;
                    if (ADT_GETPROP(adt, np, "target-link-speed", &target_speed) >= 0 &&
                        target_speed > 0) {
                        max_speed = target_speed;
                    } else if (ADT_GETPROP(adt, np, "expected-link-speed", &target_speed) >= 0 &&
                               target_speed > 0) {
                        max_speed = target_speed;
                    }
                }
            }

            printf("pcie: Port %d max speed = %d\n", port, max_speed);

            if (max_speed == 0) {
                printf("pcie: Invalid max-speed\n");
                return -1;
            }

            mask32(config_base + PCIE_CAP_BASE + PCIE_LNKCAP, PCIE_LNKCAP_SLS,
                   FIELD_PREP(PCIE_LNKCAP_SLS, max_speed));

            mask32(config_base + PCIE_CAP_BASE + PCIE_LNKCAP2, PCIE_LNKCAP2_SLS,
                   FIELD_PREP(PCIE_LNKCAP2_SLS, (1 << max_speed) - 1));

            mask16(config_base + PCIE_CAP_BASE + PCIE_LNKCTL2, PCIE_LNKCTL2_TLS,
                   FIELD_PREP(PCIE_LNKCTL2_TLS, max_speed));

            set32(config_base + DWC_DBI_LINK_WIDTH_SPEED_CONTROL, DWC_DBI_SPEED_CHANGE);
        }

        /* Max link width 1 */
        mask32(config_base + DWC_DBI_PORT_LINK_CONTROL, DWC_DBI_PORT_LINK_MODE,
               FIELD_PREP(DWC_DBI_PORT_LINK_MODE, DWC_DBI_PORT_LINK_MODE_1_LANE));
        mask32(config_base + DWC_DBI_LINK_WIDTH_SPEED_CONTROL, DWC_DBI_LINK_WIDTH,
               FIELD_PREP(DWC_DBI_LINK_WIDTH, 1));
        mask32(config_base + PCIE_CAP_BASE + PCIE_LNKCAP, PCIE_LNKCAP_MLW,
               FIELD_PREP(PCIE_LNKCAP_MLW, 1));

        /* Make Designware PCIe Core registers readonly. */
        clear32(config_base + DWC_DBI_RO_WR, DWC_DBI_RO_WR_EN);

        if (pcie_regs->type == APCIE_T602X) {
            write32(port_base[port] + 0x4020, 0x3);
            write32(port_intr2axi_base[port] + 0x80, 0x1);

            clear32(rc_base + 0x3c, 0x1);
            for (int i = 0; i < 32; i++)
                write32(port_base[port] + APCIE_T602X_PORT_MSIMAP + 4 * i, 0x80000000 | i);
        }

        read32(port_base[port] + APCIE_PORT_LINKSTS);

        /* Move to the next PCIe device on this bus. */
        config_base += (1 << 15);
    }

    pcie_initialized = true;
    printf("pcie: Initialized.\n");

    return 0;
}

int pcie_shutdown(void)
{
    if (!pcie_initialized)
        return 0;

    for (u32 port = 0; port < port_count; port++) {
        if (pcie_regs->type == APCIE_T602X)
            clear32(port_base[port] + APCIE_T602X_PORT_RESET, APCIE_PORT_RESET_DIS);
        else
            clear32(port_base[port] + APCIE_PORT_RESET, APCIE_PORT_RESET_DIS);
        clear32(port_base[port] + APCIE_PORT_APPCLK, APCIE_PORT_APPCLK_EN);
    }

    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_RESET);
    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK1REQ);
    clear32(phy_base + APCIE_PHY_CTRL, APCIE_PHY_CTRL_CLK0REQ);

    pcie_initialized = false;
    printf("pcie: Shutdown.\n");

    return 0;
}
