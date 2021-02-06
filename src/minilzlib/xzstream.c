/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    xzstream.c

Abstract:

    This module implements the XZ stream format decoding, including support for
    parsing the stream header and block header, and then handing off the block
    decoding to the LZMA2 decoder. Finally, if "meta checking" is enabled, then
    the index and stream footer are also parsed and validated. Optionally, each
    of these component structures can be checked against its CRC32 checksum, if
    "integrity checking" has been enabled. Note that this library only supports
    single-stream, single-block XZ files that have CRC32 (or None) set as their
    block checking algorithm. Finally, no BJC filters are supported, and files
    with a compressed/uncompressed size metadata indicator are not handled.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#define MINLZ_META_CHECKS

#include "minlzlib.h"
#include "xzstream.h"
#include "../utils.h"

//
// XzDecodeBlockHeader can return "I successfully found a block",
// "I failed/bad block header", or "there was no block header".
// Though minlzlib explicitly only claims to handle files with a
// single block, it needs to also handle files with no blocks at all.
// (Produced by "xz" when compressing an empty input file)
//
typedef enum _XZ_DECODE_BLOCK_HEADER_RESULT {
    XzBlockHeaderFail = 0,
    XzBlockHeaderSuccess = 1,
    XzBlockHeaderNoBlock = 2
} XZ_DECODE_BLOCK_HEADER_RESULT;

const uint8_t k_XzLzma2FilterIdentifier = 0x21;

#ifdef _WIN32
void __security_check_cookie(_In_ uintptr_t _StackCookie) { (void)(_StackCookie); }
#endif

#ifdef MINLZ_META_CHECKS
//
// XZ Stream Container State
//
typedef struct _CONTAINER_STATE
{
    //
    // Size of the XZ header and the index, used to validate against footer
    //
    uint32_t HeaderSize;
    uint32_t IndexSize;
    //
    // Size of the compressed block and its checksum
    //
    uint32_t UncompressedBlockSize;
    uint32_t UnpaddedBlockSize;
    uint32_t ChecksumSize;
} CONTAINER_STATE, * PCONTAINER_STATE;
CONTAINER_STATE Container;
#endif

#ifdef MINLZ_META_CHECKS
bool
XzDecodeVli (
    vli_type* Vli
    )
{
    uint8_t vliByte;
    uint32_t bitPos;

    //
    // Read the initial VLI byte (might be the value itself)
    //
    if (!BfRead(&vliByte))
    {
        return false;
    }
    *Vli = vliByte & 0x7F;

    //
    // Check if this was a complex VLI (and we have space for it)
    //
    bitPos = 7;
    while ((vliByte & 0x80) != 0)
    {
        //
        // Read the next byte
        //
        if (!BfRead(&vliByte))
        {
            return false;
        }

        //
        // Make sure we're not decoding an invalid VLI
        //
        if ((bitPos == (7 * VLI_BYTES_MAX)) || (vliByte == 0))
        {
            return false;
        }

        //
        // Decode it and move to the next 7 bits
        //
        *Vli |= (vli_type)((vliByte & 0x7F) << bitPos);
        bitPos += 7;
    }
    return true;
}

bool
XzDecodeIndex (
    void
    )
{
    uint32_t vli;
    uint8_t* indexStart;
    uint8_t* indexEnd;
    uint32_t* pCrc32;
    uint8_t indexByte;

    //
    // Remember where the index started so we can compute its size
    //
    BfSeek(0, &indexStart);

    //
    // The index always starts out with an empty byte
    //
    if (!BfRead(&indexByte) || (indexByte != 0))
    {
        return false;
    }

    //
    // Then the count of blocks, which we expect to be 1
    //
    if (!XzDecodeVli(&vli) || (vli != 1))
    {
        return false;
    }

    //
    // Then the unpadded block size, which should match
    //
    if (!XzDecodeVli(&vli) || (Container.UnpaddedBlockSize != vli))
    {
        return false;
    }

    //
    // Then the uncompressed block size, which should match
    //
    if (!XzDecodeVli(&vli) || (Container.UncompressedBlockSize != vli))
    {
        return false;
    }

    //
    // Then we pad to the next multiple of 4
    //
    if (!BfAlign())
    {
        return false;
    }

    //
    // Store the index size with padding to validate the footer later
    //
    BfSeek(0, &indexEnd);
    Container.IndexSize = (uint32_t)(indexEnd - indexStart);

    //
    // Read the CRC32, which is not part of the index size
    //
    if (!BfSeek(sizeof(*pCrc32), (uint8_t**)&pCrc32))
    {
        return false;
    }
#ifdef MINLZ_INTEGRITY_CHECKS
    //
    // Make sure the index is not corrupt
    //
    if (Crc32(indexStart, Container.IndexSize) != *pCrc32)
    {
        return false;
    }
#endif
    return true;
}

