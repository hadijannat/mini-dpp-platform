# Landing Page Data/Link Audit (Compliance-Heavy)

- Audit target: `https://dpp-platform.dev/`
- Audit date: 2026-02-07
- Scope: link integrity, landing-page data accuracy, and compliance-claim consistency against current codebase + official regulatory sources.

## 1) Source-of-Truth Landing Manifest

### 1.1 Clickable Elements (Source + Live)

| Element | Display Text | Source Target/Action | Live Target/Behavior | Source Reference |
|---|---|---|---|---|
| Skip link | Skip to content | `href="#main-content"` | `#main-content` anchor | `frontend/src/features/landing/LandingPage.tsx:14` |
| Brand link | DPP Platform | `href="#"` | `#` (top of page) | `frontend/src/features/landing/components/LandingHeader.tsx:32` |
| Header nav | What is DPP? | `href="#what-is-dpp"` | `#what-is-dpp` | `frontend/src/features/landing/components/LandingHeader.tsx:15` |
| Header nav | Standards | `href="#standards"` | `#standards` | `frontend/src/features/landing/components/LandingHeader.tsx:16` |
| Header nav | Features | `href="#features"` | `#features` | `frontend/src/features/landing/components/LandingHeader.tsx:17` |
| Header CTA | Sign in | `auth.signinRedirect()` | Redirects to Keycloak auth domain | `frontend/src/features/landing/components/LandingHeader.tsx:25` |
| Hero CTA | Get Started | `auth.signinRedirect()` | Redirects to Keycloak auth domain | `frontend/src/features/landing/components/HeroSection.tsx:11` |
| Hero CTA | Explore Features | `scrollIntoView('#features')` | Scrolls to features section | `frontend/src/features/landing/components/HeroSection.tsx:13` |
| Footer standards link | EU ESPR Regulation | external URL | 200 with redirect to canonical EU Commission path | `frontend/src/features/landing/components/LandingFooter.tsx:8` |
| Footer standards link | IDTA Specifications | external URL | 200 OK | `frontend/src/features/landing/components/LandingFooter.tsx:12` |
| Footer standards link | Asset Administration Shell | external URL | 404 Not Found | `frontend/src/features/landing/components/LandingFooter.tsx:16` |
| Footer standards link | Catena-X | external URL | 200 with redirect to root (`https://catena-x.net/`) | `frontend/src/features/landing/components/LandingFooter.tsx:20` |
| Footer platform action | Sign in | `auth.signinRedirect()` (or `/console` if auth) | Unauthenticated flow should redirect to Keycloak | `frontend/src/features/landing/components/LandingFooter.tsx:69` |
| Footer docs link | API Docs | `href="/docs"` | 200 but lands on SPA/landing, not Swagger docs | `frontend/src/features/landing/components/LandingFooter.tsx:81` |

### 1.2 Primary Landing Copy Claims (Compliance-Relevant)

| Claim | Source Reference |
|---|---|
| “EU ESPR Compliant” | `frontend/src/features/landing/components/HeroSection.tsx:48` |
| “full EU ESPR support” | `frontend/src/features/landing/components/HeroSection.tsx:66` |
| ESPR requires DPPs for EU products “starting 2027” | `frontend/src/features/landing/components/StandardsSection.tsx:13` |
| “Full compliance with EU regulations” | `frontend/src/features/landing/components/StandardsSection.tsx:63` |
| “Compliance Ready … CE marking fields, conformity declarations, audit-ready data exports” | `frontend/src/features/landing/components/PlatformFeaturesSection.tsx:39` |

## 2) Link Integrity and Behavior Validation

### 2.1 URL Validation Results

| URL on Landing | HTTP | Final URL | Classification |
|---|---:|---|---|
| `https://commission.europa.eu/.../sustainable-products/ecodesign-sustainable-products-regulation_en` | 200 | `https://commission.europa.eu/.../ecodesign-sustainable-products-regulation_en` | Stale redirect |
| `https://industrialdigitaltwin.org/en/content-hub/submodels` | 200 | Same | OK |
| `https://industrialdigitaltwin.org/en/content-hub/aas` | 404 | Same | Broken |
| `https://catena-x.net/en/` | 200 | `https://catena-x.net/` | Stale redirect |
| `/docs` | 200 | `https://dpp-platform.dev/docs` | Misleading destination |
| `/api/v1/docs` (expected docs route) | 200 | `https://dpp-platform.dev/api/v1/docs` | Reachable but runtime-broken UI (see below) |

