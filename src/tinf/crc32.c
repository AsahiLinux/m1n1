/*
 * CRC32 checksum
 *
 * Copyright (c) 1998-2019 Joergen Ibsen
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

/*
 * CRC32 algorithm taken from the zlib source, which is
 * Copyright (C) 1995-1998 Jean-loup Gailly and Mark Adler
 */

#include "tinf.h"

static const unsigned int tinf_crc32tab[16] = {
	0x00000000, 0x1DB71064, 0x3B6E20C8, 0x26D930AC, 0x76DC4190,
	0x6B6B51F4, 0x4DB26158, 0x5005713C, 0xEDB88320, 0xF00F9344,
	0xD6D6A3E8, 0xCB61B38C, 0x9B64C2B0, 0x86D3D2D4, 0xA00AE278,
	0xBDBDF21C
};

unsigned int tinf_crc32(const void *data, unsigned int length)
{
	const unsigned char *buf = (const unsigned char *) data;
	unsigned int crc = 0xFFFFFFFF;
	unsigned int i;

	if (length == 0) {
		return 0;
	}

	for (i = 0; i < length; ++i) {
		crc ^= buf[i];
		crc = tinf_crc32tab[crc & 0x0F] ^ (crc >> 4);
		crc = tinf_crc32tab[crc & 0x0F] ^ (crc >> 4);
	}

	return crc ^ 0xFFFFFFFF;
}
