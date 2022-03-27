/* SPDX-License-Identifier: MIT */

#include <stdbool.h>

#include "string.h"

// Routines based on The Public Domain C Library

void *memcpy(void *s1, const void *s2, size_t n)
{
    char *dest = (char *)s1;
    const char *src = (const char *)s2;

    while (n--) {
        *dest++ = *src++;
    }

    return s1;
}

void *memmove(void *s1, const void *s2, size_t n)
{
    char *dest = (char *)s1;
    const char *src = (const char *)s2;

    if (dest <= src) {
        while (n--) {
            *dest++ = *src++;
        }
    } else {
        src += n;
        dest += n;

        while (n--) {
            *--dest = *--src;
        }
    }

    return s1;
}

int memcmp(const void *s1, const void *s2, size_t n)
{
    const unsigned char *p1 = (const unsigned char *)s1;
    const unsigned char *p2 = (const unsigned char *)s2;

    while (n--) {
        if (*p1 != *p2) {
            return *p1 - *p2;
        }

        ++p1;
        ++p2;
    }

    return 0;
}

void *memset(void *s, int c, size_t n)
{
    unsigned char *p = (unsigned char *)s;

    while (n--) {
        *p++ = (unsigned char)c;
    }

    return s;
}

void *memchr(const void *s, int c, size_t n)
{
    const unsigned char *p = (const unsigned char *)s;

    while (n--) {
        if (*p == (unsigned char)c) {
            return (void *)p;
        }

        ++p;
    }

    return NULL;
}

char *strcpy(char *s1, const char *s2)
{
    char *rc = s1;

    while ((*s1++ = *s2++)) {
        /* EMPTY */
    }

    return rc;
}

char *strncpy(char *s1, const char *s2, size_t n)
{
    char *rc = s1;

    while (n && (*s1++ = *s2++)) {
        /* Cannot do "n--" in the conditional as size_t is unsigned and we have
           to check it again for >0 in the next loop below, so we must not risk
           underflow.
        */
        --n;
    }

    /* Checking against 1 as we missed the last --n in the loop above. */
    while (n-- > 1) {
        *s1++ = '\0';
    }

    return rc;
}

int strcmp(const char *s1, const char *s2)
{
    while ((*s1) && (*s1 == *s2)) {
        ++s1;
        ++s2;
    }

    return (*(unsigned char *)s1 - *(unsigned char *)s2);
}

int strncmp(const char *s1, const char *s2, size_t n)
{
    while (n && *s1 && (*s1 == *s2)) {
        ++s1;
        ++s2;
        --n;
    }

    if (n == 0) {
        return 0;
    } else {
        return (*(unsigned char *)s1 - *(unsigned char *)s2);
    }
}

size_t strlen(const char *s)
{
    size_t rc = 0;

    while (s[rc]) {
        ++rc;
    }

    return rc;
}

size_t strnlen(const char *s, size_t n)
{
    size_t rc = 0;

    while (rc < n && s[rc]) {
        ++rc;
    }

    return rc;
}

char *strchr(const char *s, int c)
{
    do {
        if (*s == (char)c) {
            return (char *)s;
        }
    } while (*s++);

    return NULL;
}

char *strrchr(const char *s, int c)
{
    size_t i = 0;

    while (s[i++]) {
        /* EMPTY */
    }

    do {
        if (s[--i] == (char)c) {
            return (char *)s + i;
        }
    } while (i);

    return NULL;
}

/* Very naive, no attempt to check for errors */
long atol(const char *s)
{
    long val = 0;
    bool neg = false;

    if (*s == '-') {
        neg = true;
        s++;
    }

    while (*s >= '0' && *s <= '9')
        val = (val * 10) + (*s++ - '0');

    if (neg)
        val = -val;

    return val;
}
