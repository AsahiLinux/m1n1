//! Ed25519 signatures.
//!
//! Edwards Digital Signature Algorithm (EdDSA) over Curve25519 as specified in
//! RFC 8032: <https://tools.ietf.org/html/rfc8032>
//!
//! This crate doesn't contain an implementation of Ed25519, but instead
//! contains an [`ed25519::Signature`][`Signature`] type which other crates can
//! use in conjunction with the [`signature::Signer`] and
//! [`signature::Verifier`] traits defined in the [`signature`] crate.
//!
//! These traits allow crates which produce and consume Ed25519 signatures
//! to be written abstractly in such a way that different signing_key/verifier
//! providers can be plugged in, enabling support for using different
//! Ed25519 implementations, including HSMs or Cloud KMS services.
//!
//! ## Minimum Supported Rust Version
//!
//! Rust **1.56** or higher.
//!
//! Minimum supported Rust version may be changed in the future, but such
//! changes will be accompanied with a minor version bump.
//!
//! # Using Ed25519 generically over algorithm implementations/providers
//!
//! By using the `ed25519` crate, you can write code which signs and verifies
//! messages using the Ed25519 signature algorithm generically over any
//! supported Ed25519 implementation (see the next section for available
//! providers).
//!
//! This allows consumers of your code to plug in whatever implementation they
//! want to use without having to add all potential Ed25519 libraries you'd
//! like to support as optional dependencies.
//!
//! ## Example
//!
//! ```
//! use ed25519::signature::{Signer, Verifier};
//!
//! pub struct HelloSigner<S>
//! where
//!     S: Signer<ed25519::Signature>
//! {
//!     pub signing_key: S
//! }
//!
//! impl<S> HelloSigner<S>
//! where
//!     S: Signer<ed25519::Signature>
//! {
//!     pub fn sign(&self, person: &str) -> ed25519::Signature {
//!         // NOTE: use `try_sign` if you'd like to be able to handle
//!         // errors from external signing services/devices (e.g. HSM/KMS)
//!         // <https://docs.rs/signature/latest/signature/trait.Signer.html#tymethod.try_sign>
//!         self.signing_key.sign(format_message(person).as_bytes())
//!     }
//! }
//!
//! pub struct HelloVerifier<V> {
//!     pub verify_key: V
//! }
//!
//! impl<V> HelloVerifier<V>
//! where
//!     V: Verifier<ed25519::Signature>
//! {
//!     pub fn verify(
//!         &self,
//!         person: &str,
//!         signature: &ed25519::Signature
//!     ) -> Result<(), ed25519::Error> {
//!         self.verify_key.verify(format_message(person).as_bytes(), signature)
//!     }
//! }
//!
//! fn format_message(person: &str) -> String {
//!     format!("Hello, {}!", person)
//! }
//! ```
//!
//! ## Using above example with `ed25519-dalek`
//!
//! The [`ed25519-dalek`] crate natively supports the [`ed25519::Signature`][`Signature`]
//! type defined in this crate along with the [`signature::Signer`] and
//! [`signature::Verifier`] traits.
//!
//! Below is an example of how a hypothetical consumer of the code above can
//! instantiate and use the previously defined `HelloSigner` and `HelloVerifier`
//! types with [`ed25519-dalek`] as the signing/verification provider:
//!
//! ```
//! use ed25519_dalek::{Signer, Verifier, Signature};
//! #
//! # pub struct HelloSigner<S>
//! # where
//! #     S: Signer<Signature>
//! # {
//! #     pub signing_key: S
//! # }
//! #
//! # impl<S> HelloSigner<S>
//! # where
//! #     S: Signer<Signature>
//! # {
//! #     pub fn sign(&self, person: &str) -> Signature {
//! #         // NOTE: use `try_sign` if you'd like to be able to handle
//! #         // errors from external signing services/devices (e.g. HSM/KMS)
//! #         // <https://docs.rs/signature/latest/signature/trait.Signer.html#tymethod.try_sign>
//! #         self.signing_key.sign(format_message(person).as_bytes())
//! #     }
//! # }
//! #
//! # pub struct HelloVerifier<V> {
//! #     pub verify_key: V
//! # }
//! #
//! # impl<V> HelloVerifier<V>
//! # where
//! #     V: Verifier<Signature>
//! # {
//! #     pub fn verify(
//! #         &self,
//! #         person: &str,
//! #         signature: &Signature
//! #     ) -> Result<(), ed25519::Error> {
//! #         self.verify_key.verify(format_message(person).as_bytes(), signature)
//! #     }
//! # }
//! #
//! # fn format_message(person: &str) -> String {
//! #     format!("Hello, {}!", person)
//! # }
//! use rand_core::OsRng; // Requires the `std` feature of `rand_core`
//!
//! /// `HelloSigner` defined above instantiated with `ed25519-dalek` as
//! /// the signing provider.
//! pub type DalekHelloSigner = HelloSigner<ed25519_dalek::Keypair>;
//!
//! let signing_key = ed25519_dalek::Keypair::generate(&mut OsRng);
//! let signer = DalekHelloSigner { signing_key };
//! let person = "Joe"; // Message to sign
//! let signature = signer.sign(person);
//!
//! /// `HelloVerifier` defined above instantiated with `ed25519-dalek`
//! /// as the signature verification provider.
//! pub type DalekHelloVerifier = HelloVerifier<ed25519_dalek::PublicKey>;
//!
//! let verify_key: ed25519_dalek::PublicKey = signer.signing_key.public;
//! let verifier = DalekHelloVerifier { verify_key };
//! assert!(verifier.verify(person, &signature).is_ok());
//! ```
//!
//! ## Using above example with `ring-compat`
//!
//! The [`ring-compat`] crate provides wrappers for [*ring*] which implement
//! the [`signature::Signer`] and [`signature::Verifier`] traits for
//! [`ed25519::Signature`][`Signature`].
//!
//! Below is an example of how a hypothetical consumer of the code above can
//! instantiate and use the previously defined `HelloSigner` and `HelloVerifier`
//! types with [`ring-compat`] as the signing/verification provider:
//!
//! ```
//! use ring_compat::signature::{
//!     ed25519::{Signature, SigningKey, VerifyingKey},
//!     Signer, Verifier
//! };
//! #
//! # pub struct HelloSigner<S>
//! # where
//! #     S: Signer<Signature>
//! # {
//! #     pub signing_key: S
//! # }
//! #
//! # impl<S> HelloSigner<S>
//! # where
//! #     S: Signer<Signature>
//! # {
//! #     pub fn sign(&self, person: &str) -> Signature {
//! #         // NOTE: use `try_sign` if you'd like to be able to handle
//! #         // errors from external signing services/devices (e.g. HSM/KMS)
//! #         // <https://docs.rs/signature/latest/signature/trait.Signer.html#tymethod.try_sign>
//! #         self.signing_key.sign(format_message(person).as_bytes())
//! #     }
//! # }
//! #
//! # pub struct HelloVerifier<V> {
//! #     pub verify_key: V
//! # }
//! #
//! # impl<V> HelloVerifier<V>
//! # where
//! #     V: Verifier<Signature>
//! # {
//! #     pub fn verify(
//! #         &self,
//! #         person: &str,
//! #         signature: &Signature
//! #     ) -> Result<(), ed25519::Error> {
//! #         self.verify_key.verify(format_message(person).as_bytes(), signature)
//! #     }
//! # }
//! #
//! # fn format_message(person: &str) -> String {
//! #     format!("Hello, {}!", person)
//! # }
//! use rand_core::{OsRng, RngCore}; // Requires the `std` feature of `rand_core`
//!
//! /// `HelloSigner` defined above instantiated with *ring* as
//! /// the signing provider.
//! pub type RingHelloSigner = HelloSigner<SigningKey>;
//!
//! let mut ed25519_seed = [0u8; 32];
//! OsRng.fill_bytes(&mut ed25519_seed);
//!
//! let signing_key = SigningKey::from_seed(&ed25519_seed).unwrap();
//! let verify_key = signing_key.verify_key();
//!
//! let signer = RingHelloSigner { signing_key };
//! let person = "Joe"; // Message to sign
//! let signature = signer.sign(person);
//!
//! /// `HelloVerifier` defined above instantiated with *ring*
//! /// as the signature verification provider.
//! pub type RingHelloVerifier = HelloVerifier<VerifyingKey>;
//!
//! let verifier = RingHelloVerifier { verify_key };
//! assert!(verifier.verify(person, &signature).is_ok());
//! ```
//!
//! # Available Ed25519 providers
//!
//! The following libraries support the types/traits from the `ed25519` crate:
//!
//! - [`ed25519-dalek`] - mature pure Rust implementation of Ed25519
//! - [`ring-compat`] - compatibility wrapper for [*ring*]
//! - [`signatory-sodiumoxide`] - compatibility wrapper for [`sodiumoxide`]
//! - [`yubihsm`] - host-side client library for YubiHSM2 devices from Yubico
//!
//! [`ed25519-dalek`]: https://docs.rs/ed25519-dalek
//! [`ring-compat`]: https://docs.rs/ring-compat
//! [*ring*]: https://github.com/briansmith/ring
//! [`signatory-ring`]: https://docs.rs/signatory-ring/
//! [`signatory-sodiumoxide`]: https://docs.rs/signatory-sodiumoxide/
//! [`sodiumoxide`]: https://github.com/sodiumoxide/sodiumoxide
//! [`yubihsm`]: https://github.com/iqlusioninc/yubihsm.rs/blob/develop/README.md
//!
//! # Features
//!
//! The following features are presently supported:
//!
//! - `pkcs8`: support for decoding/encoding PKCS#8-formatted private keys using the
//!   [`KeypairBytes`] type.
//! - `std` *(default)*: Enable `std` support in [`signature`], which currently only affects whether
//!   [`signature::Error`] implements `std::error::Error`.
//! - `serde`: Implement `serde::Deserialize` and `serde::Serialize` for [`Signature`]. Signatures
//!   are serialized as their bytes.
//! - `serde_bytes`: Implement `serde_bytes::Deserialize` and `serde_bytes::Serialize` for
//!   [`Signature`]. This enables more compact representations for formats with an efficient byte
//!   array representation. As per the `serde_bytes` documentation, this can most easily be realised
//!   using the `#[serde(with = "serde_bytes")]` annotation, e.g.:
//!
//!   ```ignore
//!   # use ed25519::Signature;
//!   # use serde::{Deserialize, Serialize};
//!   #[derive(Deserialize, Serialize)]
//!   #[serde(transparent)]
//!   struct SignatureAsBytes(#[serde(with = "serde_bytes")] Signature);
//!   ```

