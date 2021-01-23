/*
 * tinfzlib - tiny zlib decompressor
 *
 * Copyright (c) 2003-2019 Joergen Ibsen
 *
 * This software is provided 'as-is', without any express or implied
 * warranty. In no event will the authors be held liable for any damages
 * arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 *
 *   1. The origin of this software must not be misrepresented; you must
 *      not claim that you wrote the original software. If you use this
 *      software in a product, an acknowledgment in the product
 *      documentation would be appreciated but is not required.
 *
 *   2. Altered source versions must be plainly marked as such, and must
 *      not be misrepresented as being the original software.
 *
 *   3. This notice may not be removed or altered from any source
 *      distribution.
 */

#include "tinf.h"

static unsigned int read_be32(const unsigned char *p)
{
	return ((unsigned int) p[0] << 24)
	     | ((unsigned int) p[1] << 16)
	     | ((unsigned int) p[2] << 8)
	     | ((unsigned int) p[3]);
}

int tinf_zlib_uncompress(void *dest, unsigned int *destLen,
                         const void *source, unsigned int sourceLen)
{
	const unsigned char *src = (const unsigned char *) source;
	unsigned char *dst = (unsigned char *) dest;
	unsigned int a32;
	int res;
	unsigned char cmf, flg;

	/* -- Check header -- */

	/* Check room for at least 2 byte header and 4 byte trailer */
	if (sourceLen < 6) {
		return TINF_DATA_ERROR;
	}

	/* Get header bytes */
	cmf = src[0];
	flg = src[1];

	/* Check checksum */
	if ((256 * cmf + flg) % 31) {
		return TINF_DATA_ERROR;
	}

	/* Check method is deflate */
	if ((cmf & 0x0F) != 8) {
		return TINF_DATA_ERROR;
	}

	/* Check window size is valid */
	if ((cmf >> 4) > 7) {
		return TINF_DATA_ERROR;
	}

	/* Check there is no preset dictionary */
	if (flg & 0x20) {
		return TINF_DATA_ERROR;
	}

	/* -- Get Adler-32 checksum of original data -- */

	a32 = read_be32(&src[sourceLen - 4]);

	/* -- Decompress data -- */

	res = tinf_uncompress(dst, destLen, src + 2, sourceLen - 6);

	if (res != TINF_OK) {
		return TINF_DATA_ERROR;
	}

	/* -- Check Adler-32 checksum -- */

	if (a32 != tinf_adler32(dst, *destLen)) {
		return TINF_DATA_ERROR;
	}

	return TINF_OK;
}
