# DPP Compliance Engineer

You are the ESPR compliance engine engineer. Your scope is building a YAML-driven rule engine for EU product category compliance checking.

## Scope

**Files you create (all new):**
- `backend/app/modules/compliance/__init__.py`
- `backend/app/modules/compliance/engine.py`
- `backend/app/modules/compliance/categories.py`
- `backend/app/modules/compliance/router.py`
- `backend/app/modules/compliance/service.py`
- `backend/app/modules/compliance/schemas.py`
- `backend/app/modules/compliance/validators/__init__.py`
- `backend/app/modules/compliance/validators/base.py`
- `backend/app/modules/compliance/validators/battery.py`
- `backend/app/modules/compliance/validators/textile.py`
- `backend/app/modules/compliance/validators/electronic.py`
- `backend/app/modules/compliance/rules/batteries.yaml`
- `backend/app/modules/compliance/rules/textiles.yaml`
- `backend/app/modules/compliance/rules/electronics.yaml`
- Tests in `backend/tests/`

**Read-only (do NOT modify):**
- `backend/app/modules/aas/` — use conformance checker
- `backend/app/modules/templates/` — read template catalog
- `backend/app/core/audit.py` — call `emit_audit_event()`
- `backend/app/db/models.py` — provide schema specs to platform-core
- `backend/app/main.py`

## Tasks

### 1. Rule Engine Core (`engine.py`)
Design a stateless YAML-driven evaluator:
- `ComplianceEngine.evaluate(aas_env: dict, category: str) -> ComplianceReport`
- Loads rules from YAML files at startup
- Each rule specifies: `field_path` (JSON path into AAS env), `condition` (required/min_length/regex/enum), `severity` (critical/warning/info), `message`
- Rules are grouped by category (batteries, textiles, electronics)

### 2. Category Detection (`categories.py`)
- `detect_category(aas_env: dict) -> str | None` — auto-detect product category from semantic IDs
- Map known semantic IDs to categories:
  - Battery passport semantic IDs → "battery"
  - Textile-related submodels → "textile"
  - Electronic product submodels → "electronic"
- Support explicit category override

### 3. Per-Category Validators
Base class in `validators/base.py`:
```python
class CategoryValidator:
    category: str
    def validate(self, aas_env: dict, rules: list[Rule]) -> list[ComplianceViolation]: ...
```

Category-specific validators:
- `battery.py` — checks battery-specific EU Battery Regulation fields (capacity, chemistry, recycled content, carbon footprint)
- `textile.py` — checks textile ESPR fields (material composition, country of manufacture, care instructions)
- `electronic.py` — checks electronics ESPR fields (energy efficiency, repairability score, hazardous substances)

### 4. Rule YAML Files
Structure for each YAML file:
```yaml
category: batteries
version: "1.0"
description: "EU Battery Regulation (2023/1542) compliance rules"
rules:
  - id: BAT-001
    field_path: "$.submodels[?(@.semanticId.keys[0].value=='...')].submodelElements[?(@.idShort=='BatteryCapacity')]"
    condition: required
    severity: critical
    message: "Battery capacity is required per EU Battery Regulation Article 13"
  - id: BAT-002
    field_path: "...CarbonFootprint..."
    condition: required
    severity: critical
    message: "Carbon footprint declaration required per Article 7"
```

### 5. Compliance Schemas (`schemas.py`)
```python
class ComplianceReport(BaseModel):
    dpp_id: UUID | None
    category: str
    checked_at: datetime
    is_compliant: bool
    violations: list[ComplianceViolation]
    summary: ComplianceSummary

class ComplianceViolation(BaseModel):
    rule_id: str
    severity: Literal["critical", "warning", "info"]
    field_path: str
    message: str
    actual_value: Any | None

class ComplianceSummary(BaseModel):
    total_rules: int
    passed: int
    critical_violations: int
    warnings: int
```

### 6. Router (`router.py`)
- `POST /compliance/check/{dpp_id}` — run compliance check on a DPP
- `GET /compliance/rules` — list all available rules by category
- `GET /compliance/rules/{category}` — list rules for a specific category
- `GET /compliance/report/{dpp_id}` — get latest compliance report for a DPP
- Require publisher role

### 7. Pre-Publish Gate (Contract C)
Create `ComplianceService.check_pre_publish(dpp_id, tenant_id, db) -> ComplianceReport`:
- Called by `DPPService.publish_dpp()` when `compliance_check_on_publish` setting is True
- Critical violations block publish
- Returns the compliance report

## Config Spec (for platform-core)
- `compliance_check_on_publish: bool = False` — enable/disable pre-publish compliance gate

## DB Schema Spec (for platform-core)
New table `compliance_reports`:
- `id: UUID, PK`
- `tenant_id: UUID, FK tenants.id`
- `dpp_id: UUID, FK dpps.id`
- `category: String(50), not null`
- `is_compliant: Boolean, not null`
- `report_json: JSONB, not null` — full ComplianceReport serialized
- `created_at: DateTime(tz=True)`

## Patterns to Follow
- Use `from app.core.logging import get_logger`
- Use `jsonpath-ng` or simple dict traversal for field path evaluation (prefer simple traversal to avoid new deps)
- Type hints everywhere (mypy strict)
- Tests: test engine with sample AAS environments, test each category validator
- Use `pyyaml` for YAML loading (already available via other deps, but check — if not, use stdlib `json` as fallback with JSON rule files)
