# Apple Silicon JPEG encoder/decoder reverse engineering notes

## General

### REG_0x0 (+0x0000)

This register is not fully understood yet. It is set to 1 to kick off an operation.

This register appears to be 1 bit wide. It is readable/writable.

The driver resets this register to 0.


### REG_0x4 (+0x0004)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver resets this register to 0.


### MODE (+0x0008)

This register controls the mode of operation of the hardware. The details of this register are not understood yet.

This register appears to be 10 bit wide. It is readable/writable.

At minimum bits 0x043 need to be set or else reading from some registers above 0x1000 will fault.

This register is set to multiple different values throughout the reset process.


### REG_0xc (+0x000C)

This register is not understood yet.

This register is at least 10 bit wide. It appears to be read-only. The power-up state appears to be 0x200.

The driver reads this register and stores the value after an interrupt occurs.


### REG_0x10 (+0x0010)
### REG_0x14 (+0x0014)

No access to this register has been observed.

This register is at least 11 bit wide. It appears to be read-only. The power-up state appears to be 0x400.


### REG_0x18 (+0x0018)

No access to this register has been observed.

This register is at least 8 bit wide. It appears to be read-only. The power-up state appears to be 0x55.


### (+0x001C)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


### REG_0x20 (+0x0020)

This register is not understood yet.

This register appears to be 11 bit wide. It is readable/writable.

The driver resets this register to 0xff, and it is written with a 0 after an interrupt occurs.


### STATUS (+0x0024)

- bit0: Operation is completed ???
- bit1: Timeout occurred
- bit2: Read buffer overflow
- bit3: Write buffer overflow
- bit4: Codec buffer overflow
- bit5: Some kind of error, happens if macroblock settings are messed up
- bit6: AXI error
- bit7: The driver checks for this after an interrupt, but the meaning is not understood


### CODEC (+0x0028)

This register controls how the JPEG data is processed wrt subsampling mode. It affects both encode and decode.

- 0 = 4:4:4
- 1 = 4:2:2
- 2 = 4:1:1
- 3 = 4:2:0
- 4 = 4:0:0

### REG_0x2c (+0x002C)

This register is not fully understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver sets this register to 0 when decoding and 1 when encoding. If it is not set to 1 when encoding, only headers will be output. The interrupt handler makes a decision based on this register.


### REG_0x30 (+0x0030)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver resets this register to 0.


### REG_0x34 (+0x0034)

This register is not fully understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver sets this register to 1 when decoding and 0 when encoding. If it is not set to 0 when encoding, the output will be corrupted in some way.


### REG_0x38 (+0x0038)

This register is not fully understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver sets this register to 0 when decoding and 1 when encoding. If it is not set to 1 when encoding, nothing will be output. If it is set to 1 when decoding, the output will be a weird tiled format.



## Chroma control

### CHROMA_HALVE_H_TYPE1 (+0x003c)
### CHROMA_HALVE_H_TYPE2 (+0x0040)

Setting these register to 1 causes chroma to be subsampled horizontally.

The second register produces a different result from the first register. It is speculated that this is related to chroma siting, but this has not been verified yet. If both the second and the first register are set, the second appears to win.


### CHROMA_HALVE_V_TYPE1 (+0x0044)
### CHROMA_HALVE_V_TYPE2 (+0x0048)

Setting these register to 1 causes chroma to be subsampled vertically.

The second register produces a different result from the first register. It is speculated that this is related to chroma siting, but this has not been verified yet. If both the second and the first register are set, the second appears to win.


### CHROMA_DOUBLE_H (+0x004c)

Setting this register to 1 causes chroma to be doubled/interpolated horizontally.


### CHROMA_QUADRUPLE_H (+0x0050)

Setting this register to 1 causes chroma to be quadrupled/interpolated horizontally. If both this and the previous register are set, double appears to win.


### CHROMA_DOUBLE_V (+0x0054)

Setting this register to 1 causes chroma to be doubled/interpolated vertically.


## Pixel data control

### PX_USE_PLANE1 (+0x0058)

Setting this register to 1 enables use of the second pixel plane.


### PX_TILES_W (+0x005c)

This register specifies the width of the image in tiles/MCUs/macroblocks, where the macroblock size depends on the chroma subsampling mode, i.e. divroundup by 8 for 4:4:4, by 16 for 4:2:2 and 4:2:0, by 32 for 4:1:1 (FIXME verify this again).

This register is 16 bits wide.


### PX_TILES_H (+0x0060)

