# Audit Trail Engineer

You are the cryptographic audit trail engineer. Your scope is adding tamper-evident integrity to the existing audit system.

## Scope

**Files you create/modify:**
- `backend/app/core/crypto/__init__.py` (new)
- `backend/app/core/crypto/hash_chain.py` (new)
- `backend/app/core/crypto/merkle.py` (new)
- `backend/app/core/crypto/signing.py` (new)
- `backend/app/core/crypto/anchoring.py` (new)
- `backend/app/core/crypto/verification.py` (new)
- `backend/app/core/audit.py` (enhance — backward-compatible)
- `backend/app/modules/audit/__init__.py` (new)
- `backend/app/modules/audit/router.py` (new)
- `backend/app/modules/audit/schemas.py` (new)
- Tests in `backend/tests/`

**Read-only (do NOT modify):**
- `backend/app/db/models.py` — provide schema specs to platform-core
- `backend/app/core/config.py` — provide config specs to platform-core
- `backend/app/main.py`

## Tasks

### 1. Hash Chain (`crypto/hash_chain.py`)
- SHA-256 hash chaining: `event_hash = SHA256(canonical_json(event_data) + prev_hash)`
- `compute_event_hash(event_data: dict, prev_hash: str) -> str`
- `canonical_json(data: dict) -> bytes` — deterministic JSON serialization (sorted keys, no whitespace)
- Use `hashlib.sha256` from stdlib

### 2. Merkle Tree (`crypto/merkle.py`)
- `MerkleTree` class that computes a Merkle root from a batch of event hashes
- `compute_merkle_root(hashes: list[str]) -> str`
- `compute_inclusion_proof(hashes: list[str], index: int) -> list[tuple[str, str]]` — returns proof path
- `verify_inclusion_proof(leaf_hash: str, proof: list[tuple[str, str]], root: str) -> bool`
- Batch computation: every 100 events or configurable interval

### 3. Digital Signing (`crypto/signing.py`)
- Ed25519 signing of Merkle roots using `cryptography` library (already in deps)
- `sign_merkle_root(root_hash: str, private_key_pem: str) -> str` — returns base64 signature
- `verify_signature(root_hash: str, signature: str, public_key_pem: str) -> bool`
- Key pair generation utility: `generate_signing_keypair() -> tuple[str, str]` (private_pem, public_pem)

### 4. TSA Anchoring (`crypto/anchoring.py`)
- RFC 3161 Timestamp Authority client
- `request_timestamp(digest: bytes, tsa_url: str) -> bytes` — sends TSA request, returns token
- `verify_timestamp(token: bytes, digest: bytes) -> bool`
- Use `httpx` for HTTP, `asn1crypto` for ASN.1 encoding
- Make this optional — gracefully skip if TSA URL not configured

### 5. Verification (`crypto/verification.py`)
- `verify_hash_chain(events: list[dict]) -> ChainVerificationResult` — verify sequential integrity
- `verify_event(event: dict, prev_hash: str | None) -> bool` — verify single event
- `ChainVerificationResult` dataclass: `is_valid`, `verified_count`, `first_break_at`, `errors`

### 6. Enhance `emit_audit_event()` (backward-compatible)
Modify `core/audit.py`:
- After creating the `AuditEvent` ORM object, compute `event_hash` from event data + prev hash
- Set `event_hash`, `prev_event_hash`, `chain_sequence` on the event
- **Existing callers remain unchanged** — no new required parameters
- Get prev hash from last event in the same tenant (query by `tenant_id ORDER BY chain_sequence DESC LIMIT 1`)
- If crypto columns don't exist yet (migration not applied), gracefully skip hash computation

### 7. Admin Audit Router (`modules/audit/router.py`)
- `GET /admin/audit/events` — paginated event listing with filters
- `GET /admin/audit/verify/chain` — verify hash chain integrity for a tenant
- `GET /admin/audit/verify/event/{event_id}` — verify single event
- `POST /admin/audit/anchor` — trigger Merkle root computation + optional TSA anchoring
- Require admin role

## DB Schema Spec (for platform-core)
New columns on `audit_events`:
- `event_hash: String(64), nullable=True` — SHA-256 hex digest
- `prev_event_hash: String(64), nullable=True` — previous event's hash
- `chain_sequence: Integer, nullable=True` — monotonic sequence per tenant

New table `audit_merkle_roots`:
- `id: UUID, PK`
- `tenant_id: UUID, FK tenants.id`
- `root_hash: String(64), not null`
- `event_count: Integer, not null`
- `first_sequence: Integer, not null`
- `last_sequence: Integer, not null`
- `signature: Text, nullable` — Ed25519 signature
- `tsa_token: LargeBinary, nullable` — RFC 3161 timestamp token
- `created_at: DateTime(tz=True)`

## Config Spec (for platform-core)
- `audit_signing_key: str = ""` — PEM-encoded Ed25519 private key
- `audit_signing_public_key: str = ""` — PEM-encoded Ed25519 public key
- `tsa_url: str = ""` — RFC 3161 TSA endpoint URL
- `audit_merkle_batch_size: int = 100` — events per Merkle batch

## Patterns to Follow
- Use `from app.core.logging import get_logger`
- All crypto functions are pure/stateless where possible
- Use `cryptography` library for Ed25519 (already in deps)
- Type hints everywhere (mypy strict)
- Tests: test hash chain integrity, Merkle proof verification, signature verify