#![no_std]
#![cfg_attr(docsrs, feature(doc_cfg))]
#![doc(
    html_logo_url = "https://raw.githubusercontent.com/RustCrypto/meta/master/logo_small.png",
    html_root_url = "https://docs.rs/ed25519/1.3.0"
)]
#![forbid(unsafe_code)]
#![warn(missing_docs, rust_2018_idioms, unused_qualifications)]

#[cfg(feature = "pkcs8")]
#[cfg_attr(docsrs, doc(cfg(feature = "pkcs8")))]
pub mod pkcs8;

pub use signature::{self, Error};

#[cfg(feature = "pkcs8")]
pub use crate::pkcs8::KeypairBytes;

use core::{
    convert::{TryFrom, TryInto},
    fmt, str,
};

#[cfg(feature = "serde")]
use serde::{de, ser, Deserialize, Serialize};
#[cfg(feature = "serde_bytes")]
use serde_bytes_crate as serde_bytes;

/// Length of an Ed25519 signature in bytes.
#[deprecated(since = "1.3.0", note = "use ed25519::Signature::BYTE_SIZE instead")]
pub const SIGNATURE_LENGTH: usize = Signature::BYTE_SIZE;

/// Ed25519 signature.
#[derive(Copy, Clone, Eq, PartialEq)]
pub struct Signature([u8; Signature::BYTE_SIZE]);

