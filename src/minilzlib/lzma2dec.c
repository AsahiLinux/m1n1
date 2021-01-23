/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    lzma2dec.c

Abstract:

    This module implements the LZMA2 decoding logic responsible for parsing the
    LZMA2 Control Byte, the Information Bytes (Compressed & Uncompressed Stream
    Size), and the Property Byte during the initial Dictionary Reset. Note that
    this module only implements support for a single such reset (i.e.: archives
    in "solid" mode).

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#include "minlzlib.h"
#include "lzma2dec.h"

bool
Lz2DecodeChunk (
    uint32_t* BytesProcessed,
    uint32_t RawSize,
    uint16_t CompressedSize
    )
{
    uint32_t bytesProcessed;

    //
    // Go and decode this chunk, sequence by sequence
    //
    if (!LzDecode())
    {
        return false;
    }

    //
    // In a correctly formatted stream, the last arithmetic-coded sequence must
    // be zero once we finished with the last chunk. Make sure the stream ended
    // exactly where we expected it to.
    //
    if (!RcIsComplete(&bytesProcessed) || (bytesProcessed != CompressedSize))
    {
        return false;
    }

    //
    // The entire output stream must have been written to, and the dictionary
    // must be full now.
    //
    if (!DtIsComplete(&bytesProcessed) || (bytesProcessed != RawSize))
    {
        return false;
    }
    *BytesProcessed += bytesProcessed;
    return true;
}

bool
Lz2DecodeStream (
    uint32_t* BytesProcessed,
    bool GetSizeOnly
    )
{
    uint8_t* inBytes;
    LZMA2_CONTROL_BYTE controlByte;
    uint8_t propertyByte;
    uint32_t rawSize;
    uint16_t compressedSize;

    //
    // Read the first control byte
    //
    *BytesProcessed = 0;
    while (BfRead(&controlByte.Value))
    {
        //
        // When the LZMA2 control byte is 0, the entire stream is decoded. This
        // is the only success path out of this function.
        //
        if (controlByte.Value == 0)
        {
            return true;
        }

        //
        // Read the appropriate number of info bytes based on the stream type.
        //
        if (!BfSeek((controlByte.u.Common.IsLzma == 1 ) ? 4 : 2, &inBytes))
        {
            break;
        }

        //
        // For LZMA streams calculate both the uncompressed and compressed size
        // from the info bytes. Uncompressed streams only have the former.
        //
        if (controlByte.u.Common.IsLzma == 1)
        {
            rawSize = controlByte.u.Lzma.RawSize << 16;
            compressedSize = inBytes[2] << 8;
            compressedSize += inBytes[3] + 1;
        }
        else
        {
            rawSize = 0;
            compressedSize = 0;
        }

        //
        // Make sure that the output buffer that was supplied is big enough to
        // fit the uncompressed chunk, unless we're just calculating the size.
        //
        rawSize += inBytes[0] << 8;
        rawSize += inBytes[1] + 1;
        if (!GetSizeOnly && !DtSetLimit(rawSize))
        {
            break;
        }

        //
        // Check if the full LZMA state needs to be reset, which must happen at
        // the start of stream. Also check for a property reset, which occurs
        // when an LZMA stream follows an uncompressed stream. Separately,
        // check for a state reset without a property byte (happens rarely,
        // but does happen in a few compressed streams).
        //
        if ((controlByte.u.Lzma.ResetState == Lzma2FullReset) ||
            (controlByte.u.Lzma.ResetState == Lzma2PropertyReset))
        {
            //
            // Read the LZMA properties and then initialize the decoder.
            //
            if (!BfRead(&propertyByte) || !LzInitialize(propertyByte))
            {
                break;
            }
        }
        else if (controlByte.u.Lzma.ResetState == Lzma2SimpleReset)
        {
            LzResetState();
        }
        //
        // else controlByte.u.Lzma.ResetState == Lzma2NoReset, since a two-bit
        // field only has four possible values
        //

        //
        // Don't do any decompression if the caller only wants to know the size
        //
        if (GetSizeOnly)
        {
            *BytesProcessed += rawSize;
            BfSeek((controlByte.u.Common.IsLzma == 1) ? compressedSize : rawSize,
                   &inBytes);
            continue;
        }
        else if (controlByte.u.Common.IsLzma == 0)
        {
            //
            // Seek to the requested size in the input buffer
            //
            if (!BfSeek(rawSize, &inBytes))
            {
                return false;
            }

            //
            // Copy the data into the dictionary as-is
            //
            for (uint32_t i = 0; i < rawSize; i++)
            {
                DtPutSymbol(inBytes[i]);
            }

            //
            // Update bytes and keep going to the next chunk
            //
            *BytesProcessed += rawSize;
            continue;
        }

        //
        // Record how many bytes are left in this sequence as our SoftLimit for
        // the other operations. This allows us to omit most range checking
        // logic in rangedec.c. This soft limit lasts until reset below.
        //
        if (!BfSetSoftLimit(compressedSize))
        {
            break;
        }

        //
        // Read the initial range and code bytes to initialize the arithmetic
        // coding decoder, and let it know how much input data exists. We've
        // already validated that this much space exists in the input buffer.
        //
        if (!RcInitialize(&compressedSize))
        {
            break;
        }

        //
        // Start decoding the LZMA sequences in this chunk
        //
        if (!Lz2DecodeChunk(BytesProcessed, rawSize, compressedSize))
        {
            break;
        }

        //
        // Having decoded that chunk, reset our soft limit (to the full
        // input stream) so we can read the next chunk.
        //
        BfResetSoftLimit();
    }
    return false;
}
