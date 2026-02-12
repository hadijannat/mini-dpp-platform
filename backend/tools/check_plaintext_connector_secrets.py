"""Guardrail script to detect plaintext connector secrets before rollout."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Connector, DataspaceConnector, DataspaceConnectorSecret
from app.db.session import close_db, get_background_session, init_db
from app.modules.dataspace.secret_scan import (
    find_plaintext_secret_fields,
    is_encrypted_secret_value,
)


async def scan_plaintext_connector_secrets(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all plaintext secret findings across legacy and dataspace connectors."""
    findings: list[dict[str, Any]] = []

    legacy_connectors = (
        (await session.execute(select(Connector).order_by(Connector.created_at.desc())))
        .scalars()
        .all()
    )
    for connector in legacy_connectors:
        config = connector.config or {}
        for finding in find_plaintext_secret_fields(config):
            findings.append(
                {
                    "scope": "legacy_connector_config",
                    "tenant_id": str(connector.tenant_id),
                    "connector_id": str(connector.id),
                    "connector_name": connector.name,
                    "path": finding.path,
                    "key": finding.key,
                    "value_preview": finding.value_preview,
                }
            )

    dataspace_connectors = (
        (
            await session.execute(
                select(DataspaceConnector).order_by(DataspaceConnector.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    for connector in dataspace_connectors:
        runtime_config = connector.runtime_config or {}
        for finding in find_plaintext_secret_fields(runtime_config):
            findings.append(
                {
                    "scope": "dataspace_runtime_config",
                    "tenant_id": str(connector.tenant_id),
                    "connector_id": str(connector.id),
                    "connector_name": connector.name,
                    "runtime": connector.runtime.value,
                    "path": finding.path,
                    "key": finding.key,
                    "value_preview": finding.value_preview,
                }
            )

    dataspace_secrets = (
        (
            await session.execute(
                select(DataspaceConnectorSecret).order_by(
                    DataspaceConnectorSecret.created_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    for secret in dataspace_secrets:
        if is_encrypted_secret_value(secret.encrypted_value):
            continue
        findings.append(
            {
                "scope": "dataspace_connector_secret",
                "tenant_id": str(secret.tenant_id),
                "connector_id": str(secret.connector_id),
                "secret_ref": secret.secret_ref,
                "secret_id": str(secret.id),
                "issue": "encrypted_value is not prefixed with enc:v1:",
                "value_preview": (
                    f"{secret.encrypted_value[:12]}..." if secret.encrypted_value else "<empty>"
                ),
            }
        )

    return findings


async def _main() -> int:
    await init_db()
    try:
        async with get_background_session() as session:
            findings = await scan_plaintext_connector_secrets(session)
    finally:
        await close_db()

    report = {
        "status": "fail" if findings else "pass",
        "checked_at": datetime.now(UTC).isoformat(),
        "finding_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(report, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
