"""IDTA-01002 AAS Repository operations backed by PostgreSQL DPP storage."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DPP, DPPRevision, DPPStatus
from app.modules.dpps.idta_schemas import decode_cursor, encode_cursor


class AASRepositoryService:
    """IDTA-01002 AAS Repository operations backed by PostgreSQL DPP storage."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_shell_by_aas_id(
        self,
        tenant_id: UUID,
        aas_id: str,
    ) -> DPP | None:
        """Look up a published DPP by its AAS ID.

        The AAS ID may be:
        - A globalAssetId stored in asset_ids JSONB
        - The canonical urn:uuid:{dpp.id} form
        """
        # Try urn:uuid: form first
        if aas_id.startswith("urn:uuid:"):
            uuid_str = aas_id[len("urn:uuid:") :]
            try:
                dpp_uuid = UUID(uuid_str)
                result = await self._session.execute(
                    select(DPP).where(
                        DPP.id == dpp_uuid,
                        DPP.tenant_id == tenant_id,
                        DPP.status == DPPStatus.PUBLISHED,
                    )
                )
                dpp = result.scalar_one_or_none()
                if dpp:
                    return dpp
            except ValueError:
                pass

        # Search by globalAssetId via JSONB @> containment (uses GIN index)
        result = await self._session.execute(
            select(DPP).where(
                DPP.tenant_id == tenant_id,
                DPP.status == DPPStatus.PUBLISHED,
                DPP.asset_ids.op("@>")(cast({"globalAssetId": aas_id}, JSONB)),
            )
        )
        return result.scalar_one_or_none()

    async def get_published_revision(
        self,
        dpp: DPP,
    ) -> DPPRevision | None:
        """Get the current published revision for a DPP."""
        if not dpp.current_published_revision_id:
            return None
        result = await self._session.execute(
            select(DPPRevision).where(
                DPPRevision.id == dpp.current_published_revision_id,
                DPPRevision.tenant_id == dpp.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_published_revisions_batch(
        self,
        dpps: list[DPP],
    ) -> dict[UUID, DPPRevision]:
        """Batch-fetch published revisions for multiple DPPs in one query."""
        rev_ids = [
            dpp.current_published_revision_id for dpp in dpps if dpp.current_published_revision_id
        ]
        if not rev_ids:
            return {}
        result = await self._session.execute(select(DPPRevision).where(DPPRevision.id.in_(rev_ids)))
        return {rev.id: rev for rev in result.scalars().all()}

    @staticmethod
    def get_submodel_from_revision(
        aas_env: dict[str, Any],
        submodel_id: str,
    ) -> dict[str, Any] | None:
        """Extract a specific submodel by ID from an AAS environment JSON."""
        submodels: list[dict[str, Any]] = aas_env.get("submodels", [])
        for submodel in submodels:
            if submodel.get("id") == submodel_id:
                return submodel
        return None

    @staticmethod
    def list_submodel_ids(aas_env: dict[str, Any]) -> list[str]:
        """List all submodel IDs in an AAS environment."""
        return [sm.get("id", "") for sm in aas_env.get("submodels", [])]

    async def list_published_shells(
        self,
        tenant_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[DPP], str | None]:
        """List published DPPs with cursor-based pagination.

        Returns (results, next_cursor_or_None).
        Cursor is a base64url-encoded UUID of the last item.
        """
        stmt = (
            select(DPP)
            .where(
                DPP.tenant_id == tenant_id,
                DPP.status == DPPStatus.PUBLISHED,
            )
            .order_by(DPP.id)
        )
        if cursor:
            cursor_uuid = decode_cursor(cursor)
            stmt = stmt.where(DPP.id > cursor_uuid)
        # Fetch one extra to detect if there is a next page
        stmt = stmt.limit(limit + 1)

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        if len(rows) > limit:
            items = rows[:limit]
            next_cursor = encode_cursor(items[-1].id)
        else:
            items = rows
            next_cursor = None

        return items, next_cursor
