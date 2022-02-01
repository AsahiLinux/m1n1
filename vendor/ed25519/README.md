# RustCrypto: Ed25519

[![crate][crate-image]][crate-link]
[![Docs][docs-image]][docs-link]
[![Build Status][build-image]][build-link]
![Apache2/MIT licensed][license-image]
![Rust Version][rustc-image]
[![Project Chat][chat-image]][chat-link]

[Edwards Digital Signature Algorithm (EdDSA)][1] over Curve25519 as specified
in [RFC 8032][2].

This crate doesn't contain an implementation of Ed25519, but instead
contains an [`ed25519::Signature`][3] type which other crates can use in
conjunction with the [`signature::Signer`][4] and [`signature::Verifier`][5]
traits.

These traits allow crates which produce and consume Ed25519 signatures
to be written abstractly in such a way that different signer/verifier
providers can be plugged in, enabling support for using different
Ed25519 implementations, including HSMs or Cloud KMS services.

[Documentation][docs-link]

## Minimum Supported Rust Version

This crate requires **Rust 1.56** at a minimum.

We may change the MSRV in the future, but it will be accompanied by a minor
version bump.

## License

All crates licensed under either of

 * [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0)
 * [MIT license](http://opensource.org/licenses/MIT)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.

[//]: # (badges)

[crate-image]: https://img.shields.io/crates/v/ed25519.svg
[crate-link]: https://crates.io/crates/ed25519
[docs-image]: https://docs.rs/ed25519/badge.svg
[docs-link]: https://docs.rs/ed25519/
[license-image]: https://img.shields.io/badge/license-Apache2.0/MIT-blue.svg
[rustc-image]: https://img.shields.io/badge/rustc-1.56+-blue.svg
[chat-image]: https://img.shields.io/badge/zulip-join_chat-blue.svg
[chat-link]: https://rustcrypto.zulipchat.com/#narrow/stream/260048-signatures
[build-image]: https://github.com/RustCrypto/signatures/workflows/ed25519/badge.svg?branch=master&event=push
[build-link]: https://github.com/RustCrypto/signatures/actions?query=workflow%3Aed25519

[//]: # (general links)

[1]: https://en.wikipedia.org/wiki/EdDSA
[2]: https://tools.ietf.org/html/rfc8032
[3]: https://docs.rs/ed25519/latest/ed25519/struct.Signature.html
[4]: https://docs.rs/signature/latest/signature/trait.Signer.html
[5]: https://docs.rs/signature/latest/signature/trait.Verifier.html
