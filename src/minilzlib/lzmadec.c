/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    lzmadec.c

Abstract:

    This module implements the LZMA Decoding Logic responsible for decoding the
    three possible types of LZMA "packets": matches, repetitions (short \& long)
    and literals. The probability model for each type of packet is also stored
    in this file, along with the management of the previously seen packet types
    (which is tracked as the "sequence").

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#include "minlzlib.h"
#include "lzmadec.h"

//
// Probability Bit Model for Lenghts in Rep and in Match sequences
//
typedef struct _LENGTH_DECODER_STATE
{
    //
    // Bit Model for the choosing the type of length encoding
    //
    uint16_t Choice;
    uint16_t Choice2;
    //
    // Bit Model for each of the length encodings
    //
    uint16_t Low[LZMA_POSITION_COUNT][LZMA_MAX_LOW_LENGTH];
    uint16_t Mid[LZMA_POSITION_COUNT][LZMA_MAX_MID_LENGTH];
    uint16_t High[LZMA_MAX_HIGH_LENGTH];
} LENGTH_DECODER_STATE, * PLENGTH_DECODER_STATE;

//
// State used for LZMA decoding
//
typedef struct _DECODER_STATE
{
    //
    // Current type of sequence last decoded
    //
    LZMA_SEQUENCE_STATE Sequence;
    //
    // History of last 4 decoded distances
    //
    uint32_t Rep0;
    uint32_t Rep1;
    uint32_t Rep2;
    uint32_t Rep3;
    //
    // Pending length to repeat from dictionary
    //
    uint32_t Len;
    //
    // Probability Bit Models for all sequence types
    //
    union
    {
        struct
        {
            //
            // Literal model
            //
            uint16_t Literal[LZMA_LITERAL_CODERS][LZMA_LC_MODEL_SIZE];
            //
            // Last-used-distance based models
            //
            uint16_t Rep[LzmaMaxState];
            uint16_t Rep0[LzmaMaxState];
            uint16_t Rep0Long[LzmaMaxState][LZMA_POSITION_COUNT];
            uint16_t Rep1[LzmaMaxState];
            uint16_t Rep2[LzmaMaxState];
            LENGTH_DECODER_STATE RepLen;
            //
            // Explicit distance match based models
            //
            uint16_t Match[LzmaMaxState][LZMA_POSITION_COUNT];
            uint16_t DistSlot[LZMA_FIRST_CONTEXT_DISTANCE_SLOT][LZMA_DISTANCE_SLOTS];
            uint16_t Dist[(1 << 7) - LZMA_FIRST_FIXED_DISTANCE_SLOT];
            uint16_t Align[LZMA_DISTANCE_ALIGN_SLOTS];
            LENGTH_DECODER_STATE MatchLen;
        } BitModel;
        uint16_t RawProbabilities[LZMA_BIT_MODEL_SLOTS];
    } u;
} DECODER_STATE, *PDECODER_STATE;
DECODER_STATE Decoder;

//
// LZMA decoding uses 3 "properties" which determine how the probability
// bit model will be laid out. These store the number of bits that are used
// to pick the correct Literal Coder ("lc"), the number of Position bits to
// select the Literal coder ("lp"), and the number of Position Bits used to
// select various lengths ("pb"). In LZMA2, these properties are encoded in
// a single byte with the formula: ((pb * 45) + lp * 9) + lc).
//
// We only support the default {lc = 3, lp = 0, pb = 2} properties, which
// are what the main encoders out there use. This means that a total of 2
// bits will be used for arithmetic-coded bit trees that are dependent on
// the current position, and that a total of 3 bits will be used when we
// pick the arithmetic-coded bit tree used for literal coding. The 0 means
// this selection will _not_ be dependent on the position in the buffer.
//
const uint8_t k_LzSupportedProperties =
    (LZMA_PB * 45) + (LZMA_LP * 9) + (LZMA_LC);

