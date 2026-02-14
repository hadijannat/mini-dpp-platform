# Regulatory Timeline Seed

This folder stores the curated seed used by the public endpoint:

- `GET /api/v1/public/landing/regulatory-timeline`

## Precision Rule

Some standards milestones are only published with month precision.
Those entries use:

- `date_precision: month`
- `date: YYYY-MM`

The UI must render those values as month/year and must not infer a specific day.
