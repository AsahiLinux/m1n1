#![no_std]
#![cfg_attr(docsrs, feature(doc_cfg))]
#![doc(
    html_logo_url = "https://raw.githubusercontent.com/RustCrypto/media/6ee8e381/logo.svg",
    html_favicon_url = "https://raw.githubusercontent.com/RustCrypto/media/6ee8e381/logo.svg",
    html_root_url = "https://docs.rs/zeroize/1.5.2"
)]
#![warn(missing_docs, rust_2018_idioms, unused_qualifications)]

//! Securely zero memory with a simple trait ([`Zeroize`]) built on stable Rust
//! primitives which guarantee the operation will not be "optimized away".
//!
//! ## About
//!
//! [Zeroing memory securely is hard] - compilers optimize for performance, and
//! in doing so they love to "optimize away" unnecessary zeroing calls. There are
//! many documented "tricks" to attempt to avoid these optimizations and ensure
//! that a zeroing routine is performed reliably.
//!
//! This crate isn't about tricks: it uses [`core::ptr::write_volatile`]
//! and [`core::sync::atomic`] memory fences to provide easy-to-use, portable
//! zeroing behavior which works on all of Rust's core number types and slices
//! thereof, implemented in pure Rust with no usage of FFI or assembly.
//!
//! - No insecure fallbacks!
//! - No dependencies!
//! - No FFI or inline assembly! **WASM friendly** (and tested)!
//! - `#![no_std]` i.e. **embedded-friendly**!
//! - No functionality besides securely zeroing memory!
//! - (Optional) Custom derive support for zeroing complex structures
//!
//! ## Minimum Supported Rust Version
//!
//! Requires Rust **1.51** or newer.
//!
//! In the future, we reserve the right to change MSRV (i.e. MSRV is out-of-scope
//! for this crate's SemVer guarantees), however when we do it will be accompanied
//! by a minor version bump.
//!
//! ## Usage
//!
//! ```
//! use zeroize::Zeroize;
//!
//! fn main() {
//!     // Protip: don't embed secrets in your source code.
//!     // This is just an example.
//!     let mut secret = b"Air shield password: 1,2,3,4,5".to_vec();
//!     // [ ... ] open the air shield here
//!
//!     // Now that we're done using the secret, zero it out.
//!     secret.zeroize();
//! }
//! ```
//!
//! The [`Zeroize`] trait is impl'd on all of Rust's core scalar types including
//! integers, floats, `bool`, and `char`.
//!
//! Additionally, it's implemented on slices and `IterMut`s of the above types.
//!
//! When the `alloc` feature is enabled (which it is by default), it's also
//! impl'd for `Vec<T>` for the above types as well as `String`, where it provides
//! [`Vec::clear`] / [`String::clear`]-like behavior (truncating to zero-length)
//! but ensures the backing memory is securely zeroed with some caveats.
//! (NOTE: see "Stack/Heap Zeroing Notes" for important `Vec`/`String` details)
//!
//! The [`DefaultIsZeroes`] marker trait can be impl'd on types which also
//! impl [`Default`], which implements [`Zeroize`] by overwriting a value with
//! the default value.
//!
//! ## Custom Derive Support
//!
//! This crate has custom derive support for the `Zeroize` trait,
//! gated under the `zeroize` crate's `zeroize_derive` Cargo feature,
//! which automatically calls `zeroize()` on all members of a struct
//! or tuple struct.
//!
//! Attributes supported for `Zeroize`:
//!
//! On the item level:
//! - `#[zeroize(drop)]`: *deprecated* use `ZeroizeOnDrop` instead
//! - `#[zeroize(bound = "T: MyTrait")]`: this replaces any trait bounds
//!   inferred by zeroize
//!
//! On the field level:
//! - `#[zeroize(skip)]`: skips this field or variant when calling `zeroize()`
//!
//! Attributes supported for `ZeroizeOnDrop`:
//!
//! On the field level:
//! - `#[zeroize(skip)]`: skips this field or variant when calling `zeroize()`
//!
//! Example which derives `Drop`:
//!
//! ```
//! # #[cfg(feature = "zeroize_derive")]
//! # {
//! use zeroize::{Zeroize, ZeroizeOnDrop};
//!
//! // This struct will be zeroized on drop
//! #[derive(Zeroize, ZeroizeOnDrop)]
//! struct MyStruct([u8; 32]);
//! # }
//! ```
//!
//! Example which does not derive `Drop` (useful for e.g. `Copy` types)
//!
//! ```
//! #[cfg(feature = "zeroize_derive")]
//! # {
//! use zeroize::Zeroize;
//!
//! // This struct will *NOT* be zeroized on drop
//! #[derive(Copy, Clone, Zeroize)]
//! struct MyStruct([u8; 32]);
//! # }
//! ```
//!
//! Example which only derives `Drop`:
//!
//! ```
//! # #[cfg(feature = "zeroize_derive")]
//! # {
//! use zeroize::ZeroizeOnDrop;
//!
//! // This struct will be zeroized on drop
//! #[derive(ZeroizeOnDrop)]
//! struct MyStruct([u8; 32]);
//! # }
//! ```
//!
//! ## `Zeroizing<Z>`: wrapper for zeroizing arbitrary values on drop
//!
//! `Zeroizing<Z: Zeroize>` is a generic wrapper type that impls `Deref`
//! and `DerefMut`, allowing access to an inner value of type `Z`, and also
//! impls a `Drop` handler which calls `zeroize()` on its contents:
//!
//! ```
//! use zeroize::Zeroizing;
//!
//! fn main() {
//!     let mut secret = Zeroizing::new([0u8; 5]);
//!
//!     // Set the air shield password
//!     // Protip (again): don't embed secrets in your source code.
//!     secret.copy_from_slice(&[1, 2, 3, 4, 5]);
//!     assert_eq!(secret.as_ref(), &[1, 2, 3, 4, 5]);
//!
//!     // The contents of `secret` will be automatically zeroized on drop
//! }
//! ```
//!
//! ## What guarantees does this crate provide?
//!
//! This crate guarantees the following:
//!
//! 1. The zeroing operation can't be "optimized away" by the compiler.
//! 2. All subsequent reads to memory will see "zeroized" values.
//!
//! LLVM's volatile semantics ensure #1 is true.
//!
//! Additionally, thanks to work by the [Unsafe Code Guidelines Working Group],
//! we can now fairly confidently say #2 is true as well. Previously there were
//! worries that the approach used by this crate (mixing volatile and
//! non-volatile accesses) was undefined behavior due to language contained
//! in the documentation for `write_volatile`, however after some discussion
//! [these remarks have been removed] and the specific usage pattern in this
//! crate is considered to be well-defined.
//!
//! Additionally this crate leverages [`core::sync::atomic::compiler_fence`]
//! with the strictest ordering
//! ([`Ordering::SeqCst`]) as a
//! precaution to help ensure reads are not reordered before memory has been
//! zeroed.
//!
//! All of that said, there is still potential for microarchitectural attacks
//! (ala Spectre/Meltdown) to leak "zeroized" secrets through covert channels.
//! This crate makes no guarantees that zeroized values cannot be leaked
//! through such channels, as they represent flaws in the underlying hardware.
//!
//! ## Stack/Heap Zeroing Notes
//!
//! This crate can be used to zero values from either the stack or the heap.
//!
//! However, be aware several operations in Rust can unintentionally leave
//! copies of data in memory. This includes but is not limited to:
//!
//! - Moves and [`Copy`]
//! - Heap reallocation when using [`Vec`] and [`String`]
//! - Borrowers of a reference making copies of the data
//!
//! [`Pin`][`core::pin::Pin`] can be leveraged in conjunction with this crate
//! to ensure data kept on the stack isn't moved.
//!
//! The `Zeroize` impls for `Vec` and `String` zeroize the entire capacity of
//! their backing buffer, but cannot guarantee copies of the data were not
//! previously made by buffer reallocation. It's therefore important when
//! attempting to zeroize such buffers to initialize them to the correct
//! capacity, and take care to prevent subsequent reallocation.
//!
//! The `secrecy` crate provides higher-level abstractions for eliminating
//! usage patterns which can cause reallocations:
//!
//! <https://crates.io/crates/secrecy>
//!
//! ## What about: clearing registers, mlock, mprotect, etc?
//!
//! This crate is focused on providing simple, unobtrusive support for reliably
//! zeroing memory using the best approach possible on stable Rust.
//!
//! Clearing registers is a difficult problem that can't easily be solved by
//! something like a crate, and requires either inline ASM or rustc support.
//! See <https://github.com/rust-lang/rust/issues/17046> for background on
//! this particular problem.
//!
//! Other memory protection mechanisms are interesting and useful, but often
//! overkill (e.g. defending against RAM scraping or attackers with swap access).
//! In as much as there may be merit to these approaches, there are also many
//! other crates that already implement more sophisticated memory protections.
//! Such protections are explicitly out-of-scope for this crate.
//!
//! Zeroing memory is [good cryptographic hygiene] and this crate seeks to promote
//! it in the most unobtrusive manner possible. This includes omitting complex
//! `unsafe` memory protection systems and just trying to make the best memory
//! zeroing crate available.
//!
//! [Zeroing memory securely is hard]: http://www.daemonology.net/blog/2014-09-04-how-to-zero-a-buffer.html
//! [Unsafe Code Guidelines Working Group]: https://github.com/rust-lang/unsafe-code-guidelines
//! [these remarks have been removed]: https://github.com/rust-lang/rust/pull/60972
//! [good cryptographic hygiene]: https://github.com/veorq/cryptocoding#clean-memory-of-secret-data
//! [`Ordering::SeqCst`]: core::sync::atomic::Ordering::SeqCst