This register specifies the height of the image in tiles/MCUs/macroblocks, where the macroblock size depends on the chroma subsampling mode, i.e. divroundup by 16 for 4:2:0 or else by 8 (FIXME verify this again).

This register is 16 bits wide.


### PX_PLANE0_WIDTH (+0x0064)

This register specifies the width of the image data in plane 0, in bytes, minus 1. When decoding, it is important to set this correctly for the edge to be processed properly.

This register is 20 bits wide, even though the driver will sometimes write 0xffffffff.


### PX_PLANE0_HEIGHT (+0x0068)

This register specifies the height of the image data in plane 0, in rows, minus 1. When decoding, it might be important to set this correctly for the edge to be processed properly.

This register is 16 bits wide, even though the driver will sometimes write 0xffffffff.


### PX_PLANE0_TILING_H (+0x006c)

This register somehow controls how pixel data matches up with subsampled chroma data, but the details are not understood yet. Valid range 0-31.


### PX_PLANE0_TILING_V (+0x0070)

This register somehow controls how pixel data matches up with subsampled chroma data, but the details are not understood yet. Valid range 0-31.


### PX_PLANE0_STRIDE (+0x0074)

This is the row stride of plane 0 in bytes.

This register is 24 bits wide.


### PX_PLANE1_WIDTH (+0x0078)
### PX_PLANE1_HEIGHT (+0x007c)
### PX_PLANE1_TILING_H (+0x0080)
### PX_PLANE1_TILING_V (+0x0084)
### PX_PLANE1_STRIDE (+0x0088)

These registers function similarly to the plane 0 registers.


## Input/output pointers

### INPUT_START1 (+0x008c)

Input pointer 1 IOVA.


### INPUT_START2 (+0x0090)

Input pointer 2 IOVA.


### REG_0x94 (+0x0094)

This register is not understood yet.

The driver sets this register to a fixed value of 0x1f when decoding and to a value that depends on the chroma subsampling mode when encoding (0xc for 4:4:4, 0x8 for 4:2:2, 0x3 for 4:2:0, 0xb for 4:0:0), but changing it does not seem to do anything.

This register is 6 bits wide.


### REG_0x98 (+0x0098)

This register is not understood yet.

The driver sets this register to a fixed value of 1 when decoding and to a value that depends on the chroma subsampling mode when encoding (2 for 4:4:4/4:2:2/4:0:0, 1 for 4:2:0), but changing it does not seem to do anything.

This register is 6 bits wide.


### INPUT_END (+0x009c)

End of input data IOVA.

For reasons that are not understood, this is ORed with 7 when encoding.


### OUTPUT_START1 (+0x00a0)

Output pointer 1 IOVA.


### OUTPUT_START2 (+0x00a4)

Output pointer 2 IOVA.


### OUTPUT_END (+0x00a8)

End of output data IOVA.


## MATRIX_MULT (+0x00ac-0x00d7) (11 entries)

Color space conversion matrix.

The full details of the shifting/offset/final two values is not understood yet.


## DITHER (+0x00d8-0x00ff) (10 entries)

Dithering when decoding to RGB565.

The full details of this is not understood yet.


## Encoding pixel format

### ENCODE_PIXEL_FORMAT (+0x0100)

- 0 = RGB101010
- 1 = YUV10 4:4:4 linear
- 2 = RGB888
- 3 = RGB565
- 4 = YUV planar (partially tested, details not fully understood)
- 5 = YUV8 4:2:2 linear
- 6-9 = do something, may not be useful, maybe invalid, not used by driver


### ENCODE_COMPONENT0_POS (+0x0104)
### ENCODE_COMPONENT1_POS (+0x0108)
### ENCODE_COMPONENT2_POS (+0x010c)
### ENCODE_COMPONENT3_POS (+0x0110)

These registers control the positions of each component in the parsed pixel data. It is used to allow e.g. flipping between RGBA and BGRA.


### CONVERT_COLOR_SPACE (+0x0114)

Setting this register to 1 enables color space conversion when encoding


## Unknown

### REG_0x118 (+0x0118)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

This register is set to 0 when decoding and 1 when encoding.


### REG_0x11c (+0x011c)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

This register is set to 1 when decoding and 0 when encoding.


### REG_0x120 (+0x0120)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver resets this register to 0.


### TILING_ENABLE (+0x0124)

This register enables the functionality of the following two registers.

The driver sets this register to 1 when decoding if the surface "is tiled."


### TILING_PLANE0 (+0x0128)

This register is not fully understood yet. A value greater than 8 causes plane 0 to be reformatted (tiled?), but the details are not understood yet.

