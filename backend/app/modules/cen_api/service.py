"""Service layer for CEN prEN 18222 facade routes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    DPP,
    DPPIdentifier,
    DPPStatus,
    ExternalIdentifier,
    ExternalIdentifierStatus,
    IdentifierEntityType,
    VisibilityScope,
)
from app.db.models import (
    DataCarrierIdentityLevel as DBGranularity,
)
from app.modules.cen_api.schemas import CENDPPResponse
from app.modules.dpps.idta_schemas import decode_cursor, encode_cursor
from app.modules.dpps.service import DPPService
from app.modules.identifiers.schemas import IdentifierEntityType as SchemaEntityType
from app.modules.identifiers.schemas import IdentifierGranularity
from app.modules.identifiers.service import IdentifierModuleService
from app.modules.registry.service import BuiltInRegistryService
from app.modules.resolver.service import ResolverService
from app.standards.cen_pren.identifiers_18219 import IdentifierGovernanceError, IdentifierService

_IDENTIFIER_CRITICAL_KEYS = frozenset(
    {"manufacturerPartId", "serialNumber", "batchId", "globalAssetId", "gtin"}
)


class CENAPIError(ValueError):
    """Base CEN facade error."""


class CENAPINotFoundError(CENAPIError):
    """Raised when a requested resource does not exist."""


class CENAPIConflictError(CENAPIError):
    """Raised when requested mutation conflicts with lifecycle rules."""


class CENFeatureDisabledError(CENAPIError):
    """Raised when dependent subsystem is disabled in config."""


def _to_schema_entity_type(entity_type: IdentifierEntityType) -> SchemaEntityType:
    return SchemaEntityType(entity_type.value)


def _to_db_granularity(granularity: IdentifierGranularity | None) -> DBGranularity | None:
    if granularity is None:
        return None
    return DBGranularity(granularity.value)


def _to_schema_granularity(granularity: DBGranularity | None) -> IdentifierGranularity | None:
    if granularity is None:
        return None
    return IdentifierGranularity(granularity.value)


def _normalize_status(status: str | None) -> DPPStatus | None:
    if status is None:
        return None
    normalized = status.strip().lower()
    if not normalized:
        return None
    try:
        return DPPStatus(normalized)
    except ValueError as exc:
        raise CENAPIError(f"Unsupported status filter '{status}'") from exc


class CENAPIService:
    """Adapter service mapping CEN facade operations onto existing domain services."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._dpp_service = DPPService(session)
        self._identifier_service = IdentifierService(session)
        self._identifier_module = IdentifierModuleService(session)

    async def create_dpp(
        self,
        *,
        tenant_id: UUID,
        tenant_slug: str,
        owner_subject: str,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any] | None,
        required_specific_asset_ids: list[str] | None,
    ) -> DPP:
        return await self._dpp_service.create_dpp(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            owner_subject=owner_subject,
            asset_ids=asset_ids,
            selected_templates=selected_templates,
            initial_data=initial_data,
            required_specific_asset_ids=required_specific_asset_ids,
        )

    async def get_dpp(self, *, tenant_id: UUID, dpp_id: UUID) -> DPP:
        dpp = await self._dpp_service.get_dpp(dpp_id=dpp_id, tenant_id=tenant_id)
        if dpp is None:
            raise CENAPINotFoundError("DPP not found")
        return dpp

    async def get_published_dpp(self, *, tenant_id: UUID, dpp_id: UUID) -> DPP:
        dpp = await self.get_dpp(tenant_id=tenant_id, dpp_id=dpp_id)
        if dpp.status != DPPStatus.PUBLISHED:
            raise CENAPINotFoundError("DPP not found")
        return dpp

    async def search_dpps(
        self,
        *,
        tenant_id: UUID,
        limit: int,
        cursor: str | None,
        identifier: str | None,
        scheme: str | None,
        status: str | None,
        published_only: bool = False,
        user_subject: str | None = None,
        is_tenant_admin: bool = False,
    ) -> tuple[list[DPP], str | None]:
        status_filter = DPPStatus.PUBLISHED if published_only else _normalize_status(status)

        stmt: Select[tuple[UUID]] = select(DPP.id).where(DPP.tenant_id == tenant_id)
        if status_filter is not None:
            stmt = stmt.where(DPP.status == status_filter)
        if cursor:
            stmt = stmt.where(DPP.id > decode_cursor(cursor))

        if user_subject is not None and not published_only and not is_tenant_admin:
            shared_ids = await self._dpp_service.get_shared_resource_ids(
                tenant_id=tenant_id,
                resource_type="dpp",
                user_subject=user_subject,
            )
            access_conditions = [
                DPP.owner_subject == user_subject,
                DPP.visibility_scope == VisibilityScope.TENANT,
            ]
            if shared_ids:
                access_conditions.append(DPP.id.in_(shared_ids))
            stmt = stmt.where(or_(*access_conditions))

        scheme_code = scheme.strip().lower() if scheme else None
        identifier_value = identifier.strip() if identifier else None
        if scheme_code is not None or identifier_value is not None:
            stmt = (
                stmt.join(DPPIdentifier, DPPIdentifier.dpp_id == DPP.id)
                .join(
                    ExternalIdentifier,
                    ExternalIdentifier.id == DPPIdentifier.external_identifier_id,
                )
                .where(
                    ExternalIdentifier.entity_type == IdentifierEntityType.PRODUCT,
                    ExternalIdentifier.status == ExternalIdentifierStatus.ACTIVE,
                )
            )
            if scheme_code is not None:
                stmt = stmt.where(ExternalIdentifier.scheme_code == scheme_code)
            if identifier_value is not None:
                if scheme_code is not None:
                    try:
                        canonical = self._identifier_service.canonicalize(
                            scheme_code=scheme_code,
                            value_raw=identifier_value,
                        )
                    except IdentifierGovernanceError as exc:
                        raise CENAPIError(str(exc)) from exc
                    stmt = stmt.where(ExternalIdentifier.value_canonical == canonical)
                else:
                    stmt = stmt.where(
                        or_(
                            ExternalIdentifier.value_canonical == identifier_value,
                            ExternalIdentifier.value_raw == identifier_value,
                        )
                    )

        stmt = stmt.distinct().order_by(DPP.id).limit(limit + 1)
        result = await self._session.execute(stmt)
        ids = list(result.scalars().all())
        has_more = len(ids) > limit
        page_ids = ids[:limit]
        if not page_ids:
            return [], None

        rows = await self._session.execute(
            select(DPP).where(DPP.tenant_id == tenant_id, DPP.id.in_(page_ids)).order_by(DPP.id)
        )
        dpps = list(rows.scalars().all())
        next_cursor = encode_cursor(page_ids[-1]) if has_more else None
        return dpps, next_cursor

    async def read_dpp_by_identifier(
        self,
        *,
        tenant_id: UUID,
        scheme: str,
        identifier: str,
        published_only: bool = False,
        user_subject: str | None = None,
        is_tenant_admin: bool = False,
    ) -> DPP:
        dpps, _ = await self.search_dpps(
            tenant_id=tenant_id,
            limit=1,
            cursor=None,
            identifier=identifier,
            scheme=scheme,
            status=DPPStatus.PUBLISHED.value if published_only else None,
            published_only=published_only,
            user_subject=user_subject,
            is_tenant_admin=is_tenant_admin,
        )
        if not dpps:
            raise CENAPINotFoundError("DPP not found for identifier")
        return dpps[0]

    async def update_dpp(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        updated_by: str,
        asset_ids_patch: dict[str, Any] | None,
        visibility_scope: str | None,
    ) -> DPP:
        dpp = await self.get_dpp(tenant_id=tenant_id, dpp_id=dpp_id)

        if asset_ids_patch is not None:
            current_asset_ids = dict(dpp.asset_ids or {})
            merged_asset_ids = {**current_asset_ids, **asset_ids_patch}

            if dpp.status == DPPStatus.PUBLISHED and self._identifier_critical_fields_changed(
                before=current_asset_ids,
                after=merged_asset_ids,
            ):
                raise CENAPIConflictError(
                    "Published DPP identifier fields are immutable; supersede identifiers instead."
                )

            dpp.asset_ids = merged_asset_ids
            if self._settings.cen_dpp_enabled:
                try:
                    await self._identifier_service.ensure_dpp_product_identifier_from_asset_ids(
                        dpp=dpp,
                        created_by=updated_by,
                    )
                except IdentifierGovernanceError as exc:
                    raise CENAPIError(str(exc)) from exc

        if visibility_scope is not None:
            try:
                dpp.visibility_scope = VisibilityScope(visibility_scope)
            except ValueError as exc:
                raise CENAPIError("visibility_scope must be owner_team or tenant") from exc

        await self._session.flush()
        return dpp

    async def archive_dpp(self, *, tenant_id: UUID, dpp_id: UUID) -> DPP:
        try:
            return await self._dpp_service.archive_dpp(dpp_id=dpp_id, tenant_id=tenant_id)
        except ValueError as exc:
            message = str(exc)
            if "not found" in message.lower():
                raise CENAPINotFoundError(message) from exc
            raise CENAPIConflictError(message) from exc

    async def publish_dpp(self, *, tenant_id: UUID, dpp_id: UUID, published_by: str) -> DPP:
        try:
            return await self._dpp_service.publish_dpp(
                dpp_id=dpp_id,
                tenant_id=tenant_id,
                published_by_subject=published_by,
            )
        except ValueError as exc:
            message = str(exc)
            if "not found" in message.lower():
                raise CENAPINotFoundError(message) from exc
            raise CENAPIConflictError(message) from exc

    async def validate_identifier(
        self,
        *,
        entity_type: IdentifierEntityType,
        scheme_code: str,
        value_raw: str,
        granularity: IdentifierGranularity | None,
    ) -> str:
        try:
            canonical = self._identifier_service.canonicalize(
                scheme_code=scheme_code,
                value_raw=value_raw,
            )
            self._identifier_service.validate(
                scheme_code=scheme_code,
                value_canonical=canonical,
                entity_type=entity_type,
                granularity=_to_db_granularity(granularity),
            )
        except IdentifierGovernanceError as exc:
            raise CENAPIError(str(exc)) from exc
        return canonical

    async def register_identifier(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        entity_type: IdentifierEntityType,
        scheme_code: str,
        value_raw: str,
        granularity: IdentifierGranularity | None,
        dpp_id: UUID | None,
        operator_id: UUID | None,
        facility_id: UUID | None,
    ) -> ExternalIdentifier:
        try:
            return await self._identifier_module.register_identifier(
                tenant_id=tenant_id,
                created_by=created_by,
                entity_type=entity_type,
                scheme_code=scheme_code,
                value_raw=value_raw,
                granularity=_to_db_granularity(granularity),
                dpp_id=dpp_id,
                operator_id=operator_id,
                facility_id=facility_id,
            )
        except IdentifierGovernanceError as exc:
            raise CENAPIError(str(exc)) from exc

    async def supersede_identifier(
        self,
        *,
        tenant_id: UUID,
        identifier_id: UUID,
        replacement_identifier_id: UUID,
    ) -> ExternalIdentifier:
        try:
            return await self._identifier_module.supersede_identifier(
                tenant_id=tenant_id,
                identifier_id=identifier_id,
                replacement_identifier_id=replacement_identifier_id,
            )
        except IdentifierGovernanceError as exc:
            raise CENAPIError(str(exc)) from exc

    async def sync_registry_for_dpp(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        created_by: str,
    ) -> None:
        if not self._settings.registry_enabled:
            raise CENFeatureDisabledError("Registry integration is disabled")
        dpp = await self.get_published_dpp(tenant_id=tenant_id, dpp_id=dpp_id)
        revision = await self._dpp_service.get_published_revision(
            dpp_id=dpp.id, tenant_id=tenant_id
        )
        if revision is None:
            raise CENAPIConflictError("Published revision not found")

        service = BuiltInRegistryService(self._session)
        submodel_base_url = (
            self._settings.cors_origins[0]
            if self._settings.cors_origins
            else "http://localhost:8000"
        )
        await service.auto_register_from_dpp(
            dpp=dpp,
            revision=revision,
            tenant_id=tenant_id,
            created_by=created_by,
            submodel_base_url=submodel_base_url,
        )

    async def sync_resolver_for_dpp(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        created_by: str,
    ) -> None:
        if not self._settings.resolver_enabled:
            raise CENFeatureDisabledError("Resolver integration is disabled")
        dpp = await self.get_published_dpp(tenant_id=tenant_id, dpp_id=dpp_id)
        service = ResolverService(self._session)
        base_url = self._settings.resolver_base_url
        if not base_url:
            base_url = (
                self._settings.cors_origins[0]
                if self._settings.cors_origins
                else "http://localhost:8000"
            )
        await service.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url=base_url,
        )

    async def to_cen_dpp_response(
        self,
        dpp: DPP,
        *,
        primary_identifier: ExternalIdentifier | None = None,
    ) -> CENDPPResponse:
        resolved_identifier = primary_identifier
        if resolved_identifier is None:
            resolved_identifier = await self._get_primary_product_identifier(
                tenant_id=dpp.tenant_id,
                dpp_id=dpp.id,
            )
        return CENDPPResponse(
            id=dpp.id,
            platform_id=dpp.id,
            status=dpp.status.value,
            asset_ids=dpp.asset_ids or {},
            product_identifier=(
                resolved_identifier.value_canonical if resolved_identifier else None
            ),
            identifier_scheme=(resolved_identifier.scheme_code if resolved_identifier else None),
            granularity=_to_schema_granularity(
                resolved_identifier.granularity if resolved_identifier else None
            ),
            created_at=dpp.created_at,
            updated_at=dpp.updated_at,
        )

    async def _get_primary_product_identifier(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
    ) -> ExternalIdentifier | None:
        stmt = (
            select(ExternalIdentifier)
            .join(DPPIdentifier, DPPIdentifier.external_identifier_id == ExternalIdentifier.id)
            .where(
                DPPIdentifier.tenant_id == tenant_id,
                DPPIdentifier.dpp_id == dpp_id,
                ExternalIdentifier.entity_type == IdentifierEntityType.PRODUCT,
                ExternalIdentifier.status == ExternalIdentifierStatus.ACTIVE,
            )
            .order_by(ExternalIdentifier.issued_at.desc(), ExternalIdentifier.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_primary_product_identifiers_for_dpps(
        self,
        *,
        tenant_id: UUID,
        dpp_ids: Sequence[UUID],
    ) -> dict[UUID, ExternalIdentifier]:
        if not dpp_ids:
            return {}

        stmt = (
            select(DPPIdentifier.dpp_id, ExternalIdentifier)
            .join(ExternalIdentifier, DPPIdentifier.external_identifier_id == ExternalIdentifier.id)
            .where(
                DPPIdentifier.tenant_id == tenant_id,
                DPPIdentifier.dpp_id.in_(list(dpp_ids)),
                ExternalIdentifier.entity_type == IdentifierEntityType.PRODUCT,
                ExternalIdentifier.status == ExternalIdentifierStatus.ACTIVE,
            )
            .order_by(
                DPPIdentifier.dpp_id.asc(),
                ExternalIdentifier.issued_at.desc(),
                ExternalIdentifier.created_at.desc(),
            )
        )
        result = await self._session.execute(stmt)
        mapping: dict[UUID, ExternalIdentifier] = {}
        for dpp_id, external_identifier in result.all():
            if dpp_id not in mapping:
                mapping[dpp_id] = external_identifier
        return mapping

    @staticmethod
    def _identifier_critical_fields_changed(
        *,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> bool:
        for key in _IDENTIFIER_CRITICAL_KEYS:
            if str(before.get(key, "")).strip() != str(after.get(key, "")).strip():
                return True
        return False

    @staticmethod
    def identifiers_to_response(identifier: ExternalIdentifier) -> dict[str, Any]:
        return {
            "id": identifier.id,
            "tenant_id": identifier.tenant_id,
            "entity_type": _to_schema_entity_type(identifier.entity_type),
            "scheme_code": identifier.scheme_code,
            "value_raw": identifier.value_raw,
            "value_canonical": identifier.value_canonical,
            "granularity": _to_schema_granularity(identifier.granularity),
            "status": identifier.status.value,
            "replaced_by_identifier_id": identifier.replaced_by_identifier_id,
            "issued_at": identifier.issued_at,
            "deprecates_at": identifier.deprecates_at,
            "created_by_subject": identifier.created_by_subject,
            "created_at": identifier.created_at,
            "updated_at": identifier.updated_at,
        }

    async def get_public_dpp_responses(
        self,
        *,
        dpps: Sequence[DPP],
    ) -> list[CENDPPResponse]:
        if not dpps:
            return []

        identifiers_by_dpp = await self._get_primary_product_identifiers_for_dpps(
            tenant_id=dpps[0].tenant_id,
            dpp_ids=[dpp.id for dpp in dpps],
        )
        return [
            await self.to_cen_dpp_response(
                dpp,
                primary_identifier=identifiers_by_dpp.get(dpp.id),
            )
            for dpp in dpps
        ]
