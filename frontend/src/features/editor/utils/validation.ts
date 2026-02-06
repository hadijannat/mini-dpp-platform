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
    if (schema.minimum !== undefined && data < schema.minimum) {
      errors[pathKey] = `Must be ≥ ${schema.minimum}`;
    }
    if (schema.maximum !== undefined && data > schema.maximum) {
      errors[pathKey] = `Must be ≤ ${schema.maximum}`;
    }
  }

  if (schema['x-range'] && data && typeof data === 'object' && !Array.isArray(data)) {
    const range = data as { min?: number | null; max?: number | null };
    const min = typeof range.min === 'number' ? range.min : null;
    const max = typeof range.max === 'number' ? range.max : null;

    if (min !== null && schema.minimum !== undefined && min < schema.minimum) {
      errors[pathKey] = `Min must be ≥ ${schema.minimum}`;
    }
    if (max !== null && schema.maximum !== undefined && max > schema.maximum) {
      errors[pathKey] = `Max must be ≤ ${schema.maximum}`;
    }
    if (min !== null && max !== null && min > max) {
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
