# CIRPASS Lab Story Manifests

This folder contains data-first scenario definitions for `/cirpass-lab`.

## Files

- `index.yaml`: manifest registry with the latest published manifest version.
- `manifest.v1.0.0.yaml`: initial CIRPASS core-loop scenario set.

## Governance

- Every manifest change should update `last_reviewed` and `references`.
- Keep scenario content synthetic; do not embed tenant data or secrets.
- Validate changes with frontend schema checks and CIRPASS lab tests.
