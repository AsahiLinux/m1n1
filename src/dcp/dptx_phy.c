/* SPDX-License-Identifier: MIT */

#include "dptx_phy.h"
#include "malloc.h"

#include "../adt.h"
#include "../utils.h"

#define DPTX_MAX_LANES 4

enum dptx_type {
    DPTX_PHY_T8112,
    DPTX_PHY_T602X,
};

typedef struct dptx_phy {
    u64 regs[2];
    enum dptx_type type;
    u32 dcp_index;
    u32 active_lanes;
} dptx_phy_t;

int dptx_phy_activate(dptx_phy_t *phy)
{
    // MMIO: R.4   0x23c500010 (dptx-phy[1], offset 0x10) = 0x0
    // MMIO: W.4   0x23c500010 (dptx-phy[1], offset 0x10) = 0x0
    read32(phy->regs[1] + 0x10);
    write32(phy->regs[1] + 0x10, phy->dcp_index);

    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x444
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x454
    write32(phy->regs[1] + 0x48, 0x454);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x454
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x474
    write32(phy->regs[1] + 0x48, 0x474);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x474
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x434
    write32(phy->regs[1] + 0x48, 0x434);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x434
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x534
    write32(phy->regs[1] + 0x48, 0x534);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x534
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x734
    write32(phy->regs[1] + 0x48, 0x734);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x734
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x334
    write32(phy->regs[1] + 0x48, 0x334);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x334
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x335
    write32(phy->regs[1] + 0x48, 0x335);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x335
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x337
    write32(phy->regs[1] + 0x48, 0x337);
    // MMIO: R.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x337
    read32(phy->regs[1] + 0x48);
    // MMIO: W.4   0x23c500048 (dptx-phy[1], offset 0x48) = 0x333
    write32(phy->regs[1] + 0x48, 0x333);
    // MMIO: R.4   0x23c542014 (dptx-phy[0], offset 0x2014) = 0x80a0c
    read32(phy->regs[0] + 0x2014);
    // MMIO: W.4   0x23c542014 (dptx-phy[0], offset 0x2014) = 0x300a0c
    write32(phy->regs[0] + 0x2014, 0x300a0c);
    // MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x644800
    read32(phy->regs[0] + 0x20b8);
    // MMIO: W.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    write32(phy->regs[0] + 0x20b8, 0x654800);
    // MMIO: R.4   0x23c542220 (dptx-phy[0], offset 0x2220) = 0x11090a2
    read32(phy->regs[0] + 0x2220);
    // MMIO: W.4   0x23c542220 (dptx-phy[0], offset 0x2220) = 0x11090a0
    write32(phy->regs[0] + 0x2220, 0x11090a0);
    // MMIO: R.4   0x23c54222c (dptx-phy[0], offset 0x222c) = 0x103003
    read32(phy->regs[0] + 0x222c);
    // MMIO: W.4   0x23c54222c (dptx-phy[0], offset 0x222c) = 0x103803
    write32(phy->regs[0] + 0x222c, 0x103803);
    // MMIO: R.4   0x23c54222c (dptx-phy[0], offset 0x222c) = 0x103803
    read32(phy->regs[0] + 0x222c);
    // MMIO: W.4   0x23c54222c (dptx-phy[0], offset 0x222c) = 0x103903
    write32(phy->regs[0] + 0x222c, 0x103903);
    // MMIO: R.4   0x23c542230 (dptx-phy[0], offset 0x2230) = 0x2308804
    read32(phy->regs[0] + 0x2230);
    // MMIO: W.4   0x23c542230 (dptx-phy[0], offset 0x2230) = 0x2208804
    write32(phy->regs[0] + 0x2230, 0x2208804);
    // MMIO: R.4   0x23c542278 (dptx-phy[0], offset 0x2278) = 0x18300811
    read32(phy->regs[0] + 0x2278);
    // MMIO: W.4   0x23c542278 (dptx-phy[0], offset 0x2278) = 0x10300811
    write32(phy->regs[0] + 0x2278, 0x10300811);
    // MMIO: R.4   0x23c5422a4 (dptx-phy[0], offset 0x22a4) = 0x1044200
    read32(phy->regs[0] + 0x22a4);
    // MMIO: W.4   0x23c5422a4 (dptx-phy[0], offset 0x22a4) = 0x1044201
    write32(phy->regs[0] + 0x22a4, 0x1044201);
    // MMIO: R.4   0x23c544008 (dptx-phy[0], offset 0x4008) = 0x18030
    read32(phy->regs[0] + 0x4008);
    // MMIO: W.4   0x23c544008 (dptx-phy[0], offset 0x4008) = 0x30030
    write32(phy->regs[0] + 0x4008, 0x30030);
    // MMIO: R.4   0x23c544008 (dptx-phy[0], offset 0x4008) = 0x30030
    read32(phy->regs[0] + 0x4008);
    // MMIO: W.4   0x23c544008 (dptx-phy[0], offset 0x4008) = 0x30010
    write32(phy->regs[0] + 0x4008, 0x30010);
    // MMIO: R.4   0x23c54420c (dptx-phy[0], offset 0x420c) = 0x88e3
    read32(phy->regs[0] + 0x420c);
    // MMIO: W.4   0x23c54420c (dptx-phy[0], offset 0x420c) = 0x88c3
    write32(phy->regs[0] + 0x420c, 0x88c3);
    // MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x0
    read32(phy->regs[0] + 0x4600);
    // MMIO: W.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000000
    write32(phy->regs[0] + 0x4600, 0x8000000);
    // MMIO: R.4   0x23c545040 (dptx-phy[0], offset 0x5040) = 0x21780
    read32(phy->regs[0] + 0x5040);
    // MMIO: W.4   0x23c545040 (dptx-phy[0], offset 0x5040) = 0x221780
    write32(phy->regs[0] + 0x5040, 0x221780);
    // MMIO: R.4   0x23c546040 (dptx-phy[0], offset 0x6040) = 0x21780
    read32(phy->regs[0] + 0x6040);
    // MMIO: W.4   0x23c546040 (dptx-phy[0], offset 0x6040) = 0x221780
    write32(phy->regs[0] + 0x6040, 0x221780);
    // MMIO: R.4   0x23c547040 (dptx-phy[0], offset 0x7040) = 0x21780
    read32(phy->regs[0] + 0x7040);
    // MMIO: W.4   0x23c547040 (dptx-phy[0], offset 0x7040) = 0x221780
    write32(phy->regs[0] + 0x7040, 0x221780);
    // MMIO: R.4   0x23c548040 (dptx-phy[0], offset 0x8040) = 0x21780
    read32(phy->regs[0] + 0x8040);
    // MMIO: W.4   0x23c548040 (dptx-phy[0], offset 0x8040) = 0x221780
    write32(phy->regs[0] + 0x8040, 0x221780);
    // MMIO: R.4   0x23c545040 (dptx-phy[0], offset 0x5040) = 0x221780
    read32(phy->regs[0] + 0x5040);
    // MMIO: W.4   0x23c545040 (dptx-phy[0], offset 0x5040) = 0x2a1780
    write32(phy->regs[0] + 0x5040, 0x2a1780);
    // MMIO: R.4   0x23c546040 (dptx-phy[0], offset 0x6040) = 0x221780
    read32(phy->regs[0] + 0x6040);
    // MMIO: W.4   0x23c546040 (dptx-phy[0], offset 0x6040) = 0x2a1780
    write32(phy->regs[0] + 0x6040, 0x2a1780);
    // MMIO: R.4   0x23c547040 (dptx-phy[0], offset 0x7040) = 0x221780
    read32(phy->regs[0] + 0x7040);
    // MMIO: W.4   0x23c547040 (dptx-phy[0], offset 0x7040) = 0x2a1780
    write32(phy->regs[0] + 0x7040, 0x2a1780);
    // MMIO: R.4   0x23c548040 (dptx-phy[0], offset 0x8040) = 0x221780
    read32(phy->regs[0] + 0x8040);
    // MMIO: W.4   0x23c548040 (dptx-phy[0], offset 0x8040) = 0x2a1780
    write32(phy->regs[0] + 0x8040, 0x2a1780);
    // MMIO: R.4   0x23c545244 (dptx-phy[0], offset 0x5244) = 0x18
    read32(phy->regs[0] + 0x5244);
    // MMIO: W.4   0x23c545244 (dptx-phy[0], offset 0x5244) = 0x8
    write32(phy->regs[0] + 0x5244, 0x8);
    // MMIO: R.4   0x23c546244 (dptx-phy[0], offset 0x6244) = 0x18
    read32(phy->regs[0] + 0x6244);
    // MMIO: W.4   0x23c546244 (dptx-phy[0], offset 0x6244) = 0x8
    write32(phy->regs[0] + 0x6244, 0x8);
    // MMIO: R.4   0x23c547244 (dptx-phy[0], offset 0x7244) = 0x18
    read32(phy->regs[0] + 0x7244);
    // MMIO: W.4   0x23c547244 (dptx-phy[0], offset 0x7244) = 0x8
    write32(phy->regs[0] + 0x7244, 0x8);
    // MMIO: R.4   0x23c548244 (dptx-phy[0], offset 0x8244) = 0x18
    read32(phy->regs[0] + 0x8244);
    // MMIO: W.4   0x23c548244 (dptx-phy[0], offset 0x8244) = 0x8
    write32(phy->regs[0] + 0x8244, 0x8);
    // MMIO: R.4   0x23c542214 (dptx-phy[0], offset 0x2214) = 0x1e0
    read32(phy->regs[0] + 0x2214);
    // MMIO: W.4   0x23c542214 (dptx-phy[0], offset 0x2214) = 0x1e1
    write32(phy->regs[0] + 0x2214, 0x1e1);
    // MMIO: R.4   0x23c542224 (dptx-phy[0], offset 0x2224) = 0x20086001
    read32(phy->regs[0] + 0x2224);
    // MMIO: W.4   0x23c542224 (dptx-phy[0], offset 0x2224) = 0x20086000
    write32(phy->regs[0] + 0x2224, 0x20086000);
    // MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2000
    read32(phy->regs[0] + 0x2200);
    // MMIO: W.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2002
    write32(phy->regs[0] + 0x2200, 0x2002);
    // MMIO: R.4   0x23c541000 (dptx-phy[0], offset 0x1000) = 0xe0000003
    read32(phy->regs[0] + 0x1000);
    // MMIO: W.4   0x23c541000 (dptx-phy[0], offset 0x1000) = 0xe0000001
    write32(phy->regs[0] + 0x1000, 0xe0000001);
    // MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x41
    read32(phy->regs[0] + 0x4004);
    // MMIO: W.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
    write32(phy->regs[0] + 0x4004, 0x49);
    // MMIO: R.4   0x23c544404 (dptx-phy[0], offset 0x4404) = 0x555d444
    read32(phy->regs[0] + 0x4404);
    // MMIO: W.4   0x23c544404 (dptx-phy[0], offset 0x4404) = 0x555d444
    write32(phy->regs[0] + 0x4404, 0x555d444);
    // MMIO: R.4   0x23c544404 (dptx-phy[0], offset 0x4404) = 0x555d444
    read32(phy->regs[0] + 0x4404);
    // MMIO: W.4   0x23c544404 (dptx-phy[0], offset 0x4404) = 0x555d444
    write32(phy->regs[0] + 0x4404, 0x555d444);

    dptx_phy_set_active_lane_count(phy, 0);

    // MMIO: R.4   0x23c544200 (dptx-phy[0], offset 0x4200) = 0x4002430
    read32(phy->regs[0] + 0x4200);
    // MMIO: W.4   0x23c544200 (dptx-phy[0], offset 0x4200) = 0x4002420
    write32(phy->regs[0] + 0x4200, 0x4002420);
    // MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000000
    read32(phy->regs[0] + 0x4600);
    // MMIO: W.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000000
    write32(phy->regs[0] + 0x4600, 0x8000000);
    // MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000000
    read32(phy->regs[0] + 0x4600);
    // MMIO: W.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000001
    write32(phy->regs[0] + 0x4600, 0x8000001);
    // MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000001
    read32(phy->regs[0] + 0x4600);
    // MMIO: W.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000003
    write32(phy->regs[0] + 0x4600, 0x8000003);
    // MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000043
    read32(phy->regs[0] + 0x4600);
    // MMIO: R.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000043
    read32(phy->regs[0] + 0x4600);
    // MMIO: W.4   0x23c544600 (dptx-phy[0], offset 0x4600) = 0x8000041
    write32(phy->regs[0] + 0x4600, 0x8000041);
    // MMIO: R.4   0x23c544408 (dptx-phy[0], offset 0x4408) = 0x482
    read32(phy->regs[0] + 0x4408);
    // MMIO: W.4   0x23c544408 (dptx-phy[0], offset 0x4408) = 0x482
    write32(phy->regs[0] + 0x4408, 0x482);
    // MMIO: R.4   0x23c544408 (dptx-phy[0], offset 0x4408) = 0x482
    read32(phy->regs[0] + 0x4408);
    // MMIO: W.4   0x23c544408 (dptx-phy[0], offset 0x4408) = 0x483
    write32(phy->regs[0] + 0x4408, 0x483);

    return 0;
}

