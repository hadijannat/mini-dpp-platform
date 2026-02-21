"""Backfill CEN canonical identifiers and carrier bindings for existing DPPs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DPP,
    DataCarrier,
    DPPIdentifier,
    ExternalIdentifier,
    ExternalIdentifierStatus,
    IdentifierEntityType,
)
from app.db.session import close_db, get_background_session, init_db
from app.standards.cen_pren.identifiers_18219.service import IdentifierService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill canonical CEN identifiers for existing DPPs and carriers."
    )
    parser.add_argument(
        "--tenant-id",
        help="Single tenant UUID to process. Omit when using --all-tenants.",
    )
    parser.add_argument(
        "--all-tenants",
        action="store_true",
        help="Process every tenant that has at least one DPP.",
    )
    parser.add_argument(
        "--limit-per-tenant",
        type=int,
        default=None,
        help="Optional cap on number of DPPs processed per tenant.",
    )
    parser.add_argument(
        "--skip-carrier-linking",
        action="store_true",
        help="Skip data-carrier external identifier/payload hash backfill.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute and report changes without committing.",
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
        result = await session.execute(select(DPP.tenant_id).distinct())
        return [tenant_id for tenant_id in result.scalars().all() if tenant_id is not None]


async def _get_active_product_identifier_id(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    dpp_id: UUID,
) -> UUID | None:
    result = await session.execute(
        select(ExternalIdentifier.id)
        .join(DPPIdentifier, DPPIdentifier.external_identifier_id == ExternalIdentifier.id)
        .where(
            DPPIdentifier.tenant_id == tenant_id,
            DPPIdentifier.dpp_id == dpp_id,
            ExternalIdentifier.tenant_id == tenant_id,
            ExternalIdentifier.entity_type == IdentifierEntityType.PRODUCT,
            ExternalIdentifier.status == ExternalIdentifierStatus.ACTIVE,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _process_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    limit_per_tenant: int | None,
    link_carriers: bool,
) -> dict[str, int]:
    service = IdentifierService(session)
    counters: dict[str, int] = {
        "dpps_scanned": 0,
        "dpps_with_existing_identifier": 0,
        "identifiers_registered": 0,
        "dpps_without_identifier_source": 0,
        "carriers_scanned": 0,
        "carriers_identifier_linked": 0,
        "carriers_payload_hashed": 0,
    }

    stmt = select(DPP).where(DPP.tenant_id == tenant_id).order_by(DPP.id)
    if limit_per_tenant is not None:
        stmt = stmt.limit(limit_per_tenant)
    dpps = (await session.execute(stmt)).scalars().all()

    for dpp in dpps:
        counters["dpps_scanned"] += 1
        has_identifier = await service.has_active_product_identifier(
            tenant_id=tenant_id,
            dpp_id=dpp.id,
        )
        if has_identifier:
            counters["dpps_with_existing_identifier"] += 1
        else:
            identifier = await service.ensure_dpp_product_identifier_from_asset_ids(
                dpp=dpp,
                created_by=dpp.owner_subject,
            )
            if identifier is None:
                counters["dpps_without_identifier_source"] += 1
            else:
                counters["identifiers_registered"] += 1

        if not link_carriers:
            continue

        active_identifier_id = await _get_active_product_identifier_id(
            session,
            tenant_id=tenant_id,
            dpp_id=dpp.id,
        )
        carriers = (
            await session.execute(
                select(DataCarrier).where(
                    DataCarrier.tenant_id == tenant_id,
                    DataCarrier.dpp_id == dpp.id,
                )
            )
        ).scalars().all()
        for carrier in carriers:
            counters["carriers_scanned"] += 1
            if active_identifier_id is not None and carrier.external_identifier_id is None:
                carrier.external_identifier_id = active_identifier_id
                counters["carriers_identifier_linked"] += 1
            if carrier.encoded_uri and not carrier.payload_sha256:
                carrier.payload_sha256 = hashlib.sha256(
                    carrier.encoded_uri.encode("utf-8")
                ).hexdigest()
                counters["carriers_payload_hashed"] += 1

    return counters


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
            "dry_run": args.dry_run,
            "tenant_count": len(tenant_ids),
            "processed": [],
            "errors": [],
        }
        for tenant_id in tenant_ids:
            try:
                async with get_background_session() as session:
                    counters = await _process_tenant(
                        session,
                        tenant_id=tenant_id,
                        limit_per_tenant=args.limit_per_tenant,
                        link_carriers=not args.skip_carrier_linking,
                    )
                    if args.dry_run:
                        await session.rollback()
                    else:
                        await session.commit()
                    summary["processed"].append({"tenant_id": str(tenant_id), **counters})
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"].append({"tenant_id": str(tenant_id), "error": str(exc)})

        print(json.dumps(summary, indent=2))
        return 0 if not summary["errors"] else 1
    finally:
        await close_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