impl Signature {
    /// Size of an encoded Ed25519 signature in bytes.
    pub const BYTE_SIZE: usize = 64;

    /// Parse an Ed25519 signature from a byte slice.
    pub fn from_bytes(bytes: &[u8]) -> signature::Result<Self> {
        let result = bytes.try_into().map(Self).map_err(|_| Error::new())?;

        // Perform a partial reduction check on the signature's `s` scalar.
        // When properly reduced, at least the three highest bits of the scalar
        // will be unset so as to fit within the order of ~2^(252.5).
        //
        // This doesn't ensure that `s` is fully reduced (which would require a
        // full reduction check in the event that the 4th most significant bit
        // is set), however it will catch a number of invalid signatures
        // relatively inexpensively.
        if result.0[Signature::BYTE_SIZE - 1] & 0b1110_0000 != 0 {
            return Err(Error::new());
        }

        Ok(result)
    }

    /// Return the inner byte array.
    pub fn to_bytes(self) -> [u8; Self::BYTE_SIZE] {
        self.0
    }

    /// DEPRECATED: Create a new signature from a byte array.
    ///
    /// # Warning
    ///
    /// This method will panic if an invalid signature is encountered.
    ///
    /// Use [`Signature::from_bytes`] or [`Signature::try_from`] instead for
    /// a fallible conversion.
    #[deprecated(since = "1.3.0", note = "use ed25519::Signature::from_bytes instead")]
    pub fn new(bytes: [u8; Self::BYTE_SIZE]) -> Self {
        Self::from_bytes(&bytes[..]).expect("invalid signature")
    }
}

impl signature::Signature for Signature {
    fn from_bytes(bytes: &[u8]) -> signature::Result<Self> {
        Self::from_bytes(bytes)
    }
}

impl AsRef<[u8]> for Signature {
    fn as_ref(&self) -> &[u8] {
        self.0.as_ref()
    }
}

impl From<Signature> for [u8; Signature::BYTE_SIZE] {
    fn from(sig: Signature) -> [u8; Signature::BYTE_SIZE] {
        sig.0
    }
}

impl From<&Signature> for [u8; Signature::BYTE_SIZE] {
    fn from(sig: &Signature) -> [u8; Signature::BYTE_SIZE] {
        sig.0
    }
}

