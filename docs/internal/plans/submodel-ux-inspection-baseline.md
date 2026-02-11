# Submodel UX Inspection Baseline

## Scope
This baseline inspects the current implementation state of aggregated submodel viewing/editing across:

1. `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/publisher/pages/DPPEditorPage.tsx`
2. `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/pages/SubmodelEditorPage.tsx`
3. `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/viewer/pages/DPPViewerPage.tsx`

It also maps action-button behavior to backend enforcement points.

## Surface Inventory And Behavior Snapshots

### 1) Publisher Surface (`DPPEditorPage.tsx`)
Current behavior:

1. Header actions:
- `Back` button navigates to `/console/dpps`.
- `Export` menu offers `JSON`, `PDF`, `AASX`, `JSON-LD`, `Turtle`, `XML`.
- `QR Code` appears in export menu only when action policy allows (`published` + readable).
- `Publish` appears for draft DPPs only.

2. Submodel section:
- Uses server-provided `submodel_bindings` instead of template-key `includes` heuristics.
- `Refresh & Rebuild` now calls `POST /dpps/{dpp_id}/submodels/refresh-rebuild`.
- Renders each submodel as a card with support/binding metadata and deep node tree (`SubmodelNodeTree`).
- Edit links include `submodel_id` query parameter for deterministic targeting where available.

3. Integrity and events:
- Digest section includes `Copy digest` button.
- Supply-chain panel includes `Capture Event` (draft-only UI) and `View all events` link.

Notable implementation references:
- Action gating: `buildDppActionState`.
- Tree rendering: `buildSubmodelNodeTree`, `computeSubmodelHealth`, `SubmodelNodeTree`.
- Missing template add cards are disabled for unavailable/non-refreshable templates.

### 2) Editor Surface (`SubmodelEditorPage.tsx`)
Current behavior:

1. Page-level controls:
- `Back` to DPP editor.
- `Form`/`JSON` tab switch with JSON validity guard when switching to form.

2. Save workflow:
- `Save Changes`, `Reset`, `Rebuild from template` centralized in `FormToolbar`.
- Read-only warning shown when `dpp.access.can_update` is false.
- Save path validates schema, read-only, either-or qualifiers.

3. Binding and targeting:
- Uses `dpp.submodel_bindings` + optional `submodel_id` query param to resolve editing target.
- Sends optional `submodel_id` in `PUT /dpps/{dpp_id}/submodel`.
- If multiple bindings exist for one template and `submodel_id` is missing, UI blocks save/rebuild with actionable error.

4. Field-level editors:
- Relationship editing migrated from raw JSON blobs to structured reference editors.
- List controls support `x-allowed-id-short`, `x-edit-id-short`, `x-naming` display + add-item constraints.

### 3) Viewer Surface (`DPPViewerPage.tsx`)
Current behavior:

1. Public/auth-aware fetch model:
- Authenticated users hit tenant endpoint; public users hit `/api/v1/public/{tenant}/dpps/...`.

2. ESPR categorization:
- Category tabs use deep extraction (`buildSubmodelNodeTree` + `flattenSubmodelNodes`) and classify leaf nodes.
- Cards now show source submodel + deep path, not only top-level fields.

3. Advanced raw mode:
- `Raw Submodel Data (Advanced)` now renders deep tree (`SubmodelNodeTree`) instead of first-level `submodelElements` only.

## Action-Button Matrix: UI Enablement vs Backend Enforcement

