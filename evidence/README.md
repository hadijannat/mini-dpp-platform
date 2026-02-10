# Inspection Evidence Directory

This directory contains artifacts from IDTA Pipeline Inspection runs.

## Directory Structure

Each inspection run creates a timestamped directory:

```
evidence/
└── run_YYYYMMDD_HHMMSS/
    ├── ingestion_summary.json          # Template fetch results
    ├── templates/
    │   ├── digital-nameplate/
    │   │   ├── definition.json         # Definition AST
    │   │   ├── schema.json             # JSON Schema
    │   │   ├── source_metadata.json    # GitHub provenance
    │   │   └── audit.json              # audit_template_rendering output
    │   └── battery-passport/...
    ├── dpps/
    │   ├── minimal_nameplate/
    │   │   ├── create_request.json
    │   │   ├── create_response.json
    │   │   ├── exports/
    │   │   │   ├── export.aasx
    │   │   │   ├── export.json
    │   │   │   ├── export.jsonld
    │   │   │   ├── export.ttl
    │   │   │   ├── export.xml
    │   │   │   └── export.pdf
    │   │   ├── conformance/
    │   │   │   ├── aasx_validation.log
    │   │   │   └── json_validation.log
    │   │   └── roundtrip/
    │   │       ├── aasx_roundtrip.json
    │   │       └── diff.txt
    ├── frontend/
    │   ├── screenshots/
    │   │   ├── nameplate_editor.png
    │   │   └── battery_passport_editor.png
    │   ├── qualifier_enforcement_report.json
    │   └── validation_errors.json
    ├── expert_reports/
    │   ├── 01_idta_smt_specialist.md
    │   ├── 02_template_versioning.md
    │   ├── 03_parser_schema.md
    │   ├── 04_frontend_forms.md
    │   ├── 05_basyx_export.md
    │   ├── 06_persistence_integrity.md
    │   ├── 07_security_tenancy.md
    │   └── 08_qa_automation.md
    └── inspection_summary.md           # Consolidated report
```

## Usage

Evidence is collected automatically during inspection runs. To start an inspection:

```bash
# Start inspection environment
docker compose -f docker-compose.inspection.yml up -d

# Run setup script
cd backend
uv run python tests/tools/inspection_setup.py

# Evidence will be saved to evidence/run_YYYYMMDD_HHMMSS/
```

## Retention

Evidence directories should be retained for:
- **30 days**: Development inspection runs
- **1 year**: Pre-release inspection runs
- **Indefinitely**: Production release inspection runs
