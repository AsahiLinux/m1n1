/* SPDX-License-Identifier: MIT */

#ifndef SIO_H
#define SIO_H

struct sio_mapping {
    u64 phys;
    u64 iova;
    u64 size;
};

struct sio_fwparam {
    u32 key;
    u32 value;
};

extern int sio_num_fwdata;
extern struct sio_mapping *sio_fwdata;
extern int sio_num_fwparams;
extern struct sio_fwparam *sio_fwparams;

int sio_setup_fwdata(void);

#endif