bool
XzDecodeStreamFooter (
    void
    )
{
    PXZ_STREAM_FOOTER streamFooter;

    //
    // Seek past the footer, making sure we have space in the input stream
    //
    if (!BfSeek(sizeof(*streamFooter), (uint8_t**)&streamFooter))
    {
        return false;
    }

    //
    // Validate the footer magic
    //
    if (streamFooter->Magic != 'ZY')
    {
        return false;
    }

    //
    // Validate no flags other than checksum type are set
    //
    if ((streamFooter->u.Flags != 0) &&
        ((streamFooter->u.s.CheckType != XzCheckTypeCrc32) &&
         (streamFooter->u.s.CheckType != XzCheckTypeCrc64) &&
         (streamFooter->u.s.CheckType != XzCheckTypeSha2) &&
         (streamFooter->u.s.CheckType != XzCheckTypeNone)))
    {
        return false;
    }

    //
    // Validate if the footer accurately describes the size of the index
    //
    if (Container.IndexSize != (streamFooter->BackwardSize * 4))
    {
        return false;
    }
#ifdef MINLZ_INTEGRITY_CHECKS
    //
    // Compute the footer's CRC32 and make sure it's not corrupted
    //
    if (Crc32(&streamFooter->BackwardSize,
               sizeof(streamFooter->BackwardSize) +
               sizeof(streamFooter->u.Flags)) !=
        streamFooter->Crc32)
    {
        return false;
    }
#endif
    return true;
}
#endif

bool
XzDecodeBlock (
    uint8_t* OutputBuffer,
    uint32_t* BlockSize
    )
{
#ifdef MINLZ_META_CHECKS
    uint8_t *inputStart, *inputEnd;
#endif
    //
    // Decode the LZMA2 stream. If full integrity checking is enabled, also
    // save the offset before and after decoding, so we can save the block
    // sizes and compare them against the footer and index after decoding.
    //
#ifdef MINLZ_META_CHECKS
    BfSeek(0, &inputStart);
#endif
    if (!Lz2DecodeStream(BlockSize, OutputBuffer == NULL))
    {
        return false;
    }
#ifdef MINLZ_META_CHECKS
    BfSeek(0, &inputEnd);
    Container.UnpaddedBlockSize = Container.HeaderSize +
                                   (uint32_t)(inputEnd - inputStart);
    Container.UncompressedBlockSize = *BlockSize;
#endif
    //
    // After the block data, we need to pad to 32-bit alignment
    //
    if (!BfAlign())
    {
        return false;
    }
#if defined(MINLZ_INTEGRITY_CHECKS) || defined(MINLZ_META_CHECKS)
    //
    // Finally, move past the size of the checksum if any, then compare it with
    // with the actual CRC32 of the block, if integrity checks are enabled. If
    // meta checks are enabled, update the block size so the index checking can
    // validate it.
    //
    if (!BfSeek(Container.ChecksumSize, &inputEnd))
    {
        return false;
    }
#endif
    (void)(OutputBuffer);
#ifdef MINLZ_INTEGRITY_CHECKS
    if ((OutputBuffer != NULL) &&
        (Crc32(OutputBuffer, *BlockSize) != *(uint32_t*)inputEnd))
    {
        return false;
    }
#endif
#ifdef MINLZ_META_CHECKS
    Container.UnpaddedBlockSize += Container.ChecksumSize;
#endif
    return true;
}

bool
XzDecodeStreamHeader (
    void
    )
{
    PXZ_STREAM_HEADER streamHeader;

    //
    // Seek past the header, making sure we have space in the input stream
    //
    if (!BfSeek(sizeof(*streamHeader), (uint8_t**)&streamHeader))
    {
        return false;
    }
#ifdef MINLZ_META_CHECKS
    //
    // Validate the header magic
    //
    if ((*(uint32_t*)&streamHeader->Magic[1] != 'ZXz7') ||
        (streamHeader->Magic[0] != 0xFD) ||
        (streamHeader->Magic[5] != 0x00))
    {
        return false;
    }

    //
    // Validate no flags other than checksum type are set
    //
    if ((streamHeader->u.Flags != 0) &&
        ((streamHeader->u.s.CheckType != XzCheckTypeCrc32) &&
         (streamHeader->u.s.CheckType != XzCheckTypeCrc64) &&
         (streamHeader->u.s.CheckType != XzCheckTypeSha2) &&
         (streamHeader->u.s.CheckType != XzCheckTypeNone)))
    {
        return false;
    }

    //
    // Remember that a checksum might come at the end of the block later
    //
    if (streamHeader->u.s.CheckType == 0)
    {
        Container.ChecksumSize = 0;
    } else {
        Container.ChecksumSize = 4 << ((streamHeader->u.s.CheckType - 1) / 3);
    }

#endif
#ifdef MINLZ_INTEGRITY_CHECKS
    //
    // Compute the header's CRC32 and make sure it's not corrupted
    //
    if (Crc32(&streamHeader->u.Flags, sizeof(streamHeader->u.Flags)) !=
        streamHeader->Crc32)
    {
        return false;
    }
#endif
    return true;
}