This register appears to be 5 bit wide. It is readable/writable.


### TILING_PLANE1 (+0x012c)

This register is not fully understood yet. A value greater than 8 causes plane 1 to be reformatted (tiled?), but the details are not understood yet.

This register appears to be 5 bit wide. It is readable/writable.


## Decoding image size

### DECODE_MACROBLOCKS_W (+0x0130)

Sets the width of the decoded image in macroblocks, where the macroblock size depends on the chroma subsampling mode, i.e. divroundup by 8 for 4:4:4, by 16 for 4:2:2 and 4:2:0, by 32 for 4:1:1.

This register is 16 bits wide.


### DECODE_MACROBLOCKS_H (+0x0134)

Sets the height of the decoded image in macroblocks, where the macroblock size depends on the chroma subsampling mode, i.e. divroundup by 16 for 4:2:0 or else by 8.

This register is 16 bits wide.


### RIGHT_EDGE_PIXELS (+0x0138)

The driver sets this to the number of pixels that are valid in the rightmost macroblocks, but changing it does not seem to do anything.

This register is 5 bits wide.


### BOTTOM_EDGE_PIXELS (+0x013c)

The driver sets this to the number of pixels that are valid in the bottommost macroblocks, but changing it does not seem to do anything.

This register is 4 bits wide.


### RIGHT_EDGE_SAMPLES (+0x0140)

The driver sets this to the number of chroma samples that are valid in the rightmost macroblocks, but changing it does not seem to do anything.

This register is 3 bits wide.


### BOTTOM_EDGE_SAMPLES (+0x0144)

The driver sets this to the number of chroma samples that are valid in the bottommost macroblocks, but changing it does not seem to do anything.

This register is 3 bits wide.


### SCALE_FACTOR (+0x0148)

- 0 = /1
- 1 = /2
- 2 = /4
- 3 = /8

This appears to be ignored when encoding.


## Decoding pixel format

### DECODE_PIXEL_FORMAT (+0x014c)

