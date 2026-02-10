# Phase 4: Frontend Qualifier Enforcement — Expert Report

**Inspector**: Frontend Forms Engineer
**Date**: 2026-02-10
**Scope**: SubmodelEditorPage, AASRenderer, 13 field components, zodSchemaBuilder, validation utils, useEitherOrGroups hook

---

## 1. Architecture Summary

The frontend editor follows a clean **recursive type-dispatch** architecture:

```
SubmodelEditorPage (orchestrator, ~425 lines)
  └─ AASRendererList → AASRenderer (type dispatch)
       └─ PropertyField / MultiLangField / CollectionField / ListField / ...
            └─ FieldWrapper (label + error + tooltip shell)
```

**Validation layers**:
1. **Zod schema** (via `zodSchemaBuilder.ts` → `zodResolver`) — enforced by React Hook Form in real-time (`mode: 'onChange'`)
2. **Legacy validation** (`validation.ts`) — run on save for enum, pattern, range, required, readOnly, minItems, cross-field x-range
3. **Either-Or groups** (`useEitherOrGroups.ts`) — cross-field "at least one" validation on save

---

## 2. Field Type Rendering Matrix

| # | AAS Model Type | Component | Renders Correctly | Notes |
|---|---------------|-----------|:-:|-------|
| 1 | Property (xs:string) | `PropertyField` | Yes | `<input type="text">`, example_value as placeholder |
| 2 | Property (xs:integer) | `PropertyField` | Yes | `<input type="number" step="1">`, nullable |
| 3 | Property (xs:decimal) | `PropertyField` | Yes | `<input type="number" step="0.01">`, nullable |
| 4 | Property (xs:boolean) | `BooleanField` | Yes | Checkbox via delegation from PropertyField |
| 5 | Property (xs:date) | `PropertyField` | Yes | `<input type="date">` via resolveInputType |
| 6 | Property (xs:anyURI) | `PropertyField` | Yes | `<input type="url">` |
| 7 | Property + form_choices | `EnumField` | Yes | `<select>` dropdown, example_value in placeholder |
| 8 | MultiLanguageProperty | `MultiLangField` | Yes | Dynamic language rows, required_lang indicator, add/remove |
| 9 | SubmodelElementCollection | `CollectionField` | Yes | CollapsibleSection with recursive renderNode |
| 10 | SubmodelElementList | `ListField` | Yes | Add/remove items, virtualization at 20+ items |
| 11 | Entity | `EntityField` | Yes | entityType select, globalAssetId input, recursive statements |
| 12 | RelationshipElement | `RelationshipField` | Yes | First/Second reference display with ReferenceDisplay component |
| 13 | AnnotatedRelationshipElement | `AnnotatedRelationshipField` | Yes | First/Second + recursive annotations in CollapsibleSection |
| 14 | File | `FileField` | Yes | contentType + value (URL) inputs |
| 15 | Blob | `ReadOnlyField` | Yes | Read-only JSON display |
| 16 | ReferenceElement | `ReferenceField` | Yes | Reference type select + key list with add/remove |
| 17 | Range | `RangeField` | Yes | Side-by-side min/max number inputs |
| 18 | Operation / Capability / BasicEventElement | `ReadOnlyField` | Yes | Correctly rendered as read-only |

**All 12+ AAS element types are correctly dispatched** by `AASRenderer.tsx:51-106`.

---

## 3. Qualifier Enforcement Audit

### 3.1 ENFORCED Qualifiers (Working Correctly)

| Qualifier | Enforcement Layer | How Enforced | Test Coverage |
|-----------|------------------|-------------|:---:|
| **cardinality** (One/OneToMany) | Zod + UI | `isNodeRequired()` shows `*` indicator; Zod `arr.min(1)` for OneToMany lists | Yes (zodSchemaBuilder.test.ts) |
| **form_title** | UI | Used as label via `getNodeLabel()` | Indirect |
| **form_info** | UI | Tooltip description via `getNodeDescription()` | Indirect |
| **form_url** | UI | "Learn more" link in FieldWrapper | Indirect |
| **access_mode** (readonly) | UI + Dispatch | `ReadOnlyField` rendered when `access_mode === 'readonly'` | Indirect |
| **required_lang** | Zod + UI | Zod refine checks all required langs non-empty; UI shows "Required languages" hint and prevents deletion of required lang rows | Yes (zodSchemaBuilder.test.ts) |
| **either_or** | Save-time | `useEitherOrGroups` + `validateEitherOr` checks at least one group member has value | Yes (validation.test.ts) |
| **allowed_value_regex** | Zod | `strSchema.regex(new RegExp(regex))` in buildPropertySchema | Yes (zodSchemaBuilder.test.ts) |
| **allowed_range** (min/max) | Zod + validation.ts | Zod `.min()/.max()` on number types; `validation.ts` range check on x-range fields | Yes (zodSchemaBuilder.test.ts, validation.test.ts) |
| **form_choices** | Zod + UI | `z.enum(choices)` validation + `EnumField` renders `<select>` dropdown | Yes (zodSchemaBuilder.test.ts) |
| **example_value** | UI | Shown as `placeholder` on PropertyField, MultiLangField, EnumField | Indirect |

