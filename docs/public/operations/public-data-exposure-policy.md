# Public Data Exposure Policy

This policy defines what data is allowed on public landing pages and CIRPASS public lab APIs.

## Scope

- Public landing page at `https://dpp-platform.dev/`
- Public summary endpoint: `GET /api/v1/public/{tenant_slug}/landing/summary`
- CIRPASS feed endpoint: `GET /api/v1/public/cirpass/stories/latest`
- CIRPASS manifest endpoints:
  - `GET /api/v1/public/cirpass/lab/manifest/latest`
  - `GET /api/v1/public/cirpass/lab/manifest/{manifest_version}`
- CIRPASS telemetry endpoint:
  - `POST /api/v1/public/cirpass/lab/events`
- CIRPASS leaderboard/session endpoints:
  - `GET /api/v1/public/cirpass/leaderboard`
  - `POST /api/v1/public/cirpass/session`
  - `POST /api/v1/public/cirpass/leaderboard/submit`

## Contract: Public Landing Summary

The public summary endpoint returns aggregate-only fields:

- `tenant_slug`
- `published_dpps`
- `active_product_families`
- `dpps_with_traceability`
- `latest_publish_at`
- `generated_at`

Response cache policy:

- `Cache-Control: public, max-age=15, stale-while-revalidate=15`

## Contract: CIRPASS Manifest + Stories

Allowed manifest data:

- Story metadata and learning text
- Synthetic step examples (request/response/artifact/policy hints)
- Feature-flag projection for the lab UI

Not allowed:

- Tenant identifiers
- Real product payloads
- Access tokens/secrets
- Internal policy payloads beyond curated inspector hints

## Contract: CIRPASS Telemetry

Allowed telemetry fields:

- `story_id`, `step_id`, `event_type`, `mode`, `variant`, `result`, `latency_ms`, sanitized `metadata`

Storage guardrails:

- Raw SID: not stored
- Raw IP: not stored
- Raw auth token: not stored
- Raw user agent: not stored

Retention:

- `cirpass_lab_events` retention defaults to 30 days.

## Allowed vs Blocked Data

| Data item | Show/store publicly | Rule |
|---|---|---|
| Platform capabilities and standards links | Yes | Static curated copy with evidence links |
| Aggregate published DPP count | Yes | Integer only from public summary endpoint |
| Aggregate product family count | Yes | Distinct count only |
| Aggregate traceability coverage count | Yes | Count only, no raw event payloads |
| Latest publish timestamp | Yes | Single timestamp only |
| CIRPASS story summaries + synthetic step payload examples | Yes | Must remain synthetic and non-tenant specific |
| CIRPASS leaderboard nickname + score + completion time + version + rank | Yes | Pseudonymous only, no email/account linkage |
| Anonymized telemetry hashes + step metadata | Yes | No reversible identifiers or secrets |
| Product-level identifiers (`serialNumber`, `batchId`, `globalAssetId`, `dpp_id`) | No | Explicitly prohibited |
| Raw AAS submodel content from private tenants | No | Restricted to protected routes |
| Raw EPCIS payloads or location fields (`payload`, `read_point`, `biz_location`) | No | Explicitly prohibited |
| Actor/user metadata and auth claims | No | Explicitly prohibited |
| CIRPASS session token internals (`sid`, `ua_hash`, signature) | No | Never exposed in responses |

## Security Guardrails

- Public responses use allowlisted field contracts.
- Sensitive-key denylist filtering is applied to public data paths.
- CIRPASS source ingest accepts only official `cirpassproject.eu` and `zenodo.org` URLs.
- Leaderboard and telemetry endpoints use signed, short-lived sessions and rate limits.

## Change Management

- Any new public field requires API contract and security review.
- Any new public claim requires evidence links or explicit scope qualifiers.
- Breaking public API changes require docs updates before release.
