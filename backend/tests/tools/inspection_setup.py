"""Setup inspection environment with reproducible template ingestion.

This script:
1. Refreshes supported IDTA templates from upstream
2. Generates canonical definition AST + JSON schema contracts
3. Saves artifacts to an evidence run directory
4. Produces a machine-readable ingestion summary

Usage:
    uv run python tests/tools/inspection_setup.py
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db.session import close_db, get_background_session, init_db
from app.modules.templates.catalog import get_template_descriptor
from app.modules.templates.service import TemplateRegistryService

TEMPLATES = [
    "digital-nameplate",
    "carbon-footprint",
    "technical-data",
    "hierarchical-structures",
    "handover-documentation",
    "contact-information",
    "battery-passport",
]


def get_evidence_dir() -> Path:
    """Create an evidence directory for this inspection run."""
    base_dir = Path("/evidence") if Path("/evidence").exists() else Path("evidence")
    run_dir = base_dir / f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


async def ingest_template(
    template_key: str,
    service: TemplateRegistryService,
    *,
    commit: Callable[[], Any],
    evidence_dir: Path,
) -> dict[str, Any]:
    """Refresh one template and persist its generated contract artifacts."""
    descriptor = get_template_descriptor(template_key)
    if descriptor is None:
        return {
            "status": "failed",
            "error": f"Unknown template key: {template_key}",
            "error_type": "ValueError",
        }

    if not descriptor.refresh_enabled:
        return {
            "status": "skipped",
            "support_status": descriptor.support_status,
            "reason": "Template refresh disabled in catalog",
        }

    try:
        print(f"Fetching {template_key} ...")
        template = await service.refresh_template(template_key)
        await commit()

        contract = service.generate_template_contract(template)

        template_dir = evidence_dir / "templates" / template_key
        _write_json(template_dir / "definition.json", contract["definition"])
        _write_json(template_dir / "schema.json", contract["schema"])
        _write_json(template_dir / "source_metadata.json", contract["source_metadata"])

        submodel = contract["definition"].get("submodel", {})
        element_count = len(submodel.get("elements", []))

        print(
            f"OK {template_key}: "
            f"resolved={contract['source_metadata']['resolved_version']} "
            f"elements={element_count}"
        )
        return {
            "status": "success",
            "version": template.idta_version,
            "resolved_version": template.resolved_version,
            "source_file_path": template.source_file_path,
            "source_file_sha": template.source_file_sha,
            "source_kind": template.source_kind,
            "selection_strategy": template.selection_strategy,
            "definition_elements": element_count,
        }
    except Exception as exc:
        print(f"FAILED {template_key}: {exc}")
        return {
            "status": "failed",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


async def setup_inspection_environment() -> Path:
    """Run template ingestion and write a summary report."""
    print("IDTA Pipeline Inspection - Environment Setup")
    print("=" * 60)
    evidence_dir = get_evidence_dir()
    print(f"Evidence directory: {evidence_dir}")

    await init_db()
    try:
        async with get_background_session() as session:
            service = TemplateRegistryService(session)
            results: dict[str, dict[str, Any]] = {}

            for template_key in TEMPLATES:
                results[template_key] = await ingest_template(
                    template_key,
                    service,
                    commit=session.commit,
                    evidence_dir=evidence_dir,
                )

            success_count = sum(1 for value in results.values() if value["status"] == "success")
            failed_count = sum(1 for value in results.values() if value["status"] == "failed")
            skipped_count = sum(1 for value in results.values() if value["status"] == "skipped")

            summary = {
                "run_timestamp": datetime.now(UTC).isoformat(),
                "evidence_dir": str(evidence_dir),
                "templates_attempted": len(TEMPLATES),
                "templates_succeeded": success_count,
                "templates_failed": failed_count,
                "templates_skipped": skipped_count,
                "results": results,
            }

            summary_path = evidence_dir / "ingestion_summary.json"
            _write_json(summary_path, summary)

            print("=" * 60)
            print("INGESTION SUMMARY")
            print("=" * 60)
            print(f"Succeeded: {success_count}/{len(TEMPLATES)}")
            print(f"Failed: {failed_count}/{len(TEMPLATES)}")
            print(f"Skipped: {skipped_count}/{len(TEMPLATES)}")
            print(f"Report: {summary_path}")
    finally:
        await close_db()

    return evidence_dir


async def main() -> None:
    evidence_dir = await setup_inspection_environment()
    print(f"Inspection environment ready: {evidence_dir}")


if __name__ == "__main__":
    asyncio.run(main())