### 2.2 Destination Semantics Checks

- `https://dpp-platform.dev/docs` renders the SPA/landing (`<title>Mini DPP Platform</title>`), not API docs.
- `https://dpp-platform.dev/api/v1/docs` serves FastAPI Swagger page title (`Mini DPP Platform - Swagger UI`) but Swagger static assets are blocked by CSP in browser runtime (blocked `cdn.jsdelivr` script/CSS), making docs effectively non-functional for users.

## 3) Compliance Claim Verification

Regulatory sources used:
- EU Commission ESPR page: `https://commission.europa.eu/.../ecodesign-sustainable-products-regulation_en`
- EUR-Lex ESPR (EU 2024/1781): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1781`
- EUR-Lex Battery Regulation (EU 2023/1542): `https://eur-lex.europa.eu/eli/reg/2023/1542/oj/eng`

### 3.1 Claim Classification

| Claim | Classification | Rationale |
|---|---|---|
| “EU ESPR Compliant” | Accurate-but-unqualified | Strong absolute wording without scope/limitations by product family, delegated acts, or implemented module boundaries. |
| “full EU ESPR support” | Ambiguous / likely overstated | “Full” is broad. Live API and frontend route surface do not show dedicated compliance endpoints/pages in this deployment. |
| ESPR DPP requirement “starting 2027” | Inconsistent/misleading | ESPR entered into force on **2024-07-18** and rolls out via product-specific delegated acts and plans; one universal start date framing is misleading. |
| “Full compliance with EU regulations” | Accurate-but-unqualified | Unbounded claim; not scoped to specific sectors/categories/features. |
| “Compliance Ready … audit-ready data exports” | Ambiguous | Partially substantiated by export/connectors/QR features, but broad language exceeds clearly evidenced compliance surface in current public API docs. |

## 4) Codebase Capability Cross-Check (Claim Substantiation)

### 4.1 Publicly Observable Capabilities (Live OpenAPI)

Present in live OpenAPI (`/api/v1/openapi.json`):
- Public viewer endpoints (`/api/v1/public/...`)
- Connectors endpoints (`/api/v1/tenants/{tenant_slug}/connectors...`)
- Export endpoint (`/api/v1/tenants/{tenant_slug}/export/{dpp_id}`)
- QR and GS1 endpoints (`/api/v1/tenants/{tenant_slug}/qr/...`)

Not present in live OpenAPI:
- Any `/compliance` endpoint paths
- Any `/audit` endpoint paths

### 4.2 Frontend Route Surface (Repo)

Current frontend route config (`frontend/src/App.tsx`) contains:
- `/console/connectors`, `/console/carriers`, viewer and export-adjacent flows

But does **not** contain:
- `/console/compliance`
- `/console/audit`

Implication: landing compliance wording should be scoped to currently exposed capability footprint.

## 5) Final Issue Register

