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

static void *alloc_mapped_data(struct sio_data *siodata, size_t size, u64 *iova)
{
    if (siodata->num_fwdata >= MAX_FWDATA)
        return NULL;

    struct sio_mapping *mapping = &siodata->fwdata[siodata->num_fwdata];

#ifdef MERGE_SIO_FWDATA
    if (siodata->num_fwdata &&
        ALIGN_UP((mapping - 1)->size, SZ_16K) >= (mapping - 1)->size + size) {
        mapping--;
        *iova = mapping->iova + mapping->size;
        mapping->size = ALIGN_UP(mapping->size + size, SZ_4K);
        goto done;
    }
#endif

    if (!siodata->num_fwdata++)
        mapping->iova = *iova = siodata->iova_base;
    else
        mapping->iova = *iova = ALIGN_UP((mapping - 1)->iova + (mapping - 1)->size, SZ_16K);
    mapping->size = ALIGN_UP(size, SZ_4K);
    mapping->phys = top_of_memory_alloc(size);
    memset64((void *)mapping->phys, 0, ALIGN_UP(mapping->size, SZ_16K));

done:
    return (void *)((*iova - mapping->iova) + mapping->phys);
}

static void mapping_fixup(struct sio_data *siodata)
{
    for (int i = 0; i < siodata->num_fwdata; i++) {
        struct sio_mapping *mapping = &siodata->fwdata[i];
        mapping->size = ALIGN_UP(mapping->size, SZ_16K);
    }
}

static void *add_fwdata(struct sio_data *siodata, size_t size, u32 param_id)
{
    if (siodata->num_fwparams + 1 >= MAX_FWPARAMS)
        return NULL;

    u64 iova;
    void *p = alloc_mapped_data(siodata, size, &iova);

    if (!p)
        return NULL;

    struct sio_fwparam *param = &siodata->fwparams[siodata->num_fwparams];
    param->key = param_id;
    param->value = iova >> 12;
    param++;
    param->key = param_id + 1;
    param->value = size;
    siodata->num_fwparams += 2;

    return p;
}

#define PARAM_UNK_000b     0x000b
#define PARAM_PANIC_BUFFER 0x000f
#define PARAM_MAP_RANGE    0x001a
#define PARAM_DEVICE_TYPE  0x001c
#define PARAM_TUNABLES     0x001e
#define PARAM_DMASHIM_DATA 0x0022
#define PARAM_UNK_030d     0x030d

struct copy_rule {
    const char *prop;
    int fw_param;
    bool keyed;
    int blobsize;
    u32 nkeys;
    const char *keys[9];
};

#define SPACER "\xff\xff\xff\xff"

struct copy_rule copy_rules[] = {
    {
        .prop = "asio-ascwrap-tunables",
        .fw_param = PARAM_TUNABLES,
    },
    {
        .blobsize = 0x1b80,
        .fw_param = PARAM_UNK_000b,
    },
    {
        .blobsize = 0x1e000,
        .fw_param = PARAM_PANIC_BUFFER,
    },
    {
        // performance endpoint? FIFO?
        .blobsize = 0x4000,
        .fw_param = PARAM_UNK_030d,
    },
    {
        .prop = "map-range",
        .fw_param = PARAM_MAP_RANGE,
        .blobsize = 16,
        .keyed = true,
        .keys = {SPACER, SPACER, SPACER, "MISC", NULL},
    },
    {
        .prop = "dmashim",
        .fw_param = PARAM_DMASHIM_DATA,
        .blobsize = 32,
        .keyed = true,
        .keys = {"SSPI", "SUAR", "SAUD", "ADMA", "AAUD", NULL},
    },
    {
        // it seems 'device_type' must go after 'dmashim'
        .prop = "device-type",
        .fw_param = PARAM_DEVICE_TYPE,
        .blobsize = 8,
        .keyed = true,
        .keys = {"dSPI", "dUAR", "dMCA", "dDPA", "dPDM", "dALE", "dAMC", "dAPD", NULL},
    },
};

int find_key_index(const char *keylist[], u32 needle)
{
    int i;
    for (i = 0; keylist[i]; i++) {
        const char *s = keylist[i];
        u32 key = ((u32)s[0]) << 24 | ((u32)s[1]) << 16 | ((u32)s[2]) << 8 | s[3];
        if (key == needle)
            break;
    }
    return i;
}

struct sio_data *sio_setup_fwdata(const char *adt_path)
{
    struct sio_data *siodata = calloc(1, sizeof(struct sio_data));

    if (!siodata)
        return NULL;

    siodata->iova_base = 0x30000;

    int node = adt_path_offset(adt, adt_path);
    if (node < 0) {
        printf("%s: missing node %s\n", __func__, adt_path);
        goto err;
    }

    for (int i = 0; i < (int)ARRAY_SIZE(copy_rules); i++) {
        struct copy_rule *rule = &copy_rules[i];
        u32 len;

        if (!rule->prop) {
            if (!add_fwdata(siodata, rule->blobsize, rule->fw_param))
                goto err;

            continue;
        }

        const u8 *adt_blob = adt_getprop(adt, node, rule->prop, &len);
        if (!adt_blob) {
            printf("%s: missing ADT property '%s'\n", __func__, rule->prop);
            goto err;
        }

        if (!rule->keyed) {
            u8 *sio_blob = add_fwdata(siodata, len, rule->fw_param);
            if (!sio_blob)
                goto err;
            memcpy8(sio_blob, (void *)adt_blob, len);
            continue;
        }

        int nkeys = find_key_index(rule->keys, 0);
        u8 *sio_blob = add_fwdata(siodata, nkeys * rule->blobsize, rule->fw_param);
        if (!sio_blob)
            goto err;

        if (len % (rule->blobsize + 4) != 0) {
            printf("%s: bad length %d of ADT property '%s', expected multiple of %d + 4\n",
                   __func__, len, rule->prop, rule->blobsize);
            goto err;
        }

        for (u32 off = 0; off + rule->blobsize <= len; off += (rule->blobsize + 4)) {
            const u8 *p = &adt_blob[off];
            u32 key = *((u32 *)p);
            int key_idx = find_key_index(rule->keys, key);

            if (key_idx >= nkeys) {
                printf("%s: unknown key %x found in ADT property '%s'\n", __func__, key,
                       rule->prop);
                goto err;
            }

            memcpy8(sio_blob + (key_idx * rule->blobsize), (void *)(p + 4), rule->blobsize);
        }
    }

    mapping_fixup(siodata);

    return siodata;

err:
    for (int i = 0; i < MAX_FWDATA; i++) {
        if (!siodata->fwdata[i].size)
            break;
        // No way to give back memory with the top of memory
        // allocator.
        // free((void *)sio_fwdata[i].phys);
    }
    free(siodata);

    return NULL;
}
