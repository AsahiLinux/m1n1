/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    inputbuf.c

Abstract:

    This module implements helper functions for managing the input buffer that
    contains arithmetic-coded LZ77 match distance-length pairs and raw literals
    Both seeking (such that an external reader can refer to multiple bytes) and
    reading (capturing) an individual byte are supported. Support for aligning
    input data to 4 bytes (which is a requirement for XZ-encoded files) is also
    implemented.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#include "minlzlib.h"

//
// Input Buffer State
//
typedef struct _BUFFER_STATE
{
    //
    // Start of the buffer, current offset, current packet end, and total input size
    //
    uint8_t* Buffer;
    uint32_t Offset;
    uint32_t SoftLimit;
    uint32_t Size;
} BUFFER_STATE, * PBUFFER_STATE;
BUFFER_STATE In;

bool
BfAlign (
    void
    )
{
    uint8_t padByte;
    //
    // Keep reading until we reach 32-bit alignment. All bytes must be zero.
    //
    while (In.Offset & 3)
    {
        if (!BfRead(&padByte) || (padByte != 0))
        {
            return false;
        }
    }
    return true;
}

bool
BfSetSoftLimit (
    uint32_t Remaining
    )
{
    if ((In.Size - In.Offset) < Remaining)
    {
        return false;
    }
    In.SoftLimit = In.Offset + Remaining;
    return true;
}

void
BfResetSoftLimit (
    void
    )
{
    In.SoftLimit = In.Size;
}

bool
BfSeek (
    uint32_t Length,
    uint8_t** Bytes
    )
{
    //
    // Make sure the input buffer has enough space to seek the desired size, if
    // it does, return the current position and then seek past the desired size
    //
    if ((In.Offset + Length) > In.SoftLimit)
    {
        *Bytes = 0;
        return false;
    }
    *Bytes = &In.Buffer[In.Offset];
    In.Offset += Length;
    return true;
}

uint32_t
BfTell (
    void
    )
{
    return In.Offset;
}

bool
BfRead (
    uint8_t* Byte
    )
{
    uint8_t* pByte;
    //
    // Seek past the byte and read it
    //
    if (!BfSeek(sizeof(*Byte), &pByte))
    {
        *Byte = 0;
        return false;
    }
    *Byte = *pByte;
    return true;
}

void
BfInitialize (
    uint8_t* InputBuffer,
    uint32_t InputSize
    )
{
    //
    // Save all the data in the context buffer state
    //
    In.Buffer = InputBuffer;
    In.Size = InputSize;
    In.SoftLimit = InputSize;
    In.Offset = 0;
}