| ID | Severity | Type | Issue | Evidence | Recommended Correction | Confidence |
|---|---|---|---|---|---|---:|
| LP-001 | P0 | broken link | `Asset Administration Shell` footer link is dead (404). | `LandingFooter.tsx:16`; URL check `404` | Replace with a valid IDTA AAS page, e.g. `https://industrialdigitaltwin.org/en/content-hub/aasspecifications` | 0.99 |
| LP-002 | P1 | misleading link | `API Docs` points to `/docs` (SPA), not backend docs route. | `LandingFooter.tsx:81`; backend docs route in `backend/app/main.py:77` | Change footer docs link to `/api/v1/docs` | 0.99 |
| LP-003 | P1 | flow inconsistency | `/api/v1/docs` is reachable but Swagger UI assets are CSP-blocked, so docs are not usable. | Browser console CSP errors on `/api/v1/docs` | Update CSP for docs route or self-host swagger assets under same origin | 0.95 |
| LP-004 | P1 | data accuracy | ESPR text says DPP required “starting 2027” as blanket statement. | `StandardsSection.tsx:13`; EU Commission timeline shows framework in force 2024-07-18 with delegated rollout | Reword to delegated-act model and date-accurate phrasing | 0.96 |
| LP-005 | P1 | compliance-risk wording | “EU ESPR Compliant” uses absolute language without scope. | `HeroSection.tsx:48` | Qualify: “Designed to support ESPR requirements for supported product categories” | 0.92 |
| LP-006 | P1 | compliance-risk wording | “full EU ESPR support” overstates scope. | `HeroSection.tsx:66`; no live `/compliance` routes in OpenAPI | Qualify by implemented categories/features | 0.90 |
| LP-007 | P2 | compliance-risk wording | “Full compliance with EU regulations” is broad and unscoped. | `StandardsSection.tsx:63` | Scope by regulations/features actually implemented | 0.88 |
| LP-008 | P2 | claim substantiation gap | “Compliance Ready … audit-ready data exports” exceeds clear public API evidence in live deployment. | `PlatformFeaturesSection.tsx:39`; no live `/audit` or `/compliance` paths | Narrow text to currently exposed validated capabilities | 0.84 |
| LP-009 | P3 | stale redirect | EU ESPR link uses old path segment and redirects. | `LandingFooter.tsx:8`; final canonical URL differs | Update to canonical URL to avoid redirect hops | 0.86 |
| LP-010 | P3 | stale redirect | Catena-X link redirects `/en/` to root. | `LandingFooter.tsx:20`; final URL `https://catena-x.net/` | Use canonical root URL directly | 0.85 |
| LP-011 | P3 | UX consistency | Brand link uses `#` instead of explicit `/` or scroll target. | `LandingHeader.tsx:32` | Point to `/` (or `#main-content`) for deterministic behavior | 0.78 |

## 6) Fast-Fix List (Low-Risk Edits)

1. Replace broken AAS URL.
2. Change footer `API Docs` link to `/api/v1/docs`.
3. Update EU ESPR and Catena-X URLs to canonical targets (remove unnecessary redirects).
4. Reword “starting 2027” to a delegated-act-based timeline statement.
5. Add claim qualifiers to “EU ESPR Compliant”, “full EU ESPR support”, and “Full compliance with EU regulations”.

## 7) Policy/Legal Review List

1. Approve claim policy for absolute terms: `compliant`, `full support`, `full compliance`.
2. Define required qualifier template for regulatory language on marketing pages.
3. Approve product-category scope statement for ESPR support.
4. Approve public-facing wording for “audit-ready” claims.

## 8) Reproducible Checks

### 8.1 Link Validation
```bash
for u in \
  "https://dpp-platform.dev/docs" \
  "https://dpp-platform.dev/api/v1/docs" \
  "https://commission.europa.eu/energy-climate-change-environment/standards-tools-and-labels/products-labelling-rules-and-requirements/sustainable-products/ecodesign-sustainable-products-regulation_en" \
  "https://industrialdigitaltwin.org/en/content-hub/submodels" \
  "https://industrialdigitaltwin.org/en/content-hub/aas" \
  "https://catena-x.net/en/"; do
  printf "\n%s\n" "$u"
  curl -sS -L -o /dev/null -w "status=%{http_code} final=%{url_effective}\n" "$u"
done
```

### 8.2 Live Capability Surface
```bash
curl -sS https://dpp-platform.dev/api/v1/openapi.json \
  | python3 -c 'import sys,json; o=json.load(sys.stdin);\
for p in sorted(o.get("paths",{})): \
  print(p) if any(k in p for k in ["public","connectors","export","qr","templates","compliance","audit"]) else None'
```

## 9) Assumptions

1. Production behavior is measured as of 2026-02-07.
2. Severity mapping follows project default (`P0`..`P3`) with compliance wording treated as high-risk if absolute and unqualified.
3. This audit does not modify API contracts; it assesses landing-page truthfulness and link integrity.