| Action | Surface | Current UI enablement | Backend enforcement mapping | Notes |
|---|---|---|---|---|
| Back | DPP page, Submodel editor | Always visible; pure client navigation | None | Conforms to target |
| Export JSON/PDF/AASX/JSON-LD/Turtle/XML | DPP page | Disabled when `!actionState.canExport` (`can_read`) | `GET /export/{dpp_id}` with `require_access(..., "export", ...)`; AASX adds explicit publisher-role guard | UI now gates at coarse read-level; per-format disallow still backend-authoritative |
| QR Code | DPP page | Visible only when `actionState.canGenerateQr` (`published && canRead`) | `GET /qr/{dpp_id}` requires `read`; backend rejects non-published DPP (`400`) | Fully aligned |
| Publish | DPP page | Button shown for draft; disabled unless `actionState.canPublish` | `POST /dpps/{dpp_id}/publish`: owner/tenant-admin check + `require_access(..., "publish", ...)` | Fully aligned |
| Refresh & Rebuild | DPP page | Disabled unless `actionState.canRefreshRebuild` (`can_update && status!=archived`) | `POST /dpps/{dpp_id}/submodels/refresh-rebuild`: owner/tenant-admin check + `require_access(..., "update", ...)`; service blocks archived | Fully aligned |
| Edit submodel | DPP page | Disabled unless `actionState.canUpdate`; link carries `submodel_id` when known | Editing done by `PUT /dpps/{dpp_id}/submodel` with owner/tenant-admin + `update` ABAC; 409 on ambiguous binding | Deterministic targeting improved |
| Add missing template | DPP page | Disabled unless `canUpdate` and template selectable (`support_status`, `refresh_enabled`) | Same as edit: `PUT /dpps/{dpp_id}/submodel` on save | Fully aligned |
| Copy digest | DPP page | Available when digest exists | None (clipboard only) | Conforms |
| Capture Event | DPP page | Shown in draft; disabled unless `actionState.canCaptureEvent` (`draft && canUpdate`) | Capture API `POST /epcis/capture` uses `_get_dpp_or_404(... action="update")` + ABAC | Fully aligned |
| View all events | DPP page | Link shown when DPP ID exists in page | Viewer endpoint route permissions apply | UI currently not gated by `canRead`; route-level enforcement remains authoritative |
| Form/JSON tab switch | Submodel editor | Always available; JSON->Form blocked with actionable validation message on invalid JSON | None | Conforms |
| Reset | Submodel editor | Disabled when no update access, not dirty, or saving | None | Conforms |
| Rebuild from template | Submodel editor | Visible only when update access; blocked on ambiguous bindings | `PUT /dpps/{dpp_id}/submodel` with `rebuild_from_template=true`; owner/admin + update ABAC | Conforms + ambiguity safeguard |
| Save Changes | Submodel editor | Disabled when saving or no update access; blocked on ambiguity/validation errors | `PUT /dpps/{dpp_id}/submodel`; owner/admin + update ABAC; 409 ambiguity handling | Conforms |
| Add item / Up / Down / Remove | List fields | Add disabled by `x-allowed-id-short` capacity; Up/Down disabled by bounds; remove always available | Validation/contract checks at save (`validateSchema`, backend update) | Permission gating is page-level, not per-field |
| Add language / Remove language | Multi-language fields | Required languages are non-removable; add allows dynamic codes | Required-language checks via validation + save-time rules | Conforms to qualifier intent |
| Add key / Remove key | Reference fields | Structured add/remove in `ReferenceField` and `ReferenceObjectEditor` | Enforced at save/update path | Conforms, but key-type/value constraints are mostly schema-driven at save time |
| Relationship references edit | Relationship fields | Structured editors for `first`/`second` references (no raw JSON text input) | Enforced by update API + validation chain | Major UX hardening completed |

## Known Failure Modes And Status

### A) Heuristic template resolution via `includes`
Status: **Mitigated in publisher path**.

- `DPPEditorPage` now consumes `submodel_bindings` from backend and no longer does template-key `includes` matching.
- `SubmodelEditorPage` resolves via bindings first; semantic/idShort fallback remains only as compatibility fallback when no binding is present.

### B) First-level-only aggregation/view rendering
Status: **Mitigated**.

- Publisher submodel cards render deep trees.
- Viewer classification now traverses deep leaf nodes; raw advanced mode also renders deep trees.

### C) Raw-JSON-heavy relationship editing
Status: **Mitigated**.

- Relationship and annotated relationship fields now use structured reference editors.

### D) UI gating not consistently aligned to `dpp.access`
Status: **Improved, not fully closed**.

- Page-level critical actions now use centralized `actionPolicy` helper.
- Field-level controls are still not uniformly permission-aware in every component; save/rebuild remain authoritative gates.

### E) E2E qualifier suite blocked by unresolved `sonner` import
Status: **Mitigated in current branch**.

- Replaced direct `sonner` dependency path with local toaster module (`/frontend/src/lib/toast.tsx`), removing hard runtime coupling during Vite import analysis.
- Build and targeted tests pass after this change.

## Baseline Conclusions

1. The architecture now has a binding-driven backbone for submodel targeting and refresh/rebuild orchestration.
2. Progressive disclosure is materially improved through summary cards + deep tree rendering + advanced raw mode.
3. Backend enforcement remains strong and explicit for publish/update/export/QR/capture, with 409 ambiguity signaling added.
4. Remaining hardening priorities are concentrated in:
- exhaustive field-level permission consistency,
- richer constraint-level inline UX (key-type/value semantics and advanced qualifier guidance),
- full E2E rerun of qualifier suite in integrated environment.
