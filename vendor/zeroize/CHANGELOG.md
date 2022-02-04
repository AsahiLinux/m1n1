# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.5.2 (2022-01-31)
### Fixed
- Ambiguous method for `AssertZeroizeOnDrop` ([#725])

[#725]: https://github.com/RustCrypto/utils/pull/725

## 1.5.1 (2022-01-27) [YANKED]
### Fixed
- Double `mut` on `AssertZeroizeOnDrop` ([#719])

[#719]: https://github.com/RustCrypto/utils/pull/719

## 1.5.0 (2022-01-14) [YANKED]
### Added
- `Zeroize` impls for `PhantomData`, `PhantomPinned`, and tuples with 0-10 elements ([#660])
- `#[zeroize(bound = "T: MyTrait")]` ([#663])
- `ZeroizeOnDrop` trait and custom derive ([#699], [#700], [#703])

[#660]: https://github.com/RustCrypto/utils/pull/660
[#663]: https://github.com/RustCrypto/utils/pull/663
[#699]: https://github.com/RustCrypto/utils/pull/699
[#700]: https://github.com/RustCrypto/utils/pull/700
[#703]: https://github.com/RustCrypto/utils/pull/703

## 1.4.3 (2021-11-04)
### Added
- Implement `Zeroize` for `NonZeroX`

### Changed
- Moved to `RustCrypto/utils` repository

## 1.4.2 (2021-09-21)
### Added
- Derive `Default` on `Zeroizing`

## 1.4.1 (2021-07-20)
### Added
- Implement Zeroize for `[MaybeUninit<Z>]`

## 1.4.0 (2021-07-18)
NOTE: This release includes an MSRV bump to Rust 1.51. Please use `zeroize = "1.3.0"`
if you would like to support older Rust versions.

### Added
- Use const generics to impl `Zeroize` for `[Z; N]`; MSRV 1.51
- `Zeroizing::clone_from` now zeroizes the destination before cloning

## 1.3.0 (2021-04-19)
### Added
- impl `Zeroize` for `Box<[Z]>`
- Clear residual space within `Option

### Changed
- Ensure `Option` is `None` when zeroized
- Bump MSRV to 1.47

## 1.2.0 (2020-12-09)
### Added
- `Zeroize` support for x86(_64) SIMD registers

### Changed
- Simplify `String::zeroize`
- MSRV 1.44+

## 1.1.1 (2020-09-15)
- Add `doc_cfg`
- zeroize entire capacity of `String`
- zeroize entire capacity of `Vec`

## 1.1.0 (2019-12-02)
- Add `TryZeroize` trait
- Add `From<Z: Zeroize>` impl for `Zeroizing<Z>`
- Remove `bytes-preview` feature

## 1.0.0 (2019-10-13)
- Initial 1.0 release 🎉
- zeroize_derive: Remove legacy `no_drop` attribute support
- Rename `bytes` feature to `bytes-preview`
- Further relax `Zeroize` trait bounds for `Vec`
- Derive `Clone`, `Debug`, and `Eq` for `Zeroizing`

## 1.0.0-pre (2019-09-30)
- Loosen `Vec` trait bounds for `Zeroize`

## 0.10.1 (2019-09-03)
- (Optionally) Impl `Zeroize` for `Bytes` and `BytesMut`

## 0.10.0 (2019-08-19)
Barring unforeseen circumstances, this release aims to be the last `0.x`
release prior to a `zeroize` 1.0 release.

- Disable `zeroize_derive` Cargo feature by default
- Remove `std` feature in favor of `alloc`; MSRV 1.36+
- Deprecate `#[zeroize(no_drop)]` attribute
- Use 1.0 `proc-macro2`, `quote`, and `syn` crates

## 0.9.3 (2019-07-27)
- Improved attribute parser; fixes nightly build

## 0.9.2 (2019-06-28)
- README.md: add Gitter badges; update image links

## 0.9.1 (2019-06-04)
- Impl `Zeroize` for `Option<Z: Zeroize>`

## 0.9.0 (2019-06-04)
**NOTICE**: This release changes the default behavior of `derive(Zeroize)`
to no longer derive a `Drop` impl. If you wish to derive `Drop`, you must
now explicitly add a `#[zeroize(drop)]` attribute on the type for which you
are deriving `Zeroize`.

- Remove CPU fences
- Remove scary language about undefined behavior
- Bound blanket array impls on `Zeroize` instead of `DefaultIsZeroes`
- Require `zeroize(drop)` or `zeroize(no_drop)` attributes when deriving
  `Zeroize` .
- Support stablized 'alloc' crate

## 0.8.0 (2019-05-20)
- Impl `Drop` by default when deriving `Zeroize`

## 0.7.0 (2019-05-19)
- Use synstructure for custom derive
- Add explicit array impls for `DefaultIsZeroes`
- Remove `nightly` feature
- Add `Zeroizing<Z>` to zeroize values on drop

## 0.6.0 (2019-03-23)
- Add ZeroizeOnDrop marker trait + custom derive
- Custom derive support for `Zeroize`
- Rename `ZeroizeWithDefault` to `DefaultIsZeroes`

## 0.5.2 (2018-12-25)
- Add `debug_assert!` to ensure string interiors are zeroized

## 0.5.1 (2018-12-24)
- Avoid re-exporting the whole prelude

## 0.5.0 (2018-12-24)
This release is a rewrite which replaces FFI bindings to OS-specific APIs with
a pure Rust solution.

- Use `core::sync::atomic` fences
- Test wasm target
- Rewrite using `core::ptr::write_volatile`

## 0.4.2 (2018-10-12)
- Fix ldd scraper for older glibc versions

## 0.4.1 (2018-10-12)
- Support musl-libc

## 0.4.0 (2018-10-12)
- Impl `Zeroize` trait on concrete types

## 0.3.0 (2018-10-11)
- Replace `secure_zero_memory` with `Zeroize`

## 0.2.0 (2018-10-11)
- Add `Zeroize` trait

## 0.1.2 (2018-10-03)
- README.md: Fix intrinsic links

## 0.1.1 (2018-10-03)
- Documentation improvements

## 0.1.0 (2018-10-03)
- Initial release
