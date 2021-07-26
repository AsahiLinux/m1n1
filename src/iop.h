#ifndef IOP_H
#define IOP_H

#include "types.h"

typedef struct iop_dev iop_t;

iop_t *iop_init(uintptr_t base, void *shmem_paddr, uintptr_t shmem_iova);
void iop_boot(iop_t *iop);

#endif