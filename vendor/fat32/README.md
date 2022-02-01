# News
This crate has stopped updating, please use [rust-fatfs](https://github.com/rafalh/rust-fatfs).

# FAT32 FileSystem Library
[![crates.io version](https://img.shields.io/crates/v/fat32.svg)](https://crates.io/crates/fat32)

This is FAT32 FileSystem Library, which is `#![no_std]` and does not use `alloc`.
 
Test passed with [sdio_sdhc](https://github.com/play-stm32/sdio_sdhc) and WindowsAPI. 

## Supported Features
- [x] Read
- [x] Create File AND Dir
- [x] Write(OverWritten and Append)
- [x] Delete File AND DIR

## Questions
### My Device Support `std`, Can I Use This Crate?
Of course you can, but I don't recommend it. You should use `std::fs::File` OR other crates.

### Why Do You Write This Crate?
In order to support devices and environment which don't have `std`, like
* Embedded Device
* Bootloader

### Have More Examples?
* [Embedded Device's Bootloader](https://github.com/play-stm32/bootloader)

## How To Test (Only Windows)
* EDIT mount() function in lib.rs, change disk like `\\\\.\\E:`
* `cargo test`

## How To Use
You need make your library implement [`BlockDevice` trait](https://github.com/Spxg/block_device):

```rust
pub trait BlockDevice {
    type Error;
    fn read(&self, buf: &mut [u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error>;
    fn write(&self, buf: &[u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error>;
}
```

For example, I use my another library [sdio_sdhc](https://github.com/play-stm32/sdio_sdhc) to implement:

```rust
impl BlockDevice for Card {
    type Error = CmdError;

    fn read(&self, buf: &mut [u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error> {
        if number_of_blocks == 1 {
            self.read_block(buf, address as u32)?
        } else {
            self.read_multi_blocks(buf, address as u32, number_of_blocks as u32)?
        }

        Ok(())
    }

    fn write(&self, buf: &[u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error> {
        if number_of_blocks == 1 {
            self.write_block(buf, address as u32)?
        } else {
            self.write_multi_blocks(buf, address as u32, number_of_blocks as u32)?
        }

        Ok(())
    }
}
```

Now [sdio_sdhc](https://github.com/play-stm32/sdio_sdhc) library supported fat32 filesystem. 
Then, add fat32 library to your application

```
# if no feature config, the BUFFER_SIZE is 512 Bytes
fat32 = "0.2"
```

If your card block is other size, like 1024 Bytes

```
[dependencies.fat32]
version = "0.2"
default-features = false
features = ["1024"]
```

Then, you can do some tests

```rust
// Card from sdio_sdhc crate
let card = Card::init().unwrap();
// Volume from fat32 crate
let cont = Volume::new(card);
// cd root dir
let mut root = cont.root_dir();
// create file named test.txt
root.create_file("test.txt").unwrap();
// open file
let mut file = root.open_file("test.txt").unwrap();
// write buffer to file
file.write(&[80; 1234]).unwrap();
```

If all goes well, the file was created with 1234 Bytes in root dir.
