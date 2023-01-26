/* SPDX-License-Identifier: MIT */

#include "dcp.h"
#include "adt.h"
#include "malloc.h"
#include "pmgr.h"
#include "rtkit.h"
#include "utils.h"

dcp_dev_t *dcp_init(const char *dcp_path, const char *dcp_dart_path, const char *disp_dart_path)
{
    u32 sid;

    int node = adt_path_offset(adt, "/arm-io/dart-dcp/mapper-dcp");
    if (node < 0) {
        printf("dcp: mapper-dcp not found!\n");
        return NULL;
    }
    if (ADT_GETPROP(adt, node, "reg", &sid) < 0) {
        printf("dcp: failed to read dart stream ID!\n");
        return NULL;
    }

    dcp_dev_t *dcp = malloc(sizeof(dcp_dev_t));
    if (!dcp)
        return NULL;

    dcp->dart_dcp = dart_init_adt(dcp_dart_path, 0, sid, true);
    if (!dcp->dart_dcp) {
        printf("dcp: failed to initialize DCP DART\n");
        goto out_free;
    }
    u64 vm_base = dart_vm_base(dcp->dart_dcp);
    dart_setup_pt_region(dcp->dart_dcp, dcp_dart_path, sid, vm_base);

    dcp->dart_disp = dart_init_adt(disp_dart_path, 0, 0, true);
    if (!dcp->dart_disp) {
        printf("dcp: failed to initialize DISP DART\n");
        goto out_dart_dcp;
    }
    // set disp0's page tables at dart-dcp's vm-base
    dart_setup_pt_region(dcp->dart_disp, disp_dart_path, 0, vm_base);

    dcp->iovad_dcp = iovad_init(vm_base + 0x10000000, vm_base + 0x20000000);

    dcp->asc = asc_init(dcp_path);
    if (!dcp->asc) {
        printf("dcp: failed to initialize ASC\n");
        goto out_iovad;
    }

    dcp->rtkit = rtkit_init("dcp", dcp->asc, dcp->dart_dcp, dcp->iovad_dcp, NULL);
    if (!dcp->rtkit) {
        printf("dcp: failed to initialize RTKit\n");
        goto out_iovad;
    }

    if (!rtkit_boot(dcp->rtkit)) {
        printf("dcp: failed to boot RTKit\n");
        goto out_iovad;
    }

    return dcp;

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
    if (sleep) {
        rtkit_sleep(dcp->rtkit);
        pmgr_reset(0, "DISP0_CPU0");
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