XZ_DECODE_BLOCK_HEADER_RESULT
XzDecodeBlockHeader (
    void
    )
{
    PXZ_BLOCK_HEADER blockHeader;
#ifdef MINLZ_META_CHECKS
    uint32_t size;
#endif
    //
    // Seek past the header, making sure we have space in the input stream
    //
    if (!BfSeek(sizeof(*blockHeader), (uint8_t**)&blockHeader))
    {
        return XzBlockHeaderFail;
    }
    if (blockHeader->Size == 0)
    {
        //
        // That's no block! That's an index!
        //
        BfSeek((uint32_t)(-(uint16_t)sizeof(*blockHeader)),
               (uint8_t**)&blockHeader);
        return XzBlockHeaderNoBlock;
    }
#ifdef MINLZ_META_CHECKS
    //
    // Validate that the size of the header is what we expect
    //
    Container.HeaderSize = (blockHeader->Size + 1) * 4;
    if (Container.HeaderSize != sizeof(*blockHeader))
    {
        return XzBlockHeaderFail;
    }

    //
    // Validate that no additional flags or filters are enabled
    //
    if (blockHeader->u.Flags != 0)
    {
        return XzBlockHeaderFail;
    }

    //
    // Validate that the only filter is the LZMA2 filter
    //
    if (blockHeader->LzmaFlags.Id != k_XzLzma2FilterIdentifier)
    {
        return XzBlockHeaderFail;
    }

    //
    // With the expected number of property bytes
    //
    if (blockHeader->LzmaFlags.Size
        != sizeof(blockHeader->LzmaFlags.u.Properties))
    {
        return XzBlockHeaderFail;
    }

    //
    // The only property is the dictionary size, make sure it is valid.
    //
    // We don't actually need to store or compare the size with anything since
    // the library expects the caller to always put in a buffer that's large
    // enough to contain the full uncompressed file (or calling it in "get size
    // only" mode to get this information).
    //
    // This output buffer can thus be smaller than the size of the dictionary
    // which is absolutely OK as long as that's actually the size of the output
    // file. If callers pass in a buffer size that's too small, decoding will
    // fail at later stages anyway, and that's incorrect use of minlzlib.
    //
    size = blockHeader->LzmaFlags.u.s.DictionarySize;
    if (size > 39)
    {
        return XzBlockHeaderFail;
    }
#ifdef MINLZ_INTEGRITY_CHECKS
    //
    // Compute the header's CRC32 and make sure it's not corrupted
    //
    if (Crc32(blockHeader,
              Container.HeaderSize - sizeof(blockHeader->Crc32)) !=
        blockHeader->Crc32)
    {
        return XzBlockHeaderFail;
    }
#endif
#endif
    return XzBlockHeaderSuccess;
}

bool
XzDecode (
    uint8_t* InputBuffer,
    uint32_t* InputSize,
    uint8_t* OutputBuffer,
    uint32_t* OutputSize
    )
{

    //
    // Initialize the input buffer descriptor and history buffer (dictionary)
    //
    BfInitialize(InputBuffer, *InputSize ? *InputSize : UINT32_MAX);
    DtInitialize(OutputBuffer, *OutputSize);

    //
    // Decode the stream header for check for validity
    //
    if (!XzDecodeStreamHeader())
    {
        printf("header decode failed\n");
        return false;
    }

    //
    // Decode the block header for check for validity
    //
    switch (XzDecodeBlockHeader())
    {
    case XzBlockHeaderFail:
        printf("block header failed\n");
        return false;
    case XzBlockHeaderNoBlock:
        *OutputSize = 0;
        break;
    case XzBlockHeaderSuccess:
        //
        // Decode the actual block
        //
        if (!XzDecodeBlock(OutputBuffer, OutputSize))
        {
            printf("block decode failed\n");
            return false;
        }
        break;
    }

#ifdef MINLZ_META_CHECKS
    //
    // Decode the index for validity checks
    //
    if (!XzDecodeIndex())
    {
        return false;
    }

    //
    // And finally decode the footer as a final set of checks
    //
    if (!XzDecodeStreamFooter())
    {
        return false;
    }

    if (!*InputSize)
        *InputSize = BfTell();
#endif
    return true;
}
