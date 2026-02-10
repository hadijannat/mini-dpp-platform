# IDTA SMT Specialist Report

**Analyst**: IDTA Submodel Template Specialist
**Date**: 2026-02-10
**Scope**: Semantic ID coverage, qualifier conformance, and frontend enforcement across all 7 IDTA templates

---

## Executive Summary

Audited 6 of 7 IDTA submodel templates (battery-passport unavailable upstream). The template pipeline achieves **100% JSON Schema coverage** for all 216 elements and **97.2% editable coverage** (6 abstract-type read-only elements in Technical Data are correctly handled). The qualifier parsing system recognizes 15 qualifier types; **11 are fully enforced** end-to-end (backend schema + frontend rendering + Zod validation), 1 is partially enforced, and 3 are not enforced in the frontend but affect only niche use cases.

**Key finding**: The most impactful gap is `AllowedIdShort` not being validated in the frontend (MEDIUM severity, affects Handover Documentation). All other unenforced qualifiers are LOW severity and affect templates/use cases that don't currently exercise them.

---

## 1. Semantic ID Coverage

### Per-Template Results

| Template | Version | Elements | Editable | Schema Coverage | Concept Descs | ESPR Category |
|----------|---------|----------|----------|-----------------|---------------|---------------|
| carbon-footprint | 1.0.1 | 27 | 100% | 100% | 29 | environmental |
| contact-information | 1.0.1 | 36 | 100% | 100% | 35 | identity |
| digital-nameplate | 3.0.1 | 36 | 100% | 100% | 30 | identity |
| handover-documentation | 2.0.1 | 38 | 100% | 100% | 34 | endoflife |
| hierarchical-structures | 1.1.1 | 11 | 100% | 100% | 8 | materials |
| technical-data | 2.0.1 | 68 | 91.2% | 100% | 28 | compliance |
| **battery-passport** | **1.0** | **N/A** | **N/A** | **N/A** | **N/A** | **identity** |

**Aggregate**: 216 elements, 210 editable (97.2%), 164 concept descriptions, 100% schema coverage.

### Semantic ID Source

All semantic IDs are centrally managed in `shared/idta_semantic_registry.json` and consumed by both backend (via `semantic_registry.py`) and frontend. The registry includes:
- 7 template entries with canonical semantic IDs
- 9 legacy semantic ID aliases for backwards compatibility
- ESPR tier prefix mappings for 4 access levels

Every element in the definition AST carries a `semanticId` field sourced from the IDTA template's BaSyx model. The pipeline faithfully preserves these through parse -> definition -> schema -> frontend.

### Element Type Distribution

| Model Type | Count | Frontend Renderer | Notes |
|------------|-------|-------------------|-------|
| Property | 72 | PropertyField / BooleanField / EnumField | Type-dispatched by valueType and form_choices |
| MultiLanguageProperty | 42 | MultiLangField | Dynamic language management |
| SubmodelElementCollection | 37 | CollectionField | Collapsible sections |
| SubmodelElementList | 28 | ListField | Virtualized for >20 items |
| File | 10 | FileField | contentType + URL inputs |
| RelationshipElement | 6 | RelationshipField | JSON text input for references |
| Range | 6 | RangeField | Min/max number inputs |
| SubmodelElement (abstract) | 6 | ReadOnlyField | Correct degradation |
| ReferenceElement | 5 | ReferenceField | Structured type + keys editor |
| Entity | 4 | EntityField | Type selector + statements |

---

## 2. Qualifier Type Inventory

### Raw Qualifier Types Found in Templates

11 distinct qualifier type strings were found across the 6 audited templates:

| Raw Type String | Normalized SMT Field | Templates Using |
|-----------------|----------------------|-----------------|
| `SMT/Cardinality` | cardinality | carbon-footprint, digital-nameplate, handover-documentation, hierarchical-structures, technical-data |
| `Multiplicity` | cardinality | contact-information |
| `ExampleValue` | example_value | handover-documentation |
| `SMT/ExampleValue/CDD` | example_value | technical-data |
| `SMT/ExampleValue/CustomerSpecific` | example_value | technical-data |
| `SMT/ExampleValue/ECLASS` | example_value | technical-data |
| `SMT/ExampleValue/UNSPSC` | example_value | technical-data |
| `FormChoices` | form_choices | hierarchical-structures |
| `AllowedIdShort` | allowed_id_short | handover-documentation |
| `EditIdShort` | edit_id_short | hierarchical-structures |
| `Naming` | naming | technical-data |

### Full SmtQualifiers Dataclass (15 fields)

