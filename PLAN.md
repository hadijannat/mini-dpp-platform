# Standards & Data Model Review - Phase 1 Findings Report

## Summary

After thorough review of all owned files across templates, export, DPPs, QR/GS1, Catena-X, and ESPR classification, I identified 10 findings ranked by severity. The platform has strong foundations (BaSyx integration, qualifier parsing, AASX export via BaSyx writer) but has significant gaps in standards compliance that will matter for production EU ESPR and Catena-X deployments.

**Effort Estimates:**
| Severity | Count | Total Effort |
|----------|-------|--------------|
| P0 (Critical) | 2 | ~5 days |
| P1 (High) | 5 | ~8 days |
| P2 (Medium) | 3 | ~4 days |

---

## Finding 1: Submodel Integrity - JWS Signing Never Populated (P0)

**Description:** The `DPPRevision` model has `signed_jws` column and SHA-256 digest, but the JWS field is **never set** anywhere in the codebase. The digest is computed (SHA-256 of canonicalized JSON), but there is no signing key management, no JWS creation, and no verification. The export service faithfully includes `signedJws: null` in every JSON and PDF export. This means every exported DPP has **zero cryptographic integrity proof** - a consumer cannot verify the DPP was not tampered with.

**Evidence:**
- `backend/app/modules/dpps/service.py:143` - `DPPRevision` created with no `signed_jws` parameter
- `backend/app/modules/dpps/service.py:537,628,684` - Same pattern in all revision creation paths
- `backend/app/modules/export/service.py:51` - Exports `signedJws` which is always `None`
- `backend/app/db/models.py:447-450` - Column exists but is never written to

**Risk:** EU ESPR requires tamper-evident DPPs. Without JWS signing, any exported DPP can be modified without detection. This undermines the entire trust model of the platform.

**Fix Plan:**
1. Add JWS signing key management (RS256 or ES256) via settings or Keycloak integration
2. Implement `_sign_digest(digest: str) -> str` in `DPPService` using `python-jose` or `PyJWT`
3. Sign on publish (not on every draft save) - populate `signed_jws` when `publish_dpp()` is called
4. Add `verify_jws(revision: DPPRevision) -> bool` for import/validation
5. Include public key reference in export metadata for external verification

**Acceptance Criteria:**
- Published revisions have non-null `signed_jws`
- `export_json()` output includes a valid JWS that can be verified with the platform's public key
- Draft revisions may have null `signed_jws` (signing only on publish)
- Key rotation is supported without breaking existing signatures

**Test Plan:**
- Unit test: sign a digest, verify it, tamper with digest, verify fails
- Integration test: publish DPP, export JSON, verify JWS matches digest
- Test key rotation: old signatures still verify with old key

---

## Finding 2: Battery Passport Gap - IDTA 02035 Missing (P0)

**Description:** The template catalog (`catalog.py`) contains 6 templates, all from the general DPP4.0 ecosystem. The EU Battery Regulation (effective Feb 2027) requires a Battery Passport based on IDTA 02035, which has **7 submodel parts**: GeneralInformation, ProductInformation, BatteryComposition, StateOfCharge, EndOfLife, CarbonFootprint (battery-specific), and PerformanceData. None of these are in the catalog. This is a blocking gap for any battery industry deployment.

**Evidence:**
- `backend/app/modules/templates/catalog.py:28-77` - Only 6 templates, no battery passport entries
- `backend/app/core/config.py:222-230` - `template_versions` dict has no battery entries
- IDTA 02035 spec defines semantic IDs like `https://admin-shell.io/battery/BatteryPass/1/0/Submodel`

**Risk:** Battery manufacturers cannot use the platform. Battery Passport is the first EU-mandated DPP category (ahead of textiles, electronics).

**Fix Plan:**
1. Add 7 `TemplateDescriptor` entries to `TEMPLATE_CATALOG` for IDTA 02035 parts 1-7
2. Add corresponding version pins in `template_versions` config default
3. Fetch and validate the AASX templates from IDTA repository
4. Verify the BaSyx parser handles battery-specific element structures (deep nesting, many SubmodelElementLists)
5. Add battery-specific ESPR category patterns in `esprCategories.ts`

**Acceptance Criteria:**
- All 7 battery passport submodel parts have catalog entries with correct semantic IDs
- Templates can be fetched, parsed, and rendered in the editor
- Battery DPPs can be created, edited, published, and exported

**Test Plan:**
- Unit test: catalog contains all 7 battery entries with valid semantic IDs
- Integration test: fetch battery template from IDTA repo, parse AASX, build definition
- E2E test: create battery DPP with all 7 submodels, edit, publish, export AASX

---

## Finding 3: GS1 Digital Link - Missing Check Digit and GTIN Validation (P1)

