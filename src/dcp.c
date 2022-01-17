/* SPDX-License-Identifier: MIT */

#include "dcp.h"
#include "adt.h"
#include "malloc.h"
#include "rtkit.h"
#include "utils.h"

dcp_dev_t *dcp_init(const char *dcp_path, const char *dcp_dart_path, const char *disp_dart_path)
{
    dcp_dev_t *dcp = malloc(sizeof(dcp_dev_t));
    if (!dcp)
        return NULL;

    dcp->dart_dcp = dart_init_adt(dcp_dart_path, 0, 0, true);
    if (!dcp->dart_dcp) {
        printf("dcp: failed to initialize DCP DART\n");
        goto out_free;
    }

    dcp->dart_disp = dart_init_adt(disp_dart_path, 0, 0, true);
    if (!dcp->dart_disp) {
        printf("dcp: failed to initialize DISP DART\n");
        goto out_dart_dcp;
    }

    dcp->iovad_dcp = iovad_init(0x10000000, 0xf0000000);

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

    rtkit_hibernate(dcp->rtkit);
    rtkit_free(dcp->rtkit);
out_iovad:
    iovad_shutdown(dcp->iovad_dcp);
    dart_shutdown(dcp->dart_disp);
out_dart_dcp:
    dart_shutdown(dcp->dart_dcp);
out_free:
    free(dcp);
    return NULL;
}

int dcp_shutdown(dcp_dev_t *dcp)
{
    rtkit_hibernate(dcp->rtkit);
    rtkit_free(dcp->rtkit);
    dart_shutdown(dcp->dart_disp);
    dart_shutdown(dcp->dart_dcp);
    free(dcp);

    return 0;
}
