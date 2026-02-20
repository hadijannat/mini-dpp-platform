"""Encryption primitives for connector secrets and DPP field-level confidentiality."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Fields within connector config that must be encrypted at rest.
_SENSITIVE_FIELDS: frozenset[str] = frozenset({"client_secret", "token"})

# Token versions for connector/dataspace secret payloads.
_ENC_V1_PREFIX = "enc:v1:"
_ENC_V2_PREFIX = "enc:v2:"
_ENC_PREFIX = _ENC_V2_PREFIX  # New writes use v2.

_NONCE_BYTES = 12
_DEK_WRAPPING_ALGORITHM = "AES-256-GCM-KW"
_DEK_WRAPPING_AAD = b"dek-wrap:v1"
_DPP_MARKER_VERSION = "dpp:v1"


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str, *, error_context: str) -> bytes:
    try:
        return base64.b64decode(data)
    except Exception as exc:  # pragma: no cover - defensive
        raise EncryptionError(error_context) from exc


def _to_aad_bytes(aad: str | bytes | None) -> bytes | None:
    if aad is None:
        return None
    if isinstance(aad, bytes):
        return aad
    return aad.encode("utf-8")


@dataclass(slots=True)
class DPPEncryptedField:
    """Encrypted value row payload to persist in ``encrypted_values``."""

    ref_id: UUID
    json_pointer_path: str
    cipher_text: bytes
    nonce: bytes
    key_id: str
    algorithm: str
    marker_hash: str


@dataclass(slots=True)
class DPPEncryptionResult:
    """Result of preparing an AAS environment for encrypted persistence."""

    aas_env_json: dict[str, Any]
    encrypted_fields: list[DPPEncryptedField]
    wrapped_dek: str | None
    kek_id: str | None
    dek_wrapping_algorithm: str | None


class ConnectorConfigEncryptor:
    """Encrypt/decrypt connector config secrets with keyring-aware token formats."""

    def __init__(
        self,
        master_key_b64: str | None = None,
        *,
        keyring: dict[str, str] | None = None,
        active_key_id: str = "default",
    ) -> None:
        parsed_keyring: dict[str, str] = {}
        if keyring:
            parsed_keyring = {
                str(key_id).strip(): str(value).strip()
                for key_id, value in keyring.items()
                if str(key_id).strip() and str(value).strip()
            }
        if not parsed_keyring and master_key_b64:
            parsed_keyring[active_key_id.strip() or "default"] = master_key_b64.strip()
        if not parsed_keyring:
            raise EncryptionError(
                "encryption keyring is empty (set ENCRYPTION_KEYRING_JSON or ENCRYPTION_MASTER_KEY)"
            )

        self._keys: dict[str, bytes] = {}
        for key_id, key_b64 in parsed_keyring.items():
            raw_key = _b64decode(
                key_b64,
                error_context=f"encryption key '{key_id}' is not valid base64",
            )
            if len(raw_key) != 32:
                raise EncryptionError(
                    f"encryption key '{key_id}' must be 256 bits (32 bytes), got {len(raw_key)}"
                )
            self._keys[key_id] = raw_key

        active = active_key_id.strip() or "default"
        if active not in self._keys:
            active = next(iter(self._keys))
        self._active_key_id = active

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    # ------------------------------------------------------------------
    # Connector config encryption API
    # ------------------------------------------------------------------

    def encrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy with sensitive fields encrypted using ``enc:v2``."""
        result = dict(config)
        for field in _SENSITIVE_FIELDS:
            value = result.get(field)
            if value is None or value == "":
                continue
            if isinstance(value, str) and value.startswith((_ENC_V1_PREFIX, _ENC_V2_PREFIX)):
                continue
            result[field] = self._encrypt_value(str(value), aad=f"field:{field}")
        return result

    def decrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy with sensitive encrypted fields decrypted."""
        result = dict(config)
        for field in _SENSITIVE_FIELDS:
            value = result.get(field)
            if not isinstance(value, str):
                continue
            if not value.startswith((_ENC_V1_PREFIX, _ENC_V2_PREFIX)):
                continue
            result[field] = self._decrypt_value(value, aad=f"field:{field}")
        return result

    # ------------------------------------------------------------------
    # Generic token encryption API
    # ------------------------------------------------------------------

    def encrypt_secret_token(self, plaintext: str, *, aad: str | bytes | None = None) -> str:
        return self._encrypt_value(plaintext, aad=aad)

    def decrypt_secret_token(self, token: str, *, aad: str | bytes | None = None) -> str:
        return self._decrypt_value(token, aad=aad)

    def _encrypt_value(self, plaintext: str, *, aad: str | bytes | None = None) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        aad_bytes = _to_aad_bytes(aad)
        key = self._keys[self._active_key_id]
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad_bytes)
        payload = _b64encode(nonce + ciphertext)
        return f"{_ENC_V2_PREFIX}{self._active_key_id}:{payload}"

    def _decrypt_value(self, token: str, *, aad: str | bytes | None = None) -> str:
        if token.startswith(_ENC_V2_PREFIX):
            return self._decrypt_value_v2(token, aad=aad)
        if token.startswith(_ENC_V1_PREFIX):
            return self._decrypt_value_v1(token)
        raise EncryptionError("value does not have a supported encrypted prefix")

    def _decrypt_value_v2(self, token: str, *, aad: str | bytes | None = None) -> str:
        raw = token[len(_ENC_V2_PREFIX) :]
        if ":" not in raw:
            raise EncryptionError("corrupted enc:v2 payload (missing key id delimiter)")
        key_id, b64_payload = raw.split(":", 1)
        key_id = key_id.strip()
        if key_id not in self._keys:
            raise EncryptionError(f"unknown encryption key id '{key_id}' for enc:v2 payload")
        blob = _b64decode(b64_payload, error_context="corrupted enc:v2 payload (bad base64)")
        if len(blob) <= _NONCE_BYTES:
            raise EncryptionError("corrupted enc:v2 payload (too short)")
        nonce = blob[:_NONCE_BYTES]
        ciphertext = blob[_NONCE_BYTES:]
        aad_bytes = _to_aad_bytes(aad)
        try:
            plaintext_bytes = AESGCM(self._keys[key_id]).decrypt(nonce, ciphertext, aad_bytes)
        except Exception as exc:
            raise EncryptionError(
                "decryption failed — key mismatch, AAD mismatch, or corrupted ciphertext"
            ) from exc
        return plaintext_bytes.decode("utf-8")

    def _decrypt_value_v1(self, token: str) -> str:
        b64_payload = token[len(_ENC_V1_PREFIX) :]
        blob = _b64decode(b64_payload, error_context="corrupted enc:v1 payload (bad base64)")
        if len(blob) <= _NONCE_BYTES:
            raise EncryptionError("corrupted enc:v1 payload (too short)")
        nonce = blob[:_NONCE_BYTES]
        ciphertext = blob[_NONCE_BYTES:]
        # v1 tokens did not carry key id or AAD. Try each configured key.
        for key in self._keys.values():
            try:
                plaintext_bytes = AESGCM(key).decrypt(nonce, ciphertext, None)
                return plaintext_bytes.decode("utf-8")
            except Exception:
                continue
        raise EncryptionError("decryption failed — no key could decrypt enc:v1 payload")

    # ------------------------------------------------------------------
    # DEK wrapping API
    # ------------------------------------------------------------------

    def wrap_dek(self, dek: bytes) -> tuple[str, str, str]:
        """Wrap a per-revision DEK under the active KEK."""
        if len(dek) != 32:
            raise EncryptionError("DEK must be 256 bits (32 bytes)")
        nonce = os.urandom(_NONCE_BYTES)
        key = self._keys[self._active_key_id]
        wrapped = AESGCM(key).encrypt(nonce, dek, _DEK_WRAPPING_AAD)
        return _b64encode(nonce + wrapped), self._active_key_id, _DEK_WRAPPING_ALGORITHM

    def unwrap_dek(
        self,
        wrapped_dek: str,
        *,
        kek_id: str,
        algorithm: str | None,
    ) -> bytes:
        """Unwrap a per-revision DEK."""
        if algorithm and algorithm != _DEK_WRAPPING_ALGORITHM:
            raise EncryptionError(f"Unsupported DEK wrapping algorithm: {algorithm}")
        key_id = kek_id.strip()
        if key_id not in self._keys:
            raise EncryptionError(f"Unknown KEK id '{key_id}'")
        blob = _b64decode(wrapped_dek, error_context="wrapped_dek is not valid base64")
        if len(blob) <= _NONCE_BYTES:
            raise EncryptionError("wrapped_dek payload is too short")
        nonce = blob[:_NONCE_BYTES]
        ciphertext = blob[_NONCE_BYTES:]
        try:
            dek = AESGCM(self._keys[key_id]).decrypt(nonce, ciphertext, _DEK_WRAPPING_AAD)
        except Exception as exc:
            raise EncryptionError("failed to unwrap DEK") from exc
        if len(dek) != 32:
            raise EncryptionError("invalid unwrapped DEK length")
        return dek


class DPPFieldEncryptor:
    """Encrypt/decrypt DPP element values tagged with ``Confidentiality=encrypted``."""

    def __init__(self, key_encryptor: ConnectorConfigEncryptor) -> None:
        self._key_encryptor = key_encryptor

    def prepare_for_storage(
        self,
        aas_env: dict[str, Any],
        *,
        tenant_id: UUID,
    ) -> DPPEncryptionResult:
        """Encrypt tagged values and return markerized payload + encrypted row records."""
        working = copy.deepcopy(aas_env)
        encrypted_fields: list[DPPEncryptedField] = []

        dek = os.urandom(32)
        wrapped_dek, kek_id, wrapping_algorithm = self._key_encryptor.wrap_dek(dek)
        dek_cipher = AESGCM(dek)

        def _walk(node: Any, *, path: str) -> None:
            if isinstance(node, dict):
                if self._is_encrypted_element(node):
                    value = node.get("value")
                    if value is not None and not self._is_encrypted_marker(value):
                        value_path = f"{path}/value"
                        ref_id = uuid4()
                        plaintext = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
                        nonce = os.urandom(_NONCE_BYTES)
                        aad = self._build_aad(tenant_id=tenant_id, path=value_path)
                        cipher_text = dek_cipher.encrypt(nonce, plaintext.encode("utf-8"), aad)
                        marker_hash = hashlib.sha256(cipher_text).hexdigest()
                        encrypted_fields.append(
                            DPPEncryptedField(
                                ref_id=ref_id,
                                json_pointer_path=value_path,
                                cipher_text=cipher_text,
                                nonce=nonce,
                                key_id="revision-dek",
                                algorithm="AES-256-GCM",
                                marker_hash=marker_hash,
                            )
                        )
                        node["value"] = {
                            "_enc_ref": str(ref_id),
                            "_enc_sha256": marker_hash,
                            "_enc_alg": "AES-256-GCM",
                            "_enc_ver": _DPP_MARKER_VERSION,
                        }

                for key, child in list(node.items()):
                    child_path = f"{path}/{self._escape_json_pointer_token(str(key))}"
                    _walk(child, path=child_path)
                return

            if isinstance(node, list):
                for index, child in enumerate(node):
                    _walk(child, path=f"{path}/{index}")

        _walk(working, path="")

        if not encrypted_fields:
            return DPPEncryptionResult(
                aas_env_json=working,
                encrypted_fields=[],
                wrapped_dek=None,
                kek_id=None,
                dek_wrapping_algorithm=None,
            )

        return DPPEncryptionResult(
            aas_env_json=working,
            encrypted_fields=encrypted_fields,
            wrapped_dek=wrapped_dek,
            kek_id=kek_id,
            dek_wrapping_algorithm=wrapping_algorithm,
        )

    def decrypt_for_read(
        self,
        aas_env: dict[str, Any],
        *,
        tenant_id: UUID,
        encrypted_rows: list[Any],
        wrapped_dek: str | None,
        kek_id: str | None,
        dek_wrapping_algorithm: str | None,
    ) -> dict[str, Any]:
        """Resolve ``_enc_ref`` markers back to plaintext values for authorized readers."""
        if not encrypted_rows:
            return copy.deepcopy(aas_env)
        if not wrapped_dek or not kek_id:
            raise EncryptionError("missing wrapped_dek/kek_id for encrypted revision")

        dek = self._key_encryptor.unwrap_dek(
            wrapped_dek,
            kek_id=kek_id,
            algorithm=dek_wrapping_algorithm,
        )
        dek_cipher = AESGCM(dek)
        by_ref = {str(row.id): row for row in encrypted_rows}

        working = copy.deepcopy(aas_env)

        def _walk(node: Any) -> Any:
            if isinstance(node, dict):
                if self._is_encrypted_marker(node):
                    ref = str(node.get("_enc_ref", ""))
                    row = by_ref.get(ref)
                    if row is None:
                        raise EncryptionError(f"Missing encrypted value row for ref '{ref}'")

                    marker_hash = str(node.get("_enc_sha256", "")).strip()
                    if marker_hash:
                        actual_hash = hashlib.sha256(bytes(row.cipher_text)).hexdigest()
                        if marker_hash != actual_hash:
                            raise EncryptionError("Encrypted marker hash mismatch")

                    aad = self._build_aad(
                        tenant_id=tenant_id,
                        path=str(row.json_pointer_path),
                    )
                    try:
                        plaintext_bytes = dek_cipher.decrypt(
                            bytes(row.nonce),
                            bytes(row.cipher_text),
                            aad,
                        )
                    except Exception as exc:
                        raise EncryptionError("Failed to decrypt encrypted DPP marker") from exc
                    try:
                        return json.loads(plaintext_bytes.decode("utf-8"))
                    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                        raise EncryptionError("Decrypted DPP payload is not valid JSON") from exc

                return {key: _walk(value) for key, value in node.items()}
            if isinstance(node, list):
                return [_walk(item) for item in node]
            return node

        return _walk(working)

    @staticmethod
    def _escape_json_pointer_token(token: str) -> str:
        return token.replace("~", "~0").replace("/", "~1")

    @staticmethod
    def _build_aad(*, tenant_id: UUID, path: str) -> bytes:
        aad = f"tenant:{tenant_id}|path:{path}|enc:{_DPP_MARKER_VERSION}"
        return aad.encode("utf-8")

    @staticmethod
    def _is_encrypted_element(node: dict[str, Any]) -> bool:
        qualifiers = node.get("qualifiers")
        if not isinstance(qualifiers, list):
            return False
        for qualifier in qualifiers:
            if not isinstance(qualifier, dict):
                continue
            q_type = str(qualifier.get("type", "")).strip().lower()
            q_value = str(qualifier.get("value", "")).strip().lower()
            if q_type == "confidentiality" and q_value == "encrypted":
                return True
        return False

    @staticmethod
    def _is_encrypted_marker(value: Any) -> bool:
        return isinstance(value, dict) and isinstance(value.get("_enc_ref"), str)