**Description:** The `build_gs1_digital_link()` method in `qr/service.py` pads GTINs to 14 digits but **never validates or computes the GS1 check digit** (the last digit of a GTIN). ISO/IEC 18975 (GS1 Digital Link) requires a valid GTIN with correct check digit. The `extract_gtin_from_asset_ids()` method generates a pseudo-GTIN from a SHA-256 hash that will have an incorrect check digit. GTINs with wrong check digits will be rejected by any GS1 resolver.

**Evidence:**
- `backend/app/modules/qr/service.py:275-284` - Pads to 14 digits with `zfill(14)` but no check digit validation
- `backend/app/modules/qr/service.py:317-326` - Pseudo-GTIN: `str(int(hash[:12], 16) % 10**13).zfill(13)` - no check digit appended
- GS1 General Specifications Section 7.9 defines the check digit algorithm (mod-10 weight-3)

**Risk:** GS1 Digital Links with invalid GTINs will fail at any standards-compliant resolver. EU ESPR references GS1 as a carrier standard.

**Fix Plan:**
1. Add `_compute_gtin_check_digit(digits: str) -> str` implementing GS1 mod-10 weight-3 algorithm
2. Validate incoming GTINs (8, 12, 13, or 14 digits) and verify check digit
3. For pseudo-GTINs, compute and append the correct check digit to make a valid GTIN-14
4. Add a `validate_gtin(gtin: str) -> bool` utility for input validation
5. Clearly mark pseudo-GTINs in the API response (e.g., `is_pseudo_gtin: true`)

**Acceptance Criteria:**
- `build_gs1_digital_link()` only accepts GTINs with valid check digits
- `extract_gtin_from_asset_ids()` generates pseudo-GTINs with correct check digits
- API response indicates when a pseudo-GTIN was generated vs. a real GTIN was used

**Test Plan:**
- Unit test: check digit computation for known GTIN-13 and GTIN-14 values
- Unit test: pseudo-GTIN generation produces valid GTIN with correct check digit
- Unit test: reject GTIN with incorrect check digit
- Integration test: GS1 Digital Link with real GTIN resolves correctly

---

## Finding 4: Catena-X Mapping - Only 3 Semantic ID Mappings (P1)

**Description:** The `CATENAX_SEMANTIC_IDS` dictionary in `mapping.py` only maps 3 of the 6 catalog templates to Catena-X SAMM semantic IDs. `contact-information`, `technical-data`, and `handover-documentation` have no Catena-X semantic ID mappings. However, the mapping code does not actually USE this dictionary - `build_shell_descriptor()` uses the semantic IDs from the AAS environment directly. So `CATENAX_SEMANTIC_IDS` is dead code, but the real problem is: the DTR descriptor uses IDTA semantic IDs (e.g., `https://admin-shell.io/...`) rather than Catena-X SAMM IDs (e.g., `urn:samm:io.catenax...`). This will cause Catena-X data space consumers to not find matching aspect models.

**Evidence:**
- `backend/app/modules/connectors/catenax/mapping.py:13-17` - Only 3 entries, never referenced
- `backend/app/modules/connectors/catenax/mapping.py:75` - `_extract_semantic_id(submodel)` uses AAS semantic ID directly
- DTR spec requires SAMM semantic IDs for Catena-X interoperability

**Risk:** DPPs published to Catena-X DTR will have IDTA semantic IDs instead of SAMM URNs, making them invisible to standard Catena-X consumers.

**Fix Plan:**
1. Add a semantic ID translation layer: IDTA -> SAMM mapping for all templates
2. In `build_shell_descriptor()`, translate the IDTA semantic ID to SAMM semantic ID when building DTR descriptors
3. Add SAMM mappings for all 6 current templates + future battery templates
4. Make the mapping configurable per connector (some DTRs may want IDTA IDs)
5. Remove dead `CATENAX_SEMANTIC_IDS` dict or replace with the active translation map

**Acceptance Criteria:**
- DTR shell descriptors use SAMM semantic IDs when targeting Catena-X
- Mapping is configurable (IDTA vs SAMM) per connector configuration
- All 6 catalog templates have SAMM ID mappings

**Test Plan:**
- Unit test: `build_shell_descriptor()` produces SAMM IDs when configured
- Unit test: fallback to IDTA IDs when no SAMM mapping exists
- Integration test: register shell in DTR mock with SAMM IDs, verify lookup works

---

## Finding 5: Template Versioning - No Upgrade Path for Existing DPPs (P1)

**Description:** Template versions are pinned in config (e.g., `"digital-nameplate": "3.0.1"`), but there is no mechanism to handle version upgrades. When a new IDTA template version is released (e.g., 3.0.2), changing the pinned version will cause all new DPPs to use the new template, but existing DPPs reference the old version's semantic ID and element structure. The `rebuild_all_from_templates()` method re-instantiates submodels from the latest template, but it does not handle structural differences between versions (added/removed/renamed elements). This can cause data loss or schema mismatches.

