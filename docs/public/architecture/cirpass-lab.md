# CIRPASS Lab Architecture

## Purpose

`/cirpass-lab` is a public learning surface for CIRPASS user stories with a game loop, deep links, and under-the-hood technical inspection.

## Public Routes

- Landing teaser: `/#cirpass-lab`
- Lab shell: `/cirpass-lab`
- Deep-link runner: `/cirpass-lab/story/:storyId/step/:stepId?mode=mock|live&variant=happy|unauthorized|not_found`

## Public APIs

- `GET /api/v1/public/cirpass/stories/latest`
- `POST /api/v1/public/cirpass/session`
- `GET /api/v1/public/cirpass/leaderboard`
- `POST /api/v1/public/cirpass/leaderboard/submit`
- `GET /api/v1/public/cirpass/lab/manifest/latest`
- `GET /api/v1/public/cirpass/lab/manifest/{manifest_version}`
- `POST /api/v1/public/cirpass/lab/events`

## Protected Lab Ops APIs

- `POST /api/v1/lab/reset`
- `POST /api/v1/lab/seed`
- `GET /api/v1/lab/status`

These routes are admin-gated and designed for deterministic live-mode sandbox readiness checks.

## Scenario Contract Boundary

### Source of truth

- Manifest sources live in `docs/public/cirpass-stories/*.yaml`
- Version index lives in `docs/public/cirpass-stories/index.yaml`

### Build-time compile

- `frontend/scripts/generate-cirpass-stories.mjs` compiles latest manifest into:
  - `frontend/src/features/cirpass-lab/stories.generated.ts`

### Runtime validation

- Frontend validates server payloads with Zod in:
  - `frontend/src/features/cirpass-lab/schema/storySchema.ts`
  - `frontend/src/features/cirpass-lab/schema/manifestLoader.ts`

### Compatibility rule

If manifest loading fails, runner falls back to the current hardcoded 5-level flow and displays a warning banner.

## Frontend Runtime

- `CirpassLabPage.tsx` is the shell.
- `StoryRunner.tsx` executes scenario lifecycle with compatibility adapter to the existing XState machine.
- Inspectors:
  - `ApiInspector`
  - `ArtifactDiffInspector`
  - `PolicyInspector`
- Deep-link and resume logic:
  - `useStoryProgress.ts`

## Feature Flags

Config keys:

- `cirpass_lab_scenario_engine_enabled`
- `cirpass_lab_live_mode_enabled`
- `cirpass_lab_inspector_enabled`

Manifest response returns current flag projection under `feature_flags`.

## Telemetry and Privacy

- Telemetry endpoint stores anonymized rows in `cirpass_lab_events`.
- No raw IP or raw SID persisted.
- Stored fields: hashed SID, story/step, mode, variant, result, latency, sanitized metadata.
- Retention controlled by `cirpass_lab_telemetry_retention_days`.

## Data Model

- `cirpass_story_snapshots`: SWR cache for CIRPASS story feed.
- `cirpass_leaderboard_entries`: pseudonymous leaderboard with best-score-per-session rules.
- `cirpass_lab_events`: anonymized step telemetry events.
