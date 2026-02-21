import type { UISchema } from '../types/uiSchema';
import { validateSchema } from './validation';

export type JsonValidationIssue = {
  path: string;
  message: string;
};

function normalizePath(path: string): string {
  const normalized = path.trim();
  return normalized || 'root';
}

export function normalizeSchemaIssues(schemaErrors: Record<string, string>): JsonValidationIssue[] {
  return Object.entries(schemaErrors)
    .map(([path, message]) => ({ path: normalizePath(path), message }))
    .sort((left, right) => left.path.localeCompare(right.path));
}

export function buildJsonIssues(
  rawValue: string,
  schema?: UISchema,
): { parsed: Record<string, unknown> | null; issues: JsonValidationIssue[] } {
  try {
    const parsedUnknown = JSON.parse(rawValue) as unknown;
    if (!parsedUnknown || typeof parsedUnknown !== 'object' || Array.isArray(parsedUnknown)) {
      return {
        parsed: null,
        issues: [{ path: 'root', message: 'JSON payload must be an object' }],
      };
    }

    const parsed = parsedUnknown as Record<string, unknown>;
    if (!schema) {
      return { parsed, issues: [] };
    }

    const schemaErrors = validateSchema(schema, parsed);
    return {
      parsed,
      issues: normalizeSchemaIssues(schemaErrors),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Invalid JSON';
    return {
      parsed: null,
      issues: [{ path: 'root', message: `Invalid JSON: ${message}` }],
    };
  }
}
