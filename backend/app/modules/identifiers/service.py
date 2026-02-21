"""Service layer for identifier governance entities and links."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DPP,
    EconomicOperator,
    ExternalIdentifier,
    ExternalIdentifierStatus,
    Facility,
    FacilityIdentifier,
    IdentifierEntityType,
    OperatorIdentifier,
)
from app.db.models import DataCarrierIdentityLevel as DBGranularity
from app.standards.cen_pren.identifiers_18219 import IdentifierGovernanceError, IdentifierService


class IdentifierModuleService:
    """High-level operations for identifier and entity endpoints."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service = IdentifierService(session)

    async def list_identifiers(
        self,
        *,
        tenant_id: UUID,
        entity_type: IdentifierEntityType | None = None,
        scheme_code: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExternalIdentifier]:
        stmt = select(ExternalIdentifier).where(ExternalIdentifier.tenant_id == tenant_id)
        if entity_type is not None:
            stmt = stmt.where(ExternalIdentifier.entity_type == entity_type)
        if scheme_code is not None:
            stmt = stmt.where(ExternalIdentifier.scheme_code == scheme_code.strip().lower())
        if status is not None:
            try:
                status_value = ExternalIdentifierStatus(status.strip().lower())
            except ValueError as exc:
                raise IdentifierGovernanceError(f"Unsupported status filter '{status}'") from exc
            stmt = stmt.where(ExternalIdentifier.status == status_value)
        stmt = stmt.order_by(ExternalIdentifier.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_identifier(
        self, *, tenant_id: UUID, identifier_id: UUID
    ) -> ExternalIdentifier | None:
        result = await self._session.execute(
            select(ExternalIdentifier).where(
                ExternalIdentifier.id == identifier_id,
                ExternalIdentifier.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def validate_identifier(
        self,
        *,
        scheme_code: str,
        value_raw: str,
        entity_type: IdentifierEntityType,
        granularity: DBGranularity | None,
    ) -> str:
        canonical = self._service.canonicalize(scheme_code, value_raw)
        self._service.validate(
            scheme_code=scheme_code,
            value_canonical=canonical,
            entity_type=entity_type,
            granularity=granularity,
        )
        return canonical

    async def register_identifier(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        entity_type: IdentifierEntityType,
        scheme_code: str,
        value_raw: str,
        granularity: DBGranularity | None,
        dpp_id: UUID | None = None,
        operator_id: UUID | None = None,
        facility_id: UUID | None = None,
    ) -> ExternalIdentifier:
        identifier = await self._service.reserve_or_register(
            tenant_id=tenant_id,
            created_by=created_by,
            entity_type=entity_type,
            scheme_code=scheme_code,
            value_raw=value_raw,
            granularity=granularity,
        )

        if dpp_id is not None:
            await self._assert_dpp_exists(tenant_id=tenant_id, dpp_id=dpp_id)
            await self._service.link_identifier_to_dpp(
                tenant_id=tenant_id,
                dpp_id=dpp_id,
                external_identifier_id=identifier.id,
            )
        if operator_id is not None:
            await self._assert_operator_exists(tenant_id=tenant_id, operator_id=operator_id)
            await self._link_operator_identifier(
                tenant_id=tenant_id,
                operator_id=operator_id,
                external_identifier_id=identifier.id,
            )
        if facility_id is not None:
            await self._assert_facility_exists(tenant_id=tenant_id, facility_id=facility_id)
            await self._link_facility_identifier(
                tenant_id=tenant_id,
                facility_id=facility_id,
                external_identifier_id=identifier.id,
            )

        return identifier

    async def supersede_identifier(
        self,
        *,
        tenant_id: UUID,
        identifier_id: UUID,
        replacement_identifier_id: UUID,
    ) -> ExternalIdentifier:
        return await self._service.supersede(
            tenant_id=tenant_id,
            identifier_id=identifier_id,
            replacement_identifier_id=replacement_identifier_id,
        )

    async def create_operator(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        legal_name: str,
        country: str | None,
        metadata_json: dict[str, object],
    ) -> EconomicOperator:
        operator = EconomicOperator(
            tenant_id=tenant_id,
            legal_name=legal_name.strip(),
            country=country.strip().upper() if country else None,
            metadata_json=metadata_json,
            created_by_subject=created_by,
        )
        self._session.add(operator)
        await self._session.flush()
        return operator

    async def list_operators(
        self, *, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[EconomicOperator]:
        result = await self._session.execute(
            select(EconomicOperator)
            .where(EconomicOperator.tenant_id == tenant_id)
            .order_by(EconomicOperator.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create_facility(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        operator_id: UUID,
        facility_name: str,
        address: dict[str, object],
        metadata_json: dict[str, object],
    ) -> Facility:
        await self._assert_operator_exists(tenant_id=tenant_id, operator_id=operator_id)
        facility = Facility(
            tenant_id=tenant_id,
            operator_id=operator_id,
            facility_name=facility_name.strip(),
            address=address,
            metadata_json=metadata_json,
            created_by_subject=created_by,
        )
        self._session.add(facility)
        await self._session.flush()
        return facility

    async def list_facilities(
        self, *, tenant_id: UUID, operator_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[Facility]:
        stmt = select(Facility).where(Facility.tenant_id == tenant_id)
        if operator_id is not None:
            stmt = stmt.where(Facility.operator_id == operator_id)
        stmt = stmt.order_by(Facility.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _assert_dpp_exists(self, *, tenant_id: UUID, dpp_id: UUID) -> DPP:
        result = await self._session.execute(
            select(DPP).where(DPP.id == dpp_id, DPP.tenant_id == tenant_id)
        )
        dpp = result.scalar_one_or_none()
        if dpp is None:
            raise IdentifierGovernanceError("DPP not found")
        return dpp

    async def _assert_operator_exists(
        self, *, tenant_id: UUID, operator_id: UUID
    ) -> EconomicOperator:
        result = await self._session.execute(
            select(EconomicOperator).where(
                EconomicOperator.id == operator_id,
                EconomicOperator.tenant_id == tenant_id,
            )
        )
        operator = result.scalar_one_or_none()
        if operator is None:
            raise IdentifierGovernanceError("Operator not found")
        return operator

    async def _assert_facility_exists(self, *, tenant_id: UUID, facility_id: UUID) -> Facility:
        result = await self._session.execute(
            select(Facility).where(
                Facility.id == facility_id,
                Facility.tenant_id == tenant_id,
            )
        )
        facility = result.scalar_one_or_none()
        if facility is None:
            raise IdentifierGovernanceError("Facility not found")
        return facility

    async def _link_operator_identifier(
        self,
        *,
        tenant_id: UUID,
        operator_id: UUID,
        external_identifier_id: UUID,
    ) -> OperatorIdentifier:
        existing = await self._session.execute(
            select(OperatorIdentifier).where(
                OperatorIdentifier.tenant_id == tenant_id,
                OperatorIdentifier.operator_id == operator_id,
                OperatorIdentifier.external_identifier_id == external_identifier_id,
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found
        link = OperatorIdentifier(
            tenant_id=tenant_id,
            operator_id=operator_id,
            external_identifier_id=external_identifier_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def _link_facility_identifier(
        self,
        *,
        tenant_id: UUID,
        facility_id: UUID,
        external_identifier_id: UUID,
    ) -> FacilityIdentifier:
        existing = await self._session.execute(
            select(FacilityIdentifier).where(
                FacilityIdentifier.tenant_id == tenant_id,
                FacilityIdentifier.facility_id == facility_id,
                FacilityIdentifier.external_identifier_id == external_identifier_id,
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found
        link = FacilityIdentifier(
            tenant_id=tenant_id,
            facility_id=facility_id,
            external_identifier_id=external_identifier_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link
