/* SPDX-License-Identifier: MIT */

#ifndef MATH_H
#define MATH_H

#if 100 * __GNUC__ + __GNUC_MINOR__ >= 303
#define NAN      __builtin_nanf("")
#define INFINITY __builtin_inff()
#else
#define NAN      (0.0f / 0.0f)
#define INFINITY 1e5000f
#endif

float expf(float);

#endif