void
LzSetLiteral (
    PLZMA_SEQUENCE_STATE State
    )
{
    if (*State <= LzmaLitShortrepLitLitState)
    {
        //
        // States 0-3 represent packets with at least 2 back-to-back literals,
        // so another literal now takes us to state 0 (3 back-to-back literals)
        //
        *State = LzmaLitLitLitState;
    }
    else if (*State <= LzmaLitShortrepState)
    {
        //
        // States 4-6 represent packets with a literal at the end, so seeing
        // another literal now takes us to 2 back-to-back literals, which are
        // state packets 1-3.
        //
        // States 7-9 represent packets with a literal at the start, followed
        // by a match/rep/shortrep. Seeing another literal now drops this first
        // literal and takes us to having a literal at the end, which are state
        // packets 4-6 that we just described in the paragraph above.
        //
        *State = (LZMA_SEQUENCE_STATE)(*State - 3);
    }
    else
    {
        //
        // Finally, state 10 and 11 represent cases without a single literal in
        // the last 2 sequence packets, so seeing a literal now takes us to a
        // "literal at the end" state, either following a match or a rep.
        //
        *State = (LZMA_SEQUENCE_STATE)(*State - 6);
    }
}

bool
LzIsLiteral (
    LZMA_SEQUENCE_STATE State
    )
{
    //
    // States 0-6 describe literal packet sequences
    //
    return State < LzmaMaxLitState;
}

void
LzSetMatch (
    PLZMA_SEQUENCE_STATE State
    )
{
    //
    // Move to the appropriate "match" state based on current literal state
    //
    *State = LzIsLiteral(*State) ? LzmaLitMatchState : LzmaNonlitMatchState;
}

void
LzSetLongRep (
    PLZMA_SEQUENCE_STATE State
    )
{
    //
    // Move to the appropriate "long rep" state based on current literal state
    //
    *State = LzIsLiteral(*State) ? LzmaLitRepState : LzmaNonlitRepState;
}

void
LzSetShortRep (
    PLZMA_SEQUENCE_STATE State
    )
{
    //
    // Move to the appropriate "short rep" state based on current literal state
    //
    *State = LzIsLiteral(*State) ? LzmaLitShortrepState : LzmaNonlitRepState;
}

uint16_t*
LzGetLiteralSlot (
    void
    )
{
    uint8_t symbol;

    //
    // To pick the correct literal coder arithmetic-coded bit tree, LZMA uses
    // the "lc" parameter to choose the number of high bits from the previous
    // symbol (in the normal case, 3). It then combines that with the "lp"
    // parameter to choose the number of low bits from the current position in
    // the dictionary. However, since "lp" is normally 0, we can omit this.
    //
    symbol = DtGetSymbol(1);
    return Decoder.u.BitModel.Literal[symbol >> (8 - LZMA_LC)];
}

uint16_t*
LzGetDistSlot (
    void
    )
{
    uint8_t slotIndex;

    //
    // There are 4 different arithmetic-coded bit trees which are used to pick
    // the correct "distance slot" when doing match distance decoding. Each of
    // them is used based on the length of the symbol that is being repeated.
    // For lengths of 2, 3, 4 bytes, a dedicated set of distance slots is used.
    // For lengths of 5 bytes or above, a shared set of distance slots is used.
    //
    if (Decoder.Len < (LZMA_FIRST_CONTEXT_DISTANCE_SLOT + LZMA_MIN_LENGTH))
    {
        slotIndex = (uint8_t)(Decoder.Len - LZMA_MIN_LENGTH);
    }
    else
    {
        slotIndex = LZMA_FIRST_CONTEXT_DISTANCE_SLOT - 1;
    }
    return Decoder.u.BitModel.DistSlot[slotIndex];
}

void
LzDecodeLiteral (
    void
    )
{
    uint16_t* probArray;
    uint8_t symbol, matchByte;

    //
    // First, choose the correct arithmetic-coded bit tree (which is based on
    // the last symbol we just decoded), then see if we last decoded a literal.
    //
    // If so, simply get the symbol from the bit tree as normal. However, if
    // we didn't last see a literal, we need to read the "match byte" that is
    // "n" bytes away from the last decoded match. We previously stored this in
    // rep0.
    //
    // Based on this match byte, we'll then use 2 other potential bit trees,
    // see LzDecodeMatched for more information.
    //
    probArray = LzGetLiteralSlot();
    if (LzIsLiteral(Decoder.Sequence))
    {

        symbol = RcGetBitTree(probArray, (1 << 8));
    }
    else
    {
        matchByte = DtGetSymbol(Decoder.Rep0 + 1);
        symbol = RcDecodeMatchedBitTree(probArray, matchByte);
    }

    //
    // Write the symbol and indicate that the last sequence was a literal
    //
    DtPutSymbol(symbol);
    LzSetLiteral(&Decoder.Sequence);
}