int dptx_phy_set_active_lane_count(dptx_phy_t *phy, u32 num_lanes)
{
    u32 l;

    printf("DPTX-PHY: set_active_lane_count(%u) phy_regs = {0x%lx, 0x%lx}\n", num_lanes,
           phy->regs[0], phy->regs[1]);

    if (num_lanes == 3 || num_lanes > DPTX_MAX_LANES)
        return -1;

    u32 ctrl = read32(phy->regs[0] + 0x4000);
    write32(phy->regs[0] + 0x4000, ctrl);

    for (l = 0; l < num_lanes; l++) {
        u64 offset = 0x5000 + 0x1000 * l;
        read32(phy->regs[0] + offset);
        write32(phy->regs[0] + offset, 0x100);
    }
    for (; l < DPTX_MAX_LANES; l++) {
        u64 offset = 0x5000 + 0x1000 * l;
        read32(phy->regs[0] + offset);
        write32(phy->regs[0] + offset, 0x300);
    }
    for (l = 0; l < num_lanes; l++) {
        u64 offset = 0x5000 + 0x1000 * l;
        read32(phy->regs[0] + offset);
        write32(phy->regs[0] + offset, 0x0);
    }
    for (; l < DPTX_MAX_LANES; l++) {
        u64 offset = 0x5000 + 0x1000 * l;
        read32(phy->regs[0] + offset);
        write32(phy->regs[0] + offset, 0x300);
    }

    if (num_lanes > 0) {
        // clear32(phy->regs[0] + 0x4000, 0x4000000);
        ctrl = read32(phy->regs[0] + 0x4000);
        ctrl &= ~0x4000000;
        write32(phy->regs[0] + 0x4000, ctrl);
    }
    phy->active_lanes = num_lanes;

    return 0;
}

