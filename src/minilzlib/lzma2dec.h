/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    lzma2dec.h

Abstract:

    This header file contains C-style data structures and enumerations that map
    back to the LZMA2 standard. This includes the encoding of the LZMA2 Control
    Byte and the possible LZMA2 Reset States.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#pragma once

//
// The most complex LZMA sequence possible is a "match" sequence where the
// the length is > 127 bytes, and the distance is > 127 bytes. This type of
// sequence starts with {1,1} for "match", followed by {1,1,nnnnnnnn} for
// "8-bit encoded length", followed by {1,1,1,1,1,1} to select the distance
// slot (63). That's 18 bits so far, which all come from arithmetic-coded
// bit trees with various probabilities. The next 26 bits are going to be
// fixed-probability, meaning that the bit tree is mathematically hardcoded
// at 50%. Finally, there are the last 4 "align" distance bits which also
// come from an arithmetic-coded bit tree, bringing the total such bits to
// 22.
//
// Each time we have to "normalize" the arithmetic coder, it consumes an
// additional byte. Normalization is done whenever we consume more than 8
// of the high bits of the coder's range (i.e.: below 2^24), so exactly
// every 8 direct bits (which always halve the range due to their 50%).
// The other bits can have arbitrary probabilities, but in the worst case
// we need to normalize the range every n bits. As such, this is a total of
// 20 worst-case normalization per LZMA sequence. Finally, we do one last
// normalization at the end of LzDecode, to make sure that the decoder is
// always in a normalized state. This means that a compressed chunk should
// be at least 21 bytes if we want to guarantee that LzDecode can never
// read past the current input stream, and avoid range checking.
//
#define LZMA_MAX_SEQUENCE_SIZE              21

//
// This describes the different ways an LZMA2 control byte can request a reset
//
typedef enum _LZMA2_COMPRESSED_RESET_STATE
{
    Lzma2NoReset = 0,
    Lzma2SimpleReset = 1,
    Lzma2PropertyReset = 2,
    Lzma2FullReset = 3
} LZMA2_COMPRESSED_RESET_STATE;

//
// This describes how an LZMA2 control byte can be parsed
//
typedef union _LZMA2_CONTROL_BYTE
{
    union
    {
        struct
        {
            uint8_t ResetState : 2;
            uint8_t Reserved : 5;
            uint8_t IsLzma : 1;
        } Raw;
        struct
        {
            uint8_t RawSize : 5;
            uint8_t ResetState : 2;
            uint8_t IsLzma : 1;
        } Lzma;
        struct
        {
            uint8_t : 7;
            uint8_t IsLzma : 1;
        } Common;
    } u;
    uint8_t Value;
} LZMA2_CONTROL_BYTE;
static_assert(sizeof(LZMA2_CONTROL_BYTE) == 1, "Invalid control byte size");