void
LzDecodeLen (
    PLENGTH_DECODER_STATE LenState,
    uint8_t PosBit
    )
{
    uint16_t* probArray;
    uint16_t limit;

    //
    // Lenghts of 2 and higher are encoded in 3 possible types of arithmetic-
    // coded bit trees, depending on the size of the length.
    //
    // Lengths 2-9 are encoded in trees called "Low" using 3 bits of data.
    // Lengths 10-17 are encoded in trees called "Mid" using 3 bits of data.
    // Lengths 18-273 are encoded in a tree called "high" using 8 bits of data.
    //
    // The appropriate "Low" or "Mid" tree is selected based on the bottom 2
    // position bits (0-3) (in the LZMA standard, this is based on the "pb",
    // while the "High" tree is shared for all positions.
    //
    // Two arithmetic-coded bit trees, called "Choice" and "Choice2" tell us
    // the type of Length, so we can choose the right tree. {0, n} tells us
    // to use the Low trees, while {1, 0} tells us to use the Mid trees. Lastly
    // {1, 1} tells us to use the High tree.
    //
    Decoder.Len = LZMA_MIN_LENGTH;
    if (RcIsBitSet(&LenState->Choice))
    {
        if (RcIsBitSet(&LenState->Choice2))
        {
            probArray = LenState->High;
            limit = LZMA_MAX_HIGH_LENGTH;
            Decoder.Len += LZMA_MAX_LOW_LENGTH + LZMA_MAX_MID_LENGTH;
        }
        else
        {
            probArray = LenState->Mid[PosBit];
            limit = LZMA_MAX_MID_LENGTH;
            Decoder.Len += LZMA_MAX_LOW_LENGTH;
        }
    }
    else
    {
        probArray = LenState->Low[PosBit];
        limit = LZMA_MAX_LOW_LENGTH;
    }
    Decoder.Len += RcGetBitTree(probArray, limit);
}

void
LzDecodeMatch (
    uint8_t PosBit
    )
{
    uint16_t* probArray;
    uint8_t distSlot, distBits;

    //
    // Decode the length component of the "match" sequence. Then, since we're
    // about  to decode a new distance, update our history by one level.
    //
    LzDecodeLen(&Decoder.u.BitModel.MatchLen, PosBit);
    Decoder.Rep3 = Decoder.Rep2;
    Decoder.Rep2 = Decoder.Rep1;
    Decoder.Rep1 = Decoder.Rep0;

    //
    // Read the first 6 bits, which make up the "distance slot"
    //
    probArray = LzGetDistSlot();
    distSlot = RcGetBitTree(probArray, LZMA_DISTANCE_SLOTS);
    if (distSlot < LZMA_FIRST_CONTEXT_DISTANCE_SLOT)
    {
        //
        // Slots 0-3 directly encode the distance as a literal number
        //
        Decoder.Rep0 = distSlot;
    }
    else
    {
        //
        // For slots 4-13, figure out how many "context encoded bits" are used
        // to encode this distance. The math works out such that slots 4-5 use
        // 1 bit, 6-7 use 2 bits, 8-9 use 3 bits, and so on and so forth until
        // slots 12-13 which use 5 bits.
        //
        // This gives us anywhere from 1-5 bits, plus the two upper bits which
        // can either be 0b10 or 0b11 (based on the bottom bit of the distance
        // slot). Thus, with the context encoded bits, we can represent lengths
        // anywhere from 0b10[0] to 0b11[11111] (i.e.: 4-127).
        //
        // For slots 14-63, we use "fixed 50% probability bits" which are also
        // called "direct bits". The formula below also tells us how many such
        // direct bits to use in this scenario. In other words, distBits can
        // either be the number of "context encoded bits" for slots 4-13, or it
        // can be the the number of "direct bits" for slots 14-63. This gives
        // us a range of of 2 to 26 bits, which are then used as middle bits.
        // Finally, the last 4 bits are called the "align" bits. The smallest
        // possible number we can encode is now going to be 0b10[00][0000] and
        // the highest is 0b11[1111111111111111111111111][1111], in other words
        // 128 to (2^31)-1.
        //
        distBits = (distSlot >> 1) - 1;
        Decoder.Rep0 = (0b10 | (distSlot & 1)) << distBits;

        //
        // Slots 4-13 have their own arithmetic-coded reverse bit trees. Slots
        // 14-63 encode the middle "direct bits" with fixed 50% probability and
        // the bottom 4 "align bits" with a shared arithmetic-coded reverse bit
        // tree.
        //
        if (distSlot < LZMA_FIRST_FIXED_DISTANCE_SLOT)
        {
            probArray = &Decoder.u.BitModel.Dist[Decoder.Rep0 - distSlot];
        }
        else
        {
            Decoder.Rep0 |= RcGetFixed(distBits - LZMA_DISTANCE_ALIGN_BITS) <<
                             LZMA_DISTANCE_ALIGN_BITS;
            distBits = LZMA_DISTANCE_ALIGN_BITS;
            probArray = Decoder.u.BitModel.Align;
        }
        Decoder.Rep0 |= RcGetReverseBitTree(probArray, distBits);
    }

    //
    // Indicate that the last sequence was a "match"
    //
    LzSetMatch(&Decoder.Sequence);
}