int dptx_phy_set_link_rate(dptx_phy_t *phy, u32 link_rate)
{
    UNUSED(link_rate);
    // MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
    read32(phy->regs[0] + 0x4004);
    // MMIO: W.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
    write32(phy->regs[0] + 0x4004, 0x49);
    // MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    read32(phy->regs[0] + 0x4000);
    // MMIO: W.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    write32(phy->regs[0] + 0x4000, 0x41021ac);
    // MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
    read32(phy->regs[0] + 0x4004);
    // MMIO: W.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x41
    write32(phy->regs[0] + 0x4004, 0x41);
    // MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    read32(phy->regs[0] + 0x4000);
    // >ep:27 00a2000000000300 ()
    // MMIO: W.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    write32(phy->regs[0] + 0x4000, 0x41021ac);
    // <ep:27 0085000000000000 ()
    // MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    read32(phy->regs[0] + 0x4000);
    // MMIO: W.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    write32(phy->regs[0] + 0x4000, 0x41021ac);
    // MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2002
    read32(phy->regs[0] + 0x2200);
    // MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2002
    read32(phy->regs[0] + 0x2200);
    // MMIO: W.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2000
    write32(phy->regs[0] + 0x2200, 0x2000);
    // MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
    read32(phy->regs[0] + 0x100c);
    // MMIO: W.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
    write32(phy->regs[0] + 0x100c, 0xf000);
    // MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
    read32(phy->regs[0] + 0x100c);
    // MMIO: W.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf008
    write32(phy->regs[0] + 0x100c, 0xf008);
    // MMIO: R.4   0x23c541014 (dptx-phy[0], offset 0x1014) = 0x1
    read32(phy->regs[0] + 0x1014);
    // MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf008
    read32(phy->regs[0] + 0x100c);
    // MMIO: W.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
    write32(phy->regs[0] + 0x100c, 0xf000);
    // MMIO: R.4   0x23c541008 (dptx-phy[0], offset 0x1008) = 0x1
    read32(phy->regs[0] + 0x1008);
    // MMIO: R.4   0x23c542220 (dptx-phy[0], offset 0x2220) = 0x11090a0
    read32(phy->regs[0] + 0x2220);
    // MMIO: W.4   0x23c542220 (dptx-phy[0], offset 0x2220) = 0x1109020
    write32(phy->regs[0] + 0x2220, 0x1109020);
    // MMIO: R.4   0x23c5420b0 (dptx-phy[0], offset 0x20b0) = 0x1e0e01c2
    read32(phy->regs[0] + 0x20b0);
    // MMIO: W.4   0x23c5420b0 (dptx-phy[0], offset 0x20b0) = 0x1e0e01c2
    write32(phy->regs[0] + 0x20b0, 0x1e0e01c2);
    // MMIO: R.4   0x23c5420b4 (dptx-phy[0], offset 0x20b4) = 0x7fffffe
    read32(phy->regs[0] + 0x20b4);
    // MMIO: W.4   0x23c5420b4 (dptx-phy[0], offset 0x20b4) = 0x7fffffe
    write32(phy->regs[0] + 0x20b4, 0x7fffffe);
    // MMIO: R.4   0x23c5420b4 (dptx-phy[0], offset 0x20b4) = 0x7fffffe
    read32(phy->regs[0] + 0x20b4);
    // MMIO: W.4   0x23c5420b4 (dptx-phy[0], offset 0x20b4) = 0x7fffffe
    write32(phy->regs[0] + 0x20b4, 0x7fffffe);
    // MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    read32(phy->regs[0] + 0x20b8);
    // MMIO: W.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    write32(phy->regs[0] + 0x20b8, 0x654800);
    // MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    read32(phy->regs[0] + 0x20b8);
    // MMIO: W.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    write32(phy->regs[0] + 0x20b8, 0x654800);
    // MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    read32(phy->regs[0] + 0x20b8);
    // MMIO: W.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    write32(phy->regs[0] + 0x20b8, 0x654800);
    // MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x654800
    read32(phy->regs[0] + 0x20b8);
    // MMIO: W.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x454800
    write32(phy->regs[0] + 0x20b8, 0x454800);
    // MMIO: R.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x454800
    read32(phy->regs[0] + 0x20b8);
    // MMIO: W.4   0x23c5420b8 (dptx-phy[0], offset 0x20b8) = 0x454800
    write32(phy->regs[0] + 0x20b8, 0x454800);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x0
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8
    write32(phy->regs[1] + 0xa0, 0x8);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
    write32(phy->regs[1] + 0xa0, 0xc);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x4000c
    write32(phy->regs[1] + 0xa0, 0x4000c);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x4000c
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
    write32(phy->regs[1] + 0xa0, 0xc);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8000c
    write32(phy->regs[1] + 0xa0, 0x8000c);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8000c
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
    write32(phy->regs[1] + 0xa0, 0xc);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0xc
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8
    write32(phy->regs[1] + 0xa0, 0x8);
    // MMIO: R.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x8
    read32(phy->regs[1] + 0xa0);
    // MMIO: W.4   0x23c5000a0 (dptx-phy[1], offset 0xa0) = 0x0
    write32(phy->regs[1] + 0xa0, 0x0);
    // MMIO: R.4   0x23c542000 (dptx-phy[0], offset 0x2000) = 0x2
    read32(phy->regs[0] + 0x2000);
    // MMIO: W.4   0x23c542000 (dptx-phy[0], offset 0x2000) = 0x2
    write32(phy->regs[0] + 0x2000, 0x2);
    // MMIO: R.4   0x23c542018 (dptx-phy[0], offset 0x2018) = 0x0
    read32(phy->regs[0] + 0x2018);
    // MMIO: W.4   0x23c542018 (dptx-phy[0], offset 0x2018) = 0x0
    write32(phy->regs[0] + 0x2018, 0x0);
    // MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf000
    read32(phy->regs[0] + 0x100c);
    // MMIO: W.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf007
    write32(phy->regs[0] + 0x100c, 0xf007);
    // MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf007
    read32(phy->regs[0] + 0x100c);
    // MMIO: W.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf00f
    write32(phy->regs[0] + 0x100c, 0xf00f);
    // MMIO: R.4   0x23c541014 (dptx-phy[0], offset 0x1014) = 0x38f
    read32(phy->regs[0] + 0x1014);
    // MMIO: R.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf00f
    read32(phy->regs[0] + 0x100c);
    // MMIO: W.4   0x23c54100c (dptx-phy[0], offset 0x100c) = 0xf007
    write32(phy->regs[0] + 0x100c, 0xf007);
    // MMIO: R.4   0x23c541008 (dptx-phy[0], offset 0x1008) = 0x9
    read32(phy->regs[0] + 0x1008);
    // MMIO: R.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2000
    read32(phy->regs[0] + 0x2200);
    // MMIO: W.4   0x23c542200 (dptx-phy[0], offset 0x2200) = 0x2002
    write32(phy->regs[0] + 0x2200, 0x2002);
    // MMIO: R.4   0x23c545010 (dptx-phy[0], offset 0x5010) = 0x18003000
    read32(phy->regs[0] + 0x5010);
    // MMIO: W.4   0x23c545010 (dptx-phy[0], offset 0x5010) = 0x18003000
    write32(phy->regs[0] + 0x5010, 0x18003000);
    // MMIO: R.4   0x23c546010 (dptx-phy[0], offset 0x6010) = 0x18003000
    read32(phy->regs[0] + 0x6010);
    // MMIO: W.4   0x23c546010 (dptx-phy[0], offset 0x6010) = 0x18003000
    write32(phy->regs[0] + 0x6010, 0x18003000);
    // MMIO: R.4   0x23c547010 (dptx-phy[0], offset 0x7010) = 0x18003000
    read32(phy->regs[0] + 0x7010);
    // MMIO: W.4   0x23c547010 (dptx-phy[0], offset 0x7010) = 0x18003000
    write32(phy->regs[0] + 0x7010, 0x18003000);
    // MMIO: R.4   0x23c548010 (dptx-phy[0], offset 0x8010) = 0x18003000
    read32(phy->regs[0] + 0x8010);
    // MMIO: W.4   0x23c548010 (dptx-phy[0], offset 0x8010) = 0x18003000
    write32(phy->regs[0] + 0x8010, 0x18003000);
    // MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x41021ac
    read32(phy->regs[0] + 0x4000);
    // MMIO: W.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x51021ac
    write32(phy->regs[0] + 0x4000, 0x51021ac);
    // MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x51021ac
    read32(phy->regs[0] + 0x4000);
    // MMIO: W.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x71021ac
    write32(phy->regs[0] + 0x4000, 0x71021ac);
    // MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x41
    read32(phy->regs[0] + 0x4004);
    // MMIO: W.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
    write32(phy->regs[0] + 0x4004, 0x49);
    // MMIO: R.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x71021ac
    read32(phy->regs[0] + 0x4000);
    // MMIO: W.4   0x23c544000 (dptx-phy[0], offset 0x4000) = 0x71021ec
    write32(phy->regs[0] + 0x4000, 0x71021ec);
    // MMIO: R.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x49
    read32(phy->regs[0] + 0x4004);
    // MMIO: W.4   0x23c544004 (dptx-phy[0], offset 0x4004) = 0x48
    write32(phy->regs[0] + 0x4004, 0x48);

    return 0;
}

