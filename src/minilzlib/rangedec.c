/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    rangedec.c

Abstract:

    This module implements the Range Decoder, which is how LZMA describes the
    arithmetic coder that it uses to represent the binary representation of the
    LZ77 match length-distance pairs after the initial compression pass. At the
    implementation level, this coder works with an alphabet of only 2 symbols:
    the bit "0", and the bit "1", so there are only ever two probability ranges
    that need to be checked each pass. In LZMA, a probability of 100% encodes a
    "0", while 0% encodes a "1". Initially, all probabilities are assumed to be
    50%. Probabilities are stored using 11-bits (2048 \=\= 100%), and thus use 16
    bits of storage. Finally, the range decoder is adaptive, meaning that each
    time a bit is decoded, the probabilities are updated: each 0 increases the
    probability of another 0, and each 1 decrases it. The algorithm adapts the
    probabilities using an exponential moving average with a shift ratio of 5.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#include "minlzlib.h"

//
// The range decoder uses 11 probability bits, where 2048 is 100% chance of a 0
//
#define LZMA_RC_PROBABILITY_BITS            11
#define LZMA_RC_MAX_PROBABILITY             (1 << LZMA_RC_PROBABILITY_BITS)
const uint16_t k_LzmaRcHalfProbability = LZMA_RC_MAX_PROBABILITY / 2;

//
// The range decoder uses an exponential moving average of the last probability
// hit (match or miss) with an adaptation rate of 5 bits (which falls in the
// middle of its 11 bits used to encode a probability.
//
#define LZMA_RC_ADAPTATION_RATE_SHIFT   5

//
// The range decoder has enough precision for the range only as long as the top
// 8 bits are still set. Once it falls below, it needs a renormalization step.
//
#define LZMA_RC_MIN_RANGE               (1 << 24)

//
// The range decoder must be initialized with 5 bytes, the first of which is
// ignored
//
#define LZMA_RC_INIT_BYTES              5

//
// State used for the binary adaptive arithmetic coder (LZMA Range Decoder)
//
typedef struct _RANGE_DECODER_STATE
{
    //
    // Start and end location of the current stream's range encoder buffer
    //
    uint8_t* Start;
    uint8_t* Limit;
    //
    // Current probability range and 32-bit arithmetic encoded sequence code
    //
    uint32_t Range;
    uint32_t Code;
} RANGE_DECODER_STATE, *PRANGE_DECODER_STATE;
RANGE_DECODER_STATE RcState;

bool
RcInitialize (
    uint16_t* ChunkSize
    )
{
    uint8_t i, rcByte;
    uint8_t* chunkEnd;

    //
    // Make sure that the input buffer has enough space for the requirements of
    // the range encoder. We (temporarily) seek forward to validate this.
    //
    if (!BfSeek(*ChunkSize, &chunkEnd))
    {
        return false;
    }
    BfSeek(-*ChunkSize, &chunkEnd);

    //
    // The initial probability range is set to its highest value, after which
    // the next 5 bytes are used to initialize the initial code. Note that the
    // first byte outputted by the encoder is always going to be zero, so it is
    // ignored here.
    //
    RcState.Range = (uint32_t)-1;
    RcState.Code = 0;
    for (i = 0; i < LZMA_RC_INIT_BYTES; i++)
    {
        BfRead(&rcByte);
        RcState.Code = (RcState.Code << 8) | rcByte;
    }

    //
    // Store our current location in the buffer now, and how far we can go on
    // reading. Then decrease the total chunk size by the count of init bytes,
    // so that the caller can check, once done (RcIsComplete), if the code has
    // become 0 exactly when the compressed chunk size has been fully consumed
    // by the decoder.
    //
    BfSeek(0, &RcState.Start);
    RcState.Limit = RcState.Start + *ChunkSize;
    *ChunkSize -= LZMA_RC_INIT_BYTES;
    return true;
}

bool
RcCanRead (
    void
    )
{
    uint8_t* pos;
    //
    // We can keep reading symbols as long as we haven't reached the end of the
    // input buffer yet.
    //
    BfSeek(0, &pos);
    return pos <= RcState.Limit;
}

bool
RcIsComplete (
    uint32_t* BytesProcessed
    )
{
    uint8_t* pos;
    //
    // When the last symbol has been decoded, the last code should be zero as
    // there is nothing left to describe. Return the offset in the buffer where
    // this occurred (which should be equal to the compressed size).
    //
    BfSeek(0, &pos);
    *BytesProcessed = (uint32_t)(pos - RcState.Start);
    return (RcState.Code == 0);
}

void
RcNormalize (
    void
    )
{
    uint8_t rcByte;
    //
    // Whenever we drop below 24 bits, there is no longer enough precision in
    // the probability range not to avoid a "stuck" state where we cannot tell
    // apart the two branches (above/below the probability range) because the
    // two options appear identical with the number of precision bits that we
    // have. In this case, shift the state by a byte (8 bits) and read another.
    //
    if (RcState.Range < LZMA_RC_MIN_RANGE)
    {
        RcState.Range <<= 8;
        RcState.Code <<= 8;
        BfRead(&rcByte);
        RcState.Code |= rcByte;
    }
}

void
RcAdapt (
    bool Miss,
    uint16_t* Probability
    )
{
    //
    // In the canonical range encoders out there (including this one used by
    // LZMA, we want the probability to adapt (change) as we read more or less
    // bits that match our expectation. In order to quickly adapt to change,
    // use an exponential moving average. The standard way of doing this is to
    // use an integer based adaptation with a shift that's somewhere between
    // {1, bits-1}. Since LZMA uses 11 bits for its model, 5 is a nice number
    // that lands exactly between 1 and 10.
    //
    if (Miss)
    {
        *Probability -= *Probability >> LZMA_RC_ADAPTATION_RATE_SHIFT;
    }
    else
    {
        *Probability += (LZMA_RC_MAX_PROBABILITY - *Probability) >>
                        LZMA_RC_ADAPTATION_RATE_SHIFT;
    }
}

