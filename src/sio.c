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

    if (!p)
        return NULL;

    struct sio_fwparam *param = &sio_fwparams[sio_num_fwparams];
    param->key = param_id;
    param->value = iova >> 12;
    param++;
    param->key = param_id + 1;
    param->value = size;
    sio_num_fwparams += 2;

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
        // peformance endpoint? FIFO?
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

int sio_setup_fwdata(void)
{
    int ret = -ENOMEM;

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

    for (int i = 0; i < (int)ARRAY_SIZE(copy_rules); i++) {
        struct copy_rule *rule = &copy_rules[i];
        u32 len;

        if (!rule->prop) {
            if (!add_fwdata(rule->blobsize, rule->fw_param))
                goto err_nomem;

            continue;
        }

        const u8 *adt_blob = adt_getprop(adt, node, rule->prop, &len);
        if (!adt_blob) {
            printf("%s: missing ADT property '%s'\n", __func__, rule->prop);
            goto err_inval;
        }

        if (!rule->keyed) {
            u8 *sio_blob = add_fwdata(len, rule->fw_param);
            if (!sio_blob)
                goto err_nomem;
            memcpy8(sio_blob, (void *)adt_blob, len);
            continue;
        }

        int nkeys = find_key_index(rule->keys, 0);
        u8 *sio_blob = add_fwdata(nkeys * rule->blobsize, rule->fw_param);
        if (!sio_blob)
            goto err_nomem;

        if (len % (rule->blobsize + 4) != 0) {
            printf("%s: bad length %d of ADT property '%s', expected multiple of %d + 4\n",
                   __func__, len, rule->prop, rule->blobsize);
            goto err_inval;
        }

        for (u32 off = 0; off + rule->blobsize <= len; off += (rule->blobsize + 4)) {
            const u8 *p = &adt_blob[off];
            u32 key = *((u32 *)p);
            int key_idx = find_key_index(rule->keys, key);

            if (key_idx >= nkeys) {
                printf("%s: unknown key %x found in ADT property '%s'\n", __func__, key,
                       rule->prop);
                goto err_inval;
            }

            memcpy8(sio_blob + (key_idx * rule->blobsize), (void *)(p + 4), rule->blobsize);
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
