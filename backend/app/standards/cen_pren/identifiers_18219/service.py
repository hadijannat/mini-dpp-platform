"""CEN prEN 18219 identifier governance service."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    DPP,
    DataCarrierIdentityLevel,
    DPPIdentifier,
    ExternalIdentifier,
    ExternalIdentifierStatus,
    IdentifierEntityType,
    IdentifierScheme,
)


class IdentifierGovernanceError(ValueError):
    """Raised when identifier governance checks fail."""


class IdentifierService:
    """Canonicalization, validation, registration, and supersede logic."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def get_scheme(self, scheme_code: str) -> IdentifierScheme | None:
        result = await self._session.execute(
            select(IdentifierScheme).where(IdentifierScheme.code == scheme_code.strip().lower())
        )
        return result.scalar_one_or_none()

    def canonicalize(self, scheme_code: str, value_raw: str) -> str:
        scheme = scheme_code.strip().lower()
        raw = value_raw.strip()
        if not raw:
            raise IdentifierGovernanceError("Identifier value cannot be empty")

        if scheme in {"gs1_gtin", "gln"}:
            return "".join(ch for ch in raw if ch.isdigit())
        if scheme == "eori":
            return raw.replace(" ", "").upper()
        if scheme in {"iec61406", "direct_url", "uri", "gs1_epc_tds23"}:
            parsed = urlparse(raw)
            if not parsed.scheme or not parsed.netloc:
                raise IdentifierGovernanceError("URI-based identifier must include scheme and host")
            normalized_scheme = parsed.scheme.lower()
            if normalized_scheme not in {"http", "https"}:
                raise IdentifierGovernanceError("URI-based identifier must use http or https")
            if normalized_scheme == "http" and not self._settings.cen_allow_http_identifiers:
                raise IdentifierGovernanceError(
                    "http identifiers are disabled by CEN profile policy"
                )
            normalized = parsed._replace(
                scheme=normalized_scheme,
                netloc=parsed.netloc.lower(),
                fragment="",
            )
            return urlunparse(normalized)

        return raw

    def validate(
        self,
        *,
        scheme_code: str,
        value_canonical: str,
        entity_type: IdentifierEntityType,
        granularity: DataCarrierIdentityLevel | None = None,
    ) -> None:
        if not value_canonical:
            raise IdentifierGovernanceError("Canonical identifier value cannot be empty")

        scheme = scheme_code.strip().lower()
        if scheme in {"gs1_gtin"} and len(value_canonical) not in {8, 12, 13, 14}:
            raise IdentifierGovernanceError("GS1 GTIN must be 8, 12, 13, or 14 digits")
        if scheme == "gs1_epc_tds23" and "/01/" not in value_canonical:
            raise IdentifierGovernanceError("GS1 EPC TDS 2.3 identifiers must be GS1 Digital Link URIs")
        if scheme == "gln" and len(value_canonical) != 13:
            raise IdentifierGovernanceError("GLN must be 13 digits")
        if scheme == "eori" and len(value_canonical) < 8:
            raise IdentifierGovernanceError("EORI must be at least 8 characters")

        if entity_type == IdentifierEntityType.PRODUCT and granularity is None:
            raise IdentifierGovernanceError("Product identifiers must include granularity")

    async def reserve_or_register(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        entity_type: IdentifierEntityType,
        scheme_code: str,
        value_raw: str,
        granularity: DataCarrierIdentityLevel | None = None,
        issued_at: datetime | None = None,
    ) -> ExternalIdentifier:
        scheme = await self.get_scheme(scheme_code)
        if scheme is None:
            raise IdentifierGovernanceError(f"Unsupported identifier scheme: {scheme_code}")

        canonical = self.canonicalize(scheme.code, value_raw)
        self.validate(
            scheme_code=scheme.code,
            value_canonical=canonical,
            entity_type=entity_type,
            granularity=granularity,
        )

        existing = await self._session.execute(
            select(ExternalIdentifier).where(
                ExternalIdentifier.scheme_code == scheme.code,
                ExternalIdentifier.value_canonical == canonical,
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found

        identifier = ExternalIdentifier(
            tenant_id=tenant_id,
            entity_type=entity_type,
            scheme_code=scheme.code,
            value_raw=value_raw.strip(),
            value_canonical=canonical,
            granularity=granularity,
            status=ExternalIdentifierStatus.ACTIVE,
            issued_at=issued_at or datetime.now(UTC),
            created_by_subject=created_by,
        )
        self._session.add(identifier)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            retry = await self._session.execute(
                select(ExternalIdentifier).where(
                    ExternalIdentifier.scheme_code == scheme.code,
                    ExternalIdentifier.value_canonical == canonical,
                )
            )
            resolved = retry.scalar_one_or_none()
            if resolved is None:
                raise
            return resolved
        return identifier

    async def supersede(
        self,
        *,
        tenant_id: UUID,
        identifier_id: UUID,
        replacement_identifier_id: UUID,
    ) -> ExternalIdentifier:
        result = await self._session.execute(
            select(ExternalIdentifier).where(
                ExternalIdentifier.id == identifier_id,
                ExternalIdentifier.tenant_id == tenant_id,
            )
        )
        current = result.scalar_one_or_none()
        if current is None:
            raise IdentifierGovernanceError("Identifier not found")

        replacement_result = await self._session.execute(
            select(ExternalIdentifier).where(
                ExternalIdentifier.id == replacement_identifier_id,
                ExternalIdentifier.tenant_id == tenant_id,
            )
        )
        replacement = replacement_result.scalar_one_or_none()
        if replacement is None:
            raise IdentifierGovernanceError("Replacement identifier not found")

        current.status = ExternalIdentifierStatus.DEPRECATED
        current.replaced_by_identifier_id = replacement.id
        current.deprecates_at = datetime.now(UTC)
        await self._session.flush()
        return current

    async def link_identifier_to_dpp(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        external_identifier_id: UUID,
    ) -> DPPIdentifier:
        existing = await self._session.execute(
            select(DPPIdentifier).where(
                DPPIdentifier.tenant_id == tenant_id,
                DPPIdentifier.dpp_id == dpp_id,
                DPPIdentifier.external_identifier_id == external_identifier_id,
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found
        link = DPPIdentifier(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            external_identifier_id=external_identifier_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def has_active_product_identifier(self, *, tenant_id: UUID, dpp_id: UUID) -> bool:
        result = await self._session.execute(
            select(DPPIdentifier)
            .join(
                ExternalIdentifier,
                DPPIdentifier.external_identifier_id == ExternalIdentifier.id,
            )
            .where(
                DPPIdentifier.tenant_id == tenant_id,
                DPPIdentifier.dpp_id == dpp_id,
                ExternalIdentifier.entity_type == IdentifierEntityType.PRODUCT,
                ExternalIdentifier.status == ExternalIdentifierStatus.ACTIVE,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def ensure_dpp_product_identifier_from_asset_ids(
        self,
        *,
        dpp: DPP,
        created_by: str,
    ) -> ExternalIdentifier | None:
        asset_ids = dpp.asset_ids or {}
        gtin = str(asset_ids.get("gtin", "")).strip()
        if gtin:
            identifier = await self.reserve_or_register(
                tenant_id=dpp.tenant_id,
                created_by=created_by,
                entity_type=IdentifierEntityType.PRODUCT,
                scheme_code="gs1_gtin",
                value_raw=gtin,
                granularity=DataCarrierIdentityLevel.ITEM,
            )
            await self.link_identifier_to_dpp(
                tenant_id=dpp.tenant_id,
                dpp_id=dpp.id,
                external_identifier_id=identifier.id,
            )
            return identifier

        global_asset_id = str(asset_ids.get("globalAssetId", "")).strip()
        if global_asset_id:
            identifier = await self.reserve_or_register(
                tenant_id=dpp.tenant_id,
                created_by=created_by,
                entity_type=IdentifierEntityType.PRODUCT,
                scheme_code="uri",
                value_raw=global_asset_id,
                granularity=DataCarrierIdentityLevel.ITEM,
            )
            await self.link_identifier_to_dpp(
                tenant_id=dpp.tenant_id,
                dpp_id=dpp.id,
                external_identifier_id=identifier.id,
            )
            return identifier
        return None