void
LzDecodeRepLen (
    uint8_t PosBit,
    bool IsLongRep
    )
{
    //
    // Decode the length byte and indicate the last sequence was a "rep".
    // If this is a short rep, then the length is always hard-coded to 1.
    //
    if (IsLongRep)
    {
        LzDecodeLen(&Decoder.u.BitModel.RepLen, PosBit);
        LzSetLongRep(&Decoder.Sequence);
    }
    else
    {
        Decoder.Len = 1;
        LzSetShortRep(&Decoder.Sequence);
    }
}

void
LzDecodeRep0(
    uint8_t PosBit
    )
{
    uint8_t bit;

    //
    // This could be a "short rep" with a length of 1, or a "long rep0" with
    // a length that we have to decode. The next bit tells us this, using the
    // arithmetic-coded bit trees stored in "Rep0Long", with 1 tree for each
    // position bit (0-3).
    //
    bit = RcIsBitSet(&Decoder.u.BitModel.Rep0Long[Decoder.Sequence][PosBit]);
    LzDecodeRepLen(PosBit, bit);
}

void
LzDecodeLongRep (
    uint8_t PosBit
    )
{
    uint32_t newRep;

    //
    // Read the next 2 bits to figure out which of the recently used distances
    // we should use for this match. The following three states are possible :
    //
    // {0,n} - "Long rep1", where the length is stored in an arithmetic-coded
    // bit tree, and the distance is the 2nd most recently used distance (Rep1)
    //
    // {1,0} - "Long rep2", where the length is stored in an arithmetic-coded
    // bit tree, and the distance is the 3rd most recently used distance (Rep2)
    //
    // {1,1} - "Long rep3", where the length is stored in an arithmetic-coded
    // bit tree, and the distance is the 4th most recently used distance (Rep3)
    //
    // Once we have the right one, we must slide down each previously recently
    // used distance, so that the distance we're now using (Rep1, Rep2 or Rep3)
    // becomes "Rep0" again.
    //
    if (RcIsBitSet(&Decoder.u.BitModel.Rep1[Decoder.Sequence]))
    {
        if (RcIsBitSet(&Decoder.u.BitModel.Rep2[Decoder.Sequence]))
        {
            newRep = Decoder.Rep3;
            Decoder.Rep3 = Decoder.Rep2;
        }
        else
        {
            newRep = Decoder.Rep2;
        }
        Decoder.Rep2 = Decoder.Rep1;
    }
    else
    {
        newRep = Decoder.Rep1;
    }
    Decoder.Rep1 = Decoder.Rep0;
    Decoder.Rep0 = newRep;
    LzDecodeRepLen(PosBit, true);
}

