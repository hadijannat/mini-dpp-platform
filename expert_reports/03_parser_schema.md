# Parser & Schema Fidelity Inspection Report

**Inspector**: Parser/Schema Engineer
**Date**: 2026-02-10
**Scope**: BaSyx parser, definition AST builder, schema generator, qualifier mapping, golden file validation

---

## Executive Summary

The template pipeline (BaSyx parser -> definition AST -> JSON Schema) is **structurally sound** with correct failsafe boundaries, comprehensive element type coverage, and robust qualifier mapping. No critical or high-severity findings. Two informational items and one low-severity gap noted.

**Overall Assessment: PASS**

---

## 1. Golden File Tests

**Status**: 6/7 golden files present and maintained

| Template | Version | Golden File |
|----------|---------|-------------|
| digital-nameplate | 3.0.1 | Present |
| contact-information | 1.0.1 | Present |
| technical-data | 2.0.1 | Present |
| carbon-footprint | 1.0.1 | Present |
| handover-documentation | 2.0.1 | Present |
| hierarchical-structures | 1.1.1 | Present |
| battery-passport | 1.0.x | **Missing** (upstream IDTA 02035 not published) |

Golden tests are E2E (require running backend stack). They verify:
- `idta_version` and `semantic_id` metadata match
- SHA-256 hashes of canonical JSON for definition and schema
- Contract endpoint returns identical definition+schema as separate endpoints

**Note**: Cannot run locally without full Docker stack. Offline verification available via `compute_golden_hashes.py`.

---

## 2. Failsafe Boundary Enforcement

| Path | File | Line | failsafe | Correct? |
|------|------|------|----------|----------|
| Ingestion (parser) | `basyx_parser.py` | 52 | `False` | YES |
| Export (AASX) | `export/service.py` | 184 | `True` | YES |
| Export (XML via service) | `export/service.py` | 139 | `True` | YES |
| Serialization (XML) | `aas/serialization.py` | 143 | `True` | YES |

**Rule**: Strict validation at system boundary (ingestion), lenient for round-tripping stored data (export). All paths comply.

---

## 3. Element Type Coverage

### Pipeline Layer Comparison

| Element Type | definition.py | schema_from_definition.py | serialization.py |
|-------------|:---:|:---:|:---:|
| Property | Explicit | Explicit | else clause |
| MultiLanguageProperty | Explicit | Explicit | Explicit |
| Range | Explicit | Explicit | Explicit |
| File | Explicit | Explicit | Explicit |
| Blob | Explicit | Explicit | Explicit |
| SubmodelElementCollection | Explicit | Explicit | Explicit |
| SubmodelElementList | Explicit | Explicit | Explicit |
| Entity | Explicit | Explicit | Explicit |
| ReferenceElement | Explicit | Explicit | else clause |
| RelationshipElement | Explicit | Explicit | Explicit |
| AnnotatedRelationshipElement | Explicit | Explicit | Explicit |
| Operation | Explicit | else (read-only) | Explicit |
| Capability | Explicit | else (read-only) | Explicit |
| BasicEventElement | Explicit | else (read-only) | Explicit |

**Coverage**: 14/14 AAS element types handled in definition builder. 11/14 have dedicated schema generators; 3 are correctly marked read-only (not user-editable structural types). Serialization covers all 14.

### Schema else Clause Behavior

Operation, Capability, and BasicEventElement fall to the `else` clause in `schema_from_definition.py:72-79`:
```python
schema = {
    "type": "object",
    "title": node.get("idShort") or "",
    "description": ...,
    "properties": {},
    "x-readonly": True,
}
```
This is **architecturally correct** -- these types represent operations/events/capabilities, not user-editable form fields.

---

## 4. Qualifier Mapping

### SMT Qualifier Types (16 total)

| Qualifier | Semantic ID | Type Aliases | Schema Effect |
|-----------|------------|-------------|--------------|
| Cardinality | `.../Cardinality/1/0` | `SMT/Cardinality`, `Cardinality`, `SMT/Multiplicity`, `Multiplicity` | `x-cardinality`, `required` |
| EitherOr | `.../EitherOr/1/0` | `SMT/EitherOr`, `EitherOr` | `x-either-or` |
| DefaultValue | `.../DefaultValue/1/0` | `SMT/DefaultValue`, `DefaultValue` | `default` |
| InitialValue | `.../InitialValue/1/0` | `SMT/InitialValue`, `InitialValue` | (stored, not schema) |
| ExampleValue | `.../ExampleValue/1/0` | `SMT/ExampleValue`, `ExampleValue` | `examples` |
| AllowedRange | `.../AllowedRange/1/0` | `SMT/AllowedRange`, `AllowedRange` | `minimum`, `maximum` |
| AllowedValue | `.../AllowedValue/1/0` | `SMT/AllowedValue`, `AllowedValue` | `pattern` |
| RequiredLang | `.../RequiredLang/1/0` | `SMT/RequiredLang`, `RequiredLang` | `x-required-languages` |
| AccessMode | `.../AccessMode/1/0` | `SMT/AccessMode`, `AccessMode` | `readOnly`, `writeOnly` |
| FormTitle | `.../FormTitle/1/0` | `SMT/FormTitle`, `FormTitle` | `title`, `x-form-title` |
| FormInfo | `.../FormInfo/1/0` | `SMT/FormInfo`, `FormInfo` | `description`, `x-form-info` |
| FormUrl | `.../FormUrl/1/0` | `SMT/FormUrl`, `FormUrl` | `x-form-url` |
| FormChoices | `.../FormChoices/1/0` | `SMT/FormChoices`, `FormChoices` | `enum`, `x-form-choices` |
| Naming | `.../Naming/1/0` | `SMT/Naming`, `Naming` | `x-naming` |
| AllowedIdShort | `.../AllowedIdShort/1/0` | `SMT/AllowedIdShort`, `AllowedIdShort` | `x-allowed-id-short` |
| EditIdShort | `.../EditIdShort/1/0` | `SMT/EditIdShort`, `EditIdShort` | `x-edit-id-short` |

