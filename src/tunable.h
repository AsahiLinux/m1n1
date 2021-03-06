#ifndef TUNABLE_H
#define TUNABLE_H

#include "types.h"

enum tunable_type { TUNABLE_TYPE_MASKN, TUNABLE_TYPE_MASK32 };

int tunable_apply(const char *path, const char *prop, enum tunable_type type);

#endif