### 3.2 NOT ENFORCED Qualifiers (Gaps)

| # | Qualifier | Backend Produces | Frontend Reads | Enforced | Severity |
|---|-----------|:---:|:---:|:---:|---------|
| **G1** | `default_value` | Yes (smt field + schema `default`) | `formDefaults.ts` reads `schema.default` for list items only | **Partial** | MEDIUM |
| **G2** | `initial_value` | Yes (smt field) | No | **No** | LOW |
| **G3** | `allowed_id_short` | Yes (`x-allowed-id-short` in schema) | No | **No** | MEDIUM |
| **G4** | `edit_id_short` | Yes (`x-edit-id-short` in schema) | No | **No** | MEDIUM |
| **G5** | `naming` | Yes (`x-naming` in schema) | No | **No** | LOW |

---

## 4. Detailed Gap Analysis

### G1: `default_value` — Partially Enforced

**Current behavior**: `formDefaults.ts:5` checks `schema.default` but only when creating new list items via `defaultValueForSchema()`. When the SubmodelEditorPage initializes for a brand new submodel (no existing data), `initialData` is `{}`, so form fields start empty even when the template specifies defaults.

**Impact**: Users must manually enter values that the template author intended as defaults, wasting time and increasing error risk.

**Expected behavior**: On first render with empty `initialData`, the form should pre-populate fields that have `node.smt.default_value` or `schema.default` set. This should be done in `useSubmodelForm` or a form initialization helper.

**UI Mockup**:
```
┌─ ManufacturerName ──────────────────┐
│ [ACME Corporation            ]      │  ← Pre-filled from default_value
│ ℹ️ Default: ACME Corporation        │  ← Hint showing the template default
└─────────────────────────────────────┘
```

### G2: `initial_value` — Not Enforced

**Current behavior**: `SmtQualifiers.initial_value` is parsed by the backend and passed in the definition node's `smt` object, but no frontend code references it.

**Difference from default_value**: Per IDTA SMT spec, `initial_value` is for the value the element should be set to when first created (a starting suggestion), while `default_value` is the value assumed when no user input is provided. The distinction matters for required fields.

**Impact**: Low — most templates use `example_value` (which IS displayed as placeholder) or `default_value`. However, templates that distinguish between "suggestion" and "assumed default" cannot express this.

**UI Mockup**:
```
┌─ SerialNumber ──────────────────────┐
│ [SN-2024-001                 ]      │  ← Pre-filled from initial_value (editable)
│ ℹ️ Suggested starting value         │
└─────────────────────────────────────┘
```

### G3: `allowed_id_short` — Not Enforced

**Current behavior**: Backend produces `x-allowed-id-short` in the UISchema, but the frontend UISchema type doesn't declare this field, and no component reads it.

**Impact**: In SMT, `allowed_id_short` constrains which idShort names are valid for dynamically created list items (SubmodelElementList) or entity statements. Without enforcement, users creating new list items can use arbitrary names, violating template structure rules.

**Affected components**: `ListField.tsx` (when adding items) and `EntityField.tsx` (entity statements with dynamic naming).

**UI Mockup**:
```
┌─ ContactRole [SubmodelElementList] ──┐
│ Add item ▼                            │
│ ┌────────────────────┐                │
│ │ ● CEO              │ ← Constrained  │
│ │   CTO              │    dropdown of  │
│ │   CFO              │    allowed IDs  │
│ │   Engineer         │                 │
│ └────────────────────┘                │
│                                       │
│ ❌ Free-text input blocked           │
└───────────────────────────────────────┘
```

