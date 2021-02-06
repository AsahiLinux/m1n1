#pragma once

#include <stdbool.h>

/*!
 * @brief          Decompresses an XZ stream from InputBuffer into OutputBuffer.
 *
 * @detail         The XZ stream must contain a single block with an LZMA2 filter
 *                 and no BJC2 filters, using default LZMA properties, and using
 *                 either CRC32 or None as the checksum type.
 *
 * @param[in]      InputBuffer - A fully formed buffer containing the XZ stream.
 * @param[in,out]  InputSize - The size of the input buffer. On output, the size
 *                 consumed from the input buffer.
 * @param[in]      OutputBuffer - A fully allocated buffer to receive the output.
 *                 Callers can pass in NULL if they do not intend to decompress,
 *                 in combination with setting OutputSize to 0, in order to query
 *                 the final expected size of the decompressed buffer.
 * @param[in,out]  OutputSize - On input, the size of the buffer. On output, the
 *                 size of the decompressed result.
 *
 * @return         true - The input buffer was fully decompressed in OutputBuffer,
 *                 or no decompression was requested, the size of the decompressed
 *                 buffer was returned in OutputSIze.
 *                 false - A failure occurred during the decompression process.
 */
bool
XzDecode (
    uint8_t* InputBuffer,
    uint32_t* InputSize,
    uint8_t* OutputBuffer,
    uint32_t* OutputSize
    );
