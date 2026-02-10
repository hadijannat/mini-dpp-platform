"""Setup inspection environment with reproducible template ingestion.

This script:
1. Fetches all 7 IDTA templates from GitHub
2. Generates definition AST and JSON Schema for each
3. Saves artifacts to evidence directory
4. Produces ingestion summary report

Usage:
    uv run python tests/tools/inspection_setup.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.templates.service import get_template_service

# Template keys to fetch
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
    """Get or create evidence directory for this inspection run."""
    base_dir = Path("/evidence") if Path("/evidence").exists() else Path("evidence")
    run_dir = base_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def ingest_template(template_key: str, service: Any, evidence_dir: Path) -> dict[str, Any]:
    """Ingest a single template and save artifacts.

    Args:
        template_key: Template identifier (e.g., 'digital-nameplate')
        service: TemplateService instance
        evidence_dir: Directory to save artifacts

    Returns:
        Dict with status, version, and any error info
    """
    try:
        print(f"📥 Fetching {template_key}...")
        contract = await service.get_contract(template_key)

        template_dir = evidence_dir / "templates" / template_key
        template_dir.mkdir(parents=True, exist_ok=True)

        # Save definition AST
        definition_path = template_dir / "definition.json"
        definition_path.write_text(json.dumps(contract["definition"], indent=2))

        # Save JSON Schema
        schema_path = template_dir / "schema.json"
        schema_path.write_text(json.dumps(contract["schema"], indent=2))

        # Save source metadata
        source_path = template_dir / "source_metadata.json"
        source_path.write_text(json.dumps(contract["source"], indent=2))

        print(f"✅ {template_key}: {contract['source']['version']}")
        return {
            "status": "success",
            "version": contract["source"]["version"],
            "source_file": contract["source"]["source_file"],
            "source_sha": contract["source"]["source_sha"],
            "definition_elements": len(contract["definition"].get("submodels", [])),
        }

    except Exception as e:
        print(f"❌ {template_key}: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
        }


async def setup_inspection_environment() -> Path:
    """Setup inspection environment and ingest all templates.

    Returns:
        Path to evidence directory
    """
    print("🔧 IDTA Pipeline Inspection - Environment Setup")
    print("=" * 60)

    # Get evidence directory
    evidence_dir = get_evidence_dir()
    print(f"\n📁 Evidence directory: {evidence_dir}")

    # Get template service
    service = get_template_service()

    # Ingest all templates
    results = {}
    for template_key in TEMPLATES:
        result = await ingest_template(template_key, service, evidence_dir)
        results[template_key] = result

    # Generate summary
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    failed_count = len(results) - success_count

    summary = {
        "run_timestamp": datetime.now().isoformat(),
        "evidence_dir": str(evidence_dir),
        "templates_attempted": len(TEMPLATES),
        "templates_succeeded": success_count,
        "templates_failed": failed_count,
        "results": results,
    }

    # Save summary
    summary_path = evidence_dir / "ingestion_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    # Print summary
    print("\n" + "=" * 60)
    print("📊 INGESTION SUMMARY")
    print("=" * 60)
    print(f"✅ Succeeded: {success_count}/{len(TEMPLATES)}")
    print(f"❌ Failed: {failed_count}/{len(TEMPLATES)}")

    if failed_count > 0:
        print("\nFailed templates:")
        for key, result in results.items():
            if result["status"] == "failed":
                print(f"  • {key}: {result['error']}")

    print(f"\n📄 Full report: {summary_path}")

    return evidence_dir


async def main():
    """Main entry point."""
    evidence_dir = await setup_inspection_environment()
    print(f"\n✨ Inspection environment ready: {evidence_dir}\n")


if __name__ == "__main__":
    asyncio.run(main())
