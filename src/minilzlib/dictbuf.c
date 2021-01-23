/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    dictbuf.c

Abstract:

    This module implements the management of the LZMA "history buffer" which is
    often called the "dictionary". Routines for writing into the history buffer
    as well as for reading back from it are implemented, as well as mechanisms
    for repeating previous symbols forward into the dictionary. This forms the
    basis for LZMA match distance-length pairs that are found and decompressed.
    Note that for simplicity's sake, the dictionary is stored directly in the
    output buffer, such that no "flushing" or copying is needed back and forth.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#include "minlzlib.h"

//
// State used for the history buffer (dictionary)
//
typedef struct _DICTIONARY_STATE
{
    //
    // Buffer, start position, current position, and offset limit in the buffer
    //
    uint8_t* Buffer;
    uint32_t BufferSize;
    uint32_t Start;
    uint32_t Offset;
    uint32_t Limit;
} DICTIONARY_STATE, *PDICTIONARY_STATE;
DICTIONARY_STATE Dictionary;

void
DtInitialize (
    uint8_t* HistoryBuffer,
    uint32_t Size
    )
{
    //
    // Initialize the buffer and reset the position
    //
    Dictionary.Buffer = HistoryBuffer;
    Dictionary.Offset = 0;
    Dictionary.BufferSize = Size;
}

bool
DtSetLimit (
    uint32_t Limit
    )
{
    //
    // Make sure that the passed in dictionary limit fits within the size, and
    // then set this as the new limit. Save the starting point (current offset)
    //
    if ((Dictionary.Offset + Limit) > Dictionary.BufferSize)
    {
        return false;
    }
    Dictionary.Limit = Dictionary.Offset + Limit;
    Dictionary.Start = Dictionary.Offset;
    return true;
}

bool
DtIsComplete (
    uint32_t* BytesProcessed
    )
{
    //
    // Return bytes processed and if the dictionary has been fully written to
    //
    *BytesProcessed = Dictionary.Offset - Dictionary.Start;
    return (Dictionary.Offset == Dictionary.Limit);
}

bool
DtCanWrite (
    uint32_t* Position
    )
{
    //
    // Return our position and make sure it's not beyond the uncompressed size
    //
    *Position = Dictionary.Offset;
    return (Dictionary.Offset < Dictionary.Limit);
}

uint8_t
DtGetSymbol (
    uint32_t Distance
    )
{
    //
    // If the dictionary is still empty, just return 0, otherwise, return the
    // symbol that is Distance bytes backward.
    //
    if (Distance > Dictionary.Offset)
    {
        return 0;
    }
    return Dictionary.Buffer[Dictionary.Offset - Distance];
}

void
DtPutSymbol (
    uint8_t Symbol
    )
{
    //
    // Write the symbol and advance our position
    //
    Dictionary.Buffer[Dictionary.Offset++] = Symbol;
}

bool
DtRepeatSymbol (
    uint32_t Length,
    uint32_t Distance
    )
{
    //
    // Make sure we never get asked to write past the end of the dictionary. We
    // should also not allow the distance to go beyond the current offset since
    // DtGetSymbol will return 0 thinking the dictionary is empty.
    //
    if (((Length + Dictionary.Offset) > Dictionary.Limit) ||
        (Distance > Dictionary.Offset))
    {
        return false;
    }

    //
    // Now rewrite the stream of past symbols forward into the dictionary.
    //
    do
    {
        DtPutSymbol(DtGetSymbol(Distance));
    } while (--Length > 0);
    return true;
}