#[cfg(feature = "alloc")]
#[cfg_attr(test, macro_use)]
extern crate alloc;

#[cfg(feature = "zeroize_derive")]
#[cfg_attr(docsrs, doc(cfg(feature = "zeroize_derive")))]
pub use zeroize_derive::{Zeroize, ZeroizeOnDrop};

#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
mod x86;

use core::marker::{PhantomData, PhantomPinned};
use core::mem::{self, MaybeUninit};
use core::num::{
    NonZeroI128, NonZeroI16, NonZeroI32, NonZeroI64, NonZeroI8, NonZeroIsize, NonZeroU128,
    NonZeroU16, NonZeroU32, NonZeroU64, NonZeroU8, NonZeroUsize,
};
use core::{ops, ptr, slice::IterMut, sync::atomic};

#[cfg(feature = "alloc")]
use alloc::{boxed::Box, string::String, vec::Vec};

/// Trait for securely erasing types from memory
pub trait Zeroize {
    /// Zero out this object from memory using Rust intrinsics which ensure the
    /// zeroization operation is not "optimized away" by the compiler.
    fn zeroize(&mut self);
}

/// Marker trait signifying that this type will [`zeroize`](Zeroize::zeroize) itself on [`Drop`].
pub trait ZeroizeOnDrop {}

