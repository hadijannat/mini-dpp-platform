"""Unit tests for dataspace service behavior."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.db.models import (
    DataspaceConformanceRun,
    DataspaceConnector,
    DataspaceConnectorSecret,
    DataspacePolicyTemplate,
    DataspacePolicyTemplateState,
    DataspaceRunStatus,
)
from app.modules.dataspace.schemas import (
    CatenaXDTRRuntimeConfig,
    DataspaceConnectorCreateRequest,
    EDCRuntimeConfig,
    SecretValueWrite,
)
from app.modules.dataspace.service import DataspaceService, DataspaceServiceError


@pytest.fixture
def encryption_key_b64() -> str:
    return base64.b64encode(b"0123456789ABCDEF0123456789ABCDEF").decode("ascii")


def _scalar_result(values: list[object]) -> object:
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: values),
    )


def _scalar_one_or_none_result(value: object | None) -> object:
    return SimpleNamespace(
        scalar_one_or_none=lambda: value,
    )


@pytest.mark.asyncio
async def test_create_connector_encrypts_secret_values(
    monkeypatch: pytest.MonkeyPatch,
    encryption_key_b64: str,
) -> None:
    monkeypatch.setenv("ENCRYPTION_MASTER_KEY", encryption_key_b64)
    get_settings.cache_clear()

    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result([]),  # existing secrets lookup
            _scalar_result(["edc-mgmt-api-key"]),  # secret refs lookup
        ]
    )
    added: list[object] = []

    def _add(entity: object) -> None:
        if isinstance(entity, DataspaceConnector) and getattr(entity, "id", None) is None:
            entity.id = uuid4()
        added.append(entity)

    session.add = Mock(side_effect=_add)

    service = DataspaceService(session)
    connector, refs = await service.create_connector(
        tenant_id=uuid4(),
        body=DataspaceConnectorCreateRequest(
            name="tenant-edc",
            runtime="edc",
            participant_id="BPNL000000000001",
            runtime_config=EDCRuntimeConfig(
                management_url="http://edc-controlplane:19193/management",
                management_api_key_secret_ref="edc-mgmt-api-key",
            ),
            secrets=[SecretValueWrite(secret_ref="edc-mgmt-api-key", value="super-secret-value")],
        ),
        created_by_subject="user-123",
    )

    assert connector.name == "tenant-edc"
    assert refs == ["edc-mgmt-api-key"]

    secret_rows = [row for row in added if isinstance(row, DataspaceConnectorSecret)]
    assert len(secret_rows) == 1
    secret_row = secret_rows[0]
    assert secret_row.secret_ref == "edc-mgmt-api-key"
    assert secret_row.encrypted_value.startswith("enc:v1:")
    assert "super-secret-value" not in secret_row.encrypted_value

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_catenax_connector_encrypts_token_secret(
    monkeypatch: pytest.MonkeyPatch,
    encryption_key_b64: str,
) -> None:
    monkeypatch.setenv("ENCRYPTION_MASTER_KEY", encryption_key_b64)
    get_settings.cache_clear()

    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result([]),  # existing secrets lookup
            _scalar_result(["dtr-token"]),  # secret refs lookup
        ]
    )
    added: list[object] = []

    def _add(entity: object) -> None:
        if isinstance(entity, DataspaceConnector) and getattr(entity, "id", None) is None:
            entity.id = uuid4()
        added.append(entity)

    session.add = Mock(side_effect=_add)

    service = DataspaceService(session)
    connector, refs = await service.create_connector(
        tenant_id=uuid4(),
        body=DataspaceConnectorCreateRequest(
            name="tenant-dtr",
            runtime="catena_x_dtr",
            participant_id="BPNL000000000001",
            runtime_config=CatenaXDTRRuntimeConfig(
                dtr_base_url="https://dtr.example.com",
                submodel_base_url="https://public.example.com",
                auth_type="token",
                token_secret_ref="dtr-token",
            ),
            secrets=[SecretValueWrite(secret_ref="dtr-token", value="dtr-secret-value")],
        ),
        created_by_subject="user-123",
    )

    assert connector.runtime.value == "catena_x_dtr"
    assert refs == ["dtr-token"]

    secret_rows = [row for row in added if isinstance(row, DataspaceConnectorSecret)]
    assert len(secret_rows) == 1
    assert secret_rows[0].encrypted_value.startswith("enc:v1:")
    assert "dtr-secret-value" not in secret_rows[0].encrypted_value
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_transition_policy_template_to_approved_sets_approver() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    service = DataspaceService(session)
    template = DataspacePolicyTemplate(
        id=uuid4(),
        name="default-policy",
        version="1",
        state=DataspacePolicyTemplateState.DRAFT,
        policy={"allow": ["read"]},
        created_by_subject="creator",
    )
    service.get_policy_template = AsyncMock(return_value=template)  # type: ignore[method-assign]

    updated = await service.transition_policy_template(
        tenant_id=uuid4(),
        policy_template_id=template.id,
        to_state=DataspacePolicyTemplateState.APPROVED,
        actor_subject="approver",
    )

    assert updated.state == DataspacePolicyTemplateState.APPROVED
    assert updated.approved_by_subject == "approver"
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_transition_policy_template_activation_supersedes_existing_active() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    previously_active = DataspacePolicyTemplate(
        id=uuid4(),
        name="core-access",
        version="1",
        state=DataspacePolicyTemplateState.ACTIVE,
        policy={"allow": ["read"]},
        created_by_subject="creator",
    )
    session.execute = AsyncMock(return_value=_scalar_result([previously_active]))

    service = DataspaceService(session)
    template = DataspacePolicyTemplate(
        id=uuid4(),
        name="core-access",
        version="2",
        state=DataspacePolicyTemplateState.APPROVED,
        policy={"allow": ["read", "transfer"]},
        created_by_subject="creator",
    )
    service.get_policy_template = AsyncMock(return_value=template)  # type: ignore[method-assign]

    updated = await service.transition_policy_template(
        tenant_id=uuid4(),
        policy_template_id=template.id,
        to_state=DataspacePolicyTemplateState.ACTIVE,
        actor_subject="governance-user",
    )

    assert updated.state == DataspacePolicyTemplateState.ACTIVE
    assert updated.approved_by_subject == "governance-user"
    assert previously_active.state == DataspacePolicyTemplateState.SUPERSEDED
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_invalid_policy_template_transition_is_rejected() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    service = DataspaceService(session)
    template = DataspacePolicyTemplate(
        id=uuid4(),
        name="immutable",
        version="1",
        state=DataspacePolicyTemplateState.DRAFT,
        policy={"allow": ["read"]},
        created_by_subject="creator",
    )
    service.get_policy_template = AsyncMock(return_value=template)  # type: ignore[method-assign]

    with pytest.raises(DataspaceServiceError, match="Invalid policy-template transition"):
        await service.transition_policy_template(
            tenant_id=uuid4(),
            policy_template_id=template.id,
            to_state=DataspacePolicyTemplateState.ACTIVE,
            actor_subject="reviewer",
        )


@pytest.mark.asyncio
async def test_execute_conformance_run_simulated_writes_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATASPACE_TCK_COMMAND", "")
    monkeypatch.setenv("DATASPACE_TCK_ARTIFACT_DIR", str(tmp_path))
    get_settings.cache_clear()

    service = DataspaceService(AsyncMock())
    run_id = uuid4()
    payload = await service._execute_conformance_run(  # noqa: SLF001 - unit test
        run_id=run_id,
        tenant_id=uuid4(),
        connector_id=uuid4(),
        profile="dsp-tck",
        metadata={"suite": "nightly"},
    )

    assert payload["mode"] == "simulated"
    assert payload["status"] == "passed"
    artifact_path = tmp_path / f"{run_id}.json"
    assert artifact_path.exists()
    stored = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert stored["run_id"] == str(run_id)
    assert stored["status"] == "passed"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_conformance_run_marks_failed_status() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    added: list[object] = []

    def _add(entity: object) -> None:
        if isinstance(entity, DataspaceConformanceRun) and getattr(entity, "id", None) is None:
            entity.id = uuid4()
        added.append(entity)

    session.add = Mock(side_effect=_add)
    service = DataspaceService(session)

    service._execute_conformance_run = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "status": "failed",
            "artifact_path": "/tmp/dsp-tck-run.json",
            "stderr": "connector did not respond",
        }
    )

    run = await service.create_conformance_run(
        tenant_id=uuid4(),
        connector_id=uuid4(),
        profile="dsp-tck",
        metadata={"job": "ci"},
        created_by_subject="system",
    )

    assert run.status == DataspaceRunStatus.FAILED
    assert run.artifact_url == "/tmp/dsp-tck-run.json"
    assert run.completed_at is not None
    assert run.result_payload is not None
    session.flush.assert_awaited()
    assert any(isinstance(entity, DataspaceConformanceRun) for entity in added)


@pytest.mark.asyncio
async def test_query_catalog_rejects_non_dsp_runtime() -> None:
    service = DataspaceService(AsyncMock())
    service.get_connector = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(runtime=SimpleNamespace(value="catena_x_dtr"))
    )

    with pytest.raises(
        DataspaceServiceError,
        match="does not support catalog query",
    ):
        await service.query_catalog(
            tenant_id=uuid4(),
            connector_id=uuid4(),
            connector_address="https://partner.example.com/protocol",
            protocol="dataspace-protocol-http",
            query_spec={},
        )


@pytest.mark.asyncio
async def test_build_regulatory_evidence_aggregates_dataspace_records() -> None:
    now = datetime.now(UTC)
    publication_id = uuid4()
    negotiation_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        category="espr_core",
                        is_compliant=True,
                        created_at=now,
                        report_json={"missing_fields": []},
                    )
                ]
            ),
            _scalar_one_or_none_result(
                SimpleNamespace(
                    revoked=False,
                    issuer_did="did:web:issuer",
                    issuance_date=now,
                    expiration_date=None,
                )
            ),
            _scalar_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        identifier="01/12345678901234",
                        link_type="dpp",
                        href="https://resolver.example/dpp/1",
                        active=True,
                        updated_at=now,
                    )
                ]
            ),
            _scalar_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        aas_id="urn:aas:example",
                        global_asset_id="urn:asset:example",
                        submodel_descriptors=[{"id": "sm1"}],
                        updated_at=now,
                    )
                ]
            ),
            _scalar_result(
                [
                    SimpleNamespace(
                        id=publication_id,
                        connector_id=uuid4(),
                        asset_id="asset-1",
                        status="published",
                        created_at=now,
                    )
                ]
            ),
            _scalar_result(
                [
                    SimpleNamespace(
                        id=negotiation_id,
                        publication_id=publication_id,
                        negotiation_id="neg-1",
                        state="FINALIZED",
                        contract_agreement_id="agreement-1",
                        updated_at=now,
                    )
                ]
            ),
            _scalar_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        negotiation_id=negotiation_id,
                        transfer_id="transfer-1",
                        state="COMPLETED",
                        updated_at=now,
                    )
                ]
            ),
            _scalar_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        run_type="dsp-tck",
                        status=DataspaceRunStatus.PASSED,
                        artifact_url="/tmp/tck.json",
                        created_at=now,
                    )
                ]
            ),
        ]
    )

    service = DataspaceService(session)
    response = await service.build_regulatory_evidence(
        tenant_id=uuid4(),
        dpp_id=uuid4(),
        profile="espr_core",
    )

    assert response.profile == "espr_core"
    assert response.credential_status.exists is True
    assert len(response.compliance_reports) == 1
    assert len(response.dataspace_publications) == 1
    assert len(response.dataspace_negotiations) == 1
    assert len(response.dataspace_transfers) == 1
    assert len(response.dataspace_conformance_runs) == 1
