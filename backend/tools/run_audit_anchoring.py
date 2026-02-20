"""Run audit Merkle anchoring batches (for cron/CronJob execution)."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models import AuditEvent
from app.db.session import close_db, get_background_session, init_db
from app.modules.audit.anchoring_service import AuditAnchoringService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anchor unanchored audit hash-chain events.")
    parser.add_argument(
        "--tenant-id",
        help="Single tenant UUID to anchor. Omit when using --all-tenants.",
    )
    parser.add_argument(
        "--all-tenants",
        action="store_true",
        help="Anchor all tenants with hashed audit events.",
    )
    parser.add_argument(
        "--max-batches-per-tenant",
        type=int,
        default=None,
        help="Optional safety cap for batches anchored per tenant in one run.",
    )
    return parser.parse_args()


async def _resolve_tenant_ids(
    *,
    tenant_id_arg: str | None,
    all_tenants: bool,
) -> list[UUID]:
    if tenant_id_arg:
        return [UUID(tenant_id_arg)]
    if not all_tenants:
        raise ValueError("Provide --tenant-id or --all-tenants")

    async with get_background_session() as session:
        result = await session.execute(
            select(AuditEvent.tenant_id)
            .where(AuditEvent.tenant_id.is_not(None), AuditEvent.event_hash.is_not(None))
            .distinct()
        )
        return [tenant_id for tenant_id in result.scalars().all() if tenant_id is not None]


async def _main() -> int:
    args = _parse_args()
    await init_db()
    try:
        tenant_ids = await _resolve_tenant_ids(
            tenant_id_arg=args.tenant_id,
            all_tenants=args.all_tenants,
        )
        summary: dict[str, object] = {
            "ran_at": datetime.now(UTC).isoformat(),
            "tenant_count": len(tenant_ids),
            "anchored": [],
            "errors": [],
        }
        for tenant_id in tenant_ids:
            try:
                async with get_background_session() as session:
                    service = AuditAnchoringService(session)
                    anchors = await service.anchor_all_pending(
                        tenant_id=tenant_id,
                        max_batches=args.max_batches_per_tenant,
                    )
                    await session.commit()
                    summary["anchored"].append(
                        {
                            "tenant_id": str(tenant_id),
                            "batch_count": len(anchors),
                            "anchor_ids": [str(anchor.id) for anchor in anchors],
                        }
                    )
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"].append({"tenant_id": str(tenant_id), "error": str(exc)})
        print(json.dumps(summary, indent=2))
        return 0 if not summary["errors"] else 1
    finally:
        await close_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