void
LzDecodeRep (
    uint8_t PosBit
    )
{
    //
    // We know this is an LZ77 distance-length pair where the distance is based
    // on a history of up to 4 previously used distance (Rep0-3). To know which
    // distance to use, the following 5 bit positions are possible (keeping in
    // mind that we've already decoded the first 2 bits {1,1} in LzDecode which
    // got us here in the first place):
    //
    // {0,0} - "Short rep", where the length is always 1 and distance is always
    // the most recently used distance (Rep0).
    //
    // {0,1} - "Long rep0", where the length is stored in an arithmetic-coded
    // bit tree, and the distance is the most recently used distance (Rep0).
    //
    // Because both of these possibilities just use Rep0, LzDecodeRep0 handles
    // these two cases. Otherwise, we use LzDecodeLongRep to read up to two
    // additional bits to figure out which recently used distance (1, 2, or 3)
    // to use.
    //
    if (RcIsBitSet(&Decoder.u.BitModel.Rep0[Decoder.Sequence]))
    {
        LzDecodeLongRep(PosBit);
    }
    else
    {
        LzDecodeRep0(PosBit);
    }
}

bool
LzDecode (
    void
    )
{
    uint32_t position;
    uint8_t posBit;

    //
    // Get the current position in dictionary, making sure we have input bytes.
    // Once we run out of bytes, normalize the last arithmetic coded byte and
    // ensure there's no pending lengths that we haven't yet repeated.
    //
    while (DtCanWrite(&position) && RcCanRead())
    {
        //
        // An LZMA packet begins here, which can have 3 possible initial bit
        // sequences that correspond to the type of encoding that was chosen
        // to represent the next stream of symbols.
        //
        // {0, n} represents a "literal", which LzDecodeLiteral decodes.
        // Literals are a single byte encoded with arithmetic-coded bit trees
        //
        // {1, 0} represents a "match", which LzDecodeMatch decodes.
        // Matches are typical LZ77 sequences with explicit length and distance
        //
        // {1, 1} represents a "rep", which LzDecodeRep decodes.
        // Reps are LZ77 sequences where the distance is encoded as a reference
        // to a previously used distance (up to 4 -- called "Rep0-3").
        //
        // Once we've decoded either the "match" or the "rep', we now have the
        // distance in "Rep0" (the most recently used distance) and the length
        // in "Len", so we will use DtRepeatSymbol to go back in the dictionary
        // buffer "Rep0" bytes and repeat that character "Len" times.
        //
        posBit = position & (LZMA_POSITION_COUNT - 1);
        if (RcIsBitSet(&Decoder.u.BitModel.Match[Decoder.Sequence][posBit]))
        {
            if (RcIsBitSet(&Decoder.u.BitModel.Rep[Decoder.Sequence]))
            {
                LzDecodeRep(posBit);
            }
            else
            {
                LzDecodeMatch(posBit);
            }

            if (!DtRepeatSymbol(Decoder.Len, Decoder.Rep0 + 1))
            {
                return false;
            }
            Decoder.Len = 0;
        }
        else
        {
            LzDecodeLiteral();
        }
    }
    RcNormalize();
    return (Decoder.Len == 0);
}

void
LzResetState (
    void
    )
{
    //
    // Initialize decoder to default state in case we're called more than once.
    // The LZMA "Bit Model" is an adaptive arithmetic-coded probability-based
    // bit tree which encodes either a "0" or a "1".
    //
    Decoder.Sequence = LzmaLitLitLitState;
    Decoder.Rep0 = Decoder.Rep1 = Decoder.Rep2 = Decoder.Rep3 = 0;
    static_assert((LZMA_BIT_MODEL_SLOTS * 2) == sizeof(Decoder.u.BitModel),
                  "Invalid size");
    for (int i = 0; i < LZMA_BIT_MODEL_SLOTS; i++)
    {
        RcSetDefaultProbability(&Decoder.u.RawProbabilities[i]);
    }
}

bool
LzInitialize (
    uint8_t Properties
    )
{
    if (Properties != k_LzSupportedProperties)
    {
        return false;
    }
    LzResetState();
    return true;
}
