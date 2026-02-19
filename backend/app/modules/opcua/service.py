"""OPC UA service layer — business logic for sources, nodesets, and mappings.

Each service class follows the EPCIS pattern: accepts an ``AsyncSession``
in ``__init__`` and calls ``flush()`` (not ``commit()``), leaving transaction
boundaries to the router middleware.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import re
import time
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import ConnectorConfigEncryptor
from app.core.logging import get_logger
from app.db.models import (
    DPPRevision,
    OPCUAMapping,
    OPCUAMappingType,
    OPCUANodeSet,
    OPCUASource,
)

from .schemas import (
    DryRunDiffEntry,
    MappingDryRunResult,
    MappingValidationResult,
    OPCUAMappingCreate,
    OPCUAMappingUpdate,
    OPCUANodeSetUploadMeta,
    OPCUASourceCreate,
    OPCUASourceUpdate,
    TestConnectionResult,
)
from .transform import validate_transform_expr

logger = get_logger(__name__)

# Regex for OPC UA NodeId: ns=<int>;s=<string> or ns=<int>;i=<int>
_NODE_ID_RE = re.compile(r"^ns=\d+;[sigb]=.+$")
# Regex for AAS idShort path: dot-separated segments
_AAS_PATH_RE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")
# Regex for SAMM URN
_SAMM_URN_RE = re.compile(r"^urn:samm:")


# ---------------------------------------------------------------------------
# Encryption helper
# ---------------------------------------------------------------------------


def _get_encryptor() -> ConnectorConfigEncryptor:
    """Return a ``ConnectorConfigEncryptor`` using the master key from settings."""
    return ConnectorConfigEncryptor(get_settings().encryption_master_key)


# ---------------------------------------------------------------------------
# OPC UA Source Service
# ---------------------------------------------------------------------------


class OPCUASourceService:
    """CRUD operations for OPC UA source connections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sources(
        self,
        tenant_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[OPCUASource], int]:
        """Return paginated sources for a tenant."""
        count_q = (
            select(func.count()).select_from(OPCUASource).where(OPCUASource.tenant_id == tenant_id)
        )
        total = (await self._session.execute(count_q)).scalar_one()

        rows_q = (
            select(OPCUASource)
            .where(OPCUASource.tenant_id == tenant_id)
            .order_by(OPCUASource.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(rows_q)).scalars().all()
        return list(rows), total

    async def get_source(
        self,
        source_id: UUID,
        tenant_id: UUID,
    ) -> OPCUASource | None:
        """Get a single source by ID within a tenant."""
        result = await self._session.execute(
            select(OPCUASource).where(
                OPCUASource.id == source_id,
                OPCUASource.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_source(
        self,
        tenant_id: UUID,
        data: OPCUASourceCreate,
        user_sub: str,
    ) -> OPCUASource:
        """Create a new OPC UA source, encrypting the password if provided."""
        encrypted_pw: str | None = None
        if data.password:
            encrypted_pw = _get_encryptor()._encrypt_value(data.password)

        source = OPCUASource(
            tenant_id=tenant_id,
            name=data.name,
            endpoint_url=data.endpoint_url,
            security_policy=data.security_policy,
            security_mode=data.security_mode,
            auth_type=data.auth_type,
            username=data.username,
            password_encrypted=encrypted_pw,
            client_cert_ref=data.client_cert_ref,
            client_key_ref=data.client_key_ref,
            server_cert_pinned_sha256=data.server_cert_pinned_sha256,
            created_by=user_sub,
        )
        self._session.add(source)
        await self._session.flush()
        await self._session.refresh(source)

        logger.info(
            "opcua_source_created",
            source_id=str(source.id),
            tenant_id=str(tenant_id),
            endpoint_url=data.endpoint_url,
        )
        return source

    async def update_source(
        self,
        source: OPCUASource,
        data: OPCUASourceUpdate,
    ) -> OPCUASource:
        """Apply partial update to an existing source."""
        update_data = data.model_dump(exclude_unset=True)

        # Handle password re-encryption separately
        new_password = data.password
        if new_password is not None:
            source.password_encrypted = _get_encryptor()._encrypt_value(new_password)

        for field_name, value in update_data.items():
            if field_name == "password":
                continue  # handled above
            if hasattr(source, field_name):
                setattr(source, field_name, value)

        await self._session.flush()
        await self._session.refresh(source)

        logger.info(
            "opcua_source_updated",
            source_id=str(source.id),
            tenant_id=str(source.tenant_id),
        )
        return source

    async def delete_source(self, source: OPCUASource) -> None:
        """Delete a source (cascades to nodesets and mappings)."""
        source_id = str(source.id)
        tenant_id = str(source.tenant_id)
        await self._session.delete(source)
        await self._session.flush()
        logger.info(
            "opcua_source_deleted",
            source_id=source_id,
            tenant_id=tenant_id,
        )

    async def test_connection(self, source: OPCUASource) -> TestConnectionResult:
        """Probe the OPC UA endpoint with a 3-second timeout.

        Attempts to connect, read server info, then disconnect.
        Does NOT create subscriptions.
        """
        try:
            from asyncua import Client as OPCUAClient  # type: ignore[import-untyped,import-not-found,unused-ignore]  # noqa: E501,I001
        except ImportError:
            return TestConnectionResult(
                success=False,
                error="asyncua library is not installed",
            )

        start = time.monotonic()
        try:
            client = OPCUAClient(url=source.endpoint_url, timeout=3)
            # If credentials configured, set them
            if source.username and source.password_encrypted:
                try:
                    password = _get_encryptor()._decrypt_value(source.password_encrypted)
                    client.set_user(source.username)
                    client.set_password(password)
                except Exception:
                    pass  # Fall back to anonymous if decryption fails

            await asyncio.wait_for(client.connect(), timeout=3.0)
            try:
                server_node = client.get_server_node()
                server_info: dict[str, Any] = {}
                try:
                    name_node = await server_node.get_child(
                        ["0:ServerStatus", "0:BuildInfo", "0:ProductName"]
                    )
                    server_info["ProductName"] = str(await name_node.read_value())
                except Exception:
                    pass
                try:
                    version_node = await server_node.get_child(
                        ["0:ServerStatus", "0:BuildInfo", "0:SoftwareVersion"]
                    )
                    server_info["SoftwareVersion"] = str(await version_node.read_value())
                except Exception:
                    pass
            finally:
                await client.disconnect()

            latency = (time.monotonic() - start) * 1000
            return TestConnectionResult(
                success=True,
                server_info=server_info or None,
                latency_ms=round(latency, 1),
            )
        except TimeoutError:
            return TestConnectionResult(
                success=False,
                error="Connection timed out after 3 seconds",
                latency_ms=round((time.monotonic() - start) * 1000, 1),
            )
        except Exception as exc:
            return TestConnectionResult(
                success=False,
                error=f"Connection failed: {type(exc).__name__}",
                latency_ms=round((time.monotonic() - start) * 1000, 1),
            )


# ---------------------------------------------------------------------------
# OPC UA NodeSet Service
# ---------------------------------------------------------------------------


class NodeSetService:
    """Business logic for NodeSet upload, parsing, storage, and search."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_nodesets(
        self,
        tenant_id: UUID,
        *,
        source_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[OPCUANodeSet], int]:
        """Return paginated nodesets for a tenant, optionally filtered by source."""
        base = select(OPCUANodeSet).where(OPCUANodeSet.tenant_id == tenant_id)
        if source_id is not None:
            base = base.where(OPCUANodeSet.source_id == source_id)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_q)).scalar_one()

        rows_q = base.order_by(OPCUANodeSet.created_at.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(rows_q)).scalars().all()
        return list(rows), total

    async def get_nodeset(
        self,
        nodeset_id: UUID,
        tenant_id: UUID,
    ) -> OPCUANodeSet | None:
        """Get a single nodeset by ID."""
        result = await self._session.execute(
            select(OPCUANodeSet).where(
                OPCUANodeSet.id == nodeset_id,
                OPCUANodeSet.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def upload(
        self,
        tenant_id: UUID,
        xml_bytes: bytes,
        meta: OPCUANodeSetUploadMeta,
        user_sub: str,
        *,
        minio_client: Any = None,
    ) -> OPCUANodeSet:
        """Parse a NodeSet2.xml and persist metadata + file to MinIO.

        Args:
            xml_bytes: Raw XML bytes of the NodeSet2.xml.
            meta: Metadata from the upload form.
            user_sub: OIDC subject of uploader.
            minio_client: Optional MinIO client (for testing injection).
        """
        from .nodeset_parser import parse_nodeset_xml

        parsed = parse_nodeset_xml(xml_bytes)

        # Store XML in MinIO
        settings = get_settings()
        bucket = settings.opcua_nodeset_bucket
        nodeset_id_placeholder = str(
            (await self._session.execute(select(func.uuid_generate_v7()))).scalar_one()
        )
        object_key = f"{tenant_id}/opcua_nodesets/{nodeset_id_placeholder}/nodeset.xml"

        if minio_client is not None:
            import io

            await asyncio.to_thread(
                minio_client.put_object,
                bucket,
                object_key,
                io.BytesIO(xml_bytes),
                len(xml_bytes),
                content_type="application/xml",
            )

        nodeset = OPCUANodeSet(
            tenant_id=tenant_id,
            source_id=meta.source_id,
            namespace_uri=parsed.namespace_uris[0] if parsed.namespace_uris else "",
            nodeset_version=parsed.nodeset_version,
            publication_date=parsed.publication_date,
            companion_spec_name=meta.companion_spec_name,
            companion_spec_version=meta.companion_spec_version,
            nodeset_file_ref=object_key,
            hash_sha256=parsed.sha256,
            parsed_node_graph=parsed.node_graph,
            parsed_summary_json=parsed.summary,
            created_by=user_sub,
        )
        self._session.add(nodeset)
        await self._session.flush()
        await self._session.refresh(nodeset)

        logger.info(
            "opcua_nodeset_uploaded",
            nodeset_id=str(nodeset.id),
            tenant_id=str(tenant_id),
            namespace_uri=nodeset.namespace_uri,
            node_count=parsed.summary.get("total_nodes", 0),
        )
        return nodeset

    async def delete_nodeset(
        self,
        nodeset: OPCUANodeSet,
        *,
        minio_client: Any = None,
    ) -> None:
        """Remove a nodeset from DB and MinIO."""
        if minio_client is not None and nodeset.nodeset_file_ref:
            try:
                await asyncio.to_thread(
                    minio_client.remove_object,
                    get_settings().opcua_nodeset_bucket,
                    nodeset.nodeset_file_ref,
                )
            except Exception:
                logger.warning(
                    "opcua_nodeset_minio_delete_failed",
                    nodeset_id=str(nodeset.id),
                    file_ref=nodeset.nodeset_file_ref,
                )
            if nodeset.companion_spec_file_ref:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(
                        minio_client.remove_object,
                        get_settings().opcua_nodeset_bucket,
                        nodeset.companion_spec_file_ref,
                    )

        nodeset_id = str(nodeset.id)
        tenant_id = str(nodeset.tenant_id)
        await self._session.delete(nodeset)
        await self._session.flush()
        logger.info(
            "opcua_nodeset_deleted",
            nodeset_id=nodeset_id,
            tenant_id=tenant_id,
        )

    def generate_download_url(
        self,
        nodeset: OPCUANodeSet,
        minio_client: Any,
    ) -> str:
        """Generate a presigned MinIO download URL (1h expiry)."""
        from datetime import timedelta

        url: str = minio_client.presigned_get_object(
            get_settings().opcua_nodeset_bucket,
            nodeset.nodeset_file_ref,
            expires=timedelta(hours=1),
        )
        return url

    @staticmethod
    def search_nodes(
        nodeset: OPCUANodeSet,
        *,
        query: str,
        node_class: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search the parsed node graph of a nodeset in-memory.

        Performs case-insensitive matching on browse_name and description.
        """
        graph: dict[str, Any] = nodeset.parsed_node_graph or {}
        results: list[dict[str, Any]] = []
        q_lower = query.lower()

        for _ns_uri, nodes in graph.items():
            if not isinstance(nodes, dict):
                continue
            for _node_id, node_info in nodes.items():
                if not isinstance(node_info, dict):
                    continue
                if node_class and node_info.get("node_class") != node_class:
                    continue
                browse_name = node_info.get("browse_name", "")
                description = node_info.get("description", "")
                if q_lower in browse_name.lower() or q_lower in (description or "").lower():
                    results.append(node_info)
                    if len(results) >= limit:
                        return results
        return results


# ---------------------------------------------------------------------------
# OPC UA Mapping Service
# ---------------------------------------------------------------------------


class MappingService:
    """CRUD + validation + dry-run for OPC UA mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_mappings(
        self,
        tenant_id: UUID,
        *,
        source_id: UUID | None = None,
        mapping_type: OPCUAMappingType | None = None,
        is_enabled: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[OPCUAMapping], int]:
        """Return paginated mappings with optional filters."""
        base = select(OPCUAMapping).where(OPCUAMapping.tenant_id == tenant_id)
        if source_id is not None:
            base = base.where(OPCUAMapping.source_id == source_id)
        if mapping_type is not None:
            base = base.where(OPCUAMapping.mapping_type == mapping_type)
        if is_enabled is not None:
            base = base.where(OPCUAMapping.is_enabled == is_enabled)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_q)).scalar_one()

        rows_q = base.order_by(OPCUAMapping.created_at.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(rows_q)).scalars().all()
        return list(rows), total

    async def get_mapping(
        self,
        mapping_id: UUID,
        tenant_id: UUID,
    ) -> OPCUAMapping | None:
        """Get a single mapping by ID."""
        result = await self._session.execute(
            select(OPCUAMapping).where(
                OPCUAMapping.id == mapping_id,
                OPCUAMapping.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_mapping(
        self,
        tenant_id: UUID,
        data: OPCUAMappingCreate,
        user_sub: str,
    ) -> OPCUAMapping:
        """Create a new mapping row."""
        mapping = OPCUAMapping(
            tenant_id=tenant_id,
            source_id=data.source_id,
            nodeset_id=data.nodeset_id,
            mapping_type=data.mapping_type,
            opcua_node_id=data.opcua_node_id,
            opcua_browse_path=data.opcua_browse_path,
            opcua_datatype=data.opcua_datatype,
            sampling_interval_ms=data.sampling_interval_ms,
            dpp_binding_mode=data.dpp_binding_mode,
            dpp_id=data.dpp_id,
            asset_id_query=data.asset_id_query,
            target_template_key=data.target_template_key,
            target_submodel_id=data.target_submodel_id,
            target_aas_path=data.target_aas_path,
            patch_op=data.patch_op,
            value_transform_expr=data.value_transform_expr,
            unit_hint=data.unit_hint,
            samm_aspect_urn=data.samm_aspect_urn,
            samm_property=data.samm_property,
            samm_version=data.samm_version,
            epcis_event_type=data.epcis_event_type,
            epcis_biz_step=data.epcis_biz_step,
            epcis_disposition=data.epcis_disposition,
            epcis_action=data.epcis_action,
            epcis_read_point=data.epcis_read_point,
            epcis_biz_location=data.epcis_biz_location,
            epcis_source_event_id_template=data.epcis_source_event_id_template,
            is_enabled=data.is_enabled,
            created_by=user_sub,
        )
        self._session.add(mapping)
        await self._session.flush()
        await self._session.refresh(mapping)

        logger.info(
            "opcua_mapping_created",
            mapping_id=str(mapping.id),
            tenant_id=str(tenant_id),
            source_id=str(data.source_id),
            mapping_type=data.mapping_type.value,
        )
        return mapping

    async def update_mapping(
        self,
        mapping: OPCUAMapping,
        data: OPCUAMappingUpdate,
    ) -> OPCUAMapping:
        """Apply partial update to a mapping."""
        update_data = data.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            if hasattr(mapping, field_name):
                setattr(mapping, field_name, value)

        await self._session.flush()
        await self._session.refresh(mapping)

        logger.info(
            "opcua_mapping_updated",
            mapping_id=str(mapping.id),
            tenant_id=str(mapping.tenant_id),
        )
        return mapping

    async def delete_mapping(self, mapping: OPCUAMapping) -> None:
        """Delete a mapping."""
        mapping_id = str(mapping.id)
        tenant_id = str(mapping.tenant_id)
        await self._session.delete(mapping)
        await self._session.flush()
        logger.info(
            "opcua_mapping_deleted",
            mapping_id=mapping_id,
            tenant_id=tenant_id,
        )

    @staticmethod
    def validate_mapping(mapping: OPCUAMapping) -> MappingValidationResult:
        """Validate a mapping's structural configuration.

        Checks NodeId syntax, AAS path format, SAMM URN, and transform expression.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. OPC UA NodeId format
        if not _NODE_ID_RE.match(mapping.opcua_node_id):
            errors.append(
                f"Invalid NodeId format: '{mapping.opcua_node_id}'. "
                "Expected ns=<int>;s=<string> or ns=<int>;i=<int>"
            )

        # 2. AAS target path (only for AAS_PATCH type)
        if mapping.mapping_type == OPCUAMappingType.AAS_PATCH:
            if not mapping.target_aas_path:
                errors.append("target_aas_path is required for AAS_PATCH mappings")
            elif not _AAS_PATH_RE.match(mapping.target_aas_path):
                errors.append(
                    f"Invalid AAS path format: '{mapping.target_aas_path}'. "
                    "Expected dot-separated idShort path (e.g. Nameplate.ManufacturerName)"
                )

        # 3. SAMM URN (optional but must be valid if present)
        if mapping.samm_aspect_urn and not _SAMM_URN_RE.match(mapping.samm_aspect_urn):
            warnings.append(f"SAMM URN '{mapping.samm_aspect_urn}' does not start with 'urn:samm:'")

        # 4. Transform expression
        if mapping.value_transform_expr:
            transform_errors = validate_transform_expr(mapping.value_transform_expr)
            for err in transform_errors:
                errors.append(f"Transform: {err}")

        # 5. EPCIS fields (only for EPCIS_EVENT type)
        if mapping.mapping_type == OPCUAMappingType.EPCIS_EVENT and not mapping.epcis_event_type:
            errors.append("epcis_event_type is required for EPCIS_EVENT mappings")

        return MappingValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def dry_run(
        self,
        mapping: OPCUAMapping,
        revision_json: dict[str, Any] | None = None,
        *,
        simulated_value: Any = "<placeholder>",
    ) -> MappingDryRunResult:
        """Preview a patch against a DPP revision without writing to DB.

        If *revision_json* is ``None``, loads the latest DPP revision from the DB.
        Performs a deep-copy, applies the simulated patch, and returns the diff.
        """
        # Load DPP revision if not provided
        if revision_json is None and mapping.dpp_id:
            result = await self._session.execute(
                select(DPPRevision)
                .where(
                    DPPRevision.dpp_id == mapping.dpp_id,
                    DPPRevision.tenant_id == mapping.tenant_id,
                )
                .order_by(DPPRevision.revision_no.desc())
                .limit(1)
            )
            rev = result.scalar_one_or_none()
            if rev and rev.aas_env_json:
                revision_json = rev.aas_env_json

        if revision_json is None:
            return MappingDryRunResult(
                mapping_id=mapping.id,
                dpp_id=mapping.dpp_id,
                diff=[],
                applied_value=None,
                transform_output=None,
            )

        # Apply transform if present
        transform_output = simulated_value
        if mapping.value_transform_expr:
            from .transform import apply_transform

            try:
                transform_output = apply_transform(mapping.value_transform_expr, simulated_value)
            except Exception as exc:
                return MappingDryRunResult(
                    mapping_id=mapping.id,
                    dpp_id=mapping.dpp_id,
                    diff=[
                        DryRunDiffEntry(
                            op="error",
                            path=mapping.target_aas_path or "",
                            old_value=None,
                            new_value=str(exc),
                        )
                    ],
                    applied_value=None,
                    transform_output=None,
                )

        # Deep-copy and apply simulated patch
        patched = copy.deepcopy(revision_json)
        diff_entries: list[DryRunDiffEntry] = []

        if mapping.target_aas_path:
            # Walk the path in the AAS JSON
            path_parts = mapping.target_aas_path.split(".")
            target = patched
            old_value = None

            try:
                for _i, part in enumerate(path_parts[:-1]):
                    if isinstance(target, dict):
                        target = target.get(part, {})
                    elif isinstance(target, list):
                        # Try to find by idShort in a collection
                        found = None
                        for item in target:
                            if isinstance(item, dict) and item.get("idShort") == part:
                                found = item
                                break
                        target = found if found is not None else {}

                final_key = path_parts[-1]
                if isinstance(target, dict):
                    old_value = target.get(final_key)
                    target[final_key] = transform_output
                    diff_entries.append(
                        DryRunDiffEntry(
                            op="replace" if old_value is not None else "add",
                            path=mapping.target_aas_path,
                            old_value=old_value,
                            new_value=transform_output,
                        )
                    )
            except Exception:
                diff_entries.append(
                    DryRunDiffEntry(
                        op="error",
                        path=mapping.target_aas_path,
                        old_value=None,
                        new_value="Could not traverse AAS path",
                    )
                )

        return MappingDryRunResult(
            mapping_id=mapping.id,
            dpp_id=mapping.dpp_id,
            diff=diff_entries,
            applied_value=transform_output,
            transform_output=transform_output,
        )