#[doc(hidden)]
pub mod __internal {
    use super::*;

    /// Auto-deref workaround for deriving `ZeroizeOnDrop`.
    pub trait AssertZeroizeOnDrop {
        fn zeroize_or_on_drop(self);
    }

    impl<T: ZeroizeOnDrop> AssertZeroizeOnDrop for &&mut T {
        fn zeroize_or_on_drop(self) {}
    }

    /// Auto-deref workaround for deriving `ZeroizeOnDrop`.
    pub trait AssertZeroize {
        fn zeroize_or_on_drop(&mut self);
    }

    impl<T: Zeroize> AssertZeroize for T {
        fn zeroize_or_on_drop(&mut self) {
            self.zeroize()
        }
    }
}

/// Marker trait for types whose `Default` is the desired zeroization result
pub trait DefaultIsZeroes: Copy + Default + Sized {}

impl<Z> Zeroize for Z
where
    Z: DefaultIsZeroes,
{
    fn zeroize(&mut self) {
        volatile_write(self, Z::default());
        atomic_fence();
    }
}

macro_rules! impl_zeroize_with_default {
    ($($type:ty),+) => {
        $(impl DefaultIsZeroes for $type {})+
    };
}

impl_zeroize_with_default!(i8, i16, i32, i64, i128, isize);
impl_zeroize_with_default!(u8, u16, u32, u64, u128, usize);
impl_zeroize_with_default!(f32, f64, char, bool);

