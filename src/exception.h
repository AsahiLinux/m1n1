/* SPDX-License-Identifier: MIT */

#ifndef __EXCEPTION_H__
#define __EXCEPTION_H__

enum exc_guard_t { GUARD_OFF, GUARD_SKIP, GUARD_MARK, GUARD_RETURN };

extern volatile enum exc_guard_t exc_guard;
extern volatile int exc_count;

void exception_initialize(void);
void exception_shutdown(void);

#endif