/// DEPRECATED: use `TryFrom<&[u8]>` instead.
///
/// # Warning
///
/// This conversion will panic if a signature is invalid.
// TODO(tarcieri): remove this in the next breaking release
impl From<[u8; Signature::BYTE_SIZE]> for Signature {
    fn from(bytes: [u8; Signature::BYTE_SIZE]) -> Signature {
        #[allow(deprecated)]
        Signature::new(bytes)
    }
}

impl TryFrom<&[u8]> for Signature {
    type Error = Error;

    fn try_from(bytes: &[u8]) -> signature::Result<Self> {
        Self::from_bytes(bytes)
    }
}

impl fmt::Debug for Signature {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "ed25519::Signature({})", self)
    }
}

impl fmt::Display for Signature {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:X}", self)
    }
}

impl fmt::LowerHex for Signature {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in &self.0 {
            write!(f, "{:02x}", byte)?;
        }
        Ok(())
    }
}

impl fmt::UpperHex for Signature {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in &self.0 {
            write!(f, "{:02X}", byte)?;
        }
        Ok(())
    }
}

/// Decode a signature from hexadecimal.
///
/// Upper and lower case hexadecimal are both accepted, however mixed case is
/// rejected.
impl str::FromStr for Signature {
    type Err = Error;

    fn from_str(hex: &str) -> signature::Result<Self> {
        if hex.as_bytes().len() != Signature::BYTE_SIZE * 2 {
            return Err(Error::new());
        }

        let mut upper_case = None;

        // Ensure all characters are valid and case is not mixed
        for &byte in hex.as_bytes() {
            match byte {
                b'0'..=b'9' => (),
                b'a'..=b'z' => match upper_case {
                    Some(true) => return Err(Error::new()),
                    Some(false) => (),
                    None => upper_case = Some(false),
                },
                b'A'..=b'Z' => match upper_case {
                    Some(true) => (),
                    Some(false) => return Err(Error::new()),
                    None => upper_case = Some(true),
                },
                _ => return Err(Error::new()),
            }
        }

        let mut result = [0u8; Self::BYTE_SIZE];
        for (digit, byte) in hex.as_bytes().chunks_exact(2).zip(result.iter_mut()) {
            *byte = str::from_utf8(digit)
                .ok()
                .and_then(|s| u8::from_str_radix(s, 16).ok())
                .ok_or_else(Error::new)?;
        }

        Self::try_from(&result[..])
    }
}

#[cfg(feature = "serde")]
impl Serialize for Signature {
    fn serialize<S: ser::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        use ser::SerializeTuple;

        let mut seq = serializer.serialize_tuple(Signature::BYTE_SIZE)?;

        for byte in &self.0[..] {
            seq.serialize_element(byte)?;
        }

        seq.end()
    }
}

// serde lacks support for deserializing arrays larger than 32-bytes
// see: <https://github.com/serde-rs/serde/issues/631>
#[cfg(feature = "serde")]
impl<'de> Deserialize<'de> for Signature {
    fn deserialize<D: de::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct ByteArrayVisitor;

        impl<'de> de::Visitor<'de> for ByteArrayVisitor {
            type Value = [u8; Signature::BYTE_SIZE];

            fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                formatter.write_str("bytestring of length 64")
            }

            fn visit_seq<A>(self, mut seq: A) -> Result<[u8; Signature::BYTE_SIZE], A::Error>
            where
                A: de::SeqAccess<'de>,
            {
                use de::Error;
                let mut arr = [0u8; Signature::BYTE_SIZE];

                for (i, byte) in arr.iter_mut().enumerate() {
                    *byte = seq
                        .next_element()?
                        .ok_or_else(|| Error::invalid_length(i, &self))?;
                }

                Ok(arr)
            }
        }

        deserializer
            .deserialize_tuple(Signature::BYTE_SIZE, ByteArrayVisitor)
            .map(|bytes| bytes.into())
    }
}

#[cfg(feature = "serde_bytes")]
impl serde_bytes::Serialize for Signature {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_bytes(&self.0)
    }
}

#[cfg(feature = "serde_bytes")]
impl<'de> serde_bytes::Deserialize<'de> for Signature {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: de::Deserializer<'de>,
    {
        struct ByteArrayVisitor;

        impl<'de> de::Visitor<'de> for ByteArrayVisitor {
            type Value = [u8; Signature::BYTE_SIZE];

            fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                formatter.write_str("bytestring of length 64")
            }

            fn visit_bytes<E>(self, bytes: &[u8]) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                use de::Error;

                bytes
                    .try_into()
                    .map_err(|_| Error::invalid_length(bytes.len(), &self))
            }
        }

        deserializer
            .deserialize_bytes(ByteArrayVisitor)
            .map(Signature::from)
    }
}
