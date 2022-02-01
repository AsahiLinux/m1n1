//! PKCS#8 private key support.
//!
//! Implements Ed25519 PKCS#8 private keys as described in RFC8410 Section 7:
//! <https://datatracker.ietf.org/doc/html/rfc8410#section-7>

pub use pkcs8::DecodePrivateKey;

#[cfg(feature = "alloc")]
pub use pkcs8::EncodePrivateKey;

use core::{
    convert::{TryFrom, TryInto},
    fmt,
};
use pkcs8::ObjectIdentifier;

#[cfg(feature = "zeroize")]
use zeroize::Zeroize;

/// Algorithm [`ObjectIdentifier`] for the Ed25519 digital signature algorithm
/// (`id-Ed25519`).
///
/// <http://oid-info.com/get/1.3.101.112>
pub const ALGORITHM_OID: ObjectIdentifier = ObjectIdentifier::new("1.3.101.112");

/// Ed25519 keypair serialized as bytes.
///
/// This type is primarily useful for decoding/encoding PKCS#8 private key
/// files (either DER or PEM) encoded using the following traits:
///
/// - [`DecodePrivateKey`]: decode DER or PEM encoded PKCS#8 private key.
/// - [`EncodePrivateKey`]: encode DER or PEM encoded PKCS#8 private key.
pub struct KeypairBytes {
    /// Ed25519 secret key.
    ///
    /// Little endian serialization of an element of the Curve25519 scalar
    /// field, prior to "clamping" (i.e. setting/clearing bits to ensure the
    /// scalar is actually a valid field element)
    pub secret_key: [u8; Self::BYTE_SIZE / 2],

    /// Ed25519 public key (if available).
    ///
    /// Compressed Edwards-y encoded curve point.
    pub public_key: Option<[u8; Self::BYTE_SIZE / 2]>,
}

impl KeypairBytes {
    /// Size of an Ed25519 keypair when serialized as bytes.
    const BYTE_SIZE: usize = 64;

    /// Serialize as a 64-byte keypair.
    ///
    /// # Returns
    ///
    /// - `Some(bytes)` if the `public_key` is present.
    /// - `None` if the `public_key` is absent (i.e. `None`).
    pub fn to_bytes(&self) -> Option<[u8; Self::BYTE_SIZE]> {
        if let Some(public_key) = &self.public_key {
            let mut result = [0u8; Self::BYTE_SIZE];
            let (sk, pk) = result.split_at_mut(Self::BYTE_SIZE / 2);
            sk.copy_from_slice(&self.secret_key);
            pk.copy_from_slice(public_key);
            Some(result)
        } else {
            None
        }
    }
}

impl TryFrom<pkcs8::PrivateKeyInfo<'_>> for KeypairBytes {
    type Error = pkcs8::Error;

    fn try_from(private_key: pkcs8::PrivateKeyInfo<'_>) -> pkcs8::Result<Self> {
        private_key.algorithm.assert_algorithm_oid(ALGORITHM_OID)?;

        if private_key.algorithm.parameters.is_some() {
            return Err(pkcs8::Error::ParametersMalformed);
        }

        // Ed25519 PKCS#8 keys are represented as a nested OCTET STRING
        // (i.e. an OCTET STRING within an OCTET STRING).
        //
        // This match statement checks and removes the inner OCTET STRING
        // header value:
        //
        // - 0x04: OCTET STRING tag
        // - 0x20: 32-byte length
        let secret_key = match private_key.private_key {
            [0x04, 0x20, rest @ ..] => rest.try_into().map_err(|_| pkcs8::Error::KeyMalformed),
            _ => Err(pkcs8::Error::KeyMalformed),
        }?;

        // TODO(tarcieri): parse public key
        let public_key = private_key
            .public_key
            .map(|bytes| bytes.try_into().map_err(|_| pkcs8::Error::KeyMalformed))
            .transpose()?;

        Ok(Self {
            secret_key,
            public_key,
        })
    }
}

impl DecodePrivateKey for KeypairBytes {}

#[cfg(feature = "alloc")]
#[cfg_attr(docsrs, doc(cfg(feature = "alloc")))]
impl EncodePrivateKey for KeypairBytes {
    fn to_pkcs8_der(&self) -> pkcs8::Result<pkcs8::PrivateKeyDocument> {
        let algorithm = pkcs8::AlgorithmIdentifier {
            oid: ALGORITHM_OID,
            parameters: None,
        };

        // Serialize private key as nested OCTET STRING
        let mut private_key = [0u8; 2 + (Self::BYTE_SIZE / 2)];
        private_key[0] = 0x04;
        private_key[1] = 0x20;
        private_key[2..].copy_from_slice(&self.secret_key);

        let result = pkcs8::PrivateKeyInfo {
            algorithm,
            private_key: &private_key,
            public_key: self.public_key.as_ref().map(AsRef::as_ref),
        }
        .to_der();

        #[cfg(feature = "zeroize")]
        private_key.zeroize();

        result
    }
}

impl<'a> fmt::Debug for KeypairBytes {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("KeypairBytes")
            .field("public_key", &self.public_key)
            .finish() // TODO: use `finish_non_exhaustive` when MSRV 1.53
    }
}

#[cfg(feature = "zeroize")]
#[cfg_attr(docsrs, doc(cfg(feature = "zeroize")))]
impl Drop for KeypairBytes {
    fn drop(&mut self) {
        self.secret_key.zeroize()
    }
}

#[cfg(test)]
mod tests {
    use super::KeypairBytes;
    use hex_literal::hex;

    const SECRET_KEY_BYTES: [u8; 32] =
        hex!("D4EE72DBF913584AD5B6D8F1F769F8AD3AFE7C28CBF1D4FBE097A88F44755842");

    const PUBLIC_KEY_BYTES: [u8; 32] =
        hex!("19BF44096984CDFE8541BAC167DC3B96C85086AA30B6B6CB0C5C38AD703166E1");

    #[test]
    fn to_bytes() {
        let valid_keypair = KeypairBytes {
            secret_key: SECRET_KEY_BYTES,
            public_key: Some(PUBLIC_KEY_BYTES),
        };

        assert_eq!(
            valid_keypair.to_bytes().unwrap(),
            hex!("D4EE72DBF913584AD5B6D8F1F769F8AD3AFE7C28CBF1D4FBE097A88F4475584219BF44096984CDFE8541BAC167DC3B96C85086AA30B6B6CB0C5C38AD703166E1")
        );

        let invalid_keypair = KeypairBytes {
            secret_key: SECRET_KEY_BYTES,
            public_key: None,
        };

        assert_eq!(invalid_keypair.to_bytes(), None);
    }
}
