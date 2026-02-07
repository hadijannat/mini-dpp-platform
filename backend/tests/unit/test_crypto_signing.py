"""Tests for crypto Ed25519 signing module."""

from __future__ import annotations

import pytest

from app.core.crypto.signing import (
    generate_signing_keypair,
    sign_merkle_root,
    verify_signature,
)


class TestGenerateSigningKeypair:
    """Tests for Ed25519 key pair generation."""

    def test_returns_pem_strings(self) -> None:
        private_pem, public_pem = generate_signing_keypair()
        assert isinstance(private_pem, str)
        assert isinstance(public_pem, str)
        assert "PRIVATE KEY" in private_pem
        assert "PUBLIC KEY" in public_pem

    def test_unique_keys(self) -> None:
        k1 = generate_signing_keypair()
        k2 = generate_signing_keypair()
        assert k1[0] != k2[0]
        assert k1[1] != k2[1]


class TestSignAndVerify:
    """Tests for signing and verification round-trip."""

    def test_sign_and_verify(self) -> None:
        private_pem, public_pem = generate_signing_keypair()
        root_hash = "a" * 64
        signature = sign_merkle_root(root_hash, private_pem)
        assert isinstance(signature, str)
        assert verify_signature(root_hash, signature, public_pem)

    def test_wrong_data_fails(self) -> None:
        private_pem, public_pem = generate_signing_keypair()
        signature = sign_merkle_root("a" * 64, private_pem)
        assert not verify_signature("b" * 64, signature, public_pem)

    def test_wrong_key_fails(self) -> None:
        priv1, _pub1 = generate_signing_keypair()
        _priv2, pub2 = generate_signing_keypair()
        signature = sign_merkle_root("a" * 64, priv1)
        assert not verify_signature("a" * 64, signature, pub2)

    def test_tampered_signature_fails(self) -> None:
        private_pem, public_pem = generate_signing_keypair()
        signature = sign_merkle_root("a" * 64, private_pem)
        # Tamper with the signature
        tampered = signature[:-4] + "XXXX"
        assert not verify_signature("a" * 64, tampered, public_pem)

    def test_invalid_private_key_type_raises(self) -> None:
        """Non-Ed25519 keys should raise TypeError."""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        rsa_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        rsa_pem = rsa_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode()
        with pytest.raises(TypeError, match="Ed25519"):
            sign_merkle_root("a" * 64, rsa_pem)

    def test_invalid_public_key_type_raises(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        rsa_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        rsa_pub_pem = rsa_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()
        with pytest.raises(TypeError, match="Ed25519"):
            verify_signature("a" * 64, "sig", rsa_pub_pem)
