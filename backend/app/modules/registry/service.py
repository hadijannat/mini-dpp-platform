"""Built-in AAS registry service (IDTA-01002-3-1 compliant)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import DPP, AssetDiscoveryMapping, DPPRevision, ShellDescriptorRecord

logger = get_logger(__name__)


class BuiltInRegistryService:
    """Service for managing shell descriptors in the built-in registry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_shell_descriptor(
        self,
        tenant_id: UUID,
        descriptor_create: Any,
        created_by: str,
    ) -> ShellDescriptorRecord:
        """Create a new shell descriptor record."""
        record = ShellDescriptorRecord(
            tenant_id=tenant_id,
            aas_id=descriptor_create.aas_id,
            id_short=descriptor_create.id_short,
            global_asset_id=descriptor_create.global_asset_id,
            specific_asset_ids=descriptor_create.specific_asset_ids,
            submodel_descriptors=descriptor_create.submodel_descriptors,
            dpp_id=descriptor_create.dpp_id,
            created_by_subject=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_shell_descriptor(
        self,
        tenant_id: UUID,
        aas_id: str,
    ) -> ShellDescriptorRecord | None:
        """Look up a shell descriptor by AAS ID within a tenant."""
        result = await self._session.execute(
            select(ShellDescriptorRecord).where(
                ShellDescriptorRecord.tenant_id == tenant_id,
                ShellDescriptorRecord.aas_id == aas_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_shell_descriptor_by_id(
        self,
        shell_id: UUID,
        tenant_id: UUID,
    ) -> ShellDescriptorRecord | None:
        """Look up a shell descriptor by its primary key."""
        result = await self._session.execute(
            select(ShellDescriptorRecord).where(
                ShellDescriptorRecord.id == shell_id,
                ShellDescriptorRecord.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_shell_descriptors(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ShellDescriptorRecord]:
        """List shell descriptors for a tenant."""
        result = await self._session.execute(
            select(ShellDescriptorRecord)
            .where(ShellDescriptorRecord.tenant_id == tenant_id)
            .order_by(ShellDescriptorRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_shell_descriptor(
        self,
        tenant_id: UUID,
        aas_id: str,
        update: Any,
    ) -> ShellDescriptorRecord | None:
        """Update an existing shell descriptor."""
        record = await self.get_shell_descriptor(tenant_id, aas_id)
        if record is None:
            return None

        if update.id_short is not None:
            record.id_short = update.id_short
        if update.global_asset_id is not None:
            record.global_asset_id = update.global_asset_id
        if update.specific_asset_ids is not None:
            record.specific_asset_ids = update.specific_asset_ids
        if update.submodel_descriptors is not None:
            record.submodel_descriptors = update.submodel_descriptors
        if update.dpp_id is not None:
            record.dpp_id = update.dpp_id

        await self._session.flush()
        return record

    async def delete_shell_descriptor(
        self,
        tenant_id: UUID,
        aas_id: str,
    ) -> bool:
        """Delete a shell descriptor by AAS ID. Returns True if deleted."""
        record = await self.get_shell_descriptor(tenant_id, aas_id)
        if record is None:
            return False
        await self._session.delete(record)
        await self._session.flush()
        return True

    async def search_by_asset_id(
        self,
        tenant_id: UUID,
        key: str,
        value: str,
    ) -> list[ShellDescriptorRecord]:
        """Search shell descriptors by a specific asset ID key/value via GIN index."""
        # JSONB containment: specific_asset_ids @> [{"name": key, "value": value}]
        target = [{"name": key, "value": value}]
        result = await self._session.execute(
            select(ShellDescriptorRecord).where(
                ShellDescriptorRecord.tenant_id == tenant_id,
                ShellDescriptorRecord.specific_asset_ids.op("@>")(target),
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Auto-registration from DPP publish
    # ------------------------------------------------------------------

    async def auto_register_from_dpp(
        self,
        dpp: DPP,
        revision: DPPRevision,
        tenant_id: UUID,
        created_by: str,
        submodel_base_url: str,
    ) -> None:
        """Create/upsert shell descriptor + discovery mappings from DPP data."""
        from app.modules.connectors.catenax.mapping import build_shell_descriptor

        shell = build_shell_descriptor(dpp, revision, submodel_base_url)
        payload = shell.to_dtr_payload()

        aas_id: str = payload["id"]
        id_short: str = payload.get("idShort", "")
        global_asset_id: str = payload.get("globalAssetId", "")
        specific_asset_ids: list[dict[str, Any]] = payload.get("specificAssetIds", [])
        submodel_descriptors: list[dict[str, Any]] = payload.get("submodelDescriptors", [])

        # Upsert shell descriptor
        stmt = pg_insert(ShellDescriptorRecord).values(
            tenant_id=tenant_id,
            aas_id=aas_id,
            id_short=id_short,
            global_asset_id=global_asset_id,
            specific_asset_ids=specific_asset_ids,
            submodel_descriptors=submodel_descriptors,
            dpp_id=dpp.id,
            created_by_subject=created_by,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_shell_descriptors_tenant_aas_id",
            set_={
                "id_short": id_short,
                "global_asset_id": global_asset_id,
                "specific_asset_ids": specific_asset_ids,
                "submodel_descriptors": submodel_descriptors,
                "dpp_id": dpp.id,
            },
        )
        await self._session.execute(stmt)

        # Create discovery mappings
        discovery_svc = DiscoveryService(self._session)

        # Map globalAssetId
        if global_asset_id:
            await discovery_svc.upsert_mapping(tenant_id, "globalAssetId", global_asset_id, aas_id)

        # Map each specific asset ID
        for asset_id_entry in specific_asset_ids:
            name = asset_id_entry.get("name", "")
            value = asset_id_entry.get("value", "")
            if name and value:
                await discovery_svc.upsert_mapping(tenant_id, name, value, aas_id)

        await self._session.flush()
        logger.info(
            "auto_registered_shell_descriptor",
            dpp_id=str(dpp.id),
            aas_id=aas_id,
        )


class DiscoveryService:
    """Service for managing asset ID to AAS ID discovery mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_mapping(
        self,
        tenant_id: UUID,
        asset_id_key: str,
        asset_id_value: str,
        aas_id: str,
    ) -> AssetDiscoveryMapping:
        """Create a new discovery mapping."""
        mapping = AssetDiscoveryMapping(
            tenant_id=tenant_id,
            asset_id_key=asset_id_key,
            asset_id_value=asset_id_value,
            aas_id=aas_id,
        )
        self._session.add(mapping)
        await self._session.flush()
        return mapping

    async def upsert_mapping(
        self,
        tenant_id: UUID,
        asset_id_key: str,
        asset_id_value: str,
        aas_id: str,
    ) -> None:
        """Insert a discovery mapping, ignoring conflicts (idempotent)."""
        stmt = pg_insert(AssetDiscoveryMapping).values(
            tenant_id=tenant_id,
            asset_id_key=asset_id_key,
            asset_id_value=asset_id_value,
            aas_id=aas_id,
        )
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_asset_discovery_tenant_key_value_aas",
        )
        await self._session.execute(stmt)

    async def lookup(
        self,
        tenant_id: UUID,
        asset_id_key: str,
        asset_id_value: str,
    ) -> list[str]:
        """Look up AAS IDs for a given asset ID key/value pair."""
        result = await self._session.execute(
            select(AssetDiscoveryMapping.aas_id).where(
                AssetDiscoveryMapping.tenant_id == tenant_id,
                AssetDiscoveryMapping.asset_id_key == asset_id_key,
                AssetDiscoveryMapping.asset_id_value == asset_id_value,
            )
        )
        return list(result.scalars().all())

    async def delete_mapping(
        self,
        tenant_id: UUID,
        asset_id_key: str,
        asset_id_value: str,
        aas_id: str,
    ) -> bool:
        """Delete a specific discovery mapping. Returns True if deleted."""
        result = await self._session.execute(
            select(AssetDiscoveryMapping).where(
                AssetDiscoveryMapping.tenant_id == tenant_id,
                AssetDiscoveryMapping.asset_id_key == asset_id_key,
                AssetDiscoveryMapping.asset_id_value == asset_id_value,
                AssetDiscoveryMapping.aas_id == aas_id,
            )
        )
        mapping = result.scalar_one_or_none()
        if mapping is None:
            return False
        await self._session.delete(mapping)
        await self._session.flush()
        return True

    async def list_mappings(
        self,
        tenant_id: UUID,
        aas_id: str | None = None,
    ) -> list[AssetDiscoveryMapping]:
        """List discovery mappings, optionally filtered by AAS ID."""
        stmt = select(AssetDiscoveryMapping).where(
            AssetDiscoveryMapping.tenant_id == tenant_id,
        )
        if aas_id is not None:
            stmt = stmt.where(AssetDiscoveryMapping.aas_id == aas_id)
        stmt = stmt.order_by(AssetDiscoveryMapping.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
