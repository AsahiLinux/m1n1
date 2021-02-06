/*
 * Copyright (c) 1995 Patrick Powell.
 *
 * This code is based on code written by Patrick Powell <papowell@astart.com>.
 * It may be used for any purpose as long as this notice remains intact on all
 * source code distributions.
 */

/*
 * Copyright (c) 2008 Holger Weiss.
 *
 * This version of the code is maintained by Holger Weiss <holger@jhweiss.de>.
 * My changes to the code may freely be used, modified and/or redistributed for
 * any purpose.  It would be nice if additions and fixes to this file (including
 * trivial code cleanups) would be sent back in order to let me include them in
 * the version available at <http://www.jhweiss.de/software/snprintf.html>.
 * However, this is not a requirement for using or redistributing (possibly
 * modified) versions of this file, nor is leaving this notice intact mandatory.
 */

/*
 * History
 *
 * 2009-03-05 Hector Martin "marcan" <marcan@marcansoft.com>
 *
 * 	Hacked up and removed a lot of stuff including floating-point support,
 * 	a bunch of ifs and defines, locales, and tests
 *
 * 2008-01-20 Holger Weiss <holger@jhweiss.de> for C99-snprintf 1.1:
 *
 * 	Fixed the detection of infinite floating point values on IRIX (and
 * 	possibly other systems) and applied another few minor cleanups.
 *
 * 2008-01-06 Holger Weiss <holger@jhweiss.de> for C99-snprintf 1.0:
 *
 * 	Added a lot of new features, fixed many bugs, and incorporated various
 * 	improvements done by Andrew Tridgell <tridge@samba.org>, Russ Allbery
 * 	<rra@stanford.edu>, Hrvoje Niksic <hniksic@xemacs.org>, Damien Miller
 * 	<djm@mindrot.org>, and others for the Samba, INN, Wget, and OpenSSH
 * 	projects.  The additions include: support the "e", "E", "g", "G", and
 * 	"F" conversion specifiers (and use conversion style "f" or "F" for the
 * 	still unsupported "a" and "A" specifiers); support the "hh", "ll", "j",
 * 	"t", and "z" length modifiers; support the "#" flag and the (non-C99)
 * 	"'" flag; use localeconv(3) (if available) to get both the current
 * 	locale's decimal point character and the separator between groups of
 * 	digits; fix the handling of various corner cases of field width and
 * 	precision specifications; fix various floating point conversion bugs;
 * 	handle infinite and NaN floating point values; don't attempt to write to
 * 	the output buffer (which may be NULL) if a size of zero was specified;
 * 	check for integer overflow of the field width, precision, and return
 * 	values and during the floating point conversion; use the OUTCHAR() macro
 * 	instead of a function for better performance; provide asprintf(3) and
 * 	vasprintf(3) functions; add new test cases.  The replacement functions
 * 	have been renamed to use an "rpl_" prefix, the function calls in the
 * 	main project (and in this file) must be redefined accordingly for each
 * 	replacement function which is needed (by using Autoconf or other means).
 * 	Various other minor improvements have been applied and the coding style
 * 	was cleaned up for consistency.
 *
 * 2007-07-23 Holger Weiss <holger@jhweiss.de> for Mutt 1.5.13:
 *
 * 	C99 compliant snprintf(3) and vsnprintf(3) functions return the number
 * 	of characters that would have been written to a sufficiently sized
 * 	buffer (excluding the '\0').  The original code simply returned the
 * 	length of the resulting output string, so that's been fixed.
 *
 * 1998-03-05 Michael Elkins <me@mutt.org> for Mutt 0.90.8:
 *
 * 	The original code assumed that both snprintf(3) and vsnprintf(3) were
 * 	missing.  Some systems only have snprintf(3) but not vsnprintf(3), so
 * 	the code is now broken down under HAVE_SNPRINTF and HAVE_VSNPRINTF.
 *
 * 1998-01-27 Thomas Roessler <roessler@does-not-exist.org> for Mutt 0.89i:
 *
 * 	The PGP code was using unsigned hexadecimal formats.  Unfortunately,
 * 	unsigned formats simply didn't work.
 *
 * 1997-10-22 Brandon Long <blong@fiction.net> for Mutt 0.87.1:
 *
 * 	Ok, added some minimal floating point support, which means this probably
 * 	requires libm on most operating systems.  Don't yet support the exponent
 * 	(e,E) and sigfig (g,G).  Also, fmtint() was pretty badly broken, it just
 * 	wasn't being exercised in ways which showed it, so that's been fixed.
 * 	Also, formatted the code to Mutt conventions, and removed dead code left
 * 	over from the original.  Also, there is now a builtin-test, run with:
 * 	gcc -DTEST_SNPRINTF -o snprintf snprintf.c -lm && ./snprintf
 *
 * 2996-09-15 Brandon Long <blong@fiction.net> for Mutt 0.43:
 *
 * 	This was ugly.  It is still ugly.  I opted out of floating point
 * 	numbers, but the formatter understands just about everything from the
 * 	normal C string format, at least as far as I can tell from the Solaris
 * 	2.5 printf(3S) man page.
 */

