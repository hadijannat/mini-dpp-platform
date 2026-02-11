import type { DefinitionNode, FormData, TemplateDefinition } from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import {
  pathToKey,
  isEmptyValue,
  deepEqual,
  definitionPathToSegments,
  getValuesAtPattern,
} from './pathUtils';

export function validateReadOnly(
  schema: UISchema | undefined,
  data: unknown,
  baseline: unknown,
  path: Array<string | number> = [],
): Record<string, string> {
  if (!schema) return {};
  const errors: Record<string, string> = {};
  const key = pathToKey(path);

  if (schema.readOnly || schema['x-readonly']) {
    if (!deepEqual(data, baseline)) {
      errors[key] = 'Read-only field cannot be modified';
    }
    return errors;
  }

  if (schema.type === 'object' && schema.properties) {
    const obj =
      data && typeof data === 'object' && !Array.isArray(data)
        ? (data as Record<string, unknown>)
        : {};
    const baseObj =
      baseline && typeof baseline === 'object' && !Array.isArray(baseline)
        ? (baseline as Record<string, unknown>)
        : {};
    for (const [prop, propSchema] of Object.entries(schema.properties)) {
      Object.assign(
        errors,
        validateReadOnly(propSchema, obj[prop], baseObj[prop], [...path, prop]),
      );
    }
  } else if (schema.type === 'array' && schema.items) {
    const list = Array.isArray(data) ? data : [];
    const baseList = Array.isArray(baseline) ? baseline : [];
    list.forEach((item, idx) => {
      Object.assign(
        errors,
        validateReadOnly(schema.items!, item, baseList[idx], [...path, idx]),
      );
    });
  }

  return errors;
}

export function validateEitherOr(
  definition: TemplateDefinition | undefined,
  data: FormData,
): string[] {
  if (!definition?.submodel?.elements?.length) return [];
  const rootIdShort = definition.submodel.idShort;
  const groups: Record<string, DefinitionNode[]> = {};

  const visit = (node: DefinitionNode) => {
    const groupId = node.smt?.either_or;
    if (groupId) {
      groups[groupId] = groups[groupId] || [];
      groups[groupId].push(node);
    }
    node.children?.forEach(visit);
    if (node.items) visit(node.items);
  };

  definition.submodel.elements.forEach(visit);

  const errors: string[] = [];
  Object.entries(groups).forEach(([groupId, nodes]) => {
    const hasValue = nodes.some((node) => {
      if (!node.path) return false;
      const segments = definitionPathToSegments(node.path, rootIdShort);
      const values = getValuesAtPattern(data, segments);
      return values.some((value) => !isEmptyValue(value));
    });
    if (!hasValue) {
      errors.push(`Either-or group "${groupId}" requires at least one value.`);
    }
  });

  return errors;
}

export function validateSchema(
  schema: UISchema | undefined,
  data: unknown,
  path: Array<string | number> = [],
): Record<string, string> {
  if (!schema) return {};
  const errors: Record<string, string> = {};
  const pathKey = pathToKey(path);

  if (schema.enum && data !== undefined && data !== null && data !== '') {
    if (!schema.enum.includes(data as string)) {
      errors[pathKey] = 'Invalid value';
    }
  }

  if (schema.pattern && typeof data === 'string' && data !== '') {
    try {
      const regex = new RegExp(schema.pattern);
      if (!regex.test(data)) {
        errors[pathKey] = 'Invalid format';
      }
    } catch {
      // Ignore invalid patterns from upstream templates.
    }
  }

  if (typeof data === 'number') {
    const range = getSchemaRange(schema);
    const minimum = range?.min ?? schema.minimum;
    const maximum = range?.max ?? schema.maximum;

    if (minimum !== undefined && data < minimum) {
      errors[pathKey] = `Must be ≥ ${minimum}`;
    }
    if (maximum !== undefined && data > maximum) {
      errors[pathKey] = `Must be ≤ ${maximum}`;
    }
  }

  if (schema['x-range'] && data && typeof data === 'object' && !Array.isArray(data)) {
    const bounds = getSchemaRange(schema);
    const minimum = bounds?.min ?? schema.minimum;
    const maximum = bounds?.max ?? schema.maximum;
    const rangeValue = data as { min?: number | null; max?: number | null };
    const minValue = typeof rangeValue.min === 'number' ? rangeValue.min : null;
    const maxValue = typeof rangeValue.max === 'number' ? rangeValue.max : null;

    if (minValue !== null && minimum !== undefined && minValue < minimum) {
      errors[pathKey] = `Min must be ≥ ${minimum}`;
    }
    if (maxValue !== null && maximum !== undefined && maxValue > maximum) {
      errors[pathKey] = `Max must be ≤ ${maximum}`;
    }
    if (minValue !== null && maxValue !== null && minValue > maxValue) {
      errors[pathKey] = 'Min cannot exceed max';
    }
  }

  if (schema['x-multi-language']) {
    const requiredLangs = schema['x-required-languages'] ?? [];
    if (requiredLangs.length > 0) {
      const obj =
        data && typeof data === 'object' && !Array.isArray(data)
          ? (data as Record<string, unknown>)
          : {};
      if (Object.keys(obj).length > 0) {
        const missing = requiredLangs.filter((lang) => {
          const value = obj[lang];
          return value === undefined || value === null || String(value).trim() === '';
        });
        if (missing.length > 0) {
          errors[pathKey] = `Missing required languages: ${missing.join(', ')}`;
        }
      }
    }
  }

  if (schema.type === 'object' && schema.properties) {
    const obj =
      data && typeof data === 'object' && !Array.isArray(data)
        ? (data as Record<string, unknown>)
        : {};
    Object.assign(errors, validateDynamicIdShortPolicy(schema, obj, path));
    const required = schema.required ?? [];

    for (const key of required) {
      const value = obj[key];
      if (isEmptyValue(value)) {
        errors[pathToKey([...path, key])] = 'Required';
      }
    }

    for (const [key, propertySchema] of Object.entries(schema.properties)) {
      const nested = validateSchema(propertySchema, obj[key], [...path, key]);
      Object.assign(errors, nested);
    }
  } else if (schema.type === 'array' && schema.items) {
    if (Array.isArray(data)) {
      if (schema.minItems !== undefined && data.length < schema.minItems) {
        errors[pathKey] = `At least ${schema.minItems} item(s) required`;
      }
      data.forEach((item, index) => {
        const nested = validateSchema(schema.items, item, [...path, index]);
        Object.assign(errors, nested);
      });
    }
  }

  return errors;
}

