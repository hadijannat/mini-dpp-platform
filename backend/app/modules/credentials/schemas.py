"""Pydantic schemas for W3C Verifiable Credentials and DID Documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# DID Document (W3C DID Core v1.0)
# ---------------------------------------------------------------------------


class VerificationMethod(BaseModel):
    """A single verification method in a DID Document."""

    id: str
    type: str = "JsonWebKey2020"
    controller: str
    public_key_jwk: dict[str, Any] = Field(alias="publicKeyJwk")

    model_config = ConfigDict(populate_by_name=True)


class DIDDocument(BaseModel):
    """W3C DID Document structure."""

    context: list[str] = Field(
        alias="@context",
        default=[
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/jws-2020/v1",
        ],
    )
    id: str
    verification_method: list[VerificationMethod] = Field(
        alias="verificationMethod",
    )
    authentication: list[str]
    assertion_method: list[str] = Field(alias="assertionMethod")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Verifiable Credential (W3C VC Data Model 2.0)
# ---------------------------------------------------------------------------


class CredentialSubject(BaseModel):
    """Subject of a Digital Product Passport credential."""

    id: str  # urn:uuid:{dpp_id}
    type: str = "DigitalProductPassport"
    aas_id: str = Field(alias="aasId")
    digest_sha256: str = Field(alias="digestSHA256")
    template_semantic_id: str | None = Field(default=None, alias="templateSemanticId")
    published_at: str | None = Field(default=None, alias="publishedAt")

    model_config = ConfigDict(populate_by_name=True)


class VCProof(BaseModel):
    """JsonWebSignature2020 proof for a Verifiable Credential."""

    type: str = "JsonWebSignature2020"
    created: str
    verification_method: str = Field(alias="verificationMethod")
    proof_purpose: str = Field(alias="proofPurpose", default="assertionMethod")
    jws: str

    model_config = ConfigDict(populate_by_name=True)


class VerifiableCredential(BaseModel):
    """W3C Verifiable Credential Data Model 2.0."""

    context: list[str] = Field(
        alias="@context",
        default=["https://www.w3.org/ns/credentials/v2"],
    )
    id: str
    type: list[str] = [
        "VerifiableCredential",
        "DigitalProductPassportCredential",
    ]
    issuer: str
    issuance_date: str = Field(alias="issuanceDate")
    expiration_date: str | None = Field(default=None, alias="expirationDate")
    credential_subject: CredentialSubject = Field(
        alias="credentialSubject",
    )
    proof: VCProof | None = None

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class VCIssueRequest(BaseModel):
    """Request body for issuing a Verifiable Credential."""

    expiration_days: int = Field(default=365, ge=1, le=3650)


class VCVerifyRequest(BaseModel):
    """Request body for verifying a Verifiable Credential."""

    credential: dict[str, Any]


class VCVerifyResponse(BaseModel):
    """Response from VC verification."""

    valid: bool
    errors: list[str] = []
    issuer_did: str | None = None
    subject_id: str | None = None


class IssuedCredentialResponse(BaseModel):
    """API response for an issued credential."""

    id: UUID
    dpp_id: UUID
    issuer_did: str
    subject_id: str
    issuance_date: datetime
    expiration_date: datetime | None = None
    revoked: bool = False
    credential: dict[str, Any]
    created_at: datetime
