import type { CirpassLabMode, CirpassLabStep, CirpassLabVariant } from '../schema/storySchema';

export interface StepRunContext {
  payload: Record<string, unknown>;
  response_status: number;
  response_body?: unknown;
  mode: CirpassLabMode;
  variant: CirpassLabVariant;
}

export interface CheckFailure {
  type: 'jsonpath' | 'jmespath' | 'status' | 'schema';
  expression?: string;
  expected?: unknown;
  actual?: unknown;
  message: string;
}

export interface CheckResult {
  passed: boolean;
  failures: CheckFailure[];
}

function isMissingValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === 'string') {
    return value.trim().length === 0;
  }
  return false;
}

function getValueByExpression(source: unknown, expression: string | undefined): unknown {
  if (!expression || !expression.trim()) {
    return undefined;
  }

  const normalized = expression.trim().replace(/^\$\./, '').replace(/^\$/, '');
  if (!normalized) {
    return source;
  }

  const path = normalized.split('.').map((part) => part.trim()).filter(Boolean);
  let cursor: unknown = source;
  for (const part of path) {
    if (!cursor || typeof cursor !== 'object') {
      return undefined;
    }
    cursor = (cursor as Record<string, unknown>)[part];
  }
  return cursor;
}

function deepEqual(lhs: unknown, rhs: unknown): boolean {
  return JSON.stringify(lhs) === JSON.stringify(rhs);
}

function evaluateStatusCheck(
  expected: unknown,
  responseStatus: number,
): CheckFailure | null {
  if (typeof expected !== 'number') {
    return null;
  }

  if (responseStatus === expected) {
    return null;
  }

  return {
    type: 'status',
    expected,
    actual: responseStatus,
    message: `Expected status ${expected}, received ${responseStatus}.`,
  };
}

function evaluateSchemaCheck(
  expression: string | undefined,
  expected: unknown,
  payload: Record<string, unknown>,
): CheckFailure[] {
  const failures: CheckFailure[] = [];
  const requiredFields =
    Array.isArray(expected) && expected.every((item) => typeof item === 'string')
      ? (expected as string[])
      : [];

  if (requiredFields.length === 0 && expression?.startsWith('required:')) {
    return failures;
  }

  for (const field of requiredFields) {
    const value = payload[field];
    if (isMissingValue(value)) {
      failures.push({
        type: 'schema',
        expression,
        expected,
        actual: payload,
        message: `Missing required field '${field}'.`,
      });
    }
  }
  return failures;
}

function evaluatePathCheck(
  type: 'jsonpath' | 'jmespath',
  expression: string | undefined,
  expected: unknown,
  context: StepRunContext,
): CheckFailure | null {
  const source = context.payload ?? (context.response_body as Record<string, unknown>) ?? {};
  const actual = getValueByExpression(source, expression);
  if (expected === 'present') {
    if (!isMissingValue(actual)) {
      return null;
    }
    return {
      type,
      expression,
      expected,
      actual,
      message: `Expected ${expression ?? 'value'} to be present.`,
    };
  }

  if (deepEqual(actual, expected)) {
    return null;
  }

  return {
    type,
    expression,
    expected,
    actual,
    message: `Expected ${expression ?? 'value'} to match required output.`,
  };
}

export function evaluateStepChecks(
  step: CirpassLabStep,
  context: StepRunContext,
): CheckResult {
  const failures: CheckFailure[] = [];

  for (const check of step.checks ?? []) {
    if (check.type === 'status') {
      const failure = evaluateStatusCheck(check.expected, context.response_status);
      if (failure) {
        failures.push(failure);
      }
      continue;
    }

    if (check.type === 'schema') {
      failures.push(...evaluateSchemaCheck(check.expression, check.expected, context.payload));
      continue;
    }

    if (check.type === 'jsonpath' || check.type === 'jmespath') {
      const failure = evaluatePathCheck(check.type, check.expression, check.expected, context);
      if (failure) {
        failures.push(failure);
      }
      continue;
    }
  }

  return {
    passed: failures.length === 0,
    failures,
  };
}

export function deriveHintFromFailures(failures: CheckFailure[]): string {
  if (failures.length === 0) {
    return 'Review payload inputs and expected API behavior for this step.';
  }
  return failures[0].message;
}