macro_rules! impl_zeroize_for_non_zero {
    ($($type:ty),+) => {
        $(impl Zeroize for $type
        {
            fn zeroize(&mut self) {
                volatile_write(self, unsafe { <$type>::new_unchecked(1) });
                atomic_fence();
            }
        })+
    };
}

impl_zeroize_for_non_zero!(
    NonZeroI8,
    NonZeroI16,
    NonZeroI32,
    NonZeroI64,
    NonZeroI128,
    NonZeroIsize
);
impl_zeroize_for_non_zero!(
    NonZeroU8,
    NonZeroU16,
    NonZeroU32,
    NonZeroU64,
    NonZeroU128,
    NonZeroUsize
);

/// Implement `Zeroize` on arrays of types that impl `Zeroize`
impl<Z, const N: usize> Zeroize for [Z; N]
where
    Z: Zeroize,
{
    fn zeroize(&mut self) {
        self.iter_mut().zeroize();
    }
}
/// Implement `ZeroizeOnDrop` on arrays of types that impl `ZeroizeOnDrop`
impl<Z, const N: usize> ZeroizeOnDrop for [Z; N] where Z: ZeroizeOnDrop {}

impl<'a, Z> Zeroize for IterMut<'a, Z>
where
    Z: Zeroize,
{
    fn zeroize(&mut self) {
        for elem in self {
            elem.zeroize();
        }
    }
}

impl<Z> Zeroize for Option<Z>
where
    Z: Zeroize,
{
    fn zeroize(&mut self) {
        if let Some(value) = self {
            value.zeroize();

            // Ensures self is None and that the value was dropped. Without the take, the drop
            // of the (zeroized) value isn't called, which might lead to a leak or other
            // unexpected behavior. For example, if this were Option<Vec<T>>, the above call to
            // zeroize would not free the allocated memory, but the the `take` call will.
            self.take();
        }

        // Ensure that if the `Option` were previously `Some` but a value was copied/moved out
        // that the remaining space in the `Option` is zeroized.
        //
        // Safety:
        //
        // The memory pointed to by `self` is valid for `mem::size_of::<Self>()` bytes.
        // It is also properly aligned, because `u8` has an alignment of `1`.
        unsafe {
            volatile_set(self as *mut _ as *mut u8, 0, mem::size_of::<Self>());
        }

        // Ensures self is overwritten with the default bit pattern. volatile_write can't be
        // used because Option<Z> is not copy.
        //
        // Safety:
        //
        // self is safe to replace with the default, which the take() call above should have
        // already done semantically. Any value which needed to be dropped will have been
        // done so by take().
        unsafe { ptr::write_volatile(self, Option::default()) }

        atomic_fence();
    }
}

impl<Z> ZeroizeOnDrop for Option<Z> where Z: ZeroizeOnDrop {}

