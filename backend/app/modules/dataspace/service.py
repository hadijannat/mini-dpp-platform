"""Dataspace control-plane service orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import ConnectorConfigEncryptor
from app.core.logging import get_logger
from app.db.models import (
    ComplianceReportRecord,
    ConnectorStatus,
    DataspaceAssetPublication,
    DataspaceConformanceRun,
    DataspaceConnector,
    DataspaceConnectorRuntime,
    DataspaceConnectorSecret,
    DataspaceNegotiation,
    DataspacePolicyTemplate,
    DataspacePolicyTemplateState,
    DataspaceRunStatus,
    DataspaceTransfer,
    DPPRevision,
    IssuedCredential,
    ResolverLink,
    ShellDescriptorRecord,
)
from app.modules.dataspace.runtime import RuntimeConnectorContext, get_runtime_adapter
from app.modules.dataspace.schemas import (
    AssetPublishRequest,
    CatenaXDTRRuntimeConfig,
    ConnectorManifest,
    CredentialStatusResponse,
    DataspaceConnectorCreateRequest,
    DataspaceConnectorUpdateRequest,
    EDCRuntimeConfig,
    ManifestChange,
    NegotiationCreateRequest,
    PolicyTemplateCreateRequest,
    PolicyTemplateUpdateRequest,
    RegulatoryEvidenceResponse,
    TransferCreateRequest,
)
from app.modules.dpps.service import DPPService

logger = get_logger(__name__)


class DataspaceServiceError(ValueError):
    """Domain error for dataspace service operations."""


class DataspaceService:
    """Tenant-scoped service for dataspace control-plane operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._dpp_service = DPPService(session)
        self._settings = get_settings()
        self._encryptor: ConnectorConfigEncryptor | None = None
        if self._settings.encryption_master_key:
            self._encryptor = ConnectorConfigEncryptor(self._settings.encryption_master_key)

    # ------------------------------------------------------------------
    # Connector CRUD
    # ------------------------------------------------------------------

    async def create_connector(
        self,
        *,
        tenant_id: UUID,
        body: DataspaceConnectorCreateRequest,
        created_by_subject: str,
    ) -> tuple[DataspaceConnector, list[str]]:
        self._ensure_runtime_config_matches(
            runtime=body.runtime,
            runtime_config=body.runtime_config,
        )
        connector = DataspaceConnector(
            tenant_id=tenant_id,
            name=body.name,
            runtime=DataspaceConnectorRuntime(body.runtime),
            participant_id=body.participant_id,
            display_name=body.display_name,
            status=ConnectorStatus.DISABLED,
            runtime_config=body.runtime_config.model_dump(mode="python"),
            created_by_subject=created_by_subject,
        )
        self._session.add(connector)
        await self._session.flush()

        await self._upsert_connector_secrets(
            tenant_id=tenant_id,
            connector_id=connector.id,
            secrets=[
                {"secret_ref": secret.secret_ref, "value": secret.value}
                for secret in body.secrets
            ],
        )
        await self._session.flush()
        refs = await self.get_connector_secret_refs(
            tenant_id=tenant_id,
            connector_id=connector.id,
        )
        return connector, refs

    async def list_connectors(
        self,
        *,
        tenant_id: UUID,
    ) -> list[DataspaceConnector]:
        result = await self._session.execute(
            select(DataspaceConnector)
            .where(DataspaceConnector.tenant_id == tenant_id)
            .order_by(DataspaceConnector.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_connector(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
    ) -> DataspaceConnector | None:
        result = await self._session.execute(
            select(DataspaceConnector).where(
                DataspaceConnector.id == connector_id,
                DataspaceConnector.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_connector(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        body: DataspaceConnectorUpdateRequest,
    ) -> tuple[DataspaceConnector, list[str]]:
        connector = await self.get_connector(tenant_id=tenant_id, connector_id=connector_id)
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {connector_id} not found")

        if body.name is not None:
            connector.name = body.name
        if body.participant_id is not None:
            connector.participant_id = body.participant_id
        if body.display_name is not None:
            connector.display_name = body.display_name
        if body.status is not None:
            connector.status = ConnectorStatus(body.status)
        if body.runtime_config is not None:
            self._ensure_runtime_config_matches(
                runtime=connector.runtime.value,
                runtime_config=body.runtime_config,
            )
            connector.runtime_config = body.runtime_config.model_dump(mode="python")
        if body.secrets is not None:
            await self._upsert_connector_secrets(
                tenant_id=tenant_id,
                connector_id=connector.id,
                secrets=[
                    {"secret_ref": secret.secret_ref, "value": secret.value}
                    for secret in body.secrets
                ],
            )

        await self._session.flush()
        refs = await self.get_connector_secret_refs(
            tenant_id=tenant_id,
            connector_id=connector.id,
        )
        return connector, refs

    async def get_connector_secret_refs(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
    ) -> list[str]:
        result = await self._session.execute(
            select(DataspaceConnectorSecret.secret_ref).where(
                DataspaceConnectorSecret.tenant_id == tenant_id,
                DataspaceConnectorSecret.connector_id == connector_id,
            )
        )
        return sorted(result.scalars().all())

    async def validate_connector(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
    ) -> dict[str, Any]:
        connector = await self.get_connector(tenant_id=tenant_id, connector_id=connector_id)
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {connector_id} not found")

        adapter = get_runtime_adapter(connector.runtime.value)
        context = await self._build_runtime_context(connector=connector)
        result = await adapter.validate(context)

        connector.last_validated_at = datetime.now(UTC)
        connector.last_validation_result = result
        if result.get("status") == "ok":
            connector.status = ConnectorStatus.ACTIVE
        else:
            connector.status = ConnectorStatus.ERROR
        await self._session.flush()

        return result

    # ------------------------------------------------------------------
    # Publication / Catalog / Negotiation / Transfer
    # ------------------------------------------------------------------

    async def publish_asset(
        self,
        *,
        tenant_id: UUID,
        body: AssetPublishRequest,
        created_by_subject: str,
    ) -> DataspaceAssetPublication:
        existing = await self._find_idempotent_publication(
            tenant_id=tenant_id,
            idempotency_key=body.idempotency_key,
        )
        if existing is not None:
            return existing

        connector = await self.get_connector(tenant_id=tenant_id, connector_id=body.connector_id)
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {body.connector_id} not found")

        dpp = await self._dpp_service.get_dpp(body.dpp_id, tenant_id)
        if dpp is None:
            raise DataspaceServiceError(f"DPP {body.dpp_id} not found")

        revision = await self._resolve_revision(
            tenant_id=tenant_id,
            dpp_id=body.dpp_id,
            revision_id=body.revision_id,
        )

        policy_template = None
        if body.policy_template_id:
            policy_template = await self.get_policy_template(
                tenant_id=tenant_id,
                policy_template_id=body.policy_template_id,
            )
            if policy_template is None:
                raise DataspaceServiceError(
                    f"Policy template {body.policy_template_id} not found"
                )

        adapter = get_runtime_adapter(connector.runtime.value)
        runtime_context = await self._build_runtime_context(connector=connector)
        runtime_result = await adapter.publish_asset(
            context=runtime_context,
            dpp=dpp,
            revision=revision,
            policy_template=policy_template.policy if policy_template else None,
        )

        publication = DataspaceAssetPublication(
            tenant_id=tenant_id,
            dpp_id=body.dpp_id,
            connector_id=connector.id,
            policy_template_id=body.policy_template_id,
            revision_id=revision.id,
            asset_id=runtime_result.asset_id,
            access_policy_id=runtime_result.access_policy_id,
            usage_policy_id=runtime_result.usage_policy_id,
            contract_definition_id=runtime_result.contract_definition_id,
            status="published",
            idempotency_key=body.idempotency_key,
            created_by_subject=created_by_subject,
        )
        self._session.add(publication)
        await self._session.flush()
        return publication

    async def query_catalog(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        connector_address: str,
        protocol: str,
        query_spec: dict[str, Any],
    ) -> dict[str, Any]:
        connector = await self.get_connector(tenant_id=tenant_id, connector_id=connector_id)
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {connector_id} not found")
        self._ensure_dsp_runtime_supported(
            runtime=connector.runtime.value,
            operation="catalog query",
        )

        adapter = get_runtime_adapter(connector.runtime.value)
        runtime_context = await self._build_runtime_context(connector=connector)
        return await adapter.query_catalog(
            context=runtime_context,
            connector_address=connector_address,
            protocol=protocol,
            query_spec=query_spec,
        )

    async def create_negotiation(
        self,
        *,
        tenant_id: UUID,
        body: NegotiationCreateRequest,
        created_by_subject: str,
    ) -> DataspaceNegotiation:
        existing = await self._find_idempotent_negotiation(
            tenant_id=tenant_id,
            idempotency_key=body.idempotency_key,
        )
        if existing is not None:
            return existing

        connector = await self.get_connector(tenant_id=tenant_id, connector_id=body.connector_id)
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {body.connector_id} not found")
        self._ensure_dsp_runtime_supported(
            runtime=connector.runtime.value,
            operation="contract negotiation",
        )

        publication = None
        if body.publication_id is not None:
            publication = await self.get_publication(
                tenant_id=tenant_id,
                publication_id=body.publication_id,
            )
            if publication is None:
                raise DataspaceServiceError(f"Publication {body.publication_id} not found")

        adapter = get_runtime_adapter(connector.runtime.value)
        runtime_context = await self._build_runtime_context(connector=connector)
        state = await adapter.initiate_negotiation(
            context=runtime_context,
            connector_address=body.connector_address,
            offer_id=body.offer_id,
            asset_id=body.asset_id,
            policy=body.policy,
        )

        negotiation = DataspaceNegotiation(
            tenant_id=tenant_id,
            connector_id=connector.id,
            publication_id=publication.id if publication else None,
            negotiation_id=state.negotiation_id,
            state=state.state,
            contract_agreement_id=state.contract_agreement_id,
            request_payload=body.model_dump(mode="python"),
            response_payload={
                "negotiation_id": state.negotiation_id,
                "state": state.state,
                "contract_agreement_id": state.contract_agreement_id,
            },
            idempotency_key=body.idempotency_key,
            created_by_subject=created_by_subject,
        )
        self._session.add(negotiation)
        await self._session.flush()
        return negotiation

    async def get_negotiation(
        self,
        *,
        tenant_id: UUID,
        negotiation_id: UUID,
    ) -> DataspaceNegotiation | None:
        result = await self._session.execute(
            select(DataspaceNegotiation).where(
                DataspaceNegotiation.id == negotiation_id,
                DataspaceNegotiation.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def refresh_negotiation(
        self,
        *,
        tenant_id: UUID,
        negotiation_id: UUID,
    ) -> DataspaceNegotiation:
        negotiation = await self.get_negotiation(
            tenant_id=tenant_id,
            negotiation_id=negotiation_id,
        )
        if negotiation is None:
            raise DataspaceServiceError(f"Negotiation {negotiation_id} not found")

        connector = await self.get_connector(
            tenant_id=tenant_id,
            connector_id=negotiation.connector_id,
        )
        if connector is None:
            raise DataspaceServiceError(
                f"Dataspace connector {negotiation.connector_id} not found"
            )
        self._ensure_dsp_runtime_supported(
            runtime=connector.runtime.value,
            operation="contract negotiation refresh",
        )

        adapter = get_runtime_adapter(connector.runtime.value)
        runtime_context = await self._build_runtime_context(connector=connector)
        state = await adapter.get_negotiation(
            context=runtime_context,
            negotiation_id=negotiation.negotiation_id,
        )

        negotiation.state = state.state
        negotiation.contract_agreement_id = state.contract_agreement_id
        negotiation.response_payload = {
            "negotiation_id": state.negotiation_id,
            "state": state.state,
            "contract_agreement_id": state.contract_agreement_id,
        }
        await self._session.flush()
        return negotiation

    async def create_transfer(
        self,
        *,
        tenant_id: UUID,
        body: TransferCreateRequest,
        created_by_subject: str,
    ) -> DataspaceTransfer:
        existing = await self._find_idempotent_transfer(
            tenant_id=tenant_id,
            idempotency_key=body.idempotency_key,
        )
        if existing is not None:
            return existing

        connector = await self.get_connector(tenant_id=tenant_id, connector_id=body.connector_id)
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {body.connector_id} not found")
        self._ensure_dsp_runtime_supported(
            runtime=connector.runtime.value,
            operation="transfer process",
        )

        negotiation = None
        if body.negotiation_id is not None:
            negotiation = await self.get_negotiation(
                tenant_id=tenant_id,
                negotiation_id=body.negotiation_id,
            )
            if negotiation is None:
                raise DataspaceServiceError(f"Negotiation {body.negotiation_id} not found")

        adapter = get_runtime_adapter(connector.runtime.value)
        runtime_context = await self._build_runtime_context(connector=connector)
        process = await adapter.initiate_transfer(
            context=runtime_context,
            connector_address=body.connector_address,
            contract_agreement_id=body.contract_agreement_id,
            asset_id=body.asset_id,
            data_destination=body.data_destination,
        )

        transfer = DataspaceTransfer(
            tenant_id=tenant_id,
            connector_id=connector.id,
            negotiation_id=negotiation.id if negotiation else None,
            transfer_id=process.transfer_id,
            state=process.state,
            data_destination=process.data_destination,
            idempotency_key=body.idempotency_key,
            created_by_subject=created_by_subject,
        )
        self._session.add(transfer)
        await self._session.flush()
        return transfer

    async def get_transfer(
        self,
        *,
        tenant_id: UUID,
        transfer_id: UUID,
    ) -> DataspaceTransfer | None:
        result = await self._session.execute(
            select(DataspaceTransfer).where(
                DataspaceTransfer.id == transfer_id,
                DataspaceTransfer.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def refresh_transfer(
        self,
        *,
        tenant_id: UUID,
        transfer_id: UUID,
    ) -> DataspaceTransfer:
        transfer = await self.get_transfer(tenant_id=tenant_id, transfer_id=transfer_id)
        if transfer is None:
            raise DataspaceServiceError(f"Transfer {transfer_id} not found")

        connector = await self.get_connector(
            tenant_id=tenant_id,
            connector_id=transfer.connector_id,
        )
        if connector is None:
            raise DataspaceServiceError(f"Dataspace connector {transfer.connector_id} not found")
        self._ensure_dsp_runtime_supported(
            runtime=connector.runtime.value,
            operation="transfer process refresh",
        )

        adapter = get_runtime_adapter(connector.runtime.value)
        runtime_context = await self._build_runtime_context(connector=connector)
        process = await adapter.get_transfer(
            context=runtime_context,
            transfer_id=transfer.transfer_id,
        )
        transfer.state = process.state
        transfer.data_destination = process.data_destination
        await self._session.flush()
        return transfer

    # ------------------------------------------------------------------
    # Conformance
    # ------------------------------------------------------------------

    async def create_conformance_run(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID | None,
        profile: str,
        metadata: dict[str, Any],
        created_by_subject: str,
    ) -> DataspaceConformanceRun:
        run = DataspaceConformanceRun(
            tenant_id=tenant_id,
            connector_id=connector_id,
            run_type=profile,
            status=DataspaceRunStatus.RUNNING,
            request_payload={
                "profile": profile,
                "metadata": metadata,
            },
            created_by_subject=created_by_subject,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()

        execution = await self._execute_conformance_run(
            run_id=run.id,
            tenant_id=tenant_id,
            connector_id=connector_id,
            profile=profile,
            metadata=metadata,
        )
        run.status = (
            DataspaceRunStatus.PASSED if execution.get("status") == "passed" else DataspaceRunStatus.FAILED
        )
        run.result_payload = execution
        run.artifact_url = execution.get("artifact_path")
        run.completed_at = datetime.now(UTC)
        await self._session.flush()
        return run

    async def get_conformance_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
    ) -> DataspaceConformanceRun | None:
        result = await self._session.execute(
            select(DataspaceConformanceRun).where(
                DataspaceConformanceRun.id == run_id,
                DataspaceConformanceRun.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def build_regulatory_evidence(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        profile: str,
    ) -> RegulatoryEvidenceResponse:
        compliance_rows = list(
            (
                await self._session.execute(
                    select(ComplianceReportRecord).where(
                        ComplianceReportRecord.tenant_id == tenant_id,
                        ComplianceReportRecord.dpp_id == dpp_id,
                    )
                )
            ).scalars().all()
        )

        credential = (
            await self._session.execute(
                select(IssuedCredential).where(
                    IssuedCredential.tenant_id == tenant_id,
                    IssuedCredential.dpp_id == dpp_id,
                )
            )
        ).scalar_one_or_none()

        resolver_rows = list(
            (
                await self._session.execute(
                    select(ResolverLink).where(
                        ResolverLink.tenant_id == tenant_id,
                        ResolverLink.dpp_id == dpp_id,
                    )
                )
            ).scalars().all()
        )

        shell_rows = list(
            (
                await self._session.execute(
                    select(ShellDescriptorRecord).where(
                        ShellDescriptorRecord.tenant_id == tenant_id,
                        ShellDescriptorRecord.dpp_id == dpp_id,
                    )
                )
            ).scalars().all()
        )

        publication_rows = list(
            (
                await self._session.execute(
                    select(DataspaceAssetPublication).where(
                        DataspaceAssetPublication.tenant_id == tenant_id,
                        DataspaceAssetPublication.dpp_id == dpp_id,
                    )
                )
            ).scalars().all()
        )
        publication_ids = [row.id for row in publication_rows]

        negotiations: list[DataspaceNegotiation] = []
        if publication_ids:
            negotiations = list(
                (
                    await self._session.execute(
                        select(DataspaceNegotiation).where(
                            DataspaceNegotiation.tenant_id == tenant_id,
                            DataspaceNegotiation.publication_id.in_(publication_ids),
                        )
                    )
                ).scalars().all()
            )

        negotiation_ids = [row.id for row in negotiations]
        transfers: list[DataspaceTransfer] = []
        if negotiation_ids:
            transfers = list(
                (
                    await self._session.execute(
                        select(DataspaceTransfer).where(
                            DataspaceTransfer.tenant_id == tenant_id,
                            DataspaceTransfer.negotiation_id.in_(negotiation_ids),
                        )
                    )
                ).scalars().all()
            )

        conformance_rows = list(
            (
                await self._session.execute(
                    select(DataspaceConformanceRun)
                    .where(DataspaceConformanceRun.tenant_id == tenant_id)
                    .order_by(DataspaceConformanceRun.created_at.desc())
                    .limit(20)
                )
            ).scalars().all()
        )

        credential_status = CredentialStatusResponse(
            exists=credential is not None,
            revoked=credential.revoked if credential else None,
            issuer_did=credential.issuer_did if credential else None,
            issuance_date=credential.issuance_date if credential else None,
            expiration_date=credential.expiration_date if credential else None,
        )

        return RegulatoryEvidenceResponse(
            dpp_id=dpp_id,
            profile=profile,
            generated_at=datetime.now(UTC),
            compliance_reports=[
                {
                    "id": str(row.id),
                    "category": row.category,
                    "is_compliant": row.is_compliant,
                    "created_at": row.created_at.isoformat(),
                    "report": row.report_json,
                }
                for row in compliance_rows
            ],
            credential_status=credential_status,
            resolver_links=[
                {
                    "id": str(row.id),
                    "identifier": row.identifier,
                    "link_type": row.link_type,
                    "href": row.href,
                    "active": row.active,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in resolver_rows
            ],
            shell_descriptors=[
                {
                    "id": str(row.id),
                    "aas_id": row.aas_id,
                    "global_asset_id": row.global_asset_id,
                    "submodel_count": len(row.submodel_descriptors or []),
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in shell_rows
            ],
            dataspace_publications=[
                {
                    "id": str(row.id),
                    "connector_id": str(row.connector_id),
                    "asset_id": row.asset_id,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                }
                for row in publication_rows
            ],
            dataspace_negotiations=[
                {
                    "id": str(row.id),
                    "publication_id": str(row.publication_id) if row.publication_id else None,
                    "negotiation_id": row.negotiation_id,
                    "state": row.state,
                    "contract_agreement_id": row.contract_agreement_id,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in negotiations
            ],
            dataspace_transfers=[
                {
                    "id": str(row.id),
                    "negotiation_id": str(row.negotiation_id) if row.negotiation_id else None,
                    "transfer_id": row.transfer_id,
                    "state": row.state,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in transfers
            ],
            dataspace_conformance_runs=[
                {
                    "id": str(row.id),
                    "run_type": row.run_type,
                    "status": row.status.value,
                    "artifact_url": row.artifact_url,
                    "created_at": row.created_at.isoformat(),
                }
                for row in conformance_rows
            ],
        )

    # ------------------------------------------------------------------
    # Manifest diff/apply
    # ------------------------------------------------------------------

    async def diff_manifest(
        self,
        *,
        tenant_id: UUID,
        manifest: ConnectorManifest,
    ) -> list[ManifestChange]:
        changes: list[ManifestChange] = []
        connector = await self.get_connector_by_name(
            tenant_id=tenant_id,
            name=manifest.connector.name,
        )

        if connector is None:
            changes.append(
                ManifestChange(
                    resource="dataspace_connector",
                    action="create",
                    field="name",
                    new_value=manifest.connector.name,
                )
            )
        else:
            if connector.participant_id != manifest.connector.participant_id:
                changes.append(
                    ManifestChange(
                        resource="dataspace_connector",
                        action="update",
                        field="participant_id",
                        old_value=connector.participant_id,
                        new_value=manifest.connector.participant_id,
                    )
                )
            if connector.runtime_config != manifest.connector.runtime_config.model_dump(mode="python"):
                changes.append(
                    ManifestChange(
                        resource="dataspace_connector",
                        action="update",
                        field="runtime_config",
                        old_value=connector.runtime_config,
                        new_value=manifest.connector.runtime_config.model_dump(mode="python"),
                    )
                )

        for template in manifest.policy_templates:
            existing = await self.get_policy_template_by_name_version(
                tenant_id=tenant_id,
                name=template.name,
                version=template.version,
            )
            if existing is None:
                changes.append(
                    ManifestChange(
                        resource="dataspace_policy_template",
                        action="create",
                        field=f"{template.name}@{template.version}",
                        new_value=template.policy,
                    )
                )
            elif existing.policy != template.policy or existing.state.value != template.state:
                changes.append(
                    ManifestChange(
                        resource="dataspace_policy_template",
                        action="update",
                        field=f"{template.name}@{template.version}",
                        old_value={
                            "state": existing.state.value,
                            "policy": existing.policy,
                        },
                        new_value={
                            "state": template.state,
                            "policy": template.policy,
                        },
                    )
                )

        return changes

    async def apply_manifest(
        self,
        *,
        tenant_id: UUID,
        manifest: ConnectorManifest,
        created_by_subject: str,
    ) -> tuple[DataspaceConnector, list[ManifestChange]]:
        changes = await self.diff_manifest(tenant_id=tenant_id, manifest=manifest)
        connector = await self.get_connector_by_name(
            tenant_id=tenant_id,
            name=manifest.connector.name,
        )
        if connector is None:
            connector, _ = await self.create_connector(
                tenant_id=tenant_id,
                body=manifest.connector,
                created_by_subject=created_by_subject,
            )
        else:
            update_body = DataspaceConnectorUpdateRequest(
                participant_id=manifest.connector.participant_id,
                display_name=manifest.connector.display_name,
                runtime_config=manifest.connector.runtime_config,
                secrets=manifest.connector.secrets or None,
            )
            connector, _ = await self.update_connector(
                tenant_id=tenant_id,
                connector_id=connector.id,
                body=update_body,
            )

        for template in manifest.policy_templates:
            existing = await self.get_policy_template_by_name_version(
                tenant_id=tenant_id,
                name=template.name,
                version=template.version,
            )
            if existing is None:
                self._session.add(
                    DataspacePolicyTemplate(
                        tenant_id=tenant_id,
                        name=template.name,
                        version=template.version,
                        state=DataspacePolicyTemplateState(template.state),
                        policy=template.policy,
                        description=template.description,
                        created_by_subject=created_by_subject,
                    )
                )
            else:
                existing.state = DataspacePolicyTemplateState(template.state)
                existing.policy = template.policy
                existing.description = template.description
        await self._session.flush()
        return connector, changes

    # ------------------------------------------------------------------
    # Policy templates
    # ------------------------------------------------------------------

    async def list_policy_templates(
        self,
        *,
        tenant_id: UUID,
    ) -> list[DataspacePolicyTemplate]:
        result = await self._session.execute(
            select(DataspacePolicyTemplate)
            .where(DataspacePolicyTemplate.tenant_id == tenant_id)
            .order_by(
                DataspacePolicyTemplate.name.asc(),
                DataspacePolicyTemplate.version.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_policy_template(
        self,
        *,
        tenant_id: UUID,
        body: PolicyTemplateCreateRequest,
        created_by_subject: str,
    ) -> DataspacePolicyTemplate:
        existing = await self.get_policy_template_by_name_version(
            tenant_id=tenant_id,
            name=body.name,
            version=body.version,
        )
        if existing is not None:
            raise DataspaceServiceError(
                f"Policy template {body.name}@{body.version} already exists"
            )
        template = DataspacePolicyTemplate(
            tenant_id=tenant_id,
            name=body.name,
            version=body.version,
            state=DataspacePolicyTemplateState.DRAFT,
            policy=body.policy,
            description=body.description,
            created_by_subject=created_by_subject,
        )
        self._session.add(template)
        await self._session.flush()
        return template

    async def update_policy_template(
        self,
        *,
        tenant_id: UUID,
        policy_template_id: UUID,
        body: PolicyTemplateUpdateRequest,
    ) -> DataspacePolicyTemplate:
        template = await self.get_policy_template(
            tenant_id=tenant_id,
            policy_template_id=policy_template_id,
        )
        if template is None:
            raise DataspaceServiceError(f"Policy template {policy_template_id} not found")
        if template.state != DataspacePolicyTemplateState.DRAFT:
            raise DataspaceServiceError("Only draft policy templates can be updated")
        if body.description is not None:
            template.description = body.description
        if body.policy is not None:
            template.policy = body.policy
        await self._session.flush()
        return template

    async def transition_policy_template(
        self,
        *,
        tenant_id: UUID,
        policy_template_id: UUID,
        to_state: DataspacePolicyTemplateState,
        actor_subject: str,
    ) -> DataspacePolicyTemplate:
        template = await self.get_policy_template(
            tenant_id=tenant_id,
            policy_template_id=policy_template_id,
        )
        if template is None:
            raise DataspaceServiceError(f"Policy template {policy_template_id} not found")

        current = template.state
        allowed: dict[DataspacePolicyTemplateState, set[DataspacePolicyTemplateState]] = {
            DataspacePolicyTemplateState.DRAFT: {DataspacePolicyTemplateState.APPROVED},
            DataspacePolicyTemplateState.APPROVED: {
                DataspacePolicyTemplateState.ACTIVE,
                DataspacePolicyTemplateState.SUPERSEDED,
            },
            DataspacePolicyTemplateState.ACTIVE: {DataspacePolicyTemplateState.SUPERSEDED},
            DataspacePolicyTemplateState.SUPERSEDED: set(),
        }
        if to_state not in allowed[current]:
            raise DataspaceServiceError(
                f"Invalid policy-template transition: {current.value} -> {to_state.value}"
            )

        if to_state == DataspacePolicyTemplateState.ACTIVE:
            active_result = await self._session.execute(
                select(DataspacePolicyTemplate).where(
                    DataspacePolicyTemplate.tenant_id == tenant_id,
                    DataspacePolicyTemplate.name == template.name,
                    DataspacePolicyTemplate.state == DataspacePolicyTemplateState.ACTIVE,
                    DataspacePolicyTemplate.id != template.id,
                )
            )
            for current_active in active_result.scalars().all():
                current_active.state = DataspacePolicyTemplateState.SUPERSEDED

        template.state = to_state
        if to_state in {
            DataspacePolicyTemplateState.APPROVED,
            DataspacePolicyTemplateState.ACTIVE,
        }:
            template.approved_by_subject = actor_subject
        await self._session.flush()
        return template

    async def get_policy_template(
        self,
        *,
        tenant_id: UUID,
        policy_template_id: UUID,
    ) -> DataspacePolicyTemplate | None:
        result = await self._session.execute(
            select(DataspacePolicyTemplate).where(
                DataspacePolicyTemplate.id == policy_template_id,
                DataspacePolicyTemplate.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_policy_template_by_name_version(
        self,
        *,
        tenant_id: UUID,
        name: str,
        version: str,
    ) -> DataspacePolicyTemplate | None:
        result = await self._session.execute(
            select(DataspacePolicyTemplate).where(
                DataspacePolicyTemplate.tenant_id == tenant_id,
                DataspacePolicyTemplate.name == name,
                DataspacePolicyTemplate.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def get_connector_by_name(
        self,
        *,
        tenant_id: UUID,
        name: str,
    ) -> DataspaceConnector | None:
        result = await self._session.execute(
            select(DataspaceConnector).where(
                and_(
                    DataspaceConnector.tenant_id == tenant_id,
                    DataspaceConnector.name == name,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_publication(
        self,
        *,
        tenant_id: UUID,
        publication_id: UUID,
    ) -> DataspaceAssetPublication | None:
        result = await self._session.execute(
            select(DataspaceAssetPublication).where(
                DataspaceAssetPublication.id == publication_id,
                DataspaceAssetPublication.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_publications(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        limit: int = 100,
    ) -> list[DataspaceAssetPublication]:
        result = await self._session.execute(
            select(DataspaceAssetPublication)
            .where(
                DataspaceAssetPublication.tenant_id == tenant_id,
                DataspaceAssetPublication.connector_id == connector_id,
            )
            .order_by(DataspaceAssetPublication.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_negotiations(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        limit: int = 100,
    ) -> list[DataspaceNegotiation]:
        result = await self._session.execute(
            select(DataspaceNegotiation)
            .where(
                DataspaceNegotiation.tenant_id == tenant_id,
                DataspaceNegotiation.connector_id == connector_id,
            )
            .order_by(DataspaceNegotiation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_transfers(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        limit: int = 100,
    ) -> list[DataspaceTransfer]:
        result = await self._session.execute(
            select(DataspaceTransfer)
            .where(
                DataspaceTransfer.tenant_id == tenant_id,
                DataspaceTransfer.connector_id == connector_id,
            )
            .order_by(DataspaceTransfer.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_conformance_runs(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        limit: int = 100,
    ) -> list[DataspaceConformanceRun]:
        result = await self._session.execute(
            select(DataspaceConformanceRun)
            .where(
                DataspaceConformanceRun.tenant_id == tenant_id,
                DataspaceConformanceRun.connector_id == connector_id,
            )
            .order_by(DataspaceConformanceRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _resolve_revision(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        revision_id: UUID | None,
    ) -> DPPRevision:
        if revision_id is None:
            revision = await self._dpp_service.get_published_revision(dpp_id, tenant_id)
            if revision is None:
                raise DataspaceServiceError(f"DPP {dpp_id} has no published revision")
            return revision

        result = await self._session.execute(
            select(DPPRevision).where(
                DPPRevision.id == revision_id,
                DPPRevision.dpp_id == dpp_id,
                DPPRevision.tenant_id == tenant_id,
            )
        )
        revision = result.scalar_one_or_none()
        if revision is None:
            raise DataspaceServiceError(
                f"Revision {revision_id} not found for DPP {dpp_id}"
            )
        return revision

    async def _upsert_connector_secrets(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        secrets: list[dict[str, str]],
    ) -> None:
        if not secrets:
            return

        existing_result = await self._session.execute(
            select(DataspaceConnectorSecret).where(
                DataspaceConnectorSecret.tenant_id == tenant_id,
                DataspaceConnectorSecret.connector_id == connector_id,
            )
        )
        existing_by_ref = {
            record.secret_ref: record for record in existing_result.scalars().all()
        }

        for secret in secrets:
            secret_ref = secret["secret_ref"]
            encrypted_value = self._encrypt_secret(secret["value"])

            current = existing_by_ref.get(secret_ref)
            if current is None:
                self._session.add(
                    DataspaceConnectorSecret(
                        tenant_id=tenant_id,
                        connector_id=connector_id,
                        secret_ref=secret_ref,
                        encrypted_value=encrypted_value,
                    )
                )
            else:
                current.encrypted_value = encrypted_value

    async def _build_runtime_context(
        self,
        *,
        connector: DataspaceConnector,
    ) -> RuntimeConnectorContext:
        result = await self._session.execute(
            select(DataspaceConnectorSecret).where(
                DataspaceConnectorSecret.connector_id == connector.id,
                DataspaceConnectorSecret.tenant_id == connector.tenant_id,
            )
        )
        secrets = result.scalars().all()
        resolved = {
            secret.secret_ref: self._decrypt_secret(secret.encrypted_value) for secret in secrets
        }
        return RuntimeConnectorContext(
            connector_id=str(connector.id),
            runtime=connector.runtime.value,
            participant_id=connector.participant_id,
            runtime_config=connector.runtime_config,
            resolved_secrets=resolved,
        )

    async def _find_idempotent_publication(
        self,
        *,
        tenant_id: UUID,
        idempotency_key: str | None,
    ) -> DataspaceAssetPublication | None:
        if not idempotency_key:
            return None
        result = await self._session.execute(
            select(DataspaceAssetPublication).where(
                DataspaceAssetPublication.tenant_id == tenant_id,
                DataspaceAssetPublication.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def _find_idempotent_negotiation(
        self,
        *,
        tenant_id: UUID,
        idempotency_key: str | None,
    ) -> DataspaceNegotiation | None:
        if not idempotency_key:
            return None
        result = await self._session.execute(
            select(DataspaceNegotiation).where(
                DataspaceNegotiation.tenant_id == tenant_id,
                DataspaceNegotiation.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def _find_idempotent_transfer(
        self,
        *,
        tenant_id: UUID,
        idempotency_key: str | None,
    ) -> DataspaceTransfer | None:
        if not idempotency_key:
            return None
        result = await self._session.execute(
            select(DataspaceTransfer).where(
                DataspaceTransfer.tenant_id == tenant_id,
                DataspaceTransfer.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    def _encrypt_secret(self, value: str) -> str:
        encryptor = self._require_encryptor()
        payload = encryptor.encrypt_config({"token": value})
        encrypted = payload.get("token")
        if not isinstance(encrypted, str):
            raise DataspaceServiceError("Failed to encrypt secret value")
        return encrypted

    def _decrypt_secret(self, value: str) -> str:
        if not value.startswith("enc:v1:"):
            return value
        encryptor = self._require_encryptor()
        payload = encryptor.decrypt_config({"token": value})
        decrypted = payload.get("token")
        if not isinstance(decrypted, str):
            raise DataspaceServiceError("Failed to decrypt secret value")
        return decrypted

    def _require_encryptor(self) -> ConnectorConfigEncryptor:
        if self._encryptor is None:
            raise DataspaceServiceError(
                "encryption_master_key must be configured for dataspace secret operations"
            )
        return self._encryptor

    @staticmethod
    def _ensure_runtime_config_matches(
        *,
        runtime: str,
        runtime_config: object,
    ) -> None:
        if runtime == "edc" and not isinstance(runtime_config, EDCRuntimeConfig):
            raise DataspaceServiceError(
                "runtime_config must be EDCRuntimeConfig for runtime=edc"
            )
        if runtime == "catena_x_dtr" and not isinstance(runtime_config, CatenaXDTRRuntimeConfig):
            raise DataspaceServiceError(
                "runtime_config must be CatenaXDTRRuntimeConfig for runtime=catena_x_dtr"
            )

    @staticmethod
    def _ensure_dsp_runtime_supported(
        *,
        runtime: str,
        operation: str,
    ) -> None:
        if runtime == DataspaceConnectorRuntime.EDC.value:
            return
        raise DataspaceServiceError(
            f"Runtime {runtime} does not support {operation}; use registry-oriented flows."
        )

    async def _execute_conformance_run(
        self,
        *,
        run_id: UUID,
        tenant_id: UUID,
        connector_id: UUID | None,
        profile: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        command = self._settings.dataspace_tck_command.strip()
        artifact_dir = Path(self._settings.dataspace_tck_artifact_dir).expanduser()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{run_id}.json"

        payload: dict[str, Any] = {
            "run_id": str(run_id),
            "tenant_id": str(tenant_id),
            "connector_id": str(connector_id) if connector_id else None,
            "profile": profile,
            "metadata": metadata,
            "started_at": datetime.now(UTC).isoformat(),
        }

        if not command:
            payload.update(
                {
                    "mode": "simulated",
                    "status": "passed",
                    "return_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "artifact_path": str(artifact_path),
                }
            )
            artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload

        args = shlex.split(command)
        env = os.environ.copy()
        env.update(
            {
                "DATASPACE_RUN_ID": str(run_id),
                "DATASPACE_TENANT_ID": str(tenant_id),
                "DATASPACE_CONNECTOR_ID": str(connector_id) if connector_id else "",
                "DATASPACE_PROFILE": profile,
            }
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self._settings.dataspace_tck_timeout_seconds,
            )
            payload.update(
                {
                    "mode": "command",
                    "status": "passed" if process.returncode == 0 else "failed",
                    "return_code": process.returncode,
                    "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                    "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                    "artifact_path": str(artifact_path),
                }
            )
        except TimeoutError:
            payload.update(
                {
                    "mode": "command",
                    "status": "failed",
                    "return_code": None,
                    "stdout": "",
                    "stderr": "Conformance command timed out",
                    "artifact_path": str(artifact_path),
                }
            )
        except Exception as exc:  # noqa: BLE001
            payload.update(
                {
                    "mode": "command",
                    "status": "failed",
                    "return_code": None,
                    "stdout": "",
                    "stderr": str(exc),
                    "artifact_path": str(artifact_path),
                }
            )

        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