#include <stdarg.h>

#include "types.h"

#define VA_START(ap, last)        va_start(ap, last)
#define VA_SHIFT(ap, value, type) /* No-op for ANSI C. */

#define ULLONG    unsigned long long
#define UINTMAX_T unsigned long
#define LLONG     long
#define INTMAX_T  long

/* Support for uintptr_t. */
#ifndef UINTPTR_T
#if HAVE_UINTPTR_T || defined(uintptr_t)
#define UINTPTR_T uintptr_t
#else
#define UINTPTR_T unsigned long int
#endif /* HAVE_UINTPTR_T || defined(uintptr_t) */
#endif /* !defined(UINTPTR_T) */

/* Support for ptrdiff_t. */
#ifndef PTRDIFF_T
#if HAVE_PTRDIFF_T || defined(ptrdiff_t)
#define PTRDIFF_T ptrdiff_t
#else
#define PTRDIFF_T long int
#endif /* HAVE_PTRDIFF_T || defined(ptrdiff_t) */
#endif /* !defined(PTRDIFF_T) */

/*
 * We need an unsigned integer type corresponding to ptrdiff_t (cf. C99:
 * 7.19.6.1, 7).  However, we'll simply use PTRDIFF_T and convert it to an
 * unsigned type if necessary.  This should work just fine in practice.
 */
#ifndef UPTRDIFF_T
#define UPTRDIFF_T PTRDIFF_T
#endif /* !defined(UPTRDIFF_T) */

/*
 * We need a signed integer type corresponding to size_t (cf. C99: 7.19.6.1, 7).
 * However, we'll simply use size_t and convert it to a signed type if
 * necessary.  This should work just fine in practice.
 */
#ifndef SSIZE_T
#define SSIZE_T size_t
#endif /* !defined(SSIZE_T) */

/*
 * Buffer size to hold the octal string representation of UINT128_MAX without
 * nul-termination ("3777777777777777777777777777777777777777777").
 */
#ifdef MAX_CONVERT_LENGTH
#undef MAX_CONVERT_LENGTH
#endif /* defined(MAX_CONVERT_LENGTH) */
#define MAX_CONVERT_LENGTH 43

/* Format read states. */
#define PRINT_S_DEFAULT   0
#define PRINT_S_FLAGS     1
#define PRINT_S_WIDTH     2
#define PRINT_S_DOT       3
#define PRINT_S_PRECISION 4
#define PRINT_S_MOD       5
#define PRINT_S_CONV      6

/* Format flags. */
#define PRINT_F_MINUS    (1 << 0)
#define PRINT_F_PLUS     (1 << 1)
#define PRINT_F_SPACE    (1 << 2)
#define PRINT_F_NUM      (1 << 3)
#define PRINT_F_ZERO     (1 << 4)
#define PRINT_F_QUOTE    (1 << 5)
#define PRINT_F_UP       (1 << 6)
#define PRINT_F_UNSIGNED (1 << 7)
#define PRINT_F_TYPE_G   (1 << 8)
#define PRINT_F_TYPE_E   (1 << 9)

/* Conversion flags. */
#define PRINT_C_CHAR  1
#define PRINT_C_SHORT 2
#define PRINT_C_LONG  3
#define PRINT_C_LLONG 4
//#define PRINT_C_LDOUBLE         5
#define PRINT_C_SIZE    6
#define PRINT_C_PTRDIFF 7
#define PRINT_C_INTMAX  8