function validateDynamicIdShortPolicy(
  schema: UISchema,
  objectData: Record<string, unknown>,
  path: Array<string | number>,
): Record<string, string> {
  const errors: Record<string, string> = {};
  const declaredKeys = new Set(Object.keys(schema.properties ?? {}));
  const dynamicKeys = Object.keys(objectData).filter((key) => !declaredKeys.has(key));

  const canEditIdShort = schema['x-edit-id-short'];
  const allowedIdShort = schema['x-allowed-id-short'] ?? [];
  const namingRule = schema['x-naming'];

  if (
    dynamicKeys.length === 0 ||
    (canEditIdShort === undefined && allowedIdShort.length === 0 && !namingRule)
  ) {
    return errors;
  }

  if (canEditIdShort === false && dynamicKeys.length > 0) {
    for (const key of dynamicKeys) {
      errors[pathToKey([...path, key])] = 'Dynamic idShort keys are not editable for this field';
    }
    return errors;
  }

  if (allowedIdShort.length > 0) {
    const patterns = allowedIdShort.map((value) => allowedIdShortPattern(value));
    for (const key of dynamicKeys) {
      if (!patterns.some((pattern) => pattern.test(key))) {
        errors[pathToKey([...path, key])] = `idShort '${key}' is not allowed`;
      }
    }
  }

  const namingPattern = namingPatternFromRule(namingRule);
  if (namingPattern) {
    for (const key of dynamicKeys) {
      if (!namingPattern.test(key)) {
        errors[pathToKey([...path, key])] = `idShort '${key}' violates naming rule '${namingRule}'`;
      }
    }
  }

  return errors;
}

function allowedIdShortPattern(template: string): RegExp {
  const escaped = template.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
  const withNumericPlaceholders = escaped.replace(/\\\{(0+)\\\}/g, (_match, zeros: string) => {
    return `\\d{${zeros.length}}`;
  });
  return new RegExp(`^${withNumericPlaceholders}$`);
}

function namingPatternFromRule(rule: string | undefined): RegExp | null {
  if (!rule) return null;
  const normalized = rule.trim();
  if (!normalized || normalized.toLowerCase() === 'dynamic') return null;

  if (normalized.toLowerCase() === 'idshort') {
    // AAS idShort compatible (simplified): starts with a letter, then alnum/underscore.
    return /^[A-Za-z][A-Za-z0-9_]*$/;
  }

  if (normalized.startsWith('regex:')) {
    const raw = normalized.slice('regex:'.length).trim();
    try {
      return new RegExp(raw);
    } catch {
      return null;
    }
  }

  try {
    return new RegExp(normalized);
  } catch {
    return null;
  }
}

function getSchemaRange(schema: UISchema): { min?: number; max?: number } | undefined {
  const raw = schema['x-allowed-range'];
  if (!raw) return undefined;
  const match = raw.match(/^\s*([+-]?\d+(?:\.\d+)?)\s*\.\.\s*([+-]?\d+(?:\.\d+)?)\s*$/);
  if (!match) return undefined;
  return { min: Number(match[1]), max: Number(match[2]) };
}
