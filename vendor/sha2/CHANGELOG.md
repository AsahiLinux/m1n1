# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.9.9 (2022-01-06)
### Fixed
- Backport [#345] bug fix for the AVX2 backend ([#346])

[#345]: https://github.com/RustCrypto/hashes/pull/345
[#346]: https://github.com/RustCrypto/hashes/pull/346

## 0.9.8 (2021-09-09) [YANKED]
### Fixed
- Bug in the AVX2 backend ([#314])

[#314]: https://github.com/RustCrypto/hashes/pull/314

## 0.9.7 (2021-09-08) [YANKED]
### Added
- x86 intrinsics support for SHA-512 ([#312])

[#312]: https://github.com/RustCrypto/hashes/pull/312

## 0.9.6 (2021-08-27)
### Changed
- Bump `cpufeatures` dependency to 0.2 ([#306])

[#306]: https://github.com/RustCrypto/hashes/pull/306

## 0.9.5 (2021-05-11)
### Changed
- Use `cpufeatures` to detect intrinsics support on `aarch64` targets ([#267])

[#267]: https://github.com/RustCrypto/hashes/pull/267

## 0.9.4 (2021-05-05)
### Added
- Hardware accelerated SHA-256 for Apple M1 CPUs with `asm` feature ([#262])

### Changed
- Bump `sha2-asm` to v0.6.1 release ([#262])
- Switch from `cpuid-bool` to `cpufeatures` ([#263])

[#262]: https://github.com/RustCrypto/hashes/pull/262
[#263]: https://github.com/RustCrypto/hashes/pull/263

## 0.9.3 (2021-01-30)
### Changed
- Use the SHA-NI extension backend with enabled `asm` feature. ([#224])

[#224]: https://github.com/RustCrypto/hashes/pull/224

## 0.9.2 (2020-11-04)
### Added
- `force-soft` feature to enforce use of software implementation. ([#203])

### Changed
- `cfg-if` dependency updated to v1.0. ([#197])

[#197]: https://github.com/RustCrypto/hashes/pull/197
[#203]: https://github.com/RustCrypto/hashes/pull/203

## 0.9.1 (2020-06-24)
### Added
- x86 hardware acceleration of SHA-256 via SHA extension instrinsics. ([#167])

[#167]: https://github.com/RustCrypto/hashes/pull/167

## 0.9.0 (2020-06-09)
### Changed
- Update to `digest` v0.9 release; MSRV 1.41+ ([#155])
- Use new `*Dirty` traits from the `digest` crate ([#153])
- Bump `block-buffer` to v0.8 release ([#151])
- Rename `*result*` to `finalize` ([#148])
- Upgrade to Rust 2018 edition ([#133])

[#155]: https://github.com/RustCrypto/hashes/pull/155
[#153]: https://github.com/RustCrypto/hashes/pull/153
[#151]: https://github.com/RustCrypto/hashes/pull/151
[#148]: https://github.com/RustCrypto/hashes/pull/148
[#133]: https://github.com/RustCrypto/hashes/pull/133

## 0.8.2 (2020-05-23)
### Added
- Expose compression function under the `compress` feature flag ([#108])

### Changed
- Use `libc` crate for `aarch64` consts ([#109])
- Minor code cleanups ([#94])

[#109]: https://github.com/RustCrypto/hashes/pull/109
[#108]: https://github.com/RustCrypto/hashes/pull/108
[#94]: https://github.com/RustCrypto/hashes/pull/94

## 0.8.1 (2020-01-05)

## 0.8.0 (2018-10-02)

## 0.7.1 (2018-04-27)

## 0.6.0 (2017-06-12)

## 0.5.3 (2017-06-03)

## 0.5.2 (2017-05-08)

## 0.5.1 (2017-05-01)

## 0.5.0 (2017-04-06)

## 0.4.2 (2017-01-23)

## 0.4.1 (2017-01-20)

## 0.4.0 (2016-12-24)

## 0.3.0 (2016-11-17)

## 0.2.0 (2016-10-26)

## 0.1.2 (2016-05-06)

## 0.1.1 (2016-05-06)

## 0.1.0 (2016-05-06)