- 0 = YUV 444 (2P)
- 1 = YUV 422 (2P)
- 2 = YUV 420 (2P)
- 3 = YUV 422 (1P)
- 4 = driver mentions YUV10 444 (1P) but it does not appear to work (driver also says it doesn't work)
- 5 = RGB888
- 6 = RGB565
- 7 = driver mentions RGB101010 but it does not appear to work (driver also says it doesn't work)


### YUV422_ORDER (+0x0150)

- 0 = Cb Y'0 Cr Y'1
- 1 = Y'0 Cb Y'1 Cr


### RGBA_ORDER (+0x0154)

- 0 = BGRA
- 1 = RGBA


### RGBA_ALPHA (+0x0158)

This value is filled in to alpha bytes when decoding into RGB888


## Unknown/status

### PLANAR_CHROMA_HALVING (+0x015c)

This register is not fully understood yet. Setting it seems to halve the chroma vertically when outputting into planar modes. This is different from the CHROMA_HALVE_V_* registers because it halves the final image, not each macroblock.

The driver seems to use this in some cases when scaling down an image by 8, but the details of this are not understood yet.

The driver resets this register to 0.


### REG_0x160 (+0x0160)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver resets this register to a configurable value that happens to be 0.


### REG_0x164 (+0x0164)

This register is not understood yet.

It appears to be read-only. The power-up state appears to be 0.

The driver reads this register and stores the value after an interrupt occurs.


### (+0x0168)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


### REG_0x16c (+0x016c)

This register is not understood yet.

It appears to be read-only. The power-up state appears to be 0.

The driver reads this register and stores the value after an interrupt occurs.


### REG_0x170 (+0x0170)

This register is not understood yet.

It appears to be read-only. The power-up state appears to be 0.

The driver reads this register and stores the value after an interrupt occurs.


### (+0x0174)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


### PERFCOUNTER (+0x0178)

This register appears to be a performance counter. It is not yet understood what is being measured.

It appears to be read-only.

The driver reads this register and accumulates it after an interrupt occurs.


### (+0x017c)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


### (+0x0180)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


### TIMEOUT (+0x0184)

This register configures the timeout. It is not yet understood what units this is in.

This register is 32 bits wide.


### HWREV (+0x0188)

This register contains the hardware revision. On the M1 Max, it is 0xd1013.


### REG_0x18c (+0x018c)

No access to this register has been observed.

This register appears to be 2 bits wide. It is readable/writable.


### REG_0x190 (+0x0190)

No access to this register has been observed.

This register appears to be 2 bits wide. It is readable/writable.


### REG_0x194 (+0x0194)

No access to this register has been observed.

This register appears to be 4 bits wide. It is readable/writable.


### REG_0x198 (+0x0198)

No access to this register has been observed.

This register appears to be 4 bits wide. It is readable/writable.


### REG_0x19c (+0x019c)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.

The driver under some conditions writes a 1 here.


## RST logging / unknown

### ENABLE_RST_LOGGING (+0x01a0)

If this register is set to 1, some data about RST blocks will be logged when encoding.


### RST_LOG_ENTRIES (+0x01a4)

This register will contain the number of RST log entries.


### REG_0x1a8 (+0x01a8)
### REG_0x1ac (+0x01ac)
### REG_0x1b0 (+0x01b0)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.


### REG_0x1b4 (+0x01b4)
### REG_0x1b8 (+0x01b8)
### REG_0x1bc (+0x01bc)

This register is not understood yet.

This register appears to be 32 bit wide. It is readable/writable.


### REG_0x1c0 (+0x01c0)
### REG_0x1c4 (+0x01c4)

This register is not understood yet.

This register appears to be 16 bit wide. It is readable/writable.


### REG_0x1c8 (+0x01c8)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.


### REG_0x1cc (+0x01cc)
### REG_0x1d0 (+0x01d0)
### REG_0x1d4 (+0x01d4)
### REG_0x1d8 (+0x01d8)

This register is not understood yet.

This register appears to be 32 bit wide. It is readable/writable.


### REG_0x1dc (+0x01dc)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.


### REG_0x1e0 (+0x01e0)

This register is not understood yet.

This register appears to be 14 bit wide. It is readable/writable.


### REG_0x1e4 (+0x01e4)

This register is not understood yet.

This register appears to be 13 bit wide. It is readable/writable.


### REG_0x1e8 (+0x01e8)

This register is not understood yet.

This register appears to be 9 bit wide. It is readable/writable.


### REG_0x1ec (+0x01ec)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.


### REG_0x1f0 (+0x01f0)

This register is not understood yet.

This register appears to be 14 bit wide. It is readable/writable.


### REG_0x1f4 (+0x01f4)

This register is not understood yet.

This register appears to be 13 bit wide. It is readable/writable.


### REG_0x1f8 (+0x01f8)

This register is not understood yet.

This register appears to be 9 bit wide. It is readable/writable.


## Compressed pixel format / Compressed DMA / unknown

### REG_0x1fc (+0x01fc)
### REG_0x200 (+0x0200)

No access to this register has been observed.

This register appears to be 2 bits wide. It is readable/writable.


### REG_0x204 (+0x0204)
### REG_0x208 (+0x0208)

This register is not understood yet.

This register appears to be 32 bit wide. It is readable/writable.


### REG_0x20c (+0x020c)
### REG_0x210 (+0x0210)
### REG_0x214 (+0x0214)
### REG_0x218 (+0x0218)

This register is not understood yet.

This register appears to be 17 bit wide. It is readable/writable.


### REG_0x21c (+0x021c)
### REG_0x220 (+0x0220)

This register is not understood yet.

This register appears to be 16 bit wide. It is readable/writable.


### REG_0x224 (+0x0224)
### REG_0x228 (+0x0228)

This register is not understood yet.

This register appears to be 17 bit wide. It is readable/writable.


### REG_0x22c (+0x022c)
### REG_0x230 (+0x0230)
### REG_0x234 (+0x0234)

This register is not understood yet.

This register appears to be 16 bit wide. It is readable/writable.


### REG_0x238 (+0x0238)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.


### REG_0x23c (+0x023c)
### REG_0x240 (+0x0240)

This register is not understood yet.

This register appears to be 4 bit wide. It is readable/writable.


### REG_0x244 (+0x0244)
### REG_0x248 (+0x0248)

This register is not understood yet.

This register appears to be 8 bit wide. It is readable/writable.


### REG_0x24c (+0x024c)

This register is not understood yet.

This register appears to be 1 bit wide. It is readable/writable.


### REG_0x250 (+0x0250)
### REG_0x254 (+0x0254)

This register is not understood yet.

This register appears to be 4 bit wide. It is readable/writable.


### REG_0x258 (+0x0258)
### REG_0x25c (+0x025c)

This register is not understood yet.

This register appears to be 8 bit wide. It is readable/writable.


## REG_0x260 (+0x0260)
## REG_0x264 (+0x0264)

No access to this register has been observed.

This register appears to be 1 bit wide. It is readable/writable.


## REG_0x268 (+0x0268)
## REG_0x26c (+0x026c)

No access to this register has been observed.

This register appears to be 7 bit wide. It is readable/writable.


## (+0x0270-0x027f)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


## REG_0x280 (+0x0280)

No access to this register has been observed.

This register appears to be 1 bit wide. It is readable/writable.


## (+0x0284-0x0fff)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


## JPEG I/O related

### JPEG_IO_FLAGS (+0x1000)

- bit0-2 control subsampling mode output into the JPEG when encoding
    - 0 = 4:4:4
    - 1 = 4:2:2
    - 2 = 4:2:0
    - 3 = monochrome
    - 4 = 4 components ??? seems to work with 422 with 444 tiling params ?????
    - 6 = indicate 4:1:1 in file, but setting CODEC = 2 doesn't actually work (broken)
- bit3 needs to be set when decoding. It must be unset when encoding. This is not fully understood yet
- bit4 causes macroblocks to _not_ be flipped horizontally. It affects both encoding and decoding.
- bit5 causes chunks of 8 bytes to _not_ be reversed. It affects both encoding and decoding.


### REG_0x1004 (+0x1004)

This register is not fully understood yet. It is set to 1 to kick off an operation.

Writing to this register while MODE is set incorrectly can trigger an exception.


### REG_0x1008 (+0x1008)

No access to this register has been observed.

This register is at least 1 bit wide. It appears to be read-only. The power-up state appears to be 1.


### QTBL_SEL (+0x100c)

This register selects the quantization table in use for each component.

- bit0-1 = component 0
- bit2-3 = component 1
- bit4-5 = component 2
- bit6-7 = component 3?


### HUFFMAN_TABLE (+0x1010)

This register controls Huffman tables used. The details of this register are not fully understood yet.

This register is 8 bits wide.


### RST_INTERVAL (+0x1014)

This register controls the interval at which RST markers will be generated when encoding.

This register is 16 bits wide.


### JPEG_HEIGHT (+0x1018)

This register specifies the height of the JPEG when encoding. It appears to only affect the header.

This register is 16 bits wide.


### JPEG_WIDTH (+0x101c)

This register specifies the width of the JPEG when encoding.

This register is 16 bits wide.


### COMPRESSED_BYTES (+0x1020)

This register will contain the final size of the JPEG when encoding


### JPEG_OUTPUT_FLAGS (+0x1024)

- bit0 doesn't seem to do anything
- bit1 = output only SOS/EOI, no SOI/DQT/SOF0/DHT
- bit2 = output SOF0 after DHT instead of before it
- bit3 doesn't seem to do anything
- bit4 not sure exactly what this does, but it makes compression worse


### REG_0x1028 (+0x1028)

This register is not understood yet.

The driver sets this register to 0x400 when decoding.

This register appears to be 32 bits wide, but writing 0xffffffff results in 0x8000071f.


### REG_0x102c (+0x102c)

This register is not understood yet.

The driver reads this register and does something with it after an interrupt occurs.


### BITSTREAM_CORRUPTION (+0x1030)

This register is not understood yet. It supposedly contains information about bitstream corruption.


## (+0x1034-0x107f)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


## REG_0x1080 (+0x1080)

No access to this register has been observed.

This register appears to be 5 bit wide. It is readable/writable.


## REG_0x1084 (+0x1084)

No access to this register has been observed.

This register appears to be 7 bit wide. It is readable/writable.


## (+0x1088)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


## REG_0x108c (+0x108c)

No access to this register has been observed.

This register appears to be 32 bit wide. It is readable/writable.


## REG_0x1090 (+0x1090)

No access to this register has been observed.

This register appears to be 8 bit wide. It is readable/writable.


## (+0x1094-0x10df)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


## SHIKINO_VERSION_MAGIC0 (+0x10e0)
## SHIKINO_VERSION_MAGIC1 (+0x10e4)
## SHIKINO_VERSION_MAGIC2 (+0x10e8)
## SHIKINO_VERSION_MAGIC3 (+0x10ec)
## SHIKINO_VERSION_MAGIC4 (+0x10f0)

Contains ASCII text 'SHIKINO KJN-7GI 0001'


## (+0x10f4-0x10ff)

No access to this register has been observed.

It appears to be read-only. The power-up state appears to be 0.


## QTBL (+0x1100-0x11ff)

Quantization tables. The exact layout is not understood yet (zigzag or not?)


## (+0x1200-0x1fff)

No access to this register has been observed.


## RSTLOG (+0x2000-0x2fff)

RST log. The details of this are not understood yet.


## (+0x3000-0x3fff)

No access to this register has been observed.
