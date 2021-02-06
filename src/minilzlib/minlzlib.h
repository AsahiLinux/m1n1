/*++

Copyright (c) Alex Ionescu.  All rights reserved.

Module Name:

    minlzlib.h

Abstract:

    This header file is the main include for the minlz library. It contains the
    internal function definitions for the history \& input buffers, the LZMA and
    LZMA2 decoders, and the arithmetic (de)coder.

Author:

    Alex Ionescu (@aionescu) 15-Apr-2020 - Initial version

Environment:

    Windows & Linux, user mode and kernel mode.

--*/

#pragma once

//
// C Standard Headers
//
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>

//
// Input Buffer Management
//
bool BfRead(uint8_t* Byte);
bool BfSeek(uint32_t Length, uint8_t** Bytes);
uint32_t BfTell(void);
bool BfAlign(void);
void BfInitialize(uint8_t* InputBuffer, uint32_t InputSize);
bool BfSetSoftLimit(uint32_t Remaining);
void BfResetSoftLimit(void);

//
// Dictionary (History Buffer) Management
//
bool DtRepeatSymbol(uint32_t Length, uint32_t Distance);
void DtInitialize(uint8_t* HistoryBuffer, uint32_t Position);
bool DtSetLimit(uint32_t Limit);
void DtPutSymbol(uint8_t Symbol);
uint8_t DtGetSymbol(uint32_t Distance);
bool DtCanWrite(uint32_t* Position);
bool DtIsComplete(uint32_t* BytesProcessed);

//
// Range Decoder
//
uint8_t RcGetBitTree(uint16_t* BitModel, uint16_t Limit);
uint8_t RcGetReverseBitTree(uint16_t* BitModel, uint8_t HighestBit);
uint8_t RcDecodeMatchedBitTree(uint16_t* BitModel, uint8_t MatchByte);
uint32_t RcGetFixed(uint8_t HighestBit);
bool RcInitialize(uint16_t* ChunkSize);
uint8_t RcIsBitSet(uint16_t* Probability);
void RcNormalize(void);
bool RcCanRead(void);
bool RcIsComplete(uint32_t* Offset);
void RcSetDefaultProbability(uint16_t* Probability);

//
// LZMA Decoder
//
bool LzDecode(void);
bool LzInitialize(uint8_t Properties);
void LzResetState(void);

//
// LZMA2 Decoder
//
bool Lz2DecodeStream(uint32_t* BytesProcessed, bool GetSizeOnly);
#ifdef MINLZ_INTEGRITY_CHECKS
//
// Checksum Management
//
uint32_t OsComputeCrc32(uint32_t Initial, const uint8_t* Data, uint32_t Length);
#define Crc32(Buffer, Length) OsComputeCrc32(0, (const uint8_t*)Buffer, Length)
#endif