The backend `qualifiers.py` recognizes 15 qualifier types via dual matching (type string OR semantic ID):

1. **cardinality** - One / ZeroToOne / ZeroToMany / OneToMany
2. **either_or** - Cross-field group identifier
3. **default_value** - Pre-fill value
4. **initial_value** - Initial value (distinct from default)
5. **example_value** - Placeholder hint
6. **allowed_range** - min..max numeric constraint
7. **allowed_value_regex** - Pattern validation
8. **required_lang** - Mandatory languages for MLP
9. **access_mode** - ReadOnly / WriteOnly
10. **form_title** - Override display label
11. **form_info** - Override description
12. **form_url** - Documentation link
13. **form_choices** - Enum options
14. **naming** - IdShort generation hint
15. **allowed_id_short** - Constrained idShort values

Plus 2 additional qualifiers from the SMT spec handled separately:
16. **edit_id_short** - Boolean flag for idShort editability

---

## 3. Frontend Enforcement Matrix

### Enforcement Status per Qualifier

| Qualifier | Backend → Schema | Frontend UI | Zod Validation | Overall |
|-----------|------------------|-------------|----------------|---------|
| cardinality | `x-cardinality`, `required[]` | `isNodeRequired()` asterisk | `min(1)` for lists, required fields | FULL |
| example_value | `examples[]` | Placeholder in Property/MLP/Enum | N/A (hint only) | FULL |
| form_choices | `enum`, `x-form-choices` | EnumField `<select>` | `z.enum()` | FULL |
| required_lang | `x-required-languages` | Pre-populated rows, no-remove | `.refine()` non-empty check | FULL |
| access_mode | `readOnly`, `x-readonly` | ReadOnlyField routing | `z.unknown()` | FULL |
| either_or | `x-either-or` | `useEitherOrGroups` hook | Custom `validate()` | FULL |
| allowed_range | `minimum`, `maximum` | Number input step | `.min()/.max()` | FULL |
| allowed_value_regex | `pattern`, `x-allowed-value` | N/A | `.regex()` | FULL |
| form_title | Schema `title`, `x-form-title` | `getNodeLabel()` priority | N/A | FULL |
| form_info | Schema `description`, `x-form-info` | `getNodeDescription()` tooltip | N/A | FULL |
| form_url | `x-form-url` | FieldWrapper "Learn more" link | N/A | FULL |
| default_value | Schema `default` | **Not read** to pre-populate | N/A | PARTIAL |
| allowed_id_short | `x-allowed-id-short` | **Not in UISchema type** | **Not validated** | NOT ENFORCED |
| edit_id_short | `x-edit-id-short` | **Not in UISchema type** | **Not validated** | NOT ENFORCED |
| naming | `x-naming` | **Not in UISchema type** | **Not consumed** | NOT ENFORCED |
| initial_value | **Not mapped to schema** | **Not in SmtQualifiers usage** | **Not validated** | NOT ENFORCED |

### Score: 11/15 fully enforced (73%), 1 partial (7%), 3 not enforced (20%)

---

## 4. UISchema Type Gap

The frontend `UISchema` TypeScript type (`frontend/src/features/editor/types/uiSchema.ts`) is missing several `x-` extension fields that the backend emits:

**Present in UISchema type**:
- `x-multi-language`, `x-range`, `x-file-upload`, `x-reference`, `x-entity`
- `x-relationship`, `x-annotated-relationship`, `x-readonly`, `x-blob`
- `x-form-url`, `x-required-languages`, `x-allowed-range`

