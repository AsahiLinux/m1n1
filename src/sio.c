/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "errno.h"
#include "malloc.h"
#include "sio.h"
#include "types.h"
#include "utils.h"

// Reuse pages for different data sections, if space allows it
#define MERGE_SIO_FWDATA

#define SIO_KEY(s)  _SIO_KEY(#s)
#define _SIO_KEY(s) (((s)[0] << 24) | ((s)[1] << 16) | ((s)[2] << 8) | (s)[3])

#define MAX_FWDATA   6
#define MAX_FWPARAMS 16

int sio_num_fwdata;
struct sio_mapping *sio_fwdata;
int sio_num_fwparams;
struct sio_fwparam *sio_fwparams;

static void *alloc_mapped_data(size_t size, u64 *iova)
{
    if (sio_num_fwdata >= MAX_FWDATA)
        return NULL;

    struct sio_mapping *mapping = &sio_fwdata[sio_num_fwdata];

#ifdef MERGE_SIO_FWDATA
    if (sio_num_fwdata && ALIGN_UP((mapping - 1)->size, SZ_16K) >= (mapping - 1)->size + size) {
        mapping--;
        *iova = mapping->iova + mapping->size;
        mapping->size = ALIGN_UP(mapping->size + size, SZ_4K);
        goto done;
    }
#endif

    if (!sio_num_fwdata++)
        mapping->iova = *iova = 0x30000;
    else
        mapping->iova = *iova = ALIGN_UP((mapping - 1)->iova + (mapping - 1)->size, SZ_16K);
    mapping->size = ALIGN_UP(size, SZ_4K);
    mapping->phys = top_of_memory_alloc(size);
    memset64((void *)mapping->phys, 0, ALIGN_UP(mapping->size, SZ_16K));

done:
    return (void *)((*iova - mapping->iova) + mapping->phys);
}

static void mapping_fixup(void)
{
    for (int i = 0; i < sio_num_fwdata; i++) {
        struct sio_mapping *mapping = &sio_fwdata[i];
        mapping->size = ALIGN_UP(mapping->size, SZ_16K);
    }
}

static void *add_fwdata(size_t size, u32 param_id)
{
    if (sio_num_fwparams + 1 >= MAX_FWPARAMS)
        return NULL;

    u64 iova;
    void *p = alloc_mapped_data(size, &iova);

    struct sio_fwparam *param = &sio_fwparams[sio_num_fwparams];
    param->key = param_id;
    param->value = iova >> 12;
    param++;
    param->key = param_id + 1;
    param->value = size;
    sio_num_fwparams += 2;

    return p;
}

int sio_setup_fwdata(void)
{
    int ret = -ENOMEM;
    u32 len;

    if (sio_fwdata)
        return 0;

    sio_fwdata = calloc(MAX_FWDATA, sizeof(*sio_fwdata));
    if (!sio_fwdata)
        return -ENOMEM;
    sio_num_fwdata = 0;

    sio_fwparams = calloc(MAX_FWPARAMS, sizeof(*sio_fwdata));
    if (!sio_fwparams) {
        free(sio_fwdata);
        return -ENOMEM;
    }
    sio_num_fwparams = 0;

    int node = adt_path_offset(adt, "/arm-io/sio");
    if (node < 0) {
        printf("%s: missing node\n", __func__);
        goto err_inval;
    }

    {
        const u8 *prop = adt_getprop(adt, node, "asio-ascwrap-tunables", &len);
        u8 *asio_tunables = add_fwdata(len, 0x1e);
        if (!asio_tunables)
            goto err_nomem;
        memcpy8(asio_tunables, (void *)prop, len);
    }

    u8 *unk_0b = add_fwdata(0x1b80, 0xb);
    if (!unk_0b)
        goto err_nomem;
    u8 *unk_0f = add_fwdata(0x1e000, 0xf); // crash dump memory
    if (!unk_0f)
        goto err_nomem;
    u8 *unk_ep3_0d = add_fwdata(0x4000, 0x30d); // peformance endpoint? FIFO?
    if (!unk_ep3_0d)
        goto err_nomem;

    {
        u8 *map_range = add_fwdata(0x50, 0x1a);
        if (!map_range)
            goto err_nomem;
        const u32 *prop = adt_getprop(adt, node, "map-range", &len);
        if (len != 20 || prop[0] != (u32)SIO_KEY(MISC)) {
            printf("%s: bad 'map-range' property (%d, %x)\n", __func__, len, prop[0]);
            goto err_inval;
        }
        memcpy8(map_range + 48, (void *)(prop + 1), 16);
    }

    {
        u8 *dmashim = add_fwdata(0xa0, 0x22);
        if (!dmashim)
            goto err_nomem;
        const u32 *prop = adt_getprop(adt, node, "dmashim", &len);
        for (; len >= 36; len -= 36) {
            switch (prop[0]) {
                case SIO_KEY(SSPI):
                    memcpy8(dmashim, (void *)(prop + 1), 32);
                    break;

                case SIO_KEY(SUAR):
                    memcpy8(dmashim + 32, (void *)(prop + 1), 32);
                    break;

                case SIO_KEY(SAUD):
                    memcpy8(dmashim + 64, (void *)(prop + 1), 32);
                    break;

                case SIO_KEY(ADMA):
                    break;

                case SIO_KEY(AAUD):
                    break;

                default:
                    printf("%s: unknown 'dmashim' entry %x\n", __func__, prop[0]);
            };

            prop += 9;
        }
    }

    { // it seems 'device_type' must go after 'dmashim'
        u8 *device_type = add_fwdata(0x40, 0x1c);
        if (!device_type)
            goto err_nomem;
        const u32 *prop = adt_getprop(adt, node, "device-type", &len);
        for (; len >= 12; len -= 12) {
            switch (prop[0]) {
                case SIO_KEY(dSPI):
                    memcpy8(device_type, (void *)(prop + 1), 8);
                    break;

                case SIO_KEY(dUAR):
                    memcpy8(device_type + 8, (void *)(prop + 1), 8);
                    break;

                case SIO_KEY(dMCA):
                    memcpy8(device_type + 16, (void *)(prop + 1), 8);
                    break;

                case SIO_KEY(dDPA):
                    memcpy8(device_type + 24, (void *)(prop + 1), 8);
                    break;

                default:
                    printf("%s: unknown 'device-type' entry %x\n", __func__, prop[0]);
            };

            prop += 3;
        }
    }

    mapping_fixup();

    return 0;

err_inval:
    ret = -EINVAL;
    goto err;
err_nomem:
    ret = -ENOMEM;
    goto err;

err:
    for (int i = 0; i < MAX_FWDATA; i++) {
        if (!sio_fwdata[i].size)
            break;
        // No way to give back memory with the top of memory
        // allocator.
        // free((void *)sio_fwdata[i].phys);
    }
    free(sio_fwdata);
    free(sio_fwparams);
    sio_fwdata = NULL;
    sio_fwparams = NULL;

    return ret;
}