/// Impl `Zeroize` on slices of MaybeUninit types
/// This impl can eventually be optimized using an memset intrinsic,
/// such as `core::intrinsics::volatile_set_memory`.
/// This fills the slice with zeros
/// Note that this ignore invariants that Z might have, because MaybeUninit removes all invariants.
impl<Z> Zeroize for [MaybeUninit<Z>] {
    fn zeroize(&mut self) {
        let ptr = self.as_mut_ptr() as *mut MaybeUninit<u8>;
        let size = self.len().checked_mul(mem::size_of::<Z>()).unwrap();
        assert!(size <= core::isize::MAX as usize);
        // Safety:
        //
        // This is safe, because every valid pointer is well aligned for u8
        // and it is backed by a single allocated object for at least `self.len() * size_pf::<Z>()` bytes.
        // and 0 is a valid value for `MaybeUninit<Z>`
        // The memory of the slice should not wrap around the address space.
        unsafe { volatile_set(ptr, MaybeUninit::new(0), size) }
        atomic_fence();
    }
}

/// Impl `Zeroize` on slices of types that can be zeroized with `Default`.
///
/// This impl can eventually be optimized using an memset intrinsic,
/// such as `core::intrinsics::volatile_set_memory`. For that reason the blanket
/// impl on slices is bounded by `DefaultIsZeroes`.
///
/// To zeroize a mut slice of `Z: Zeroize` which does not impl
/// `DefaultIsZeroes`, call `iter_mut().zeroize()`.
impl<Z> Zeroize for [Z]
where
    Z: DefaultIsZeroes,
{
    fn zeroize(&mut self) {
        assert!(self.len() <= core::isize::MAX as usize);
        // Safety:
        //
        // This is safe, because the slice is well aligned and is backed by a single allocated
        // object for at least `self.len()` elements of type `Z`.
        // `self.len()` is also not larger than an `isize`, because of the assertion above.
        // The memory of the slice should not wrap around the address space.
        unsafe { volatile_set(self.as_mut_ptr(), Z::default(), self.len()) };
        atomic_fence();
    }
}

#[cfg(feature = "alloc")]
#[cfg_attr(docsrs, doc(cfg(feature = "alloc")))]
impl<Z> Zeroize for Vec<Z>
where
    Z: Zeroize,
{
    /// "Best effort" zeroization for `Vec`.
    ///
    /// Ensures the entire capacity of the `Vec` is zeroed. Cannot ensure that
    /// previous reallocations did not leave values on the heap.
    fn zeroize(&mut self) {
        use core::slice;
        // Zeroize all the initialized elements.
        self.iter_mut().zeroize();

        // Set the Vec's length to 0 and drop all the elements.
        self.clear();
        // Zero the full capacity of `Vec`.
        // Safety:
        //
        // This is safe, because `Vec` never allocates more than `isize::MAX` bytes.
        // This exact use case is even mentioned in the documentation of `pointer::add`.
        // This is safe because MaybeUninit ignores all invariants,
        // so we can create a slice of MaybeUninit<Z> using the full capacity of the Vec
        let uninit_slice = unsafe {
            slice::from_raw_parts_mut(self.as_mut_ptr() as *mut MaybeUninit<Z>, self.capacity())
        };
        uninit_slice.zeroize();
    }
}

#[cfg(feature = "alloc")]
#[cfg_attr(docsrs, doc(cfg(feature = "alloc")))]
impl<Z> ZeroizeOnDrop for Vec<Z> where Z: ZeroizeOnDrop {}

#[cfg(feature = "alloc")]
#[cfg_attr(docsrs, doc(cfg(feature = "alloc")))]
impl<Z> Zeroize for Box<[Z]>
where
    Z: Zeroize,
{
    /// Unlike `Vec`, `Box<[Z]>` cannot reallocate, so we can be sure that we are not leaving
    /// values on the heap.
    fn zeroize(&mut self) {
        self.iter_mut().zeroize();
    }
}

