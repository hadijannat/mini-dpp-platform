# CIRPASS Lab Architecture

## Purpose

`/cirpass-lab` delivers a public, gamified learning surface for CIRPASS user stories while preserving strict data-boundary and pseudonymous interaction rules.

## Public Surface

- Landing teaser section (`/#cirpass-lab`) links into simulator route.
- Simulator route (`/cirpass-lab`) is public and client-rendered.
- Public APIs:
  - `GET /api/v1/public/cirpass/stories/latest`
  - `POST /api/v1/public/cirpass/session`
  - `GET /api/v1/public/cirpass/leaderboard`
  - `POST /api/v1/public/cirpass/leaderboard/submit`

## Backend Components

### Module

- `backend/app/modules/cirpass/public_router.py`: API contract and status mapping.
- `backend/app/modules/cirpass/service.py`: SWR refresh, token signing, leaderboard ranking/rate limits.
- `backend/app/modules/cirpass/parser.py`: official-source discovery (CIRPASS + Zenodo), metadata extraction, PDF parsing.
- `backend/app/modules/cirpass/schemas.py`: typed request/response contracts.

### Data Model

- `cirpass_story_snapshots`
  - Stores normalized level/story payload snapshots and source metadata.
  - Supports stale-while-refresh feed serving.
- `cirpass_leaderboard_entries`
  - Stores pseudonymous best-score rows per `(sid, version)`.
  - No tenant/account linkage.

### SWR Strategy

1. Serve latest snapshot immediately.
2. If snapshot age exceeds `cirpass_refresh_ttl_seconds`, response is marked `source_status="stale"`.
3. Trigger one background refresh task (process-local lock).
4. On refresh failure, keep previous snapshot.
5. If no snapshot exists and refresh fails, return `503`.

## Frontend Components

- `frontend/src/features/cirpass-lab/pages/CirpassLabPage.tsx`
- `frontend/src/features/cirpass-lab/components/*`
- `frontend/src/features/cirpass-lab/machines/cirpassMachine.ts`
- `frontend/src/features/cirpass-lab/hooks/*`

### Twin-Layer UI

- `TwinLayerShell` toggles Joyful/Technical layers via Spacebar or button.
- Joyful layer: stage cards and progression feedback.
- Technical layer: React Flow process graph + payload preview.

### Lifecycle Enforcement

XState machine enforces strict progression:

`create -> access -> update -> transfer -> deactivate -> completed`

Each stage validates mandatory payload fields before transitioning.

## Leaderboard Security Posture

- Browser session tokens are HMAC-signed and time-limited.
- Token binds to user-agent hash.
- Nickname regex: `^[A-Za-z0-9_-]{3,20}$`.
- Submission throttles:
  - Max 3 submissions/hour per session id.
  - Max 20 submissions/day per IP hash.
- Retention cleanup removes entries older than 90 days on submit path.

## Operational Notes

- For production, set `CIRPASS_SESSION_TOKEN_SECRET` explicitly.
- Source ingestion accepts only official domains; non-official links are rejected.
- Landing performance is preserved by isolating heavy simulator dependencies to `/cirpass-lab`.
