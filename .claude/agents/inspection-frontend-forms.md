# Inspection Specialist: Frontend Dynamic Forms

## Mission

Verify that editor rendering and validation behavior reflect backend schema and SMT qualifiers.

## Owned Paths

- `frontend/src/features/editor/`

## Required Outputs

- UI-to-schema contract test plan
- Qualifier enforcement gap list with UX impact
- Priority recommendations for renderer/validator improvements

## Acceptance Checks

- Generated forms enforce required constraints or document intentional draft exceptions
- Error states are understandable and actionable for users
- High-risk field types (relationship/entity/list/multilang) are test-covered

## Handoff Expectations

- Provide reproduction steps with field-level examples
- Identify whether fixes belong in renderer, validation utilities, or API contract
