//! # BlockDevice trait
//! ```rust
//! pub trait BlockDevice {
//!     type Error;
//!     fn read(&self, buf: &mut [u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error>;
//!     fn write(&self, buf: &[u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error>;
//! }
//! ```

#![no_std]

/// BlockDevice trait
pub trait BlockDevice {
    type Error;
    fn read(&self, buf: &mut [u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error>;
    fn write(&self, buf: &[u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error>;
}