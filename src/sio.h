/* SPDX-License-Identifier: MIT */

#ifndef SIO_H
#define SIO_H

#include "types.h"

struct sio_mapping {
    u64 phys;
    u64 iova;
    u64 size;
};

struct sio_fwparam {
    u32 key;
    u32 value;
};

#define MAX_FWDATA   6
#define MAX_FWPARAMS 16

struct sio_data {
    u64 iova_base;
    struct sio_mapping fwdata[MAX_FWDATA];
    struct sio_fwparam fwparams[MAX_FWPARAMS];
    int num_fwdata;
    int num_fwparams;
};

struct sio_data *sio_setup_fwdata(const char *adt_path);

#endif
