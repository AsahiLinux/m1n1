/* SPDX-License-Identifier: MIT */

#include <string.h>

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