u32 dptx_phy_dcp_output(dptx_phy_t *phy)
{
    switch (phy->type) {
        case DPTX_PHY_T8112:
            return 5;
        case DPTX_PHY_T602X:
            return 4;
        default:
            return 5;
    }
}

dptx_phy_t *dptx_phy_init(const char *phy_node, u32 dcp_index)
{
    enum dptx_type type;
    int adt_phy_path[8];

    int node = adt_path_offset_trace(adt, phy_node, adt_phy_path);
    if (node < 0) {
        printf("DPtx-phy: Error getting phy node %s\n", phy_node);
        return NULL;
    }

    if (adt_is_compatible(adt, node, "dptx-phy,t8112"))
        type = DPTX_PHY_T8112;
    else if (adt_is_compatible(adt, node, "dptx-phy,t602x"))
        type = DPTX_PHY_T602X;
    else {
        printf("DPtx-phy: dptx-phy node %s is not compatible\n", phy_node);
        return NULL;
    }

    dptx_phy_t *phy = calloc(sizeof *phy, 1);
    if (!phy)
        return NULL;

    phy->type = type;
    phy->dcp_index = dcp_index;

    if (adt_get_reg(adt, adt_phy_path, "reg", 0, &phy->regs[0], NULL) < 0) {
        printf("DPtx-phy: failed to get %s.reg[0]\n", phy_node);
        goto out_err;
    }

    if (adt_get_reg(adt, adt_phy_path, "reg", 1, &phy->regs[1], NULL) < 0) {
        printf("DPtx-phy: failed to get %s.reg[1]\n", phy_node);
        goto out_err;
    }

    return phy;

out_err:
    free(phy);
    return NULL;
}

void dptx_phy_shutdown(dptx_phy_t *phy)
{
    free(phy);
}