#ifndef MAX
#define MAX(x, y) ((x >= y) ? x : y)
#endif /* !defined(MAX) */
#ifndef CHARTOINT
#define CHARTOINT(ch) (ch - '0')
#endif /* !defined(CHARTOINT) */
#ifndef ISDIGIT
#define ISDIGIT(ch) ('0' <= (unsigned char)ch && (unsigned char)ch <= '9')
#endif /* !defined(ISDIGIT) */

#define OUTCHAR(str, len, size, ch)                                                                \
    do {                                                                                           \
        if (len + 1 < size)                                                                        \
            str[len] = ch;                                                                         \
        (len)++;                                                                                   \
    } while (/* CONSTCOND */ 0)

static void fmtstr(char *, size_t *, size_t, const char *, int, int, int);
static void fmtint(char *, size_t *, size_t, INTMAX_T, int, int, int, int);
static void printsep(char *, size_t *, size_t);
static int getnumsep(int);
static int convert(UINTMAX_T, char *, size_t, int, int);

int vsnprintf(char *str, size_t size, const char *format, va_list args)
{
    INTMAX_T value;
    unsigned char cvalue;
    const char *strvalue;
    INTMAX_T *intmaxptr;
    PTRDIFF_T *ptrdiffptr;
    SSIZE_T *sizeptr;
    LLONG *llongptr;
    long int *longptr;
    int *intptr;
    short int *shortptr;
    signed char *charptr;
    size_t len = 0;
    int overflow = 0;
    int base = 0;
    int cflags = 0;
    int flags = 0;
    int width = 0;
    int precision = -1;
    int state = PRINT_S_DEFAULT;
    char ch = *format++;

    /*
     * C99 says: "If `n' is zero, nothing is written, and `s' may be a null
     * pointer." (7.19.6.5, 2)  We're forgiving and allow a NULL pointer
     * even if a size larger than zero was specified.  At least NetBSD's
     * snprintf(3) does the same, as well as other versions of this file.
     * (Though some of these versions will write to a non-NULL buffer even
     * if a size of zero was specified, which violates the standard.)
     */
    if (str == NULL && size != 0)
        size = 0;

    while (ch != '\0')
        switch (state) {
            case PRINT_S_DEFAULT:
                if (ch == '%')
                    state = PRINT_S_FLAGS;
                else
                    OUTCHAR(str, len, size, ch);
                ch = *format++;
                break;
            case PRINT_S_FLAGS:
                switch (ch) {
                    case '-':
                        flags |= PRINT_F_MINUS;
                        ch = *format++;
                        break;
                    case '+':
                        flags |= PRINT_F_PLUS;
                        ch = *format++;
                        break;
                    case ' ':
                        flags |= PRINT_F_SPACE;
                        ch = *format++;
                        break;
                    case '#':
                        flags |= PRINT_F_NUM;
                        ch = *format++;
                        break;
                    case '0':
                        flags |= PRINT_F_ZERO;
                        ch = *format++;
                        break;
                    case '\'': /* SUSv2 flag (not in C99). */
                        flags |= PRINT_F_QUOTE;
                        ch = *format++;
                        break;
                    default:
                        state = PRINT_S_WIDTH;
                        break;
                }
                break;
            case PRINT_S_WIDTH:
                if (ISDIGIT(ch)) {
                    ch = CHARTOINT(ch);
                    if (width > (INT_MAX - ch) / 10) {
                        overflow = 1;
                        goto out;
                    }
                    width = 10 * width + ch;
                    ch = *format++;
                } else if (ch == '*') {
                    /*
                     * C99 says: "A negative field width argument is
                     * taken as a `-' flag followed by a positive
                     * field width." (7.19.6.1, 5)
                     */
                    if ((width = va_arg(args, int)) < 0) {
                        flags |= PRINT_F_MINUS;
                        width = -width;
                    }
                    ch = *format++;
                    state = PRINT_S_DOT;
                } else
                    state = PRINT_S_DOT;
                break;
            case PRINT_S_DOT:
                if (ch == '.') {
                    state = PRINT_S_PRECISION;
                    ch = *format++;
                } else
                    state = PRINT_S_MOD;
                break;
            case PRINT_S_PRECISION:
                if (precision == -1)
                    precision = 0;
                if (ISDIGIT(ch)) {
                    ch = CHARTOINT(ch);
                    if (precision > (INT_MAX - ch) / 10) {
                        overflow = 1;
                        goto out;
                    }
                    precision = 10 * precision + ch;
                    ch = *format++;
                } else if (ch == '*') {
                    /*
                     * C99 says: "A negative precision argument is
                     * taken as if the precision were omitted."
                     * (7.19.6.1, 5)
                     */
                    if ((precision = va_arg(args, int)) < 0)
                        precision = -1;
                    ch = *format++;
                    state = PRINT_S_MOD;
                } else
                    state = PRINT_S_MOD;
                break;
            case PRINT_S_MOD:
                switch (ch) {
                    case 'h':
                        ch = *format++;
                        if (ch == 'h') { /* It's a char. */
                            ch = *format++;
                            cflags = PRINT_C_CHAR;
                        } else
                            cflags = PRINT_C_SHORT;
                        break;
                    case 'l':
                        ch = *format++;
                        if (ch == 'l') { /* It's a long long. */
                            ch = *format++;
                            cflags = PRINT_C_LLONG;
                        } else
                            cflags = PRINT_C_LONG;
                        break;
                    case 'j':
                        cflags = PRINT_C_INTMAX;
                        ch = *format++;
                        break;
                    case 't':
                        cflags = PRINT_C_PTRDIFF;
                        ch = *format++;
                        break;
                    case 'z':
                        cflags = PRINT_C_SIZE;
                        ch = *format++;
                        break;
                }
                state = PRINT_S_CONV;
                break;
            case PRINT_S_CONV:
                switch (ch) {
                    case 'd':
                        /* FALLTHROUGH */
                    case 'i':
                        switch (cflags) {
                            case PRINT_C_CHAR:
                                value = (signed char)va_arg(args, int);
                                break;
                            case PRINT_C_SHORT:
                                value = (short int)va_arg(args, int);
                                break;
                            case PRINT_C_LONG:
                                value = va_arg(args, long int);
                                break;
                            case PRINT_C_LLONG:
                                value = va_arg(args, LLONG);
                                break;
                            case PRINT_C_SIZE:
                                value = va_arg(args, SSIZE_T);
                                break;
                            case PRINT_C_INTMAX:
                                value = va_arg(args, INTMAX_T);
                                break;
                            case PRINT_C_PTRDIFF:
                                value = va_arg(args, PTRDIFF_T);
                                break;
                            default:
                                value = va_arg(args, int);
                                break;
                        }
                        fmtint(str, &len, size, value, 10, width, precision, flags);
                        break;
                    case 'X':
                        flags |= PRINT_F_UP;
                        /* FALLTHROUGH */
                    case 'x':
                        base = 16;
                        /* FALLTHROUGH */
                    case 'o':
                        if (base == 0)
                            base = 8;
                        /* FALLTHROUGH */
                    case 'u':
                        if (base == 0)
                            base = 10;
                        flags |= PRINT_F_UNSIGNED;
                        switch (cflags) {
                            case PRINT_C_CHAR:
                                value = (unsigned char)va_arg(args, unsigned int);
                                break;
                            case PRINT_C_SHORT:
                                value = (unsigned short int)va_arg(args, unsigned int);
                                break;
                            case PRINT_C_LONG:
                                value = va_arg(args, unsigned long int);
                                break;
                            case PRINT_C_LLONG:
                                value = va_arg(args, ULLONG);
                                break;
                            case PRINT_C_SIZE:
                                value = va_arg(args, size_t);
                                break;
                            case PRINT_C_INTMAX:
                                value = va_arg(args, UINTMAX_T);
                                break;
                            case PRINT_C_PTRDIFF:
                                value = va_arg(args, UPTRDIFF_T);
                                break;
                            default:
                                value = va_arg(args, unsigned int);
                                break;
                        }
                        fmtint(str, &len, size, value, base, width, precision, flags);
                        break;
                    case 'c':
                        cvalue = va_arg(args, int);
                        OUTCHAR(str, len, size, cvalue);
                        break;
                    case 's':
                        strvalue = va_arg(args, char *);
                        fmtstr(str, &len, size, strvalue, width, precision, flags);
                        break;
                    case 'p':
                        /*
                         * C99 says: "The value of the pointer is
                         * converted to a sequence of printing
                         * characters, in an implementation-defined
                         * manner." (C99: 7.19.6.1, 8)
                         */
                        if ((strvalue = va_arg(args, void *)) == NULL)
                            /*
                             * We use the glibc format.  BSD prints
                             * "0x0", SysV "0".
                             */
                            fmtstr(str, &len, size, "(nil)", width, -1, flags);
                        else {
                            /*
                             * We use the BSD/glibc format.  SysV
                             * omits the "0x" prefix (which we emit
                             * using the PRINT_F_NUM flag).
                             */
                            flags |= PRINT_F_NUM;
                            flags |= PRINT_F_UNSIGNED;
                            fmtint(str, &len, size, (UINTPTR_T)strvalue, 16, width, precision,
                                   flags);
                        }
                        break;
                    case 'n':
                        switch (cflags) {
                            case PRINT_C_CHAR:
                                charptr = va_arg(args, signed char *);
                                *charptr = len;
                                break;
                            case PRINT_C_SHORT:
                                shortptr = va_arg(args, short int *);
                                *shortptr = len;
                                break;
                            case PRINT_C_LONG:
                                longptr = va_arg(args, long int *);
                                *longptr = len;
                                break;
                            case PRINT_C_LLONG:
                                llongptr = va_arg(args, LLONG *);
                                *llongptr = len;
                                break;
                            case PRINT_C_SIZE:
                                /*
                                 * C99 says that with the "z" length
                                 * modifier, "a following `n' conversion
                                 * specifier applies to a pointer to a
                                 * signed integer type corresponding to
                                 * size_t argument." (7.19.6.1, 7)
                                 */
                                sizeptr = va_arg(args, SSIZE_T *);
                                *sizeptr = len;
                                break;
                            case PRINT_C_INTMAX:
                                intmaxptr = va_arg(args, INTMAX_T *);
                                *intmaxptr = len;
                                break;
                            case PRINT_C_PTRDIFF:
                                ptrdiffptr = va_arg(args, PTRDIFF_T *);
                                *ptrdiffptr = len;
                                break;
                            default:
                                intptr = va_arg(args, int *);
                                *intptr = len;
                                break;
                        }
                        break;
                    case '%': /* Print a "%" character verbatim. */
                        OUTCHAR(str, len, size, ch);
                        break;
                    default: /* Skip other characters. */
                        break;
                }
                ch = *format++;
                state = PRINT_S_DEFAULT;
                base = cflags = flags = width = 0;
                precision = -1;
                break;
        }
out:
    if (len < size)
        str[len] = '\0';
    else if (size > 0)
        str[size - 1] = '\0';

    if (overflow || len >= INT_MAX) {
        return -1;
    }
    return (int)len;
}

