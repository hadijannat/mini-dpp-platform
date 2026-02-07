"""
Ed25519 digital signing for Merkle roots.

Uses the ``cryptography`` library for Ed25519 key generation, signing, and
verification. Signatures provide non-repudiation for audit batches.
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)


def generate_signing_keypair() -> tuple[str, str]:
    """Generate a new Ed25519 key pair for audit signing.

    Returns
    -------
    tuple[str, str]
        ``(private_key_pem, public_key_pem)`` as PEM-encoded strings.
    """
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def sign_merkle_root(root_hash: str, private_key_pem: str) -> str:
    """Sign a Merkle root hash with an Ed25519 private key.

    Parameters
    ----------
    root_hash:
        Hex-encoded Merkle root hash to sign.
    private_key_pem:
        PEM-encoded Ed25519 private key.

    Returns
    -------
    str
        Base64-encoded Ed25519 signature.
    """
    private_key = load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("Expected an Ed25519 private key")
    signature = private_key.sign(root_hash.encode("utf-8"))
    return base64.b64encode(signature).decode("utf-8")


def verify_signature(
    root_hash: str, signature: str, public_key_pem: str
) -> bool:
    """Verify an Ed25519 signature on a Merkle root hash.

    Parameters
    ----------
    root_hash:
        Hex-encoded Merkle root hash that was signed.
    signature:
        Base64-encoded Ed25519 signature to verify.
    public_key_pem:
        PEM-encoded Ed25519 public key.

    Returns
    -------
    bool
        ``True`` if the signature is valid.
    """
    public_key = load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(public_key, Ed25519PublicKey):
        raise TypeError("Expected an Ed25519 public key")
    try:
        public_key.verify(
            base64.b64decode(signature),
            root_hash.encode("utf-8"),
        )
        return True
    except InvalidSignature:
        return False