#[cfg(feature = "alloc")]
#[cfg_attr(docsrs, doc(cfg(feature = "alloc")))]
impl<Z> ZeroizeOnDrop for Box<[Z]> where Z: ZeroizeOnDrop {}

#[cfg(feature = "alloc")]
#[cfg_attr(docsrs, doc(cfg(feature = "alloc")))]
impl Zeroize for String {
    fn zeroize(&mut self) {
        unsafe { self.as_mut_vec() }.zeroize();
    }
}

/// Fallible trait for representing cases where zeroization may or may not be
/// possible.
///
/// This is primarily useful for scenarios like reference counted data, where
/// zeroization is only possible when the last reference is dropped.
pub trait TryZeroize {
    /// Try to zero out this object from memory using Rust intrinsics which
    /// ensure the zeroization operation is not "optimized away" by the
    /// compiler.
    #[must_use]
    fn try_zeroize(&mut self) -> bool;
}

/// `Zeroizing` is a a wrapper for any `Z: Zeroize` type which implements a
/// `Drop` handler which zeroizes dropped values.
#[derive(Debug, Default, Eq, PartialEq)]
pub struct Zeroizing<Z: Zeroize>(Z);

impl<Z> Zeroizing<Z>
where
    Z: Zeroize,
{
    /// Move value inside a `Zeroizing` wrapper which ensures it will be
    /// zeroized when it's dropped.
    pub fn new(value: Z) -> Self {
        value.into()
    }
}

impl<Z: Zeroize + Clone> Clone for Zeroizing<Z> {
    fn clone(&self) -> Self {
        Self(self.0.clone())
    }

    fn clone_from(&mut self, source: &Self) {
        self.0.zeroize();
        self.0.clone_from(&source.0);
    }
}

impl<Z> From<Z> for Zeroizing<Z>
where
    Z: Zeroize,
{
    fn from(value: Z) -> Zeroizing<Z> {
        Zeroizing(value)
    }
}

impl<Z> ops::Deref for Zeroizing<Z>
where
    Z: Zeroize,
{
    type Target = Z;

    fn deref(&self) -> &Z {
        &self.0
    }
}

impl<Z> ops::DerefMut for Zeroizing<Z>
where
    Z: Zeroize,
{
    fn deref_mut(&mut self) -> &mut Z {
        &mut self.0
    }
}

impl<Z> Zeroize for Zeroizing<Z>
where
    Z: Zeroize,
{
    fn zeroize(&mut self) {
        self.0.zeroize();
    }
}

impl<Z> ZeroizeOnDrop for Zeroizing<Z> where Z: Zeroize {}

impl<Z> Drop for Zeroizing<Z>
where
    Z: Zeroize,
{
    fn drop(&mut self) {
        self.0.zeroize()
    }
}

/// Use fences to prevent accesses from being reordered before this
/// point, which should hopefully help ensure that all accessors
/// see zeroes after this point.
#[inline]
fn atomic_fence() {
    atomic::compiler_fence(atomic::Ordering::SeqCst);
}

/// Perform a volatile write to the destination
#[inline]
fn volatile_write<T: Copy + Sized>(dst: &mut T, src: T) {
    unsafe { ptr::write_volatile(dst, src) }
}

/// Perform a volatile `memset` operation which fills a slice with a value
///
/// Safety:
/// The memory pointed to by `dst` must be a single allocated object that is valid for `count`
/// contiguous elements of `T`.
/// `count` must not be larger than an `isize`.
/// `dst` being offset by `mem::size_of::<T> * count` bytes must not wrap around the address space.
/// Also `dst` must be properly aligned.
#[inline]
unsafe fn volatile_set<T: Copy + Sized>(dst: *mut T, src: T, count: usize) {
    // TODO(tarcieri): use `volatile_set_memory` when stabilized
    for i in 0..count {
        // Safety:
        //
        // This is safe because there is room for at least `count` objects of type `T` in the
        // allocation pointed to by `dst`, because `count <= isize::MAX` and because
        // `dst.add(count)` must not wrap around the address space.
        let ptr = dst.add(i);
        // Safety:
        //
        // This is safe, because the pointer is valid and because `dst` is well aligned for `T` and
        // `ptr` is an offset of `dst` by a multiple of `mem::size_of::<T>()` bytes.
        ptr::write_volatile(ptr, src);
    }
}

