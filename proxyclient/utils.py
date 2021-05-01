#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

def align(v, a=16384):
    return (v + a - 1) & ~(a - 1)

