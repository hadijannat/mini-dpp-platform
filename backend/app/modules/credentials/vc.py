"""Verifiable Credential issuance and verification."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DPP, DPPRevision, IssuedCredential
from app.modules.credentials.did import DIDService
from app.modules.credentials.schemas import (
    CredentialSubject,
    VCProof,
    VCVerifyResponse,
    VerifiableCredential,
)


class VCService:
    """Issue and verify W3C Verifiable Credentials for DPPs."""

    def __init__(self, did_service: DIDService) -> None:
        self._did = did_service

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------

    async def issue_credential(
        self,
        *,
        dpp: DPP,
        revision: DPPRevision,
        tenant_slug: str,
        expiration_days: int = 365,
        created_by: str,
        db: AsyncSession,
    ) -> IssuedCredential:
        """Issue a W3C VC for a published DPP and persist it."""
        did = self._did.generate_did_web(tenant_slug)
        key_id = f"{did}#{self._did.key_id}"
        now = datetime.now(UTC)
        expires = now + timedelta(days=expiration_days)
        vc_id = f"urn:uuid:{uuid.uuid4()}"

        # Extract template semantic ID from AAS environment
        template_sem_id = _extract_template_semantic_id(revision.aas_env_json)

        subject = CredentialSubject(
            id=f"urn:uuid:{dpp.id}",
            aas_id=f"urn:uuid:{dpp.id}",
            digest_sha256=revision.digest_sha256 or "",
            template_semantic_id=template_sem_id,
            published_at=now.isoformat(),
        )

        # Build unsigned credential
        vc = VerifiableCredential(
            id=vc_id,
            issuer=did,
            issuance_date=now.isoformat(),
            expiration_date=expires.isoformat(),
            credential_subject=subject,
        )

        # Sign
        proof = self._create_jws_proof(
            payload=vc.model_dump(by_alias=True, exclude={"proof"}),
            did=did,
            key_id=key_id,
        )
        vc.proof = proof
        vc_json = vc.model_dump(by_alias=True)

        # Persist
        record = IssuedCredential(
            tenant_id=dpp.tenant_id,
            dpp_id=dpp.id,
            credential_json=vc_json,
            issuer_did=did,
            subject_id=f"urn:uuid:{dpp.id}",
            issuance_date=now,
            expiration_date=expires,
            created_by_subject=created_by,
        )
        db.add(record)
        await db.flush()
        return record

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_credential(self, credential: dict[str, Any]) -> VCVerifyResponse:
        """Verify a submitted Verifiable Credential.

        Validates:
        1. Structural completeness (proof, JWS present)
        2. Issuer DID matches this platform's key (only locally-issued VCs accepted)
        3. JWS signature against the platform's public key
        4. Credential expiration
        """
        errors: list[str] = []

        # Basic structure checks
        if "proof" not in credential:
            errors.append("Missing 'proof' field")
            return VCVerifyResponse(
                valid=False,
                errors=errors,
                issuer_did=credential.get("issuer"),
                subject_id=_extract_subject_id(credential),
            )

        proof = credential["proof"]
        jws_token = proof.get("jws", "")
        if not jws_token:
            errors.append("Missing JWS in proof")
            return VCVerifyResponse(
                valid=False,
                errors=errors,
                issuer_did=credential.get("issuer"),
                subject_id=_extract_subject_id(credential),
            )

        # Validate issuer DID belongs to this platform
        issuer_did = credential.get("issuer", "")
        expected_prefix = self._did.did_web_prefix
        if not issuer_did or not issuer_did.startswith(expected_prefix):
            errors.append("Credential issuer does not match this platform")
            return VCVerifyResponse(
                valid=False,
                errors=errors,
                issuer_did=issuer_did or None,
                subject_id=_extract_subject_id(credential),
            )

        # Verify JWS signature using only the algorithm matching our key type
        try:
            algorithm = _detect_algorithm(self._did.private_key)
            public_key = self._did.private_key.public_key()
            jwt.decode(
                jws_token,
                public_key,
                algorithms=[algorithm],
                options={"verify_exp": False, "verify_aud": False},
            )
        except jwt.InvalidTokenError as e:
            errors.append(f"Invalid JWS signature: {e}")
        except Exception as e:
            errors.append(f"Verification error: {e}")

        # Check expiration
        exp_date = credential.get("expirationDate")
        if exp_date:
            try:
                exp_dt = datetime.fromisoformat(exp_date)
                if exp_dt < datetime.now(UTC):
                    errors.append("Credential has expired")
            except ValueError:
                errors.append("Invalid expirationDate format")

        return VCVerifyResponse(
            valid=len(errors) == 0,
            errors=errors,
            issuer_did=credential.get("issuer"),
            subject_id=_extract_subject_id(credential),
        )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    async def get_credential_for_dpp(
        self, dpp_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession
    ) -> IssuedCredential | None:
        """Get the issued credential for a DPP."""
        stmt = select(IssuedCredential).where(
            IssuedCredential.dpp_id == dpp_id,
            IssuedCredential.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_credentials(
        self,
        tenant_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IssuedCredential]:
        """List issued credentials for a tenant."""
        stmt = (
            select(IssuedCredential)
            .where(IssuedCredential.tenant_id == tenant_id)
            .order_by(IssuedCredential.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_jws_proof(
        self,
        payload: dict[str, Any],
        did: str,
        key_id: str,
    ) -> VCProof:
        """Create a JWS proof over the credential payload."""
        now = datetime.now(UTC)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        algorithm = _detect_algorithm(self._did.private_key)
        token: str = jwt.encode(
            {"vc": canonical, "iss": did, "iat": int(now.timestamp())},
            self._did.private_key,
            algorithm=algorithm,
            headers={"kid": key_id},
        )
        return VCProof(
            created=now.isoformat(),
            verification_method=key_id,
            proof_purpose="assertionMethod",
            jws=token,
        )


# ======================================================================
# Helpers
# ======================================================================

_PrivateKeyTypes = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey | ed25519.Ed25519PrivateKey


def _detect_algorithm(key: _PrivateKeyTypes) -> str:
    if isinstance(key, rsa.RSAPrivateKey):
        return "RS256"
    if isinstance(key, ec.EllipticCurvePrivateKey):
        curve = key.curve
        if isinstance(curve, ec.SECP384R1):
            return "ES384"
        if isinstance(curve, ec.SECP521R1):
            return "ES512"
        return "ES256"
    if isinstance(key, ed25519.Ed25519PrivateKey):
        return "EdDSA"
    return "RS256"


def _extract_template_semantic_id(
    aas_env: dict[str, Any],
) -> str | None:
    """Extract the first submodel semantic ID from AAS environment."""
    submodels = aas_env.get("submodels", [])
    if not submodels:
        return None
    first = submodels[0]
    sem = first.get("semanticId", {})
    keys = sem.get("keys", [])
    if keys:
        return str(keys[0].get("value", ""))
    return None


def _extract_subject_id(credential: dict[str, Any]) -> str | None:
    """Extract credentialSubject.id from a VC dict."""
    subject = credential.get("credentialSubject", {})
    if isinstance(subject, dict):
        return subject.get("id")
    return None
