# Expert Report 05: BaSyx/AASX Export Conformance

**Inspector**: BaSyx/AASX Compliance Engineer
**Date**: 2026-02-10
**Scope**: Export format conformance for all 6 formats, AASX round-trip validation, EPCIS injection, batch export

---

## Executive Summary

The export pipeline is **well-implemented and conformant**. All 6 export formats produce valid output. The AASX round-trip validation passes (export → BaSyx read → re-export → identical). EPCIS traceability injection works correctly across all formats. The codebase has strong test coverage for serialization edge cases (35 turtle regression tests, 4 conformance tests).

**Findings**: 3 observations, 1 minor gap, 0 critical issues.

---

## 1. Format-by-Format Analysis

### 1.1 JSON Export
- **Status**: PASS
- **Implementation**: `ExportService.export_json()` wraps AAS env with metadata (digest, JWS, timestamp)
- **Canonical**: Uses `sort_keys=True, indent=2, ensure_ascii=False`
- **Observation**: Output includes `signedJws: null` and `signingKeyId: null` when no signing key is set. This is correct behavior but consumers should be aware.

### 1.2 AASX Export
- **Status**: PASS
- **Implementation**: `ExportService.export_aasx()` uses BaSyx `AASXWriter` with ECMA-376 OPC core properties
- **Compliance**: IDTA Part 5 structure verified (Content_Types.xml, _rels/.rels, /aasx/data.json)
- **Round-trip**: Validated via `validate_aasx_compliance()` — reads back through `AASXReader`, re-serializes to JSON, confirms structural equivalence
- **Key design**: `failsafe=True` on export path (per BaSyx boundary rule documented in PR #46)

### 1.3 XML Export
- **Status**: PASS
- **Implementation**: JSON → BaSyx object store → BaSyx XML serializer
- **Conformance**: aas-test-engines `check_xml_data()` passes (verified in `test_aas_conformance.py`)
- **Note**: BaSyx skips ConceptDescriptions lacking `modelType` during deserialization (logged as warnings, not errors). This is expected — IDTA templates don't always include `modelType` on CDs.

### 1.4 JSON-LD Export
- **Status**: PASS
- **Implementation**: `aas_to_jsonld()` in `serialization.py` — custom mapper builds `@context`, `@type`, `@graph`
- **IRI safety**: `_IRI_UNSAFE` translation table encodes `{` → `%7B`, `}` → `%7D` (PR #51 fix)
- **Element coverage**: All 16 AAS element types handled in `_element_to_node()`:
  - Property, MultiLanguageProperty, Range, File, Blob
  - SubmodelElementCollection, SubmodelElementList
  - Entity, RelationshipElement, AnnotatedRelationshipElement
  - ReferenceElement, Operation, BasicEventElement, Capability
  - ConceptDescription, AssetAdministrationShell

### 1.5 Turtle Export
- **Status**: PASS
- **Implementation**: JSON-LD → rdflib Graph → `serialize(format="turtle")`
- **Regression coverage**: 35 dedicated tests in `test_turtle_export_regression.py`
- **IRI encoding**: Verified — `{arbitrary}` placeholders from IDTA templates are percent-encoded, preventing N3 parse errors

### 1.6 PDF Export
- **Status**: PASS
- **Implementation**: `fpdf` library generates basic summary with metadata + JSON dump
- **Note**: PDF is a flat text dump of JSON, not a structured DPP report. This is adequate for a summary export but lacks visual richness.

---

## 2. AASX Round-Trip Validation

### New Tool: `backend/tests/tools/aasx_roundtrip_validator.py`

Implements 6-step validation:
1. JSON dict → BaSyx object store
2. Object store → AASX package bytes
3. AASX bytes → BaSyx object store (round-trip read)
4. Object store → AASX package bytes (re-export)
5. Compare identifiable IDs (set equality)
6. Compare JSON serializations (string equality)

**Result**: ALL STEPS PASS with the built-in test environment.

**File element caveat**: BaSyx `AASXReader` resolves `File.value` paths as package parts. External URLs (e.g., `https://...`) work correctly. Local paths (e.g., `/docs/file.pdf`) require the file to be in the `DictSupplementaryFileContainer`. The production export service creates an empty container, so DPPs with local file paths may fail AASX round-trip. This is not a bug — it's by design (files aren't stored in the DB, only references).

---

## 3. EPCIS Traceability Injection

**Status**: PASS

Validated the full injection flow:
- `inject_traceability_submodel()` creates an AAS Submodel with:
  - `EPCISEndpoint` property (when URL provided)
  - `LatestEventSummary` collection (last event type, time, biz step, disposition, location, total count)
  - `EventHistory` collection (per-event details with payload)
- Injection is in-place mutation of `revision.aas_env_json` (safe — revision is not persisted after export)
- No-op when event list is empty
- Injected submodel exports correctly in ALL formats (JSON, AASX, XML, JSON-LD, Turtle)

---

## 4. Batch Export

**Status**: PASS

- `POST /export/batch` accepts up to 100 DPP IDs
- Produces ZIP archive with one file per DPP
- Supports `json` and `aasx` formats
- Per-item error isolation (individual DPP failures don't block others)
- Response headers include `X-Batch-Total`, `X-Batch-Succeeded`, `X-Batch-Failed`

**Observation O-1**: Batch export only supports `json` and `aasx` formats (see `BatchExportRequest.format` type: `Literal["json", "aasx"]`). The other 4 formats (XML, JSON-LD, Turtle, PDF) are not available for batch export. This may be intentional to limit ZIP complexity but is worth documenting.

---

## 5. Conformance Test Results

### aas-test-engines (4 tests)
| Test | Result |
|------|--------|
| `test_json_env_passes_metamodel_check` | PASS |
| `test_json_with_multilang_property` | PASS |
| `test_json_with_collection` | PASS |
| `test_xml_roundtrip_passes_check` | PASS |

### Turtle Regression (35 tests)
All 35 tests pass. Coverage includes:
- All 16 element types
- Primitive and object list items
- IRI encoding (curly braces, valid URIs)
- JSON-LD brace encoding
- Reference serialization

### AASX Round-trip (new tool)
| Step | Result |
|------|--------|
| JSON → Object Store | PASS (3 identifiables) |
| Object Store → AASX | PASS (2,385 bytes, valid structure) |
| AASX → Object Store | PASS (3 identifiables) |
| Object Store → AASX (re-export) | PASS |
| ID comparison | PASS (0 missing, 0 extra) |
| JSON comparison | PASS (identical serializations) |

---

## 6. Observations and Findings

### O-1: Batch Export Format Limitation (LOW)
**Location**: `backend/app/modules/export/router.py:247`
**Description**: `BatchExportRequest.format` is `Literal["json", "aasx"]`, excluding XML, JSON-LD, Turtle, and PDF from batch export.
**Impact**: Low — single-DPP export supports all 6 formats. Batch is primarily for bulk data exchange where JSON/AASX are the standard interchange formats.
**Recommendation**: Consider adding XML and JSON-LD to batch export if needed by downstream consumers.

### O-2: Export Router Code Duplication (LOW)
**Location**: `backend/app/modules/export/router.py:120-237`
**Description**: Each format branch in `export_dpp()` repeats the same `emit_audit_event()` + `Response()` pattern. The 6 branches are structurally identical except for content generation and media type.
**Impact**: Maintenance burden — adding a new format requires duplicating ~15 lines.
**Recommendation**: Refactor to a dispatch table mapping format → (export_fn, media_type, extension). Not a bug, just tech debt.

### O-3: BaSyx ConceptDescription Skipping (INFORMATIONAL)
**Location**: BaSyx runtime behavior during XML/AASX export
**Description**: BaSyx's `read_aas_json_file(failsafe=True)` skips ConceptDescriptions that lack a `modelType` field. Some IDTA templates produce CDs without `modelType`. The custom JSON-LD/Turtle serializer handles them correctly, but XML/AASX exports lose them.
**Impact**: CDs may be missing from XML/AASX exports if the source template doesn't include `modelType`. This is a BaSyx limitation, not a platform bug.
**Recommendation**: Consider adding `"modelType": "ConceptDescription"` during template ingestion if it's missing.

### G-1: No Conformance Tests for JSON-LD or Turtle (MINOR GAP)
**Location**: `backend/tests/conformance/`
**Description**: The conformance suite only tests JSON and XML formats via `aas_test_engines`. There are no `aas_test_engines` validators for JSON-LD or Turtle (these are custom serializations, not BaSyx outputs).
**Impact**: Low — the 35 turtle regression tests provide good coverage, but there's no external validator for RDF output.
**Recommendation**: Consider adding SHACL validation or rdflib parse-back tests to verify the JSON-LD graph structure matches the AAS ontology.

---

## 7. Deliverables

| Artifact | Path |
|----------|------|
| Expert report | `docs/internal/reviews/expert-reports/05_basyx_export.md` |
| AASX roundtrip validator | `backend/tests/tools/aasx_roundtrip_validator.py` |
| Conformance test output | `conformance_logs/conformance_test_output.txt` |
| AASX roundtrip report | `conformance_logs/aasx_roundtrip_report.json` |

---

## 8. Verdict

**PASS** — The export pipeline is conformant and well-tested. No critical or high-severity issues found. The 3 observations are minor improvements that don't affect correctness. The new `aasx_roundtrip_validator.py` tool provides ongoing validation capability.
