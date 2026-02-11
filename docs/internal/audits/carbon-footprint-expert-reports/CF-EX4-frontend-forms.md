# CF-EX4 Frontend Dynamic Forms

## Owner
Frontend Dynamic Forms Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/pages/SubmodelEditorPage.tsx`
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/AASRenderer.tsx`
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/fields/ListField.tsx`
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/utils/zodSchemaBuilder.ts`
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/utils/validation.ts`
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/types/uiSchema.ts`

## Findings
1. Frontend UISchema contract was missing backend-emitted qualifier extensions (`CF-003`).
2. Save validation did not enforce `x-allowed-id-short`, `x-edit-id-short`, and `x-naming` (`CF-004`).
3. `orderRelevant` list semantics were not reflected in list controls (`CF-005`).

## Implemented
- Extended `UISchema` typing with required `x-*` extensions.
- Added dynamic idShort enforcement for naming and pattern controls.
- Added list move up/down controls for `orderRelevant=true` paths in list rendering.
- Added/updated tests in renderer and validation suites.

## Evidence Command
```bash
npm test -- --run src/features/editor/components/AASRenderer.test.tsx src/features/editor/utils/zodSchemaBuilder.test.ts src/features/editor/utils/validation.test.ts
```

## Acceptance Criteria
- Carbon Footprint list and collection fields render with required constraints.
- Unsupported dynamic keys are rejected deterministically on save.
- `orderRelevant` lists expose reordering actions and preserve updated order in output.
