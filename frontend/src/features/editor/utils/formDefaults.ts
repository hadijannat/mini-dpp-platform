import type { UISchema } from '../types/uiSchema';

export function defaultValueForSchema(schema?: UISchema): unknown {
  if (!schema) return '';
  if (schema.default !== undefined) return schema.default;
  if (schema.enum && schema.enum.length > 0) return schema.enum[0];
  if (schema['x-multi-language']) return {};
  if (schema['x-range']) return { min: null, max: null };
  if (schema['x-file-upload']) return { contentType: '', value: '' };
  if (schema['x-reference']) return { type: 'ModelReference', keys: [] };
  if (schema['x-entity']) {
    return { entityType: 'SelfManagedEntity', globalAssetId: '', statements: {} };
  }
  if (schema['x-relationship']) return { first: null, second: null };
  if (schema['x-annotated-relationship']) {
    return { first: null, second: null, annotations: {} };
  }
  switch (schema.type) {
    case 'object':
      return {};
    case 'array':
      return [];
    case 'number':
    case 'integer':
      return null;
    case 'boolean':
      return false;
    default:
      return '';
  }
}
