import { describe, expect, it } from 'vitest';
import { deriveHintFromFailures, evaluateStepChecks } from './checkEngine';
import type { CirpassLabStep } from '../schema/storySchema';

const baseStep: CirpassLabStep = {
  id: 'create-passport',
  level: 'create',
  title: 'Create passport',
  actor: 'Manufacturer',
  intent: 'Create payload',
  explanation_md: 'Create payload',
  checks: [],
  variants: ['happy'],
};

describe('checkEngine', () => {
  it('passes deterministic checks for matching payload and status', () => {
    const step: CirpassLabStep = {
      ...baseStep,
      checks: [
        { type: 'status', expected: 201 },
        { type: 'schema', expression: 'required:create_fields', expected: ['identifier'] },
        { type: 'jsonpath', expression: '$.identifier', expected: 'present' },
      ],
    };

    const result = evaluateStepChecks(step, {
      payload: { identifier: 'did:web:test' },
      response_status: 201,
      mode: 'mock',
      variant: 'happy',
    });

    expect(result.passed).toBe(true);
    expect(result.failures).toHaveLength(0);
  });

  it('returns failures and hint when checks fail', () => {
    const step: CirpassLabStep = {
      ...baseStep,
      checks: [
        { type: 'status', expected: 200 },
        { type: 'jsonpath', expression: '$.identifier', expected: 'present' },
      ],
    };

    const result = evaluateStepChecks(step, {
      payload: {},
      response_status: 403,
      mode: 'mock',
      variant: 'unauthorized',
    });

    expect(result.passed).toBe(false);
    expect(result.failures.length).toBeGreaterThan(0);
    expect(deriveHintFromFailures(result.failures)).toContain('Expected');
  });
});