**Missing from UISchema type** (backend emits but frontend can't read with type safety):
- `x-cardinality` - Emitted by `_apply_smt()`
- `x-form-title` - Emitted by `_apply_smt()`
- `x-form-info` - Emitted by `_apply_smt()`
- `x-form-choices` - Emitted by `_apply_smt()`
- `x-allowed-value` - Emitted by `_apply_smt()`
- `x-allowed-id-short` - Emitted by `_apply_smt()`
- `x-edit-id-short` - Emitted by `_apply_smt()`
- `x-naming` - Emitted by `_apply_smt()`
- `x-semantic-id` - Emitted by `_property_schema()`

**Impact**: The frontend works around this by reading directly from `node.smt` (the DefinitionNode's SMT qualifiers) rather than from the schema. This is correct for the current architecture since the definition AST is the primary source. However, the schema could serve as a fallback for schema-only rendering paths (e.g., `buildFromUISchema()`).

---

## 5. Structural Gaps

### Childless Collections (10 total)

| Template | Element | Impact |
|----------|---------|--------|
| carbon-footprint | GoodsHandoverAddress | Falls back to schema-driven rendering |
| digital-nameplate | AddressInformation | Falls back to schema-driven rendering |
| technical-data | 8 ArbitrarySMC / Section collections | Intentionally empty "arbitrary" placeholders |

**Assessment**: `CollectionField` correctly falls back to `schema.properties` when `node.children` is empty (lines 59-71). No user impact.

### Statementless Entities (2 total)

| Template | Element | Impact |
|----------|---------|--------|
| handover-documentation | Entity (in Entities list) | Shows JSON fallback |
| hierarchical-structures | Node (leaf) | Shows JSON fallback |

**Assessment**: `EntityField` renders a JSON `<pre>` block when no statements exist and current data has statement content (lines 99-109). Acceptable degradation.

### RelationshipElement JSON Input (6 elements)

The 6 `RelationshipElement` instances in Hierarchical Structures (HasPart, IsPartOf, SameAs) require users to input AAS references as raw JSON text. `RelationshipField` shows a structured `ReferenceDisplay` for existing references but uses a plain text input for new reference entry.

**Assessment**: MEDIUM usability impact. The `ReferenceField` already has a structured key-type/value editor that could be adapted for first/second reference editing.

---

## 6. Findings Summary

| ID | Severity | Title | Template(s) |
|----|----------|-------|-------------|
| SMT-FIND-01 | INFO | Battery Passport template unavailable | battery-passport |
| SMT-FIND-02 | **MEDIUM** | AllowedIdShort not enforced in frontend | handover-documentation |
| SMT-FIND-03 | LOW | EditIdShort not enforced in frontend | hierarchical-structures |
| SMT-FIND-04 | LOW | Naming qualifier not surfaced in frontend | technical-data |
| SMT-FIND-05 | LOW | DefaultValue/InitialValue not pre-populated | all (latent) |
| SMT-FIND-06 | INFO | 6 abstract SubmodelElement items | technical-data |
| SMT-FIND-07 | INFO | 10 childless/statementless containers | multiple |
| SMT-FIND-08 | **MEDIUM** | RelationshipElement references as JSON text | hierarchical-structures |
| SMT-FIND-09 | INFO | Qualifier type naming inconsistency | all |
| SMT-FIND-10 | INFO | UISchema type missing x- extension fields | frontend |

---

## 7. Recommendations

### Priority 1 (MEDIUM — should fix)

1. **SMT-FIND-02**: Add `x-allowed-id-short` to UISchema type. In ListField/EntityField, validate new item idShort values against the allowed list when adding dynamic items.

2. **SMT-FIND-08**: Upgrade RelationshipField's edit mode to use structured inputs (Reference Type dropdown + Key type/value pairs) instead of raw JSON text. Reuse the pattern from `ReferenceField`.

### Priority 2 (LOW — nice to have)

3. **SMT-FIND-05**: In `formDefaults.ts`, read `UISchema.default` values to pre-populate form fields when no initial data exists.

4. **SMT-FIND-10**: Add all missing `x-` fields to `UISchema` type for type safety and forward compatibility.

5. **SMT-FIND-03/04**: When idShort editing or arbitrary field creation is implemented, consume `x-edit-id-short` and `x-naming` from schema.

### No Action Required

6. **SMT-FIND-01/06/07/09**: Informational findings requiring no code changes.

---

## 8. Methodology

1. **Audit tool**: Ran `backend/tests/tools/audit_template_rendering.py --json` which fetches all 7 IDTA templates from GitHub, runs them through the full pipeline (BaSyx parse -> definition AST -> JSON Schema), and produces per-element inventory with schema coverage analysis.

2. **Frontend analysis**: Read all 14 editor components (`AASRenderer`, `PropertyField`, `MultiLangField`, `EnumField`, `CollectionField`, `ListField`, `EntityField`, `RangeField`, `FileField`, `ReferenceField`, `RelationshipField`, `AnnotatedRelationshipField`, `ReadOnlyField`, `BooleanField`), 3 hooks (`useSubmodelForm`, `useEitherOrGroups`, `useConceptDescriptions`), `zodSchemaBuilder.ts`, `pathUtils.ts`, and type definitions.

3. **Qualifier tracing**: Mapped each of the 15 SmtQualifiers fields from `qualifiers.py` through `schema_from_definition.py` (backend schema emission) to `zodSchemaBuilder.ts` (Zod validation) and field components (UI rendering).

4. **Machine-readable data**: Full analysis data in `docs/internal/reviews/expert-reports/semantic_analysis.json`.