**Evidence:**
- `backend/app/core/config.py:222-230` - Single version pin per template, no version history
- `backend/app/modules/dpps/service.py:552-596` - `rebuild_all_from_templates()` blindly re-instantiates from new template
- `backend/app/modules/templates/service.py:73-95` - `get_template()` only looks up the pinned version
- No migration path or version compatibility checks

**Risk:** Template version upgrade can silently drop data or break existing DPPs. Users may lose submodel data that existed in v3.0.1 but is not in v3.0.2.

**Fix Plan:**
1. Store the template version used in each DPP revision (already in `DPPRevision` via template's `idta_version`)
2. Keep old template versions in DB alongside new ones (multi-version template storage)
3. Add version compatibility check before rebuild: diff old vs new template definitions
4. Implement a migration preview endpoint: show what fields will be added/removed/changed
5. Add a `--dry-run` option to `rebuild_all_from_templates()`

**Acceptance Criteria:**
- Old DPPs continue to render correctly when template version changes
- Rebuild from templates shows a preview of changes before applying
- Template DB can hold multiple versions simultaneously
- DPP revision records which template version was used

**Test Plan:**
- Unit test: rebuild with compatible version preserves all data
- Unit test: rebuild with incompatible version (removed field) shows warning, preserves data
- Integration test: upgrade template version, verify old DPPs still work

---

## Finding 6: ESPR Category Classifier - Overly Broad Pattern Matching (P1)

**Description:** The ESPR classifier in `esprCategories.ts` uses substring matching on `idShort` values. This causes false positives: e.g., `ProductName` matches "product" -> Identity AND "name" -> Identity (correct but for wrong reason). More critically, `EndOfLifeDate` matches "end" -> Repair/End-of-Life (false positive - it's a date property, not recycling info). The pattern `"name"` matches any field with "name" in it (ManufacturerName, ContactName, FileName), all incorrectly classified as Identity. Pattern `"standard"` matches `StandardPackaging` as Compliance. The classifier has no negative patterns or priority weighting.

**Evidence:**
- `frontend/src/features/viewer/utils/esprCategories.ts:19-20` - "name" pattern is too broad
- `frontend/src/features/viewer/utils/esprCategories.ts:59` - "end" pattern matches EndOfLifeDate, EndDate, etc.
- `frontend/src/features/viewer/utils/esprCategories.ts:69-76` - First-match wins, no scoring

**Risk:** Viewer displays AAS elements in wrong ESPR tabs, misleading users about regulatory compliance. Could lead to incorrect ESPR compliance assessments.

**Fix Plan:**
1. Replace substring matching with word-boundary-aware matching (split on camelCase/snake_case, match whole words)
2. Add negative patterns (exclusions) per category
3. Add a priority/confidence scoring system instead of first-match-wins
4. Remove overly broad patterns: "name", "end", "part", "model"
5. Add semantic ID-based classification as primary classifier, fall back to idShort patterns
6. Add unit tests with real IDTA template idShort values

**Acceptance Criteria:**
- `ProductName` classifies as Identity (correct), but `FileName` does not
- `EndOfLifeDate` does NOT classify as Repair/End-of-Life
- Semantic ID-based classification works for all 6 current templates
- False positive rate < 5% on real IDTA template elements

**Test Plan:**
- Unit test: classify every idShort from the 6 IDTA templates, verify accuracy
- Unit test: known false positives are correctly handled
- Manual test: view a real DPP in the viewer, verify tab assignments

---

## Finding 7: AASX Export - No XML Serialization Option (P1)

**Description:** The AASX export uses BaSyx's `write_all_aas_objects()` with `write_json=True`, producing JSON-only AASX packages. IDTA Part 5 specifies both JSON and XML as valid serialization formats inside AASX. Some AAS tools and registries (e.g., Eclipse BaSyx Server, AASX Package Explorer) expect XML serialization by default. There is no option for the user to choose. Additionally, the export has no JSON-LD or semantic web output format, which limits interoperability with EU DPP registries that may require linked data.

**Evidence:**
- `backend/app/modules/export/service.py:100` - `write_json=True` hardcoded
- `backend/app/modules/export/service.py:24` - `ExportFormat = Literal["json", "aasx", "pdf"]` - no XML option
- IDTA 2006-2-0 Part 5 Section 5.2.2 allows both JSON and XML serialization

**Risk:** AASX packages may not be importable by tools that expect XML format. Limited interoperability.

**Fix Plan:**
1. Add `serialization` parameter to `export_aasx()`: `"json"` (default) or `"xml"`
2. When `serialization="xml"`, use BaSyx's XML writer
3. Add `xml` as an optional export format in the router
4. Document the serialization format in export metadata
5. (P2/future) Add JSON-LD export using AAS4Web context

**Acceptance Criteria:**
- AASX export supports both JSON and XML serialization
- Default remains JSON for backward compatibility
- XML-serialized AASX validates in AASX Package Explorer

**Test Plan:**
- Unit test: export AASX with XML serialization, validate ZIP structure
- Unit test: export AASX with JSON serialization (existing test)
- Integration test: import XML AASX into BaSyx server

---

## Finding 8: AASX Export - OPC Core Properties Incomplete (P2)

**Description:** The AASX export sets OPC core properties (`creator`, `title`, `description`, `version`, `revision`) but is missing several fields recommended by IDTA Part 5: `subject` (should reference the product), `category` (should be "Digital Product Passport"), `keywords` (template keys), and `identifier` (should be the globalAssetId). The `_create_core_properties()` method that builds complete Dublin Core metadata is dead code - it's never called because the BaSyx writer handles this, but the BaSyx writer doesn't set all fields.

**Evidence:**
- `backend/app/modules/export/service.py:89-99` - Limited OPC properties set
- `backend/app/modules/export/service.py:174-192` - `_create_core_properties()` is dead code (never called)
- `backend/app/modules/export/service.py:149-157` - `_create_content_types()` is dead code
- `backend/app/modules/export/service.py:159-165` - `_create_root_rels()` is dead code
- `backend/app/modules/export/service.py:167-172` - `_create_aas_rels()` is dead code

**Risk:** Minor. OPC metadata is informational. Some AASX validators may warn about missing fields.

**Fix Plan:**
1. Add `subject`, `category`, `keywords`, and `identifier` to OPC core properties
2. Remove dead code methods (`_create_core_properties`, `_create_content_types`, `_create_root_rels`, `_create_aas_rels`)
3. Verify pyecma376_2 CoreProperties supports all needed fields

**Acceptance Criteria:**
- OPC core properties include globalAssetId as identifier
- Dead code removed from export service
- AASX validates without warnings in AASX Package Explorer

**Test Plan:**
- Unit test: verify OPC core properties contain expected fields
- Unit test: validate AASX structure after adding new properties

---

## Finding 9: Template Definition Builder - Missing AAS Element Types (P2)

**Description:** The `TemplateDefinitionBuilder._element_definition()` handles 8 AAS element types: Property, MultiLanguageProperty, Range, File, Blob, SubmodelElementCollection, SubmodelElementList, Entity, and AnnotatedRelationshipElement. Missing from explicit handling: `ReferenceElement`, `RelationshipElement`, `Operation`, `Capability`, and `BasicEventElement`. These fall through to the default case and get minimal definition (no type-specific fields). The `basyx_builder.py` handles more types but the definition builder does not capture reference element first/second, operation variables, etc.

**Evidence:**
- `backend/app/modules/templates/definition.py:101-135` - Only 8 isinstance checks
- Missing: `model.ReferenceElement` (no `value` reference captured)
- Missing: `model.RelationshipElement` (no `first`/`second` references captured)
- Missing: `model.Operation` (no input/output variable definitions)
- `backend/app/modules/templates/service.py:846-965` - UI schema builder handles all types correctly (15 types)

**Risk:** Templates containing ReferenceElement or RelationshipElement will have incomplete definitions. The editor may not render them correctly. However, these types are rare in DPP4.0 templates.

**Fix Plan:**
1. Add `model.ReferenceElement` handling to capture the value reference
2. Add `model.RelationshipElement` handling for first/second references
3. Add `model.Operation` handling for inputVariable/outputVariable/inoutputVariable
4. Add `model.Capability` and `model.BasicEventElement` as no-op (they have no editable content)

**Acceptance Criteria:**
- Definition builder produces complete definitions for all 13 AAS SubmodelElement types
- ReferenceElement definitions include the value reference structure
- RelationshipElement definitions include first/second references

**Test Plan:**
- Unit test: build definition from template containing ReferenceElement
- Unit test: build definition from template containing RelationshipElement
- Integration test: parse real IDTA template with Operation elements

---

## Finding 10: Catena-X DTR Client - No Token Refresh or Retry Logic (P2)

**Description:** The DTR client obtains an OIDC token via client credentials flow but stores it for the lifetime of the client instance. There is no token refresh, no expiry check, and no retry on 401. If the token expires during a long-running publish operation (or if the token TTL is short), subsequent requests will fail with 401 and the user gets a generic error. Additionally, there is no retry logic for transient network errors (503, connection timeout).

**Evidence:**
- `backend/app/modules/connectors/catenax/dtr_client.py:86-96` - Token fetched once in `_get_client()`
- `backend/app/modules/connectors/catenax/dtr_client.py:110-125` - `_obtain_oidc_token()` called once
- No expiry tracking, no refresh, no 401 retry

**Risk:** DTR publish operations will fail silently after token expiry. Users will need to manually re-test the connector.

**Fix Plan:**
1. Track token expiry time from the OIDC response (`expires_in` field)
2. Refresh token before it expires (or on 401 response)
3. Add retry logic with exponential backoff for transient errors (503, timeout)
4. Add `httpx` event hooks for automatic 401 -> refresh -> retry

**Acceptance Criteria:**
- DTR client automatically refreshes expired tokens
- Transient errors are retried up to 3 times with backoff
- Token refresh failure produces a clear error message

**Test Plan:**
- Unit test: mock expired token, verify refresh is triggered
- Unit test: mock 503 response, verify retry with backoff
- Unit test: mock persistent 401 after refresh, verify clear error

---
---

# Backend & Security Review -- Phase 1 Findings Report

**Reviewer:** backend-security
**Date:** 2026-02-06
**Scope:** backend/app/core/, backend/app/modules/policies/, backend/app/modules/tenants/, backend/app/db/models.py, infra/opa/, infra/keycloak/, security tests

---

## Top 10 Findings (Ranked by Severity)

---

### F1. Connector Secrets Stored in Plaintext JSONB (P0 -- Critical)

**Description:** Connector `config` column stores `client_secret`, `token`, and `client_id` as plaintext JSONB in the `connectors` table. Anyone with database read access (backup tapes, SQL injection elsewhere, DB admin) can extract third-party DTR credentials.

**Evidence:**
- `backend/app/db/models.py:835` -- `config: Mapped[dict[str, Any]] = mapped_column(JSONB, ...)`
- `backend/app/modules/connectors/catenax/service.py:75-76` -- `client_secret=config.get("client_secret")`, `token=config.get("token")`
- `backend/app/modules/connectors/catenax/service.py:81-88` -- secrets written directly to `Connector(config=config)`

**Risk:** An attacker who gains read access to the database obtains all Catena-X DTR credentials, enabling unauthorized DTR access and potential supply-chain manipulation.

**Fix Plan:**
1. Encrypt sensitive fields within the `config` JSONB before persisting using the existing `EncryptedValue` model pattern or AES-256-GCM envelope encryption with `encryption_master_key`.
2. Add a `ConnectorConfigEncryptor` utility that encrypts `client_secret` and `token` fields on write and decrypts on read.
3. Migrate existing plaintext connector configs with an Alembic data migration.

**Acceptance Criteria:**
- Connector secrets are never stored in plaintext in the database.
- `SELECT config FROM connectors` returns ciphertext for sensitive fields.
- Existing connectors are migrated.

**Test Plan:**
- Unit test: verify encrypted values roundtrip correctly.
- Integration test: create connector, read raw DB row, confirm secrets are ciphertext.
- Verify connector test/publish still works after encryption.

**Effort:** 2-3 days

---

### F2. Audit Logging Not Implemented (P0 -- Critical)

**Description:** The `AuditEvent` model exists in the schema (with table, indexes, and RLS), but **no code anywhere writes audit events**. Zero audit records are created for any action -- create, read, update, publish, export, delete, policy changes, or connector operations. Grep for `AuditEvent` in `backend/app/modules/` returns zero hits.

**Evidence:**
- `backend/app/db/models.py:868-913` -- AuditEvent model defined
- Grep `AuditEvent` in `backend/app/modules/` -- 0 matches
- Grep `audit` in `backend/app/modules/` -- only docstring mentions of "audit trails" in DPP service

**Risk:** Complete lack of accountability and forensic capability. Impossible to detect unauthorized access, trace data breaches, or satisfy EU ESPR/DPP regulatory compliance requirements for audit trails.

**Fix Plan:**
1. Create `backend/app/core/audit.py` with an `emit_audit_event()` async helper that creates `AuditEvent` records.
2. Add audit calls at all CRUD endpoints in DPP, export, publish, archive, connector, policy, and tenant routers.
3. Include subject, action, resource_type, resource_id, decision (from ABAC), IP, user-agent.
4. Add a middleware or FastAPI dependency that auto-captures request context for audit.

**Acceptance Criteria:**
- Every state-changing API call produces an AuditEvent row.
- Export and publish operations are audited.
- ABAC deny decisions are audited.
- `SELECT count(*) FROM audit_events` > 0 after a typical API session.

**Test Plan:**
- Unit tests for `emit_audit_event()`.
- Integration tests: perform DPP lifecycle (create, edit, publish, export, archive), verify audit events exist with correct action/resource.
- Test denied access also produces audit event.

**Effort:** 3-4 days

---

### F3. Rate Limiting Fails Open and Is Per-IP Only (P1 -- High)

**Description:** When Redis is unavailable, rate limiting is completely bypassed (fail-open). The rate limiter is per-IP only with no per-user or per-tenant throttling, making it trivial to bypass via IP rotation or overwhelm specific tenants.

**Evidence:**
- `backend/app/core/rate_limit.py:97-99` -- `if r is None: return await call_next(request)` (fail open)
- `backend/app/core/rate_limit.py:110-112` -- Redis exception also fails open
- `backend/app/core/rate_limit.py:101` -- key is `rl:{client_ip}:...` -- IP only, no user/tenant dimension
- `backend/app/core/rate_limit.py:83` -- development entirely skipped

**Risk:** If Redis goes down (crash, OOM, network partition), all API rate limiting vanishes. An attacker behind NAT/VPN can exhaust backend resources. No per-tenant fairness means one tenant can starve others.

**Fix Plan:**
1. Add a fallback in-memory rate limiter (token bucket or sliding window with TTL dict) that activates when Redis is unavailable.
2. Add per-user rate limiting using JWT `sub` claim as secondary key.
3. Add per-tenant rate limiting using `tenant_slug` from path.
4. Add rate-limit logging/metrics for Redis failures.

**Acceptance Criteria:**
- Rate limiting is enforced even when Redis is unavailable.
- Authenticated requests are additionally rate-limited by user subject.
- Tenant-scoped endpoints are rate-limited per tenant.

**Test Plan:**
- Unit test: simulate Redis unavailability, verify requests are still rate-limited via fallback.
- Unit test: verify per-user rate key includes subject.
- Load test: verify per-tenant fairness.

**Effort:** 2-3 days

---

### F4. HSTS Missing `preload` Directive, No CSP Header (P1 -- High)

**Description:** The `Strict-Transport-Security` header is set in production but does not include the `preload` directive, meaning the domain is not eligible for browser HSTS preload lists. No `Content-Security-Policy` header is set at all.

**Evidence:**
- `backend/app/core/middleware.py:26` -- `"Strict-Transport-Security": "max-age=63072000; includeSubDomains"` -- missing `preload`
- No CSP header in middleware or Caddyfile
- `Caddyfile:1-21` -- no security headers configured at proxy level

**Risk:** Without `preload`, first-time visitors are vulnerable to SSL-stripping attacks before receiving the HSTS header. Without CSP, the application is more vulnerable to XSS and data injection attacks (the API returns JSON so direct impact is limited, but `docs`/`redoc` endpoints render HTML).

**Fix Plan:**
1. Add `preload` to HSTS header: `max-age=63072000; includeSubDomains; preload`.
2. Submit domain to hstspreload.org after deployment.
3. Add Content-Security-Policy header for API responses: `default-src 'none'; frame-ancestors 'none'`.
4. Configure CSP in Caddyfile for frontend responses.

**Acceptance Criteria:**
- HSTS header includes `preload` in production.
- CSP header present on all API responses.
- HSTS preload eligibility check passes.

**Test Plan:**
- Unit test: verify middleware returns correct HSTS header with preload in production.
- Unit test: verify CSP header present.
- Manual: run hstspreload.org checker.

**Effort:** 0.5 days

---

### F5. Encryption Master Key Has No Rotation Mechanism (P1 -- High)

**Description:** The `encryption_master_key` is a single static environment variable with no versioning, rotation, or re-encryption capability. The `EncryptedValue` model stores a `key_id` field, but there is no code that uses it for key rotation. No encryption/decryption service exists beyond the model schema.

**Evidence:**
- `backend/app/core/config.py:186-188` -- `encryption_master_key: str = Field(default="")`
- `backend/app/db/models.py:474-526` -- EncryptedValue model with `key_id`, `cipher_text`, `nonce`, `algorithm`
- Grep for encryption-related code in `backend/app/` -- only model definitions and config, no encryption service

**Risk:** If the master key is compromised, all encrypted data is exposed with no way to rotate keys. There is no actual encryption service implemented, so `EncryptedValue` is currently unused despite being in the schema.

**Fix Plan:**
1. Create `backend/app/core/encryption.py` with `EnvelopeEncryptionService` -- generates per-record DEKs, encrypts with AES-256-GCM, wraps DEK with master key.
2. Support key versioning: `key_id` format `mk-v1`, `mk-v2`, etc.
3. Add `rotate_master_key` management command that re-wraps DEKs with new master key.
4. Integrate encryption service with `DPPRevision` creation for sensitive submodel elements.

**Acceptance Criteria:**
- Encryption service can encrypt/decrypt field values.
- Key rotation re-wraps all DEKs without decrypting/re-encrypting data.
- `key_id` tracks which master key version was used.

**Test Plan:**
- Unit tests for encrypt/decrypt roundtrip.
- Unit test for key rotation (verify ciphertext unchanged, DEK re-wrapped).
- Integration test: create DPP with encrypted fields, read back.

**Effort:** 3-5 days

---

### F6. X-Forwarded-For IP Spoofing in Rate Limiter (P1 -- High)

**Description:** The `_get_client_ip()` function trusts `X-Forwarded-For` and `X-Real-IP` headers unconditionally, allowing any client to spoof their IP address and bypass per-IP rate limiting.

**Evidence:**
- `backend/app/core/rate_limit.py:52-57` -- trusts leftmost `X-Forwarded-For` value without validation
- `backend/app/core/rate_limit.py:59-60` -- trusts `X-Real-IP` header

**Risk:** An attacker can set `X-Forwarded-For: random-ip-each-request` to get unlimited fresh rate-limit buckets, completely defeating rate limiting. This also affects IP-based audit logging.

**Fix Plan:**
1. Only trust proxy headers when `TRUSTED_PROXIES` is configured (e.g., Caddy's internal IP `172.x.x.x`).
2. When behind a known number of proxies, use rightmost-minus-N from `X-Forwarded-For`.
3. Add `trusted_proxy_count` or `trusted_proxy_cidrs` to Settings.
4. Alternatively, since Caddy is the single proxy, use `X-Real-IP` set by Caddy and validate against trusted CIDR.

**Acceptance Criteria:**
- IP extraction validates proxy headers against trusted proxy list.
- Spoofed `X-Forwarded-For` from untrusted sources is ignored.

**Test Plan:**
- Unit test: request with spoofed `X-Forwarded-For` from untrusted source uses connection IP.
- Unit test: request from trusted proxy correctly extracts client IP.

**Effort:** 1 day

---

### F7. Policy Router Missing OPA ABAC Checks (P2 -- Medium)

**Description:** The policies router (`backend/app/modules/policies/router.py`) uses only tenant-level RBAC (TenantPublisher, TenantAdmin dependencies) but does not call `require_access()` or `check_access()` for OPA-based ABAC evaluation. This is inconsistent with all other routers (DPP, export, template, connector, settings, masters) which all call `require_access()`.

**Evidence:**
- `backend/app/modules/policies/router.py:56-220` -- no `require_access`, `check_access`, or `from app.core.security import` for ABAC
- Compare with `backend/app/modules/dpps/router.py:13` which imports and uses `require_access`
- Compare with `backend/app/modules/connectors/router.py:11` which imports and uses `require_access`

**Risk:** Policy management bypasses the centralized ABAC policy engine. If OPA policies are updated to restrict policy management (e.g., only certain admins can modify element-level policies), those restrictions won't be enforced.

**Fix Plan:**
1. Add `require_access()` calls to all policy router endpoints with resource type `"policy"`.
2. Add corresponding OPA policy rules for policy management actions.
3. Add audit events for policy CRUD operations.

**Acceptance Criteria:**
- All policy endpoints call `require_access()` with appropriate action.
- OPA rego policy includes rules for `read`/`create`/`delete` on resource type `policy`.

**Test Plan:**
- Unit test: verify ABAC is checked for policy endpoints.
- OPA rego test: verify policy management rules work correctly.

**Effort:** 1 day

---

### F8. OIDC Issuer Verification Disabled in JWT Library (P2 -- Medium)

**Description:** The JWT decode call explicitly disables issuer verification at the library level (`"verify_iss": False`), then performs manual issuer validation afterward. While the manual check is implemented correctly, disabling library-level verification increases the surface for bugs -- if the manual check is accidentally removed or bypassed, tokens from any issuer would be accepted.

**Evidence:**
- `backend/app/core/security/oidc.py:148-154` -- `options={"verify_aud": False, "verify_iss": False, ...}`
- `backend/app/core/security/oidc.py:157-163` -- manual issuer check follows

**Risk:** Defense-in-depth weakness. The manual check is currently correct, but this pattern is fragile. If a future refactor extracts the decode without the manual check, issuer validation would silently disappear.

**Fix Plan:**
1. Enable `verify_iss: True` in the jwt.decode options and pass the primary issuer.
2. Keep the manual multi-issuer check as a secondary validation for the additional allowed issuers.
3. Alternatively, if python-jose doesn't support multi-issuer, document clearly why `verify_iss` is False with a big warning comment.

**Acceptance Criteria:**
- JWT library-level issuer verification is enabled, OR a clear comment explains why it must remain disabled with a reference to the manual check.
- Existing issuer validation test suite passes.

**Test Plan:**
- Existing tests `test_oidc_validation.py` cover issuer rejection.
- Add test: verify token with missing issuer claim is rejected.

**Effort:** 0.5 days

---

### F9. DPP Revisions Endpoint Missing OPA ABAC Check (P2 -- Medium)

**Description:** The `list_revisions` endpoint in the DPP router checks ownership manually but does not call `require_access()` for ABAC enforcement, unlike all other DPP endpoints. This means OPA policies cannot control revision list access.

**Evidence:**
- `backend/app/modules/dpps/router.py:689-725` -- `list_revisions()` checks `dpp.owner_subject != tenant.user.sub` but never calls `require_access()`
- Compare with `get_dpp()` at line 466 which calls `require_access(tenant.user, "read", _dpp_resource(dpp), tenant=tenant)`

**Risk:** OPA cannot enforce fine-grained access control on revision listing. Revision data (audit trail of all edits) may be visible to users who shouldn't see it if OPA policies are tightened.

**Fix Plan:**
1. Add `await require_access(tenant.user, "read_revisions", _dpp_resource(dpp), tenant=tenant)` call.
2. Add corresponding OPA policy rule for `read_revisions` action.

**Acceptance Criteria:**
- `list_revisions` endpoint checks ABAC before returning data.
- OPA policy covers `read_revisions` action.

**Test Plan:**
- Unit test: verify ABAC deny blocks revision listing.
- OPA rego test: verify `read_revisions` policy rule.

**Effort:** 0.5 days

---

### F10. No SAST/DAST in CI Pipeline (P2 -- Medium)

**Description:** The security CI pipeline runs only Trivy (filesystem vulnerability scan) and SBOM generation. There is no Static Application Security Testing (SAST) like Semgrep or Bandit, and no Dynamic Application Security Testing (DAST).

**Evidence:**
- `.github/workflows/security.yml:1-41` -- only `sbom` and `trivy` jobs
- `.github/workflows/ci.yml` -- linting only (ruff, mypy, eslint), no security scanning
- No Semgrep, Bandit, pip-audit, or npm audit steps

**Risk:** Known vulnerability patterns (SQL injection, SSRF, path traversal, hardcoded secrets) in application code would not be caught automatically. Dependency vulnerabilities in Python packages (beyond what Trivy catches) may go undetected.

**Fix Plan:**
1. Add Semgrep to CI with Python and TypeScript rule sets (free for open source).
2. Add Bandit for Python-specific security analysis.
3. Add `pip-audit` for Python dependency vulnerability checking.
4. Add `npm audit` for frontend dependency checking.
5. Consider adding DAST in a future phase.

**Acceptance Criteria:**
- Semgrep runs on every PR with at least `p/python` and `p/typescript` rulesets.
- Bandit runs with medium+ confidence findings failing the build.
- `pip-audit` and `npm audit` run as separate CI steps.

**Test Plan:**
- Verify CI pipeline runs SAST tools.
- Verify known-bad patterns trigger alerts.

**Effort:** 1 day

---

## Summary Table

| # | Finding | Severity | Effort |
|---|---------|----------|--------|
| F1 | Connector secrets stored in plaintext JSONB | P0 | 2-3d |
| F2 | Audit logging not implemented | P0 | 3-4d |
| F3 | Rate limiting fails open, per-IP only | P1 | 2-3d |
| F4 | HSTS missing `preload`, no CSP | P1 | 0.5d |
| F5 | No encryption key rotation mechanism | P1 | 3-5d |
| F6 | X-Forwarded-For IP spoofing | P1 | 1d |
| F7 | Policy router missing OPA ABAC | P2 | 1d |
| F8 | OIDC issuer verification disabled in JWT lib | P2 | 0.5d |
| F9 | Revisions endpoint missing OPA ABAC | P2 | 0.5d |
| F10 | No SAST/DAST in CI | P2 | 1d |

**Total estimated effort: 15-20 days**

---

## Positive Observations

The following security patterns are well implemented:

1. **ABAC architecture is solid** -- OPA client fails closed on timeout/error (denies access), comprehensive Rego policy set covering DPP lifecycle, element-level masking/hiding, Catena-X BPN-based sharing.
2. **Tenant RLS at database level** -- PostgreSQL row-level security with `current_setting('app.current_tenant')` on all tenant-scoped tables, admin bypass role with `BYPASSRLS`.
3. **Production safety validator** -- `model_validator` on Settings catches missing encryption key, debug=True, and default CORS origins in production.
4. **OIDC implementation is thorough** -- JWKS caching with rotation, azp + multi-issuer validation, role extraction from realm + resource + flat claims.
5. **CORS is production-validated** -- explicit origin list, no wildcards, production override enforced.
6. **Test coverage for security** -- unit tests for ABAC enforcement, role merging, OIDC token validation including azp mismatch and issuer rejection.
