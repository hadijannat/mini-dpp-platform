"""
AES-256-GCM envelope encryption for sensitive configuration fields.

Provides ConnectorConfigEncryptor that transparently encrypts/decrypts
specific fields (e.g. client_secret, token) within a JSONB config dict,
leaving non-sensitive fields in plaintext for queryability.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Fields within connector config that must be encrypted at rest.
_SENSITIVE_FIELDS: frozenset[str] = frozenset({"client_secret", "token"})

# Prefix used to identify encrypted field values in JSONB.
_ENC_PREFIX = "enc:v1:"


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


class ConnectorConfigEncryptor:
    """
    Encrypts and decrypts sensitive fields in a connector config dict.

    Uses AES-256-GCM with a 12-byte random nonce per field. Encrypted values
    are stored as ``enc:v1:<base64(nonce + ciphertext)>`` so that JSONB
    remains valid and non-sensitive fields stay queryable.

    Usage::

        encryptor = ConnectorConfigEncryptor(master_key_b64)
        encrypted_config = encryptor.encrypt_config(raw_config)
        decrypted_config = encryptor.decrypt_config(encrypted_config)
    """

    _NONCE_BYTES = 12

    def __init__(self, master_key_b64: str) -> None:
        if not master_key_b64:
            raise EncryptionError("encryption_master_key must not be empty")
        try:
            raw_key = base64.b64decode(master_key_b64)
        except Exception as exc:
            raise EncryptionError("encryption_master_key is not valid base64") from exc
        if len(raw_key) != 32:
            raise EncryptionError(
                f"encryption_master_key must be 256 bits (32 bytes), got {len(raw_key)}"
            )
        self._aesgcm = AESGCM(raw_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of *config* with sensitive fields encrypted."""
        result = dict(config)
        for field in _SENSITIVE_FIELDS:
            value = result.get(field)
            if value is None or value == "":
                continue
            if isinstance(value, str) and value.startswith(_ENC_PREFIX):
                # Already encrypted — leave as-is (idempotent).
                continue
            result[field] = self._encrypt_value(str(value))
        return result

    def decrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of *config* with sensitive fields decrypted."""
        result = dict(config)
        for field in _SENSITIVE_FIELDS:
            value = result.get(field)
            if not isinstance(value, str) or not value.startswith(_ENC_PREFIX):
                continue
            result[field] = self._decrypt_value(value)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encrypt_value(self, plaintext: str) -> str:
        nonce = os.urandom(self._NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        payload = base64.b64encode(nonce + ciphertext).decode("ascii")
        return f"{_ENC_PREFIX}{payload}"

    def _decrypt_value(self, token: str) -> str:
        if not token.startswith(_ENC_PREFIX):
            raise EncryptionError("value does not have the expected encrypted prefix")
        b64_payload = token[len(_ENC_PREFIX) :]
        try:
            raw = base64.b64decode(b64_payload)
        except Exception as exc:
            raise EncryptionError("corrupted encrypted payload (bad base64)") from exc
        if len(raw) <= self._NONCE_BYTES:
            raise EncryptionError("corrupted encrypted payload (too short)")
        nonce = raw[: self._NONCE_BYTES]
        ciphertext = raw[self._NONCE_BYTES :]
        try:
            plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise EncryptionError(
                "decryption failed — key mismatch or corrupted ciphertext"
            ) from exc
        return plaintext_bytes.decode("utf-8")
