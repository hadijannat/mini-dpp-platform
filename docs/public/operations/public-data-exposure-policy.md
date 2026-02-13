# Public Data Exposure Policy

This policy defines what data is allowed on public landing pages and public summary endpoints.

## Scope

- Public landing page at `https://dpp-platform.dev/`
- Public summary endpoint: `GET /api/v1/public/{tenant_slug}/landing/summary`
- Audience: manufacturers, regulators, recyclers/repair networks, and consumers

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

## Allowed vs Blocked Data

| Data item | Show on landing | Rule |
|---|---|---|
| Platform capabilities and standards links | Yes | Static curated copy with evidence links |
| Aggregate published DPP count | Yes | Integer only from public summary endpoint |
| Aggregate product family count | Yes | Distinct count only |
| Aggregate traceability coverage count | Yes | Count only, no raw event payloads |
| Latest publish timestamp | Yes | Single timestamp only |
| Product-level identifiers (`serialNumber`, `batchId`, `globalAssetId`, `dpp_id`) | No | Explicitly prohibited |
| Raw AAS submodel content | No | Restricted to viewer/protected routes |
| Raw EPCIS event payloads or location fields (`payload`, `read_point`, `biz_location`) | No | Explicitly prohibited |
| Actor/user metadata | No | Explicitly prohibited |

## Landing Claims Source of Truth

| Claim style | Source/evidence | Notes |
|---|---|---|
| “Supports ESPR-aligned workflows for supported categories” | [EU ESPR overview](https://commission.europa.eu/energy-climate-change-environment/standards-tools-and-labels/products-labelling-rules-and-requirements/sustainable-products/ecodesign-sustainable-products-regulation_en), [EU 2024/1781](https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng) | Must include qualifier; never imply universal compliance across all categories |
| AAS and IDTA-oriented interoperability language | [IDTA submodels](https://industrialdigitaltwin.org/en/content-hub/submodels), [AAS specifications](https://industrialdigitaltwin.org/en/content-hub/aasspecifications) | Link to standards and avoid absolute claims |
| Platform feature claims | `/api/v1/docs` | Claims must match currently exposed behavior |

## Security Guardrails

- Public responses use allowlisted aggregate fields for landing summaries.
- Sensitive-key denylist filtering is applied to public data paths to prevent accidental leakage.
- Public landing UI renders only known aggregate keys and ignores unexpected response fields.

## Review and Change Management

- Any new public landing metric requires API contract review and security review.
- Any new public claim requires evidence links or explicit scope qualifiers.
- Breaking changes to public fields require release-note and docs updates before rollout.