### G4: `edit_id_short` — Not Enforced

**Current behavior**: Backend produces `x-edit-id-short` (boolean) in the UISchema, but the frontend doesn't declare or use it.

**Impact**: `edit_id_short: true` means users should be allowed to edit the idShort of list items or entity statements. `edit_id_short: false` (or absent) means idShort names are fixed by the template. Currently, the frontend always generates index-based paths (`name.0`, `name.1`) and never allows idShort editing, so this is effectively always `false`.

**UI Mockup (when edit_id_short=true)**:
```
┌─ MaterialComposition [List] ──────────┐
│  Item 1:                               │
│  idShort: [Polyethylene       ] ← Edit │
│  Value:   [67.5              ]          │
│                                         │
│  Item 2:                               │
│  idShort: [Polypropylene      ] ← Edit │
│  Value:   [32.5              ]          │
│                                         │
│  [+ Add item]                          │
└─────────────────────────────────────────┘
```

### G5: `naming` — Not Enforced

**Current behavior**: Backend produces `x-naming` in the UISchema, but the frontend doesn't read it. Per IDTA SMT spec, `naming` provides a pattern or convention for how idShort names should be formed (e.g., `"Material_"` meaning items should be named `Material_1`, `Material_2`, etc.).

**Impact**: Low — purely cosmetic/naming convention. Without enforcement, auto-generated item names use generic index-based patterns.

**UI Mockup**:
```
┌─ Substances [SubmodelElementList] ────┐
│  Substance_1: [Lead   ] [0.001 %]     │  ← Auto-named per naming pattern
│  Substance_2: [Cadmium] [0.0005%]     │
│  [+ Add Substance_3]                  │  ← Button label uses naming pattern
└────────────────────────────────────────┘
```

---

## 5. Validation Coverage Assessment

### 5.1 Zod Schema Builder (`zodSchemaBuilder.ts`)

| Scenario | Covered | Test |
|----------|:-------:|------|
| String property | Yes | zodSchemaBuilder.test.ts line 25 |
| Integer with int() constraint | Yes | line 30 |
| Decimal as number | Yes | line 37 |
| Boolean | Yes | line 43 |
| allowed_range on integer | Yes | line 50 |
| form_choices → z.enum | Yes | line 60 |
| allowed_value_regex | Yes | line 69 |
| MultiLanguageProperty record | Yes | line 81 |
| required_lang refine | Yes | line 93 |
| Range min≤max | Yes | line 118 |
| Collection recursive | Yes | line 134 |
| List array + OneToMany min(1) | Yes | line 157 |
| File structure | Yes | line 194 |
| ReferenceElement | Yes | line 208 |
| RelationshipElement (AAS ref) | Yes | line 224 |
| AnnotatedRelationshipElement | Yes | line 279 |
| UISchema fallback | Yes | line 313 |
| Entity statements recursive | **No** | Missing: no test for Entity Zod validation |
| Blob handled | **No** | Missing: Blob is rendered via ReadOnlyField, not tested in Zod |
| allowed_range raw string parse | **No** | normalizeRange() raw string branch not tested |

### 5.2 Legacy Validation (`validation.ts`)

| Scenario | Covered | Test |
|----------|:-------:|------|
| Required field check | Yes | validation.test.ts line 17 |
| Enum validation | Yes | line 29 |
| Pattern validation | Yes | line 38 |
| Number range (min/max) | Yes | line 47 |
| x-range min≤max | Yes | line 58 |
| x-multi-language required langs | Yes | line 68 |
| Nested object recursion | Yes | line 79 |
| Array minItems | Yes | line 96 |
| ReadOnly field protection | Yes | line 113 |
| Either-Or group validation | Yes | line 147 |

### 5.3 Missing Test Coverage

1. **Entity Zod validation**: No test for `buildEntitySchema()` producing correct nested shape
2. **normalizeRange raw string**: The `range.raw` → regex parse path in `normalizeRange()` has no unit test
3. **E2E qualifier enforcement**: No Playwright test validates qualifier behavior in the actual rendered form

---

## 6. Code Quality Findings

### F1: Duplicate Either-Or Logic (LOW)

`useEitherOrGroups.ts` and `validation.ts:validateEitherOr()` contain identical tree-walking and group validation logic. The hook's `validate` function and the standalone `validateEitherOr` do exactly the same thing. The SubmodelEditorPage uses the hook version (`validateEitherOrGroups`) in `handleSave`.

