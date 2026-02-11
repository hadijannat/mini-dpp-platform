# IDTA Digital Nameplate Completeness + Attachment Pipeline Upgrade (2026-02-11)

## Scope
This audit documents the platform changes that resolve incomplete Digital Nameplate editing (notably `AddressInformation`) and add authenticated private attachment uploads/downloads for file elements.

## Root Cause
`AddressInformation` placeholders could be present without concrete child structure in template contracts, producing effectively non-editable collections/lists in the frontend renderer.

## Implemented Behavior
1. Contracts now run semantic-registry-driven drop-in expansion before definition/schema generation.
2. Definition nodes now carry optional `supplementalSemanticIds` and `x_resolution` metadata for resolver traceability.
3. Schema conversion now emits explicit unresolved hints instead of silent empty collection/list placeholders:
   - `x-unresolved-definition: true`
   - `x-unresolved-reason: <reason>`
4. Non-rebuild submodel updates now support on-write structural backfill from template structure when existing elements are structurally empty and incoming payload includes nested data.
5. File schema keeps open MIME policy with syntactic validation and UX suggestions (`application/pdf`, `image/png`).

## Registry-Driven Drop-in Resolution
Resolution is declared in `shared/idta_semantic_registry.json` under `dropin_bindings` and is keyed by target semantic IDs. Each binding declares:
- `source_template_key`
- `source_selector` (path/semantic/model type)
- optional target template/model constraints
- projection strategy

No template-specific branching is required in business logic.

## Attachment Pipeline
### API
- `POST /api/v1/tenants/{tenant_slug}/dpps/{dpp_id}/attachments`
- `GET /api/v1/tenants/{tenant_slug}/dpps/{dpp_id}/attachments/{attachment_id}`

### Security model
- Upload requires authenticated update access and owner/admin permission.
- Download requires authenticated read access (owner, tenant admin, or explicit share).
- No unauthenticated public download path is exposed.

### Storage model
- Objects are stored in MinIO bucket `minio_bucket_attachments` under tenant/DPP-scoped keys.
- Metadata is persisted in `dpp_attachments`.
- Integrity hash (`sha256`) is persisted with metadata.
- MIME and size limits are enforced via config (`mime_validation_regex`, `attachments_max_upload_bytes`).

## Frontend Renderer Expectations
- File fields support both manual URL/reference mode and upload mode.
- Upload mode hydrates form values with backend response payload (`content_type`, private API `url`).
- MIME input remains open but validated against contract/backend regex.

## Rollout and Operational Controls
1. No forced historical bulk rewrite is required.
2. On-write repair/backfill applies during normal update operations.
3. Existing explicit rebuild flows remain available for controlled recovery.
4. If a contract still has unresolved nodes, `x-unresolved-definition` metadata is surfaced for diagnostics rather than failing silently.
