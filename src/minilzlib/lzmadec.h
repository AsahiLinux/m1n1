/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    lzmadec.h

Abstract:

    This header file contains C-style definitions, constants, and enumerations
    that map back to the LZMA Standard, specifically the probability model that
    is used for encoding probabilities.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#pragma once

//
// Literals can be 0-255 and are encoded in 3 different types of slots based on
// the previous literal decoded and the "match byte" used.
//
#define LZMA_LITERALS                       256
#define LZMA_LC_TYPES                       3
#define LZMA_LC_MODEL_SIZE                  (LZMA_LC_TYPES * LZMA_LITERALS)

//
// These are the hardcoded LZMA properties we support for position and coders
//
#define LZMA_LC                             3
#define LZMA_PB                             2
#define LZMA_LP                             0
#define LZMA_LITERAL_CODERS                 (1 << LZMA_LC)
#define LZMA_POSITION_COUNT                 (1 << LZMA_PB)

//
// Lengths are described in three different ways using "low", "mid", and "high"
// bit trees. The first two trees encode 3 bits, the last encodes 8. We never
// encode a length less than 2 bytes, since that's wasteful.
//
#define LZMA_MAX_LOW_LENGTH                 (1 << 3)
#define LZMA_MAX_MID_LENGTH                 (1 << 3)
#define LZMA_MAX_HIGH_LENGTH                (1 << 8)
#define LZMA_MIN_LENGTH                     2

//
// Distances can be encoded in different ways, based on the distance slot.
// Lengths of 2, 3, 4 bytes are directly encoded with their own slot. Lengths
// over 5 share a slot, which is then further subdivded into 3 different ways
// of encoding them, which are described in the source.
//
#define LZMA_DISTANCE_SLOTS                 64
#define LZMA_FIRST_CONTEXT_DISTANCE_SLOT    4
#define LZMA_FIRST_FIXED_DISTANCE_SLOT      14
#define LZMA_DISTANCE_ALIGN_BITS            4
#define LZMA_DISTANCE_ALIGN_SLOTS           (1 << LZMA_DISTANCE_ALIGN_BITS)

//
// Total number of probabilities that we need to store
//
#define LZMA_BIT_MODEL_SLOTS                (1174 +                     \
                                             (LZMA_LITERAL_CODERS *     \
                                              LZMA_LC_MODEL_SIZE))

//
// The LZMA probability bit model is typically based on the last LZMA sequences
// that were decoded. There are 11 such possibilities that are tracked.
//
typedef enum _LZMA_SEQUENCE_STATE
{
    //
    // State where we last saw three literals
    //
    LzmaLitLitLitState,
    //
    // States where we last saw two literals preceeded by a non-literal
    //
    LzmaMatchLitLitState,
    LzmaRepLitLitState,
    LzmaLitShortrepLitLitState,
    //
    // States where we last saw one literal preceeded by a non-literal
    //
    LzmaMatchLitState,
    LzmaRepLitState,
    LzmaLitShortrepLitState,
    //
    // Separator between states where we last saw at least one literal
    //
    LzmaMaxLitState,
    //
    // States where we last saw a non-literal preceeded by a literal
    //
    LzmaLitMatchState = 7,
    LzmaLitRepState,
    LzmaLitShortrepState,
    //
    // States where we last saw two non-literals
    //
    LzmaNonlitMatchState,
    LzmaNonlitRepState,
    //
    // Separator for number of total states
    //
    LzmaMaxState
} LZMA_SEQUENCE_STATE, * PLZMA_SEQUENCE_STATE;
