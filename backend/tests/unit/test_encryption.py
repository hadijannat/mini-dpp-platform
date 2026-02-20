"""
Unit tests for AES-256-GCM connector config encryption.

Tests encrypt/decrypt roundtrip, idempotency, error handling,
and that raw DB reads would show ciphertext (not plaintext).
"""

import base64
import os

import pytest

from app.core.encryption import (
    _ENC_PREFIX,
    _SENSITIVE_FIELDS,
    ConnectorConfigEncryptor,
    EncryptionError,
)


@pytest.fixture
def master_key_b64() -> str:
    """Generate a valid 256-bit master key (base64-encoded)."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


@pytest.fixture
def encryptor(master_key_b64: str) -> ConnectorConfigEncryptor:
    return ConnectorConfigEncryptor(master_key_b64)


# --------------------------------------------------------------------------
# Happy-path roundtrip
# --------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip(encryptor: ConnectorConfigEncryptor) -> None:
    """Encrypting then decrypting should return the original config."""
    config = {
        "dtr_base_url": "https://dtr.example.com",
        "auth_type": "oidc",
        "client_id": "my-client",
        "client_secret": "super-secret-value",
        "token": "my-bearer-token",
        "bpn": "BPNL000000000001",
    }
    encrypted = encryptor.encrypt_config(config)
    decrypted = encryptor.decrypt_config(encrypted)

    assert decrypted == config


def test_sensitive_fields_are_encrypted(encryptor: ConnectorConfigEncryptor) -> None:
    """After encryption, sensitive fields must be ciphertext with the enc: prefix."""
    config = {
        "client_secret": "super-secret-value",
        "token": "my-bearer-token",
        "dtr_base_url": "https://dtr.example.com",
    }
    encrypted = encryptor.encrypt_config(config)

    for field in _SENSITIVE_FIELDS:
        if field in config:
            assert encrypted[field].startswith(_ENC_PREFIX), (
                f"{field} should be encrypted but is: {encrypted[field][:30]}..."
            )
            assert encrypted[field] != config[field]

    # Non-sensitive fields must remain in plaintext.
    assert encrypted["dtr_base_url"] == "https://dtr.example.com"


def test_raw_db_read_shows_ciphertext(encryptor: ConnectorConfigEncryptor) -> None:
    """Simulates a raw DB read: encrypted fields must NOT contain the original plaintext."""
    config = {"client_secret": "my-secret", "token": "my-token"}
    encrypted = encryptor.encrypt_config(config)

    # A raw SELECT would return the encrypted dict — verify no plaintext leaks.
    assert "my-secret" not in str(encrypted)
    assert "my-token" not in str(encrypted)


# --------------------------------------------------------------------------
# Idempotency
# --------------------------------------------------------------------------


def test_encrypt_is_idempotent(encryptor: ConnectorConfigEncryptor) -> None:
    """Encrypting an already-encrypted config should not double-encrypt."""
    config = {"client_secret": "secret", "token": "tok"}
    once = encryptor.encrypt_config(config)
    twice = encryptor.encrypt_config(once)

    # Values should be identical (not re-encrypted).
    assert once["client_secret"] == twice["client_secret"]
    assert once["token"] == twice["token"]

    # And decryption still works.
    decrypted = encryptor.decrypt_config(twice)
    assert decrypted == config


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------


def test_none_and_empty_fields_left_as_is(encryptor: ConnectorConfigEncryptor) -> None:
    """None and empty-string sensitive fields should not be encrypted."""
    config: dict[str, str | None] = {"client_secret": None, "token": ""}
    encrypted = encryptor.encrypt_config(config)

    assert encrypted["client_secret"] is None
    assert encrypted["token"] == ""


def test_non_sensitive_fields_untouched(encryptor: ConnectorConfigEncryptor) -> None:
    """Fields not in _SENSITIVE_FIELDS must pass through unchanged."""
    config = {"dtr_base_url": "https://dtr.example.com", "bpn": "BPNL000000000001"}
    encrypted = encryptor.encrypt_config(config)
    assert encrypted == config


def test_decrypt_non_encrypted_fields_passthrough(encryptor: ConnectorConfigEncryptor) -> None:
    """Decrypting a config with plaintext sensitive fields should pass them through."""
    config = {"client_secret": "plain-text-value", "dtr_base_url": "https://example.com"}
    decrypted = encryptor.decrypt_config(config)
    assert decrypted == config


# --------------------------------------------------------------------------
# Unique nonces
# --------------------------------------------------------------------------


def test_encrypting_same_value_produces_different_ciphertext(
    encryptor: ConnectorConfigEncryptor,
) -> None:
    """Each encryption must use a unique nonce, so ciphertexts differ."""
    config = {"client_secret": "same-value"}
    enc1 = encryptor.encrypt_config(config)
    enc2 = encryptor.encrypt_config(config)

    # Due to random nonces, the encrypted values should differ.
    assert enc1["client_secret"] != enc2["client_secret"]

    # But both should decrypt to the same plaintext.
    assert encryptor.decrypt_config(enc1) == encryptor.decrypt_config(enc2)


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------


def test_empty_master_key_raises() -> None:
    with pytest.raises(EncryptionError, match="keyring is empty"):
        ConnectorConfigEncryptor("")


def test_invalid_base64_master_key_raises() -> None:
    with pytest.raises(EncryptionError, match="not valid base64"):
        ConnectorConfigEncryptor("not-valid-base64!!!")


def test_wrong_key_length_raises() -> None:
    short_key = base64.b64encode(os.urandom(16)).decode("ascii")  # 128-bit, not 256-bit
    with pytest.raises(EncryptionError, match="256 bits"):
        ConnectorConfigEncryptor(short_key)


def test_decrypt_with_wrong_key_raises(master_key_b64: str) -> None:
    """Decrypting with a different master key should fail (GCM auth tag mismatch)."""
    encryptor_a = ConnectorConfigEncryptor(master_key_b64)
    different_key = base64.b64encode(os.urandom(32)).decode("ascii")
    encryptor_b = ConnectorConfigEncryptor(different_key)

    config = {"client_secret": "secret-value"}
    encrypted = encryptor_a.encrypt_config(config)

    with pytest.raises(EncryptionError, match="decryption failed"):
        encryptor_b.decrypt_config(encrypted)


def test_corrupted_ciphertext_raises(encryptor: ConnectorConfigEncryptor) -> None:
    """Tampering with ciphertext should cause decryption to fail."""
    config = {"client_secret": "secret-value"}
    encrypted = encryptor.encrypt_config(config)

    # Corrupt the base64 payload by flipping a character.
    enc_val = encrypted["client_secret"]
    payload = enc_val[len(_ENC_PREFIX) :]
    corrupted = payload[:-2] + ("A" if payload[-2] != "A" else "B") + payload[-1]
    encrypted["client_secret"] = f"{_ENC_PREFIX}{corrupted}"

    with pytest.raises(EncryptionError):
        encryptor.decrypt_config(encrypted)