/// `PhantomData` is always zero sized so provide a Zeroize implementation.
impl<Z> Zeroize for PhantomData<Z> {
    fn zeroize(&mut self) {}
}
/// `PhantomData` is always zero sized so provide a ZeroizeOnDrop implementation.
impl<Z> ZeroizeOnDrop for PhantomData<Z> {}
/// `PhantomPinned` is zero sized so provide a Zeroize implementation.
impl Zeroize for PhantomPinned {
    fn zeroize(&mut self) {}
}
/// `PhantomPinned` is zero sized so provide a ZeroizeOnDrop implementation.
impl ZeroizeOnDrop for PhantomPinned {}
/// `()` is zero sized so provide a Zeroize implementation.
impl Zeroize for () {
    fn zeroize(&mut self) {}
}
/// `()` is zero sized so provide a ZeroizeOnDrop implementation.
impl ZeroizeOnDrop for () {}

/// Generic implementation of Zeroize for tuples up to 10 parameters.
impl<A: Zeroize> Zeroize for (A,) {
    fn zeroize(&mut self) {
        self.0.zeroize();
    }
}
/// Generic implementation of ZeroizeOnDrop for tuples up to 10 parameters.
impl<A: ZeroizeOnDrop> ZeroizeOnDrop for (A,) {}
macro_rules! impl_zeroize_tuple {
    ( $( $type_name:ident )+ ) => {
        impl<$($type_name: Zeroize),+> Zeroize for ($($type_name),+) {
            fn zeroize(&mut self) {
                #[allow(non_snake_case)]
                let ($($type_name),+) = self;
                $($type_name.zeroize());+
            }
        }

        impl<$($type_name: ZeroizeOnDrop),+> ZeroizeOnDrop for ($($type_name),+) { }
    }
}
// Generic implementations for tuples up to 10 parameters.
impl_zeroize_tuple! { A B }
impl_zeroize_tuple! { A B C }
impl_zeroize_tuple! { A B C D }
impl_zeroize_tuple! { A B C D E }
impl_zeroize_tuple! { A B C D E F }
impl_zeroize_tuple! { A B C D E F G }
impl_zeroize_tuple! { A B C D E F G H }
impl_zeroize_tuple! { A B C D E F G H I }
impl_zeroize_tuple! { A B C D E F G H I L }

#[cfg(test)]
mod tests {
    use super::*;

    use core::mem::size_of;

    #[cfg(feature = "alloc")]
    use alloc::boxed::Box;

    #[derive(Clone, Debug, PartialEq)]
    struct ZeroizedOnDrop(u64);

    impl Drop for ZeroizedOnDrop {
        fn drop(&mut self) {
            self.0.zeroize();
        }
    }

    #[test]
    fn non_zero() {
        macro_rules! non_zero_test {
            ($($type:ty),+) => {
                $(let mut value = <$type>::new(42).unwrap();
                value.zeroize();
                assert_eq!(value.get(), 1);)+
            };
        }

        non_zero_test!(
            NonZeroI8,
            NonZeroI16,
            NonZeroI32,
            NonZeroI64,
            NonZeroI128,
            NonZeroIsize
        );
        non_zero_test!(
            NonZeroU8,
            NonZeroU16,
            NonZeroU32,
            NonZeroU64,
            NonZeroU128,
            NonZeroUsize
        );
    }

    #[test]
    fn zeroize_byte_arrays() {
        let mut arr = [42u8; 137];
        arr.zeroize();
        assert_eq!(arr.as_ref(), [0u8; 137].as_ref());
    }

