"""Unit tests for dataspace router endpoint contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response, status

from app.db.models import DataspacePolicyTemplateState, DataspaceRunStatus
from app.modules.dataspace.router import (
    activate_policy_template,
    approve_policy_template,
    create_dsp_tck_run,
    get_dpp_regulatory_evidence,
    get_dsp_tck_run,
    get_negotiation,
    get_transfer,
    list_connector_assets,
    list_connector_conformance_runs,
    list_connector_negotiations,
    list_connector_transfers,
    list_dataspace_connectors,
    list_policy_templates,
    supersede_policy_template,
    update_policy_template,
)
from app.modules.dataspace.router import (
    apply_manifest as apply_manifest_endpoint,
)
from app.modules.dataspace.router import (
    diff_manifest as diff_manifest_endpoint,
)
from app.modules.dataspace.schemas import (
    ConformanceRunRequest,
    ConnectorManifest,
    CredentialStatusResponse,
    DataspaceConnectorCreateRequest,
    EDCRuntimeConfig,
    ManifestChange,
    RegulatoryEvidenceResponse,
)


def _tenant() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub="test-user-123"),
    )


def _manifest() -> ConnectorManifest:
    return ConnectorManifest(
        connector=DataspaceConnectorCreateRequest(
            name="tenant-edc",
            runtime="edc",
            participant_id="BPNL000000000001",
            runtime_config=EDCRuntimeConfig(
                management_url="http://edc-controlplane:19193/management",
                management_api_key_secret_ref="edc-mgmt-api-key",
            ),
            secrets=[],
        ),
        policy_templates=[],
    )


def _connector_record(*, name: str, owner_subject: str) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        runtime=SimpleNamespace(value="edc"),
        participant_id="BPNL000000000001",
        display_name=None,
        status=SimpleNamespace(value="disabled"),
        runtime_config={
            "management_url": "http://edc-controlplane:19193/management",
            "management_api_key_secret_ref": "edc-mgmt-api-key",
            "protocol": "dataspace-protocol-http",
        },
        created_by_subject=owner_subject,
        last_validated_at=None,
        last_validation_result=None,
        created_at=now,
        updated_at=now,
    )


def _policy_template_record(*, name: str, owner_subject: str) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        version="1.0.0",
        state=SimpleNamespace(value="draft"),
        description=None,
        policy={"@type": "Policy"},
        created_by_subject=owner_subject,
        approved_by_subject=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_dataspace_connectors_filters_non_accessible_rows() -> None:
    tenant = _tenant()
    db = AsyncMock()
    allowed = _connector_record(name="allowed-connector", owner_subject=tenant.user.sub)
    denied = _connector_record(name="denied-connector", owner_subject="other-subject")
    service = SimpleNamespace(
        list_connectors=AsyncMock(return_value=[allowed, denied]),
        get_connector_secret_refs=AsyncMock(side_effect=[["secret-1"]]),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch(
            "app.modules.dataspace.router.check_access",
            new=AsyncMock(
                side_effect=[
                    SimpleNamespace(is_allowed=True),
                    SimpleNamespace(is_allowed=False),
                ]
            ),
        ) as check_access,
    ):
        response = await list_dataspace_connectors(db=db, tenant=tenant)

    service.list_connectors.assert_awaited_once()
    assert check_access.await_count == 2
    service.get_connector_secret_refs.assert_awaited_once_with(
        tenant_id=tenant.tenant_id,
        connector_id=allowed.id,
    )
    assert response.count == 1
    assert response.connectors[0].id == allowed.id


@pytest.mark.asyncio
async def test_list_policy_templates_filters_non_accessible_rows() -> None:
    tenant = _tenant()
    db = AsyncMock()
    allowed = _policy_template_record(name="allowed-policy", owner_subject=tenant.user.sub)
    denied = _policy_template_record(name="denied-policy", owner_subject="other-subject")
    service = SimpleNamespace(
        list_policy_templates=AsyncMock(return_value=[allowed, denied]),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch(
            "app.modules.dataspace.router.check_access",
            new=AsyncMock(
                side_effect=[
                    SimpleNamespace(is_allowed=True),
                    SimpleNamespace(is_allowed=False),
                ]
            ),
        ) as check_access,
    ):
        response = await list_policy_templates(db=db, tenant=tenant)

    service.list_policy_templates.assert_awaited_once_with(tenant_id=tenant.tenant_id)
    assert check_access.await_count == 2
    assert response.count == 1
    assert response.templates[0].id == allowed.id


@pytest.mark.asyncio
async def test_list_connector_assets_returns_publication_rows() -> None:
    connector_id = uuid4()
    tenant = _tenant()
    db = AsyncMock()
    publication = SimpleNamespace(
        id=uuid4(),
        status="published",
        dpp_id=uuid4(),
        connector_id=connector_id,
        asset_id="asset-123",
        access_policy_id="access-1",
        usage_policy_id="usage-1",
        contract_definition_id="contract-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_connector=AsyncMock(return_value=SimpleNamespace(id=connector_id)),
        list_publications=AsyncMock(return_value=[publication]),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await list_connector_assets(
            connector_id=connector_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    service.list_publications.assert_awaited_once()
    assert response.count == 1
    assert response.items[0].asset_id == "asset-123"


@pytest.mark.asyncio
async def test_list_connector_assets_returns_404_when_missing_connector() -> None:
    connector_id = uuid4()
    tenant = _tenant()
    db = AsyncMock()
    service = SimpleNamespace(get_connector=AsyncMock(return_value=None))

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await list_connector_assets(
            connector_id=connector_id,
            db=db,
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_connector_negotiations_returns_rows() -> None:
    connector_id = uuid4()
    tenant = _tenant()
    db = AsyncMock()
    negotiation = SimpleNamespace(
        id=uuid4(),
        connector_id=connector_id,
        publication_id=uuid4(),
        negotiation_id="neg-1",
        state="FINALIZED",
        contract_agreement_id="agreement-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_connector=AsyncMock(return_value=SimpleNamespace(id=connector_id)),
        list_negotiations=AsyncMock(return_value=[negotiation]),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await list_connector_negotiations(
            connector_id=connector_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert response.count == 1
    assert response.items[0].negotiation_id == "neg-1"


@pytest.mark.asyncio
async def test_list_connector_transfers_returns_rows() -> None:
    connector_id = uuid4()
    tenant = _tenant()
    db = AsyncMock()
    transfer = SimpleNamespace(
        id=uuid4(),
        connector_id=connector_id,
        negotiation_id=uuid4(),
        transfer_id="transfer-1",
        state="COMPLETED",
        data_destination={"type": "HttpProxy"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_connector=AsyncMock(return_value=SimpleNamespace(id=connector_id)),
        list_transfers=AsyncMock(return_value=[transfer]),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await list_connector_transfers(
            connector_id=connector_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert response.count == 1
    assert response.items[0].transfer_id == "transfer-1"


@pytest.mark.asyncio
async def test_list_connector_conformance_runs_returns_rows() -> None:
    connector_id = uuid4()
    tenant = _tenant()
    db = AsyncMock()
    run = SimpleNamespace(
        id=uuid4(),
        connector_id=connector_id,
        run_type="dsp-tck",
        status="passed",
        request_payload={"profile": "dsp-tck"},
        result_payload={"status": "passed"},
        artifact_url="/tmp/run.json",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_connector=AsyncMock(return_value=SimpleNamespace(id=connector_id)),
        list_conformance_runs=AsyncMock(return_value=[run]),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await list_connector_conformance_runs(
            connector_id=connector_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert response.count == 1
    assert response.items[0].status == "passed"


@pytest.mark.asyncio
async def test_update_policy_template_requires_owner_scoped_update_access() -> None:
    tenant = _tenant()
    db = AsyncMock()
    request = MagicMock()
    policy_template_id = uuid4()
    existing = _policy_template_record(name="policy-a", owner_subject=tenant.user.sub)
    existing.id = policy_template_id
    updated = _policy_template_record(name="policy-a", owner_subject=tenant.user.sub)
    updated.id = policy_template_id
    service = SimpleNamespace(
        get_policy_template=AsyncMock(return_value=existing),
        update_policy_template=AsyncMock(return_value=updated),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dataspace.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await update_policy_template(
            policy_template_id=policy_template_id,
            body=SimpleNamespace(description="updated description"),
            request=request,
            db=db,
            tenant=tenant,
        )

    service.get_policy_template.assert_awaited_once_with(
        tenant_id=tenant.tenant_id,
        policy_template_id=policy_template_id,
    )
    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "update"
    service.update_policy_template.assert_awaited_once()
    db.commit.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.id == policy_template_id


@pytest.mark.asyncio
async def test_update_policy_template_returns_404_when_missing() -> None:
    tenant = _tenant()
    db = AsyncMock()
    policy_template_id = uuid4()
    service = SimpleNamespace(
        get_policy_template=AsyncMock(return_value=None),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_policy_template(
            policy_template_id=policy_template_id,
            body=SimpleNamespace(description="updated description"),
            request=MagicMock(),
            db=db,
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "to_state"),
    [
        (approve_policy_template, DataspacePolicyTemplateState.APPROVED),
        (activate_policy_template, DataspacePolicyTemplateState.ACTIVE),
        (supersede_policy_template, DataspacePolicyTemplateState.SUPERSEDED),
    ],
)
async def test_policy_template_transitions_require_owner_scoped_update_access(
    endpoint,
    to_state: DataspacePolicyTemplateState,
) -> None:
    tenant = _tenant()
    db = AsyncMock()
    request = MagicMock()
    policy_template_id = uuid4()
    existing = _policy_template_record(name="policy-a", owner_subject=tenant.user.sub)
    existing.id = policy_template_id
    transitioned = _policy_template_record(name="policy-a", owner_subject=tenant.user.sub)
    transitioned.id = policy_template_id
    transitioned.state = SimpleNamespace(value=to_state.value)
    service = SimpleNamespace(
        get_policy_template=AsyncMock(return_value=existing),
        transition_policy_template=AsyncMock(return_value=transitioned),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dataspace.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await endpoint(
            policy_template_id=policy_template_id,
            request=request,
            db=db,
            tenant=tenant,
        )

    service.get_policy_template.assert_awaited_once_with(
        tenant_id=tenant.tenant_id,
        policy_template_id=policy_template_id,
    )
    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "update"
    service.transition_policy_template.assert_awaited_once_with(
        tenant_id=tenant.tenant_id,
        policy_template_id=policy_template_id,
        to_state=to_state,
        actor_subject=tenant.user.sub,
    )
    db.commit.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.id == policy_template_id
    assert response.state == to_state.value


@pytest.mark.asyncio
async def test_diff_manifest_returns_changes() -> None:
    tenant = _tenant()
    db = AsyncMock()
    manifest = _manifest()
    service = SimpleNamespace(
        diff_manifest=AsyncMock(
            return_value=[
                ManifestChange(
                    resource="dataspace_connector",
                    action="create",
                    field="name",
                    new_value="tenant-edc",
                )
            ]
        )
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await diff_manifest_endpoint(
            body=manifest,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    service.diff_manifest.assert_awaited_once()
    assert response.has_changes is True
    assert len(response.changes) == 1


@pytest.mark.asyncio
async def test_apply_manifest_returns_noop_when_no_changes() -> None:
    tenant = _tenant()
    db = AsyncMock()
    manifest = _manifest()
    request = MagicMock()
    http_response = Response()
    connector = SimpleNamespace(id=uuid4())
    service = SimpleNamespace(
        apply_manifest=AsyncMock(return_value=(connector, [])),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dataspace.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await apply_manifest_endpoint(
            body=manifest,
            request=request,
            response=http_response,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    service.apply_manifest.assert_awaited_once()
    db.commit.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.status == "noop"
    assert response.connector_id == connector.id
    assert http_response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_create_dsp_tck_run_for_connector_returns_run() -> None:
    connector_id = uuid4()
    tenant = _tenant()
    db = AsyncMock()
    request = MagicMock()
    run = SimpleNamespace(
        id=uuid4(),
        connector_id=connector_id,
        run_type="dsp-tck",
        status=DataspaceRunStatus.PASSED,
        request_payload={"profile": "dsp-tck"},
        result_payload={"status": "passed"},
        artifact_url="/tmp/dsp-tck.json",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_connector=AsyncMock(return_value=SimpleNamespace(id=connector_id)),
        create_conformance_run=AsyncMock(return_value=run),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dataspace.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await create_dsp_tck_run(
            body=ConformanceRunRequest(
                connector_id=connector_id,
                profile="dsp-tck",
                metadata={"source": "test"},
            ),
            request=request,
            db=db,
            tenant=tenant,
        )

    service.get_connector.assert_awaited_once()
    service.create_conformance_run.assert_awaited_once()
    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "update"
    db.commit.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.status == "passed"
    assert response.connector_id == connector_id


@pytest.mark.asyncio
async def test_create_dsp_tck_run_without_connector_uses_create_permission() -> None:
    tenant = _tenant()
    db = AsyncMock()
    request = MagicMock()
    run = SimpleNamespace(
        id=uuid4(),
        connector_id=None,
        run_type="dsp-tck",
        status=DataspaceRunStatus.PASSED,
        request_payload={"profile": "dsp-tck"},
        result_payload={"status": "passed"},
        artifact_url="/tmp/dsp-tck.json",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        create_conformance_run=AsyncMock(return_value=run),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dataspace.router.emit_audit_event", new=AsyncMock()),
    ):
        response = await create_dsp_tck_run(
            body=ConformanceRunRequest(profile="dsp-tck", metadata={}),
            request=request,
            db=db,
            tenant=tenant,
        )

    service.create_conformance_run.assert_awaited_once()
    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "create"
    assert response.status == "passed"


@pytest.mark.asyncio
async def test_get_negotiation_requires_read_connector_access() -> None:
    tenant = _tenant()
    db = AsyncMock()
    negotiation_id = uuid4()
    connector_id = uuid4()
    negotiation = SimpleNamespace(
        id=negotiation_id,
        connector_id=connector_id,
        publication_id=uuid4(),
        negotiation_id="neg-runtime-1",
        state="FINALIZED",
        contract_agreement_id="agreement-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    connector = SimpleNamespace(id=connector_id)
    service = SimpleNamespace(
        get_negotiation=AsyncMock(return_value=negotiation),
        get_connector=AsyncMock(return_value=connector),
        refresh_negotiation=AsyncMock(return_value=negotiation),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await get_negotiation(
            negotiation_id=negotiation_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "read"
    service.refresh_negotiation.assert_awaited_once()
    assert response.id == negotiation_id


@pytest.mark.asyncio
async def test_get_transfer_requires_read_connector_access() -> None:
    tenant = _tenant()
    db = AsyncMock()
    transfer_id = uuid4()
    connector_id = uuid4()
    transfer = SimpleNamespace(
        id=transfer_id,
        connector_id=connector_id,
        negotiation_id=uuid4(),
        transfer_id="transfer-runtime-1",
        state="COMPLETED",
        data_destination={"type": "HttpProxy"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    connector = SimpleNamespace(id=connector_id)
    service = SimpleNamespace(
        get_transfer=AsyncMock(return_value=transfer),
        get_connector=AsyncMock(return_value=connector),
        refresh_transfer=AsyncMock(return_value=transfer),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await get_transfer(
            transfer_id=transfer_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "read"
    service.refresh_transfer.assert_awaited_once()
    assert response.id == transfer_id


@pytest.mark.asyncio
async def test_get_dsp_tck_run_returns_404_when_missing() -> None:
    tenant = _tenant()
    db = AsyncMock()
    run_id = uuid4()
    service = SimpleNamespace(get_conformance_run=AsyncMock(return_value=None))

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await get_dsp_tck_run(
            run_id=run_id,
            db=db,
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_dsp_tck_run_requires_connector_read_access() -> None:
    tenant = _tenant()
    db = AsyncMock()
    connector_id = uuid4()
    run_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        connector_id=connector_id,
        run_type="dsp-tck",
        status=DataspaceRunStatus.PASSED,
        request_payload={"profile": "dsp-tck"},
        result_payload={"status": "passed"},
        artifact_url="/tmp/dsp-tck.json",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_conformance_run=AsyncMock(return_value=run),
        get_connector=AsyncMock(return_value=SimpleNamespace(id=connector_id)),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await get_dsp_tck_run(
            run_id=run_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "read"
    service.get_connector.assert_awaited_once()
    assert response.id == run_id


@pytest.mark.asyncio
async def test_get_dsp_tck_run_without_connector_uses_connector_create_permission() -> None:
    tenant = _tenant()
    db = AsyncMock()
    run_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        connector_id=None,
        run_type="dsp-tck",
        status=DataspaceRunStatus.PASSED,
        request_payload={"profile": "dsp-tck"},
        result_payload={"status": "passed"},
        artifact_url="/tmp/dsp-tck.json",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        get_conformance_run=AsyncMock(return_value=run),
    )

    with (
        patch("app.modules.dataspace.router.DataspaceService", return_value=service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await get_dsp_tck_run(
            run_id=run_id,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    assert require_access.await_args.args[1] == "create"
    assert response.id == run_id


@pytest.mark.asyncio
async def test_get_dpp_regulatory_evidence_returns_service_payload() -> None:
    tenant = _tenant()
    db = AsyncMock()
    dpp_id = uuid4()
    dpp_service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id,
                owner_subject=tenant.user.sub,
                status="published",
            )
        )
    )
    evidence = RegulatoryEvidenceResponse(
        dpp_id=dpp_id,
        profile="espr_core",
        generated_at=datetime.now(UTC),
        compliance_reports=[],
        credential_status=CredentialStatusResponse(exists=False),
        resolver_links=[],
        shell_descriptors=[],
        dataspace_publications=[],
        dataspace_negotiations=[],
        dataspace_transfers=[],
        dataspace_conformance_runs=[],
    )
    dataspace_service = SimpleNamespace(build_regulatory_evidence=AsyncMock(return_value=evidence))

    with (
        patch("app.modules.dataspace.router.DPPService", return_value=dpp_service),
        patch("app.modules.dataspace.router.DataspaceService", return_value=dataspace_service),
        patch("app.modules.dataspace.router.require_access", new=AsyncMock()) as require_access,
    ):
        response = await get_dpp_regulatory_evidence(
            dpp_id=dpp_id,
            db=db,
            tenant=tenant,
            profile="espr_core",
        )

    dpp_service.get_dpp.assert_awaited_once()
    dataspace_service.build_regulatory_evidence.assert_awaited_once()
    require_access.assert_awaited_once()
    assert response.dpp_id == dpp_id
    assert response.profile == "espr_core"
