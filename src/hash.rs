use sha2::{Digest, Sha256};

const HEX_DIGITS: &[u8; 16] = b"0123456789abcdef";

pub(crate) fn sha256_hex(val: &str) -> String {
    let digest: [u8; 32] = Sha256::digest(val.as_bytes()).into();
    let mut encoded: String = String::with_capacity(digest.len() * 2);
    for byte in digest {
        encoded.push(char::from(HEX_DIGITS[usize::from(byte >> 4)]));
        encoded.push(char::from(HEX_DIGITS[usize::from(byte & 0x0f)]));
    }
    encoded
}
