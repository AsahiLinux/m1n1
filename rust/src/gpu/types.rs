// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! Common types for firmware structure definitions

use core::fmt;
use core::ops::{Deref, DerefMut, Index, IndexMut};

/// An unaligned u64 type.
///
/// This is useful to avoid having to pack firmware structures entirely, since that is incompatible
/// with `#[derive(Debug)]` and atomics.
#[derive(Copy, Clone, Default)]
#[repr(C, packed(1))]
pub(crate) struct U64(pub(crate) u64);

impl fmt::Debug for U64 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let v = self.0;
        f.write_fmt(format_args!("{:#x}", v))
    }
}

/// An unaligned u32 type.
///
/// This is useful to avoid having to pack firmware structures entirely, since that is incompatible
/// with `#[derive(Debug)]` and atomics.
#[derive(Copy, Clone, Default)]
#[repr(C, packed(1))]
pub(crate) struct U32(pub(crate) u32);

impl fmt::Debug for U32 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let v = self.0;
        f.write_fmt(format_args!("{:#x}", v))
    }
}

/// A convenience type for a number of padding bytes. Hidden from Debug formatting.
#[derive(Copy, Clone)]
#[repr(C, packed)]
pub(crate) struct Pad<const N: usize>([u8; N]);

impl<const N: usize> Default for Pad<N> {
    fn default() -> Self {
        Self([0; N])
    }
}

impl<const N: usize> fmt::Debug for Pad<N> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_fmt(format_args!("<pad>"))
    }
}

/// A convenience type for a fixed-sized array with Default/Zeroable impls.
#[derive(Copy, Clone)]
#[repr(C)]
pub(crate) struct Array<const N: usize, T>([T; N]);

impl<const N: usize, T> Array<N, T> {
    pub(crate) fn new(data: [T; N]) -> Self {
        Self(data)
    }
}

impl<const N: usize, T: Default> Default for Array<N, T> {
    fn default() -> Self {
        Self(core::array::from_fn(|_| Default::default()))
    }
}

impl<const N: usize, T> Index<usize> for Array<N, T> {
    type Output = T;

    fn index(&self, index: usize) -> &Self::Output {
        &self.0[index]
    }
}

impl<const N: usize, T> IndexMut<usize> for Array<N, T> {
    fn index_mut(&mut self, index: usize) -> &mut Self::Output {
        &mut self.0[index]
    }
}

impl<const N: usize, T> Deref for Array<N, T> {
    type Target = [T; N];

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

impl<const N: usize, T> DerefMut for Array<N, T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.0
    }
}

impl<const N: usize, T: Sized + fmt::Debug> fmt::Debug for Array<N, T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}
