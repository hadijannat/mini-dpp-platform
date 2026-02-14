# Regulatory Timeline Seed

This folder stores the curated seed used by the public endpoint:

- `GET /api/v1/public/landing/regulatory-timeline`
- Primary repo seed: `docs/public/regulatory-timeline/events.seed.yaml`
- Packaged fallback seed: `backend/app/modules/regulatory_timeline/data/events.seed.yaml`

## Freshness Semantics

The landing timeline header surfaces API freshness status:

- `source_status=fresh` -> UI label: `Live verified feed`
- `source_status=stale` -> UI label: `Refreshing...`

Stale status means the latest cached snapshot is served while background refresh is in progress.

## Seed Resolution Order

Runtime seed resolution for the timeline service uses this order:

1. Config override: `regulatory_timeline_seed_path` (if set)
2. Repo seed: `docs/public/regulatory-timeline/events.seed.yaml`
3. Packaged seed fallback in backend module data directory

## Precision Rule

Some standards milestones are only published with month precision.
Those entries use:

- `date_precision: month`
- `date: YYYY-MM`

The UI must render those values as month/year and must not infer a specific day.
