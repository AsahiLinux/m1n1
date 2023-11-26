/* SPDX-License-Identifier: MIT */

#include "../config.h"

#include "adt.h"
#include "afk.h"
#include "dcp.h"
#include "firmware.h"
#include "malloc.h"
#include "pmgr.h"
#include "rtkit.h"
#include "smc.h"
#include "string.h"
#include "utils.h"

#include "dcp/dptx_phy.h"

struct adt_function_smc_gpio {
    u32 phandle;
    char four_cc[4];
    u32 gpio;
    u32 unk;
};

static char dcp_pmgr_dev[16] = "DISP0_CPU0";
static u32 dcp_die;

static int dcp_hdmi_dptx_init(dcp_dev_t *dcp, const display_config_t *cfg)
{
    int node = adt_path_offset(adt, cfg->dp2hdmi_gpio);
    if (node < 0) {
        printf("dcp: failed to find dp2hdmi-gpio node '%s'\n", cfg->dp2hdmi_gpio);
        return -1;
    }
    struct adt_function_smc_gpio dp2hdmi_pwr, hdmi_pwr;

    int err =
        adt_getprop_copy(adt, node, "function-dp2hdmi_pwr_en", &dp2hdmi_pwr, sizeof(dp2hdmi_pwr));
    if (err < 0)
        printf("dcp: failed to get dp2hdmi_pwr_en gpio\n");
    else
        dcp->dp2hdmi_pwr_gpio = dp2hdmi_pwr.gpio;
    err = adt_getprop_copy(adt, node, "function-hdmi_pwr_en", &hdmi_pwr, sizeof(hdmi_pwr));
    if (err < 0)
        printf("dcp: failed to get hdmi_pwr_en gpio\n");
    else
        dcp->hdmi_pwr_gpio = hdmi_pwr.gpio;

    if (dcp->dp2hdmi_pwr_gpio && dcp->hdmi_pwr_gpio) {
        smc_dev_t *smc = smc_init();
        if (smc) {
            smc_write_u32(smc, dcp->dp2hdmi_pwr_gpio, 0x800001);
            smc_write_u32(smc, dcp->hdmi_pwr_gpio, 0x800001);
            smc_shutdown(smc);
        }
    }

    dcp->die = cfg->die;

    dcp->phy = dptx_phy_init(cfg->dptx_phy, cfg->dcp_index);
    if (!dcp->phy) {
        printf("dcp: failed to init (lp)dptx-phy '%s'\n", cfg->dptx_phy);
        return -1;
    }

    dcp->dpav_ep = dcp_dpav_init(dcp);
    if (!dcp->dpav_ep) {
        printf("dcp: failed to initialize dpav endpoint\n");
        return -1;
    }

    dcp->dptx_ep = dcp_dptx_init(dcp, cfg->num_dptxports);
    if (!dcp->dptx_ep) {
        printf("dcp: failed to initialize dptx-port endpoint\n");
        dcp_dpav_shutdown(dcp->dpav_ep);
        return -1;
    }

#ifdef RTKIT_SYSLOG
    // start system endpoint when extended logging is requested
    dcp->system_ep = dcp_system_init(dcp);
    if (!dcp->system_ep) {
        printf("dcp: failed to initialize system endpoint\n");
        dcp_dptx_shutdown(dcp->dptx_ep);
        dcp_dpav_shutdown(dcp->dpav_ep);
        return -1;
    }

    dcp_system_set_property_u64(dcp->system_ep, "gAFKConfigLogMask", 0xffff);
#endif

    return 0;
}

int dcp_connect_dptx(dcp_dev_t *dcp)
{
    if (dcp->dptx_ep && dcp->phy) {
        return dcp_dptx_connect(dcp->dptx_ep, dcp->phy, dcp->die, 0);
    }

    return 0;
}

int dcp_work(dcp_dev_t *dcp)
{
    return afk_epic_work(dcp->afk, -1);
}