    #[test]
    fn zeroize_on_drop_byte_arrays() {
        let mut arr = [ZeroizedOnDrop(42); 1];
        unsafe { core::ptr::drop_in_place(&mut arr) };
        assert_eq!(arr.as_ref(), [ZeroizedOnDrop(0); 1].as_ref());
    }

    #[test]
    fn zeroize_maybeuninit_byte_arrays() {
        let mut arr = [MaybeUninit::new(42u64); 64];
        arr.zeroize();
        let arr_init: [u64; 64] = unsafe { core::mem::transmute(arr) };
        assert_eq!(arr_init, [0u64; 64]);
    }

    #[test]
    fn zeroize_check_zerosize_types() {
        // Since we assume these types have zero size, we test this holds for
        // the current version of Rust.
        assert_eq!(size_of::<()>(), 0);
        assert_eq!(size_of::<PhantomPinned>(), 0);
        assert_eq!(size_of::<PhantomData<usize>>(), 0);
    }

    #[test]
    fn zeroize_check_tuple() {
        let mut tup1 = (42u8,);
        tup1.zeroize();
        assert_eq!(tup1, (0u8,));

        let mut tup2 = (42u8, 42u8);
        tup2.zeroize();
        assert_eq!(tup2, (0u8, 0u8));
    }

    #[test]
    fn zeroize_on_drop_check_tuple() {
        let mut tup1 = (ZeroizedOnDrop(42),);
        unsafe { core::ptr::drop_in_place(&mut tup1) };
        assert_eq!(tup1, (ZeroizedOnDrop(0),));

        let mut tup2 = (ZeroizedOnDrop(42), ZeroizedOnDrop(42));
        unsafe { core::ptr::drop_in_place(&mut tup2) };
        assert_eq!(tup2, (ZeroizedOnDrop(0), ZeroizedOnDrop(0)));
    }

    #[cfg(feature = "alloc")]
    #[test]
    fn zeroize_vec() {
        let mut vec = vec![42; 3];
        vec.zeroize();
        assert!(vec.is_empty());
    }

    #[cfg(feature = "alloc")]
    #[test]
    fn zeroize_vec_entire_capacity() {
        #[derive(Clone)]
        struct PanicOnNonZeroDrop(u64);

        impl Zeroize for PanicOnNonZeroDrop {
            fn zeroize(&mut self) {
                self.0 = 0;
            }
        }

        impl Drop for PanicOnNonZeroDrop {
            fn drop(&mut self) {
                if self.0 != 0 {
                    panic!("dropped non-zeroized data");
                }
            }
        }

        // Ensure that the entire capacity of the vec is zeroized and that no unitinialized data
        // is ever interpreted as initialized
        let mut vec = vec![PanicOnNonZeroDrop(42); 2];

        unsafe {
            vec.set_len(1);
        }

        vec.zeroize();

        unsafe {
            vec.set_len(2);
        }

        drop(vec);
    }

    #[cfg(feature = "alloc")]
    #[test]
    fn zeroize_string() {
        let mut string = String::from("Hello, world!");
        string.zeroize();
        assert!(string.is_empty());
    }

    #[cfg(feature = "alloc")]
    #[test]
    fn zeroize_string_entire_capacity() {
        let mut string = String::from("Hello, world!");
        string.truncate(5);

        string.zeroize();

        // convert the string to a vec to easily access the unused capacity
        let mut as_vec = string.into_bytes();
        unsafe { as_vec.set_len(as_vec.capacity()) };

        assert!(as_vec.iter().all(|byte| *byte == 0));
    }

    #[cfg(feature = "alloc")]
    #[test]
    fn zeroize_box() {
        let mut boxed_arr = Box::new([42u8; 3]);
        boxed_arr.zeroize();
        assert_eq!(boxed_arr.as_ref(), &[0u8; 3]);
    }
}