**Recommendation**: Remove `validateEitherOr` from `validation.ts` or delegate to the same implementation.

### F2: Zod + Legacy Double Validation (LOW)

The SubmodelEditorPage runs BOTH Zod validation (via zodResolver, `mode: 'onChange'`) AND legacy `validateSchema()` + `validateReadOnly()` on save. This means:
- Real-time: Zod catches type errors, range violations, regex mismatches
- On save: Legacy catches the same things plus readOnly and required checks

This creates a confusing UX where some errors appear immediately (Zod) and others only on save (legacy). It works correctly but could be simplified.

### F3: `defaultValueForSchema` Doesn't Check `node.smt.default_value` (MEDIUM)

The function only checks `schema.default`, but the SMT `default_value` lives on `node.smt.default_value` which is a different object. The backend does propagate `default_value` into `schema.default` via `schema_from_definition.py:310-312`, but only when `schema.type` is set. For edge cases where type is missing, the default is lost.

### F4: ReferenceDisplay Duplicated (LOW)

`RelationshipField.tsx` and `AnnotatedRelationshipField.tsx` both define identical `AASKey`, `AASReference` types and `ReferenceDisplay` components. Should be extracted to a shared component.

### F5: UISchema Type Missing Extensions (MEDIUM)

The `UISchema` type in `uiSchema.ts` doesn't declare `x-allowed-id-short`, `x-edit-id-short`, or `x-naming` fields that the backend produces. This means TypeScript won't flag missing usage, and the data is silently ignored.

---

## 7. Security Observations

1. **JSON injection in RelationshipField**: Lines 63-68 of both `RelationshipField.tsx` and `AnnotatedRelationshipField.tsx` use `JSON.parse(e.target.value)` to parse user input into reference objects. While this is sandboxed to the form state and never sent to the server directly, malformed JSON is silently swallowed. No XSS risk since React escapes rendered values.

2. **Regex injection from templates**: `zodSchemaBuilder.ts:114` and `validation.ts:110` construct `new RegExp(regex)` from template-provided patterns. Both are wrapped in try/catch, so catastrophic regex patterns won't crash the page. However, ReDoS (Regular Expression Denial of Service) from malicious templates could freeze the browser tab.

---

## 8. Recommendations

### Priority 1 (Should Fix)
1. **Pre-populate `default_value`**: In `useSubmodelForm.ts` or a new `buildDefaultValues()` utility, walk the definition tree and set initial values from `node.smt.default_value` when `initialData` is empty for that field.
2. **Add `x-allowed-id-short` to UISchema type** and enforce in `ListField` when creating new items (show constrained dropdown instead of free index).
3. **Add `x-edit-id-short` to UISchema type** and conditionally show editable idShort input in `ListField.ListItem`.

### Priority 2 (Nice to Have)
4. **Implement `naming` pattern** for auto-generated list item labels.
5. **Use `initial_value`** as pre-fill when first initializing a field (distinct from `default_value` which applies when field is left untouched).
6. **Extract `ReferenceDisplay`** into a shared component.
7. **Add `normalizeRange` raw string test** to zodSchemaBuilder.test.ts.

### Priority 3 (Maintenance)
8. **Remove duplicate either-or logic** from `validation.ts`.
9. **Consider ReDoS mitigation** — add timeout or use safe-regex library for template patterns.

---

## 9. Summary

| Metric | Value |
|--------|-------|
| Total SMT qualifiers | 16 |
| Enforced in validation | 11 (69%) |
| Enforced in UI only | 3 (form_title, form_info, form_url) |
| Not enforced at all | 5 (31%) |
| Field types rendering correctly | 18/18 (100%) |
| Zod test scenarios covered | 17/20 (85%) |
| Validation test scenarios covered | 10/10 (100%) |
| Code quality findings | 5 (0 HIGH, 2 MEDIUM, 3 LOW) |

**Overall assessment**: The frontend editor is well-architected with comprehensive field type coverage and solid validation for the core qualifiers. The 5 unenforced qualifiers (`default_value` partial, `initial_value`, `allowed_id_short`, `edit_id_short`, `naming`) are all related to dynamic list/entity element naming and initialization — features that are less commonly used in practice but important for full IDTA SMT compliance.