static void fmtstr(char *str, size_t *len, size_t size, const char *value, int width, int precision,
                   int flags)
{
    int padlen, strln; /* Amount to pad. */
    int noprecision = (precision == -1);

    if (value == NULL) /* We're forgiving. */
        value = "(null)";

    /* If a precision was specified, don't read the string past it. */
    for (strln = 0; value[strln] != '\0' && (noprecision || strln < precision); strln++)
        continue;

    if ((padlen = width - strln) < 0)
        padlen = 0;
    if (flags & PRINT_F_MINUS) /* Left justify. */
        padlen = -padlen;

    while (padlen > 0) { /* Leading spaces. */
        OUTCHAR(str, *len, size, ' ');
        padlen--;
    }
    while (*value != '\0' && (noprecision || precision-- > 0)) {
        OUTCHAR(str, *len, size, *value);
        value++;
    }
    while (padlen < 0) { /* Trailing spaces. */
        OUTCHAR(str, *len, size, ' ');
        padlen++;
    }
}

static void fmtint(char *str, size_t *len, size_t size, INTMAX_T value, int base, int width,
                   int precision, int flags)
{
    UINTMAX_T uvalue;
    char iconvert[MAX_CONVERT_LENGTH];
    char sign = 0;
    char hexprefix = 0;
    int spadlen = 0; /* Amount to space pad. */
    int zpadlen = 0; /* Amount to zero pad. */
    int pos;
    int separators = (flags & PRINT_F_QUOTE);
    int noprecision = (precision == -1);

    if (flags & PRINT_F_UNSIGNED)
        uvalue = value;
    else {
        uvalue = (value >= 0) ? value : -value;
        if (value < 0)
            sign = '-';
        else if (flags & PRINT_F_PLUS) /* Do a sign. */
            sign = '+';
        else if (flags & PRINT_F_SPACE)
            sign = ' ';
    }

    pos = convert(uvalue, iconvert, sizeof(iconvert), base, flags & PRINT_F_UP);

    if (flags & PRINT_F_NUM && uvalue != 0) {
        /*
         * C99 says: "The result is converted to an `alternative form'.
         * For `o' conversion, it increases the precision, if and only
         * if necessary, to force the first digit of the result to be a
         * zero (if the value and precision are both 0, a single 0 is
         * printed).  For `x' (or `X') conversion, a nonzero result has
         * `0x' (or `0X') prefixed to it." (7.19.6.1, 6)
         */
        switch (base) {
            case 8:
                if (precision <= pos)
                    precision = pos + 1;
                break;
            case 16:
                hexprefix = (flags & PRINT_F_UP) ? 'X' : 'x';
                break;
        }
    }

    if (separators) /* Get the number of group separators we'll print. */
        separators = getnumsep(pos);

    zpadlen = precision - pos - separators;
    spadlen = width                         /* Minimum field width. */
              - separators                  /* Number of separators. */
              - MAX(precision, pos)         /* Number of integer digits. */
              - ((sign != 0) ? 1 : 0)       /* Will we print a sign? */
              - ((hexprefix != 0) ? 2 : 0); /* Will we print a prefix? */

    if (zpadlen < 0)
        zpadlen = 0;
    if (spadlen < 0)
        spadlen = 0;

    /*
     * C99 says: "If the `0' and `-' flags both appear, the `0' flag is
     * ignored.  For `d', `i', `o', `u', `x', and `X' conversions, if a
     * precision is specified, the `0' flag is ignored." (7.19.6.1, 6)
     */
    if (flags & PRINT_F_MINUS) /* Left justify. */
        spadlen = -spadlen;
    else if (flags & PRINT_F_ZERO && noprecision) {
        zpadlen += spadlen;
        spadlen = 0;
    }
    while (spadlen > 0) { /* Leading spaces. */
        OUTCHAR(str, *len, size, ' ');
        spadlen--;
    }
    if (sign != 0) /* Sign. */
        OUTCHAR(str, *len, size, sign);
    if (hexprefix != 0) { /* A "0x" or "0X" prefix. */
        OUTCHAR(str, *len, size, '0');
        OUTCHAR(str, *len, size, hexprefix);
    }
    while (zpadlen > 0) { /* Leading zeros. */
        OUTCHAR(str, *len, size, '0');
        zpadlen--;
    }
    while (pos > 0) { /* The actual digits. */
        pos--;
        OUTCHAR(str, *len, size, iconvert[pos]);
        if (separators > 0 && pos > 0 && pos % 3 == 0)
            printsep(str, len, size);
    }
    while (spadlen < 0) { /* Trailing spaces. */
        OUTCHAR(str, *len, size, ' ');
        spadlen++;
    }
}

static void printsep(char *str, size_t *len, size_t size)
{
    OUTCHAR(str, *len, size, ',');
}

static int getnumsep(int digits)
{
    int separators = (digits - ((digits % 3 == 0) ? 1 : 0)) / 3;
    return separators;
}

static int convert(UINTMAX_T value, char *buf, size_t size, int base, int caps)
{
    const char *digits = caps ? "0123456789ABCDEF" : "0123456789abcdef";
    size_t pos = 0;

    /* We return an unterminated buffer with the digits in reverse order. */
    do {
        buf[pos++] = digits[value % base];
        value /= base;
    } while (value != 0 && pos < size);

    return (int)pos;
}

int vsprintf(char *buf, const char *fmt, va_list args)
{
    return vsnprintf(buf, INT_MAX, fmt, args);
}
