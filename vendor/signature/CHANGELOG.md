# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.5.0 (2022-01-04)
### Changed
- Bump `digest` dependency to v0.10 ([#850])
- Bump `signature-derive` dependency to v1.0.0-pre.4 ([#866])

[#850]: https://github.com/RustCrypto/traits/pull/850
[#866]: https://github.com/RustCrypto/traits/pull/866

## 1.4.0 (2021-10-20)
### Added
- Re-export `rand_core` when the `rand-preview` feature is enabled ([#683])
- `SignerMut` trait ([#734])

### Fixed
- Show error source in `Display` impl ([#791])

[#683]: https://github.com/RustCrypto/traits/pull/683
[#734]: https://github.com/RustCrypto/traits/pull/734
[#791]: https://github.com/RustCrypto/traits/pull/791

## 1.3.2 (2021-10-21)
### Fixed
- Backport changes from [#791] to the 1.3.x series.

## 1.3.1 (2021-06-29)
### Added
- `Result` alias ([#676])

[#676]: https://github.com/RustCrypto/traits/pull/676

## 1.3.0 (2021-01-06)
### Changed
- Bump `rand_core` to v0.6 ([#457])
- Bump `signature-derive` v1.0.0-pre.3 ([#459])

[#457]: https://github.com/RustCrypto/traits/pull/457
[#459]: https://github.com/RustCrypto/traits/pull/459

## 1.2.2 (2020-07-29)
### Added
- `RandomizedDigestSigner` ([#235])

[#235]: https://github.com/RustCrypto/traits/pull/235

## 1.2.1 (2020-07-29)
### Removed
- RNG generic parameter `R` from `RandomizedSigner` ([#231])

[#231]: https://github.com/RustCrypto/traits/pull/231

## 1.2.0 (2020-07-29) [YANKED]
- Note: this release was published without the intended changes

## 1.1.0 (2020-06-09)
### Changed
- Upgrade `digest` to v0.9; MSRV 1.41+ ([#186])

[#186]: https://github.com/RustCrypto/traits/pull/186

## 1.0.1 (2020-04-19)
### Changed
- Upgrade `signature_derive` to v1.0.0-pre.2 ([#98])

[#98]: https://github.com/RustCrypto/traits/pull/98

## 1.0.0 (2020-04-18)

Initial 1.0 release! 🎉

### Changed
- Rename `DigestSignature` => `PrehashSignature` ([#96])

[#96]: https://github.com/RustCrypto/traits/pull/96

## 1.0.0-pre.5 (2020-03-16)
### Changed
- Improve `Debug` impl on `Error` ([#89])
- Rename `Signature::as_slice` -> `as_bytes` ([#87])

[#89]: https://github.com/RustCrypto/traits/pull/89
[#87]: https://github.com/RustCrypto/traits/pull/87

## 1.0.0-pre.4 (2020-03-15)
### Added
- Mark preview features as unstable in `Cargo.toml` ([#82])

### Changed
- Have `Signature::from_bytes` take a byte slice ([#84])
- Ensure `Error::new()` is mandatory ([#83])

### Removed
- `BoxError` type alias ([#81])

[#84]: https://github.com/RustCrypto/traits/pull/84
[#83]: https://github.com/RustCrypto/traits/pull/83
[#82]: https://github.com/RustCrypto/traits/pull/82
[#81]: https://github.com/RustCrypto/traits/pull/81

## 1.0.0-pre.3 (2020-03-08)
### Fixed
- docs.rs rendering ([#76])

[#76]: https://github.com/RustCrypto/traits/pull/76

## 1.0.0-pre.2 (2020-03-08)
### Added
- `RandomizedSigner` trait ([#73])
- Design documentation ([#72])

### Changed
- Error cleanups ([#74])
- Crate moved to `RustCrypto/traits` ([#71])

[#74]: https://github.com/RustCrypto/traits/pull/74
[#73]: https://github.com/RustCrypto/traits/pull/73
[#72]: https://github.com/RustCrypto/traits/pull/72
[#71]: https://github.com/RustCrypto/traits/pull/71

## 1.0.0-pre.1 (2019-10-27)
### Changed
- Use `Error::source` instead of `::cause` ([RustCrypto/signatures#37])

### Removed
- Remove `alloc` feature; MSRV 1.34+ ([RustCrypto/signatures#38])

[RustCrypto/signatures#38]: https://github.com/RustCrypto/signatures/pull/38
[RustCrypto/signatures#37]: https://github.com/RustCrypto/signatures/pull/37

## 1.0.0-pre.0 (2019-10-11)
### Changed
- Revert removal of `DigestSignature` ([RustCrypto/signatures#33])
- 1.0 stabilization proposal ([RustCrypto/signatures#32])

[RustCrypto/signatures#33]: https://github.com/RustCrypto/signatures/pull/33
[RustCrypto/signatures#32]: https://github.com/RustCrypto/signatures/pull/32

## 0.3.0 (2019-10-10)
### Changed
- Simplify alloc gating; MSRV 1.36+ ([RustCrypto/signatures#28])
- Replace `DigestSignature` trait with `#[digest(...)]` attribute ([RustCrypto/signatures#27])
- signature_derive: Upgrade to 1.x proc macro crates ([RustCrypto/signatures#26])

[RustCrypto/signatures#28]: https://github.com/RustCrypto/signatures/pull/28
[RustCrypto/signatures#27]: https://github.com/RustCrypto/signatures/pull/27
[RustCrypto/signatures#26]: https://github.com/RustCrypto/signatures/pull/27

## 0.2.0 (2019-06-06)
### Added
- `signature_derive`: Custom derive support for `Signer`/`Verifier` ([RustCrypto/signatures#18])

### Changed
- Have `DigestSigner`/`DigestVerifier` take `Digest` instance ([RustCrypto/signatures#17])

[RustCrypto/signatures#18]: https://github.com/RustCrypto/signatures/pull/18
[RustCrypto/signatures#17]: https://github.com/RustCrypto/signatures/pull/17

## 0.1.0 (2019-05-25)

- Initial release