dcp_dev_t *dcp_init(const display_config_t *cfg)
{
    u32 sid;

    if (cfg && cfg->dptx_phy[0]) {
        if (os_firmware.version != V13_5) {
            printf("dcp: dtpx-port is only supported with V13_5 OS firmware.\n");
            return NULL;
        }

        strncpy(dcp_pmgr_dev, cfg->pmgr_dev, sizeof(dcp_pmgr_dev));
        dcp_die = cfg->die;
        pmgr_adt_power_enable(cfg->dcp);
        pmgr_adt_power_enable(cfg->dptx_phy);
        mdelay(25);
    }

    int dart_node = adt_path_offset(adt, cfg->dcp_dart);
    int node = adt_first_child_offset(adt, dart_node);
    if (node < 0) {
        printf("dcp: mapper-dcp* not found!\n");
        return NULL;
    }
    if (ADT_GETPROP(adt, node, "reg", &sid) < 0) {
        printf("dcp: failed to read dart stream ID!\n");
        return NULL;
    }

    dcp_dev_t *dcp = calloc(1, sizeof(dcp_dev_t));
    if (!dcp)
        return NULL;

    dcp->dart_dcp = dart_init_adt(cfg->dcp_dart, 0, sid, true);
    if (!dcp->dart_dcp) {
        printf("dcp: failed to initialize DCP DART\n");
        goto out_free;
    }
    u64 vm_base = dart_vm_base(dcp->dart_dcp);
    dart_setup_pt_region(dcp->dart_dcp, cfg->dcp_dart, sid, vm_base);

    dcp->dart_disp = dart_init_adt(cfg->disp_dart, 0, 0, true);
    if (!dcp->dart_disp) {
        printf("dcp: failed to initialize DISP DART\n");
        goto out_dart_dcp;
    }
    // set disp0's page tables at dart-dcp's vm-base
    dart_setup_pt_region(dcp->dart_disp, cfg->disp_dart, 0, vm_base);

    dcp->iovad_dcp = iovad_init(vm_base + 0x10000000, vm_base + 0x20000000);

    dcp->asc = asc_init(cfg->dcp);
    if (!dcp->asc) {
        printf("dcp: failed to initialize ASC\n");
        goto out_iovad;
    }

    dcp->rtkit = rtkit_init("dcp", dcp->asc, dcp->dart_dcp, dcp->iovad_dcp, NULL, false);
    if (!dcp->rtkit) {
        printf("dcp: failed to initialize RTKit\n");
        goto out_iovad;
    }

    if (!rtkit_boot(dcp->rtkit)) {
        printf("dcp: failed to boot RTKit\n");
        goto out_iovad;
    }

    dcp->afk = afk_epic_init(dcp->rtkit);
    if (!dcp->afk) {
        printf("dcp: failed to initialize AFK\n");
        goto out_rtkit;
    }

    if (cfg && cfg->dptx_phy[0]) {
        int ret = dcp_hdmi_dptx_init(dcp, cfg);
        if (ret < 0)
            goto out_afk;
    }

    return dcp;

out_afk:
    afk_epic_shutdown(dcp->afk);
out_rtkit:
    rtkit_quiesce(dcp->rtkit);
    rtkit_free(dcp->rtkit);
out_iovad:
    iovad_shutdown(dcp->iovad_dcp, dcp->dart_dcp);
    dart_shutdown(dcp->dart_disp);
out_dart_dcp:
    dart_shutdown(dcp->dart_dcp);
out_free:
    free(dcp);
    return NULL;
}

int dcp_shutdown(dcp_dev_t *dcp, bool sleep)
{
    /* dcp/dcp0 on desktop M2 and M2 Pro/Max devices do not wake from sleep */
    dcp_system_shutdown(dcp->system_ep);
    dcp_dptx_shutdown(dcp->dptx_ep);
    dcp_dpav_shutdown(dcp->dpav_ep);
    free(dcp->phy);
    afk_epic_shutdown(dcp->afk);
    if (sleep) {
        rtkit_sleep(dcp->rtkit);
        pmgr_reset(dcp_die, dcp_pmgr_dev);
    } else {
        rtkit_quiesce(dcp->rtkit);
    }
    rtkit_free(dcp->rtkit);
    dart_shutdown(dcp->dart_disp);
    iovad_shutdown(dcp->iovad_dcp, dcp->dart_dcp);
    dart_shutdown(dcp->dart_dcp);
    free(dcp);

    return 0;
}