**Test results**: 18/18 qualifier tests passing. AllowedRange validates min <= max with degradation to raw-only on inverted ranges.

---

## 5. Definition AST Completeness

### Template Rendering Audit Results

| Template | Elements | Editable | ReadOnly | Gaps |
|----------|----------|----------|----------|------|
| carbon-footprint | 27 | 27 (100%) | 0 | 1 empty collection |
| contact-information | 36 | 36 (100%) | 0 | 0 |
| digital-nameplate | 38 | 38 (100%) | 0 | 0 |
| handover-documentation | 23 | 23 (100%) | 0 | 0 |
| hierarchical-structures | 26 | 20 (76.9%) | 6 | 2 empty lists + 3 empty collections |
| technical-data | 66 | 66 (100%) | 0 | 8 empty collections |

**Totals**: 216 elements, 210 editable (97.2%), 6 read-only, 6 gap flags

**Gap Analysis**: All "gaps" are empty SubmodelElementCollections (structural placeholders for user-extensible containers like `ArbitrarySMC`, `GoodsHandoverAddress`). These are **expected** in IDTA templates that define extensible schemas.

Element types encountered across all templates:
- Property: 72
- MultiLanguageProperty: 42
- SubmodelElementCollection: 37
- SubmodelElementList: 28
- File: 10
- RelationshipElement: 6
- Range: 6
- SubmodelElement (synthetic list items): 6
- ReferenceElement: 5
- Entity: 4

---

## 6. Test Coverage Summary

| Test Suite | Tests | Status |
|-----------|-------|--------|
| `test_smt_qualifiers.py` | 18 | All passing |
| `test_turtle_export_regression.py` | 35 | All passing |
| Template unit tests | 54 | All passing (1 integration test error due to no DB) |
| Schema-related tests | 153 | All passing |
| Golden files | 6 | Present (E2E, cannot run locally) |

---

## Findings

### PSF-1 [INFO]: Operation/Capability/BasicEventElement produce read-only schema

**Location**: `schema_from_definition.py:72-79`
**Description**: These 3 types fall to the `else` clause producing `{"type": "object", "x-readonly": True}`. This is by design -- they are structural metadata types, not user-editable values.
**Risk**: None.

### PSF-2 [LOW]: Synthetic list item fallback incomplete

**Location**: `schema_from_definition.py:110-120`
**Description**: When `SubmodelElementList` has `typeValueListElement` of Operation/Capability/BasicEventElement and no sample items, the synthetic fallback produces `{"type": "string"}` instead of an appropriate object schema.
**Risk**: Minimal -- no current IDTA template uses lists of these types.
**Recommendation**: Add these types to the synthetic node fallback set in `_list_schema()`.

### PSF-3 [INFO]: Battery passport golden file pending

**Description**: No golden file for `battery-passport`. IDTA 02035 template source not yet published upstream.
**Tracking**: Already documented in CLAUDE.md.

### PSF-4 [GOOD]: Dual-path concept description extraction

**Location**: `definition.py:180-214`
**Description**: `_concept_description_definition()` tries structured IEC 61360 data specification first, then falls back to top-level attributes. Handles both modern and legacy concept descriptions robustly.

### PSF-5 [GOOD]: Multi-convention qualifier recognition

**Location**: `qualifiers.py:111-211`
**Description**: Each qualifier type matches by both type-string aliases (e.g., `SMT/Cardinality` and `Cardinality`) AND semantic ID URIs. Resilient against different template encoding conventions.

### PSF-6 [GOOD]: Deterministic ordering throughout pipeline

**Description**: Both `definition.py` and `schema_from_definition.py` sort elements by `(idShort, path, modelType)` tuples. Qualifiers sorted by `(type, value, semanticId)`. This ensures golden file hashes remain stable regardless of BaSyx iteration order.

---

## Recommendations

1. **PSF-2 fix**: Add Operation/Capability/BasicEventElement to the `_list_schema` synthetic type set (maps to read-only object schema). Low priority.
2. **Battery passport golden**: Monitor IDTA 02035 publication. Add golden file once available.
3. **Consider offline golden verification**: The `compute_golden_hashes.py` tool could be enhanced to also validate schema structure (not just hashes) for CI environments without a full backend.
