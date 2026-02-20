"""DID Document generation using the did:web method."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

from app.modules.credentials.schemas import (
    DIDDocument,
    VerificationMethod,
)


class DIDService:
    """Generate and resolve did:web DID Documents."""

    def __init__(
        self,
        base_url: str,
        signing_key_pem: str,
        key_id: str = "key-1",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._key_id = key_id
        self._private_key = _load_private_key(signing_key_pem)

    # ------------------------------------------------------------------
    # DID generation
    # ------------------------------------------------------------------

    def generate_did_web(self, tenant_slug: str) -> str:
        """Build a did:web identifier for a tenant.

        Maps to: https://{domain}/t/{tenant_slug}/.well-known/did.json
        """
        # did:web encodes path separators as colons
        domain = self._base_url.split("://", 1)[-1]
        encoded = quote(domain, safe="") + ":t:" + quote(tenant_slug)
        return f"did:web:{encoded}"

    def generate_did_document(self, tenant_slug: str) -> DIDDocument:
        """Generate a full DID Document for a tenant."""
        did = self.generate_did_web(tenant_slug)
        vm_id = f"{did}#{self._key_id}"
        jwk = self._export_public_key_jwk()

        return DIDDocument(
            id=did,
            verification_method=[
                VerificationMethod(
                    id=vm_id,
                    type="JsonWebKey2020",
                    controller=did,
                    public_key_jwk=jwk,
                )
            ],
            authentication=[vm_id],
            assertion_method=[vm_id],
        )

    # ------------------------------------------------------------------
    # Key export
    # ------------------------------------------------------------------

    def _export_public_key_jwk(self) -> dict[str, Any]:
        """Export the public key component as JWK."""
        pk = self._private_key
        if isinstance(pk, rsa.RSAPrivateKey):
            return _rsa_public_jwk(pk)
        if isinstance(pk, ec.EllipticCurvePrivateKey):
            return _ec_public_jwk(pk)
        if isinstance(pk, ed25519.Ed25519PrivateKey):
            return _ed25519_public_jwk(pk)
        msg = f"Unsupported key type: {type(pk).__name__}"
        raise TypeError(msg)

    def export_public_jwk(self) -> dict[str, Any]:
        """Public accessor for verifier key discovery endpoints."""
        return self._export_public_key_jwk()

    @property
    def private_key(
        self,
    ) -> rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey | ed25519.Ed25519PrivateKey:
        return self._private_key

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def did_web_prefix(self) -> str:
        """Return the common did:web prefix for all tenants on this platform.

        e.g. "did:web:dpp-platform.dev:t:" — any valid issuer DID issued by
        this platform will start with this prefix.
        """
        domain = self._base_url.split("://", 1)[-1]
        encoded_domain = quote(domain, safe="")
        return f"did:web:{encoded_domain}:t:"


# ======================================================================
# Private helpers
# ======================================================================

_PrivateKeyTypes = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey | ed25519.Ed25519PrivateKey


def _load_private_key(pem: str) -> _PrivateKeyTypes:
    """Load a PEM-encoded private key (RSA, EC, or Ed25519)."""
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(
        key,
        (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey, ed25519.Ed25519PrivateKey),
    ):
        msg = f"Unsupported key type: {type(key).__name__}"
        raise TypeError(msg)
    return key


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _rsa_public_jwk(pk: rsa.RSAPrivateKey) -> dict[str, Any]:
    pub = pk.public_key().public_numbers()
    n_bytes = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
    e_bytes = pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "n": _b64url(n_bytes),
        "e": _b64url(e_bytes),
        "alg": "RS256",
        "use": "sig",
    }


def _ec_public_jwk(pk: ec.EllipticCurvePrivateKey) -> dict[str, Any]:
    pub = pk.public_key().public_numbers()
    curve = pk.curve
    if isinstance(curve, ec.SECP256R1):
        crv, alg, size = "P-256", "ES256", 32
    elif isinstance(curve, ec.SECP384R1):
        crv, alg, size = "P-384", "ES384", 48
    else:
        crv, alg, size = "P-521", "ES512", 66
    return {
        "kty": "EC",
        "crv": crv,
        "x": _b64url(pub.x.to_bytes(size, "big")),
        "y": _b64url(pub.y.to_bytes(size, "big")),
        "alg": alg,
        "use": "sig",
    }


def _ed25519_public_jwk(pk: ed25519.Ed25519PrivateKey) -> dict[str, Any]:
    pub_bytes = pk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": _b64url(pub_bytes),
        "alg": "EdDSA",
        "use": "sig",
    }


def did_to_url(did: str) -> str | None:
    """Convert a did:web identifier to its HTTPS URL."""
    if not did.startswith("did:web:"):
        return None
    # did:web:example.com:path:to → https://example.com/path/to
    parts = did[8:].split(":")
    domain = parts[0]
    path = "/".join(parts[1:])
    if path:
        return f"https://{domain}/{path}/.well-known/did.json"
    return f"https://{domain}/.well-known/did.json"


def did_document_to_json(doc: DIDDocument) -> str:
    """Serialize DID Document to canonical JSON."""
    return json.dumps(doc.model_dump(by_alias=True), sort_keys=True, separators=(",", ":"))