uint8_t
RcIsBitSet (
    uint16_t* Probability
    )
{
    uint32_t bound;
    uint8_t bit;

    //
    // Always begin by making sure the range has been normalized for precision
    //
    RcNormalize();

    //
    // Check if the current arithmetic code is descried by the next calculated
    // proportionally-divided probability range. Recall that the probabilities
    // encode the chance of the symbol (bit) being a 0 -- not a 1!
    //
    // Therefore, if the next chunk of the code lies outside of this new range,
    // we are still on the path to our 0. Otherwise, if the code is now part of
    // the newly defined range (inclusive), then we produce a 1 and limit the
    // range to produce a new range and code for the next decoding pass.
    //
    bound = (RcState.Range >> LZMA_RC_PROBABILITY_BITS) * *Probability;
    if (RcState.Code < bound)
    {
        RcState.Range = bound;
        bit = 0;
    }
    else
    {
        RcState.Range -= bound;
        RcState.Code -= bound;
        bit = 1;
    }

    //
    // Always finish by adapt the probabilities based on the bit value
    //
    RcAdapt(bit, Probability);
    return bit;
}

uint8_t
RcIsFixedBitSet(
    void
    )
{
    uint8_t bit;

    //
    // This is a specialized version of RcIsBitSet with two differences:
    //
    // First, there is no adaptive probability -- it is hardcoded to 50%.
    //
    // Second, because there are 11 bits per probability, and 50% is 1<<10,
    // "(LZMA_RC_PROBABILITY_BITS) * Probability" is essentially 1. As such,
    // we can just shift by 1 (in other words, halving the range).
    //
    RcNormalize();
    RcState.Range >>= 1;
    if (RcState.Code < RcState.Range)
    {
        bit = 0;
    }
    else
    {
        RcState.Code -= RcState.Range;
        bit = 1;
    }
    return bit;
}

uint8_t
RcGetBitTree (
    uint16_t* BitModel,
    uint16_t Limit
    )
{
    uint16_t symbol;

    //
    // Context probability bit trees always begin at index 1. Iterate over each
    // decoded bit and just keep shifting it in place, until we reach the total
    // expected number of bits, which should never be over 8 (limit is 0x100).
    //
    // Once decoded, always subtract the limit back from the symbol since we go
    // one bit "past" the limit in the loop, as a side effect of the tree being
    // off-by-one.
    //
    for (symbol = 1; symbol < Limit; )
    {
        symbol = (symbol << 1) | RcIsBitSet(&BitModel[symbol]);
    }
    return (symbol - Limit) & 0xFF;
}

uint8_t
RcGetReverseBitTree (
    uint16_t* BitModel,
    uint8_t HighestBit
    )
{
    uint16_t symbol;
    uint8_t i, bit, result;

    //
    // This is the same logic as in RcGetBitTree, but with the bits actually
    // encoded in reverse order. We keep track of the probability index as the
    // "symbol" just like RcGetBitTree, but actually decode the result in the
    // opposite order.
    //
    for (i = 0, symbol = 1, result = 0; i < HighestBit; i++)
    {
        bit = RcIsBitSet(&BitModel[symbol]);
        symbol = (symbol << 1) | bit;
        result |= bit << i;
    }
    return result;
}

uint8_t
RcDecodeMatchedBitTree (
    uint16_t* BitModel,
    uint8_t MatchByte
    )
{
    uint16_t symbol, bytePos, matchBit;
    uint8_t bit;

    //
    // Parse each bit in the "match byte" (see LzDecodeLiteral), which we call
    // a "match bit".
    //
    // Then, treat this as a special bit tree decoding where two possible trees
    // are used: one for when the "match bit" is set, and a separate one for
    // when the "match bit" is not set. Since each tree can encode up to 256
    // symbols, each one has 0x100 slots.
    //
    // Finally, we have the original bit tree which we'll revert back to once
    // the match bits are no longer in play, which we parse for the remainder
    // of the symbol.
    //
    for (bytePos = MatchByte, symbol = 1; symbol < 0x100; bytePos <<= 1)
    {
        matchBit = (bytePos >> 7) & 1;

        bit = RcIsBitSet(&BitModel[symbol + (0x100 * (matchBit + 1))]);
        symbol = (symbol << 1) | bit;

        if (matchBit != bit)
        {
            while (symbol < 0x100)
            {
                symbol = (symbol << 1) | RcIsBitSet(&BitModel[symbol]);
            }
            break;
        }
    }
    return symbol & 0xFF;
}

uint32_t
RcGetFixed (
    uint8_t HighestBit
    )
{
    uint32_t symbol;

    //
    // Fixed probability bit trees always begin at index 0. Iterate over each
    // decoded bit and just keep shifting it in place, until we reach the total
    // expected number of bits (typically never higher than 26 -- the maximum
    // number of "direct bits" that the distance of a "match" can encode).
    //
    symbol = 0;
    do
    {
        symbol = (symbol << 1) | RcIsFixedBitSet();
    } while (--HighestBit > 0);
    return symbol;
}

void
RcSetDefaultProbability (
    uint16_t* Probability
    )
{
    //
    // By default, we initialize the probabilities to 0.5 (50% chance).
    //
    *Probability = k_LzmaRcHalfProbability;
}
