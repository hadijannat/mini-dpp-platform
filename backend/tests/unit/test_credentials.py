"""Unit tests for Verifiable Credentials and DID module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _generate_rsa_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def _generate_ec_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture()
def rsa_pem() -> str:
    return _generate_rsa_pem()


@pytest.fixture()
def ec_pem() -> str:
    return _generate_ec_pem()


# ---------------------------------------------------------------------------
# DID Document tests
# ---------------------------------------------------------------------------


class TestDIDService:
    def test_generate_did_web(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService

        svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        did = svc.generate_did_web("acme")
        assert did.startswith("did:web:")
        assert "acme" in did

    def test_generate_did_document_structure(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService

        svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        doc = svc.generate_did_document("acme")
        dumped = doc.model_dump(by_alias=True)

        assert "@context" in dumped
        assert "https://www.w3.org/ns/did/v1" in dumped["@context"]
        assert dumped["id"].startswith("did:web:")
        assert len(dumped["verificationMethod"]) == 1
        vm = dumped["verificationMethod"][0]
        assert "publicKeyJwk" in vm
        assert vm["publicKeyJwk"]["kty"] == "RSA"
        assert len(dumped["authentication"]) == 1
        assert len(dumped["assertionMethod"]) == 1

    def test_ec_key_jwk(self, ec_pem: str) -> None:
        from app.modules.credentials.did import DIDService

        svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=ec_pem,
        )
        doc = svc.generate_did_document("test-tenant")
        jwk = doc.model_dump(by_alias=True)["verificationMethod"][0]["publicKeyJwk"]
        assert jwk["kty"] == "EC"
        assert jwk["crv"] == "P-256"
        assert "x" in jwk
        assert "y" in jwk

    def test_did_web_prefix(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService

        svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        prefix = svc.did_web_prefix
        assert prefix == "did:web:dpp-platform.dev:t:"
        # All generated DIDs should start with this prefix
        did = svc.generate_did_web("acme")
        assert did.startswith(prefix)

    def test_did_to_url(self) -> None:
        from app.modules.credentials.did import did_to_url

        url = did_to_url("did:web:dpp-platform.dev:t:acme")
        assert url == "https://dpp-platform.dev/t/acme/.well-known/did.json"

    def test_did_to_url_root(self) -> None:
        from app.modules.credentials.did import did_to_url

        url = did_to_url("did:web:example.com")
        assert url == "https://example.com/.well-known/did.json"

    def test_did_to_url_non_web(self) -> None:
        from app.modules.credentials.did import did_to_url

        assert did_to_url("did:key:z123") is None


# ---------------------------------------------------------------------------
# VC Issuance / Verification tests
# ---------------------------------------------------------------------------


class TestVCService:
    def test_create_jws_proof_rsa(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        proof = vc_svc._create_jws_proof(
            payload={"test": "data"},
            did="did:web:dpp-platform.dev:t:acme",
            key_id="did:web:dpp-platform.dev:t:acme#key-1",
        )
        assert proof.type == "JsonWebSignature2020"
        assert proof.jws  # non-empty JWS token
        assert proof.proof_purpose == "assertionMethod"

    def test_verify_valid_credential(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VerifiableCredential,
        )
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        did = did_svc.generate_did_web("acme")
        key_id = f"{did}#key-1"

        subject = CredentialSubject(
            id="urn:uuid:test-dpp",
            aas_id="urn:uuid:test-dpp",
            digest_sha256="abc123",
        )
        vc = VerifiableCredential(
            id="urn:uuid:test-vc",
            issuer=did,
            issuance_date="2026-01-01T00:00:00Z",
            credential_subject=subject,
        )
        proof = vc_svc._create_jws_proof(
            payload=vc.model_dump(by_alias=True, exclude={"proof"}),
            did=did,
            key_id=key_id,
        )
        vc.proof = proof
        vc_dict = vc.model_dump(by_alias=True)

        result = vc_svc.verify_credential(vc_dict)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_verify_missing_proof(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        result = vc_svc.verify_credential({"issuer": "did:web:test"})
        assert result.valid is False
        assert any("proof" in e.lower() for e in result.errors)

    def test_verify_tampered_jws(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VerifiableCredential,
        )
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        did = did_svc.generate_did_web("acme")
        key_id = f"{did}#key-1"

        subject = CredentialSubject(
            id="urn:uuid:test-dpp",
            aas_id="urn:uuid:test-dpp",
            digest_sha256="abc123",
        )
        vc = VerifiableCredential(
            id="urn:uuid:test-vc",
            issuer=did,
            issuance_date="2026-01-01T00:00:00Z",
            credential_subject=subject,
        )
        proof = vc_svc._create_jws_proof(
            payload=vc.model_dump(by_alias=True, exclude={"proof"}),
            did=did,
            key_id=key_id,
        )
        # Tamper with JWS
        proof.jws = proof.jws[:-5] + "XXXXX"
        vc.proof = proof
        vc_dict = vc.model_dump(by_alias=True)

        result = vc_svc.verify_credential(vc_dict)
        assert result.valid is False

    def test_verify_wrong_issuer_rejected(self, rsa_pem: str) -> None:
        """A credential with an issuer DID not matching this platform is rejected."""
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VerifiableCredential,
        )
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        did = did_svc.generate_did_web("acme")
        key_id = f"{did}#key-1"

        subject = CredentialSubject(
            id="urn:uuid:test-dpp",
            aas_id="urn:uuid:test-dpp",
            digest_sha256="abc123",
        )
        vc = VerifiableCredential(
            id="urn:uuid:test-vc",
            issuer="did:web:evil.com:t:acme",  # wrong platform
            issuance_date="2026-01-01T00:00:00Z",
            credential_subject=subject,
        )
        proof = vc_svc._create_jws_proof(
            payload=vc.model_dump(by_alias=True, exclude={"proof"}),
            did=did,
            key_id=key_id,
        )
        vc.proof = proof
        vc_dict = vc.model_dump(by_alias=True)

        result = vc_svc.verify_credential(vc_dict)
        assert result.valid is False
        assert any("issuer" in e.lower() for e in result.errors)

    def test_verify_missing_issuer_rejected(self, rsa_pem: str) -> None:
        """A credential with no issuer field is rejected."""
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        result = vc_svc.verify_credential(
            {
                "proof": {"jws": "eyJhbGciOiJSUzI1NiJ9.test.sig"},
            }
        )
        assert result.valid is False
        assert any("issuer" in e.lower() for e in result.errors)

    def test_verify_expired_credential(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VerifiableCredential,
        )
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        did = did_svc.generate_did_web("acme")
        key_id = f"{did}#key-1"

        subject = CredentialSubject(
            id="urn:uuid:test-dpp",
            aas_id="urn:uuid:test-dpp",
            digest_sha256="abc123",
        )
        vc = VerifiableCredential(
            id="urn:uuid:test-vc",
            issuer=did,
            issuance_date="2020-01-01T00:00:00Z",
            expiration_date="2020-06-01T00:00:00+00:00",
            credential_subject=subject,
        )
        proof = vc_svc._create_jws_proof(
            payload=vc.model_dump(by_alias=True, exclude={"proof"}),
            did=did,
            key_id=key_id,
        )
        vc.proof = proof
        vc_dict = vc.model_dump(by_alias=True)

        result = vc_svc.verify_credential(vc_dict)
        assert result.valid is False
        assert any("expired" in e.lower() for e in result.errors)

    def test_verify_tampered_credential_body_fails(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VerifiableCredential,
        )
        from app.modules.credentials.vc import VCService

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        did = did_svc.generate_did_web("acme")
        key_id = f"{did}#key-1"

        subject = CredentialSubject(
            id="urn:uuid:test-dpp",
            aas_id="urn:uuid:test-dpp",
            digest_sha256="abc123",
        )
        vc = VerifiableCredential(
            id="urn:uuid:test-vc",
            issuer=did,
            issuance_date="2026-01-01T00:00:00Z",
            credential_subject=subject,
        )
        proof = vc_svc._create_jws_proof(
            payload=vc.model_dump(by_alias=True, exclude={"proof"}),
            did=did,
            key_id=key_id,
        )
        vc.proof = proof
        vc_dict = vc.model_dump(by_alias=True)

        # Tamper credential body while keeping the original proof.
        vc_dict["credentialSubject"]["digestSHA256"] = "tampered"

        result = vc_svc.verify_credential(vc_dict)
        assert result.valid is False
        assert any("proof hash does not match" in e.lower() for e in result.errors)

    def test_verify_legacy_proof_binding_still_supported(self, rsa_pem: str) -> None:
        from app.modules.credentials.did import DIDService
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VCProof,
            VerifiableCredential,
        )
        from app.modules.credentials.vc import VCService, _detect_algorithm

        did_svc = DIDService(
            base_url="https://dpp-platform.dev",
            signing_key_pem=rsa_pem,
        )
        vc_svc = VCService(did_svc)
        did = did_svc.generate_did_web("acme")
        key_id = f"{did}#key-1"

        subject = CredentialSubject(
            id="urn:uuid:test-dpp",
            aas_id="urn:uuid:test-dpp",
            digest_sha256="abc123",
        )
        vc = VerifiableCredential(
            id="urn:uuid:test-vc",
            issuer=did,
            issuance_date="2026-01-01T00:00:00Z",
            credential_subject=subject,
        )
        payload = vc.model_dump(by_alias=True, exclude={"proof"})
        legacy_canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        token = jwt.encode(
            {"vc": legacy_canonical, "iss": did, "iat": 1_700_000_000},
            did_svc.private_key,
            algorithm=_detect_algorithm(did_svc.private_key),
            headers={"kid": key_id},
        )
        vc.proof = VCProof(
            created="2026-01-01T00:00:00Z",
            verification_method=key_id,
            proof_purpose="assertionMethod",
            jws=token,
        )

        result = vc_svc.verify_credential(vc.model_dump(by_alias=True))
        assert result.valid is True
        assert result.errors == []


class TestCredentialPublicRouter:
    @pytest.mark.asyncio
    @patch("app.modules.credentials.public_router._get_did_service")
    @patch("app.modules.credentials.public_router.get_settings")
    async def test_get_public_jwks_returns_key_with_kid(
        self,
        mock_get_settings: MagicMock,
        mock_get_did_service: MagicMock,
    ) -> None:
        from app.modules.credentials.public_router import get_public_jwks

        did_service = MagicMock()
        did_service.export_public_jwk.return_value = {"kty": "RSA", "n": "abc", "e": "AQAB"}
        mock_get_did_service.return_value = did_service

        settings = MagicMock()
        settings.dpp_signing_key_id = "dpp-signing-kid"
        mock_get_settings.return_value = settings

        response = await get_public_jwks()

        assert response == {
            "keys": [
                {
                    "kty": "RSA",
                    "n": "abc",
                    "e": "AQAB",
                    "kid": "dpp-signing-kid",
                }
            ]
        }


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_verifiable_credential_serialization(self) -> None:
        from app.modules.credentials.schemas import (
            CredentialSubject,
            VerifiableCredential,
        )

        subject = CredentialSubject(
            id="urn:uuid:123",
            aas_id="urn:uuid:123",
            digest_sha256="abc",
        )
        vc = VerifiableCredential(
            id="urn:uuid:vc-1",
            issuer="did:web:example.com",
            issuance_date="2026-01-01T00:00:00Z",
            credential_subject=subject,
        )
        data = vc.model_dump(by_alias=True)
        assert data["@context"] == ["https://www.w3.org/ns/credentials/v2"]
        assert data["credentialSubject"]["aasId"] == "urn:uuid:123"
        assert data["issuanceDate"] == "2026-01-01T00:00:00Z"

    def test_did_document_serialization(self) -> None:
        from app.modules.credentials.schemas import (
            DIDDocument,
            VerificationMethod,
        )

        doc = DIDDocument(
            id="did:web:test",
            verification_method=[
                VerificationMethod(
                    id="did:web:test#key-1",
                    controller="did:web:test",
                    public_key_jwk={"kty": "RSA", "n": "abc", "e": "AQAB"},
                )
            ],
            authentication=["did:web:test#key-1"],
            assertion_method=["did:web:test#key-1"],
        )
        data = doc.model_dump(by_alias=True)
        assert "@context" in data
        assert data["verificationMethod"][0]["publicKeyJwk"]["kty"] == "RSA"

    def test_vc_verify_response(self) -> None:
        from app.modules.credentials.schemas import VCVerifyResponse

        resp = VCVerifyResponse(
            valid=False,
            errors=["Bad signature"],
            issuer_did="did:web:test",
        )
        assert resp.valid is False
        assert len(resp.errors) == 1
