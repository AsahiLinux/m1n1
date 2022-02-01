//! PKCS#8 private key tests

#![cfg(feature = "pkcs8")]

use ed25519::pkcs8::{DecodePrivateKey, KeypairBytes};
use hex_literal::hex;

#[cfg(feature = "alloc")]
use ed25519::pkcs8::EncodePrivateKey;

/// Ed25519 PKCS#8 v1 private key encoded as ASN.1 DER
const PKCS8_V1_DER: &[u8] = include_bytes!("examples/pkcs8-v1.der");

/// Ed25519 PKCS#8 v2 private key + public key encoded as ASN.1 DER
const PKCS8_V2_DER: &[u8] = include_bytes!("examples/pkcs8-v2.der");

#[test]
fn decode_pkcs8_v1() {
    let pk = KeypairBytes::from_pkcs8_der(PKCS8_V1_DER).unwrap();

    // Extracted with:
    // $ openssl asn1parse -inform der -in tests/examples/p256-priv.der
    assert_eq!(
        pk.secret_key,
        &hex!("D4EE72DBF913584AD5B6D8F1F769F8AD3AFE7C28CBF1D4FBE097A88F44755842")[..]
    );

    assert_eq!(pk.public_key, None);
}

#[test]
fn decode_pkcs8_v2() {
    let pk = KeypairBytes::from_pkcs8_der(PKCS8_V2_DER).unwrap();

    // Extracted with:
    // $ openssl asn1parse -inform der -in tests/examples/p256-priv.der
    assert_eq!(
        pk.secret_key,
        &hex!("D4EE72DBF913584AD5B6D8F1F769F8AD3AFE7C28CBF1D4FBE097A88F44755842")[..]
    );

    assert_eq!(
        pk.public_key.unwrap(),
        hex!("19BF44096984CDFE8541BAC167DC3B96C85086AA30B6B6CB0C5C38AD703166E1")
    );
}

#[cfg(feature = "alloc")]
#[test]
fn encode_pkcs8_v1() {
    let pk = KeypairBytes::from_pkcs8_der(PKCS8_V1_DER).unwrap();
    let pk_der = pk.to_pkcs8_der().unwrap();
    assert_eq!(pk_der.as_ref(), PKCS8_V1_DER);
}

#[cfg(feature = "alloc")]
#[test]
fn encode_pkcs8_v2() {
    let pk = KeypairBytes::from_pkcs8_der(PKCS8_V2_DER).unwrap();
    let pk2 = KeypairBytes::from_pkcs8_der(pk.to_pkcs8_der().unwrap().as_ref()).unwrap();
    assert_eq!(pk.secret_key, pk2.secret_key);
    assert_eq!(pk.public_key, pk2.public_key);
}
