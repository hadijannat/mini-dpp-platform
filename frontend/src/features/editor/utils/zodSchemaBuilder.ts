import { z, type ZodTypeAny } from 'zod';
import type { DefinitionNode, TemplateDefinition } from '../types/definition';
import type { UISchema } from '../types/uiSchema';

const DEFAULT_MIME_PATTERN =
  '^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$';

/** AAS Reference schema matching BaSyx model: {type, keys: [{type, value}]} */
const aasReferenceSchema = z.object({
  type: z.string().optional(),
  keys: z.array(z.object({
    type: z.string(),
    value: z.string(),
  })).optional(),
}).nullable();

/**
 * Builds a Zod schema from a DefinitionNode tree and UISchema.
 * Used with zodResolver to power React Hook Form validation.
 */
export function buildZodSchema(
  definition?: TemplateDefinition,
  uiSchema?: UISchema,
): ZodTypeAny {
  const elements = definition?.submodel?.elements;
  if (elements && elements.length > 0) {
    return buildFromDefinition(elements, uiSchema);
  }
  if (uiSchema) {
    return buildFromUISchema(uiSchema);
  }
  return z.record(z.string(), z.unknown());
}

function buildFromDefinition(
  nodes: DefinitionNode[],
  rootSchema?: UISchema,
): ZodTypeAny {
  const shape: Record<string, ZodTypeAny> = {};
  for (const node of nodes) {
    const key = node.idShort;
    if (!key) continue;
    const fieldSchema = rootSchema?.properties?.[key];
    shape[key] = buildNodeSchema(node, fieldSchema);
  }
  return z.object(shape).passthrough();
}

function buildNodeSchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  switch (node.modelType) {
    case 'SubmodelElementCollection':
      return buildCollectionSchema(node, schema);
    case 'SubmodelElementList':
      return buildListSchema(node, schema);
    case 'MultiLanguageProperty':
      return buildMultiLangSchema(node, schema);
    case 'Range':
      return buildRangeSchema();
    case 'File':
      return buildFileSchema(schema);
    case 'ReferenceElement':
      return z.object({
        type: z.string(),
        keys: z.array(z.object({ type: z.string(), value: z.string() }).passthrough()),
      }).passthrough();
    case 'Entity':
      return buildEntitySchema(node, schema);
    case 'RelationshipElement':
      return z.object({ first: aasReferenceSchema, second: aasReferenceSchema });
    case 'AnnotatedRelationshipElement':
      return buildAnnotatedRelationshipSchema(node, schema);
    case 'Property':
      return buildPropertySchema(node, schema);
    default:
      return z.unknown();
  }
}

function buildPropertySchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  const valueType = node.valueType;
  const range = normalizeRange(node.smt?.allowed_range);

  // Integer types
  if (valueType === 'xs:integer' || valueType === 'xs:long' || valueType === 'xs:short' || valueType === 'xs:int') {
    let s = z.number().int();
    if (range?.min !== undefined) s = s.min(range.min);
    if (range?.max !== undefined) s = s.max(range.max);
    if (schema?.minimum !== undefined) s = s.min(schema.minimum);
    if (schema?.maximum !== undefined) s = s.max(schema.maximum);
    return s.nullable();
  }

  // Decimal types
  if (valueType === 'xs:decimal' || valueType === 'xs:double' || valueType === 'xs:float') {
    let s = z.number();
    if (range?.min !== undefined) s = s.min(range.min);
    if (range?.max !== undefined) s = s.max(range.max);
    if (schema?.minimum !== undefined) s = s.min(schema.minimum);
    if (schema?.maximum !== undefined) s = s.max(schema.maximum);
    return s.nullable();
  }

  // Boolean
  if (valueType === 'xs:boolean' || schema?.type === 'boolean') {
    return z.boolean();
  }

  // Enum from form_choices or schema
  const choices = node.smt?.form_choices ?? schema?.enum;
  if (choices && choices.length > 0) {
    return z.enum(choices as [string, ...string[]]);
  }

  // Date / dateTime types — validate ISO format
  if (valueType === 'xs:date') {
    return z.string().refine(
      (v) => v === '' || /^\d{4}-\d{2}-\d{2}$/.test(v),
      { message: 'Expected date format YYYY-MM-DD' },
    ).nullable();
  }
  if (valueType === 'xs:dateTime') {
    return z.string().refine(
      (v) => v === '' || /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v),
      { message: 'Expected dateTime format YYYY-MM-DDThh:mm' },
    ).nullable();
  }

  // String with optional pattern
  let strSchema = z.string();
  const regex = node.smt?.allowed_value_regex;
  if (regex) {
    try {
      strSchema = strSchema.regex(new RegExp(regex), 'Invalid format');
    } catch {
      // Ignore invalid regex from upstream templates
    }
  }
  if (schema?.pattern) {
    try {
      strSchema = strSchema.regex(new RegExp(schema.pattern), 'Invalid format');
    } catch {
      // Ignore invalid patterns
    }
  }

  return strSchema.nullable();
}

function normalizeRange(
  range?: { min?: number; max?: number; raw?: string | null } | null,
): { min?: number; max?: number } | undefined {
  if (!range) return undefined;
  if (range.min !== undefined || range.max !== undefined) {
    return { min: range.min, max: range.max };
  }
  if (!range.raw) return undefined;
  const match = range.raw.match(/^\s*([+-]?\d+(?:\.\d+)?)\s*\.\.\s*([+-]?\d+(?:\.\d+)?)\s*$/);
  if (!match) return undefined;
  return { min: Number(match[1]), max: Number(match[2]) };
}

function buildCollectionSchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  const children = node.children ?? [];
  if (children.length === 0) {
    return schema?.properties
      ? buildFromUISchema(schema)
      : z.record(z.string(), z.unknown());
  }
  const shape: Record<string, ZodTypeAny> = {};
  for (const child of children) {
    const key = child.idShort;
    if (!key) continue;
    const childSchema = schema?.properties?.[key];
    shape[key] = buildNodeSchema(child, childSchema);
  }
  return z.object(shape).passthrough();
}

function buildListSchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  const itemDef = node.items;
  const itemSchema = schema?.items;
  const itemZod = itemDef
    ? buildNodeSchema(itemDef, itemSchema)
    : itemSchema
      ? buildFromUISchema(itemSchema)
      : z.unknown();

  let arr = z.array(itemZod);

  // Cardinality-based min/max
  const cardinality = node.smt?.cardinality;
  if (cardinality === 'OneToMany' || cardinality === 'One') {
    arr = arr.min(1);
  }
  if (schema?.minItems !== undefined) {
    arr = arr.min(schema.minItems);
  }
  return arr;
}

function buildMultiLangSchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  const requiredLangs = node.smt?.required_lang ?? schema?.['x-required-languages'] ?? [];
  let s = z.record(z.string(), z.string());
  if (requiredLangs.length > 0) {
    s = s.refine(
      (obj) => requiredLangs.every((lang) => obj[lang] && obj[lang].trim() !== ''),
      { message: `Missing required languages: ${requiredLangs.join(', ')}` },
    ) as unknown as typeof s;
  }
  return s;
}

function buildRangeSchema(): ZodTypeAny {
  return z
    .object({
      min: z.number().nullable(),
      max: z.number().nullable(),
    })
    .refine(
      (data) => {
        if (data.min !== null && data.max !== null) return data.min <= data.max;
        return true;
      },
      { message: 'Min cannot exceed max' },
    );
}

function buildFileSchema(schema?: UISchema): ZodTypeAny {
  const contentTypePattern =
    schema?.properties?.contentType?.pattern ??
    schema?.['x-content-type-pattern'] ??
    DEFAULT_MIME_PATTERN;
  let contentType: ZodTypeAny = z.string();
  try {
    const pattern = new RegExp(contentTypePattern);
    contentType = contentType.refine(
      (value) => value.trim() === '' || pattern.test(value.trim()),
      'Invalid MIME type',
    );
  } catch {
    // Ignore invalid patterns from upstream contracts.
  }
  return z.object({ contentType, value: z.string() }).passthrough();
}

function buildEntitySchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  const statementsShape: Record<string, ZodTypeAny> = {};
  for (const stmt of node.statements ?? []) {
    if (stmt.idShort) {
      const stmtSchema = schema?.properties?.statements?.properties?.[stmt.idShort];
      statementsShape[stmt.idShort] = buildNodeSchema(stmt, stmtSchema);
    }
  }
  return z.object({
    entityType: z.string(),
    globalAssetId: z.string(),
    statements: Object.keys(statementsShape).length > 0
      ? z.object(statementsShape).passthrough()
      : z.record(z.string(), z.unknown()),
  }).passthrough();
}

function buildAnnotatedRelationshipSchema(node: DefinitionNode, schema?: UISchema): ZodTypeAny {
  const annotationsShape: Record<string, ZodTypeAny> = {};
  for (const ann of node.annotations ?? []) {
    if (ann.idShort) {
      const annSchema = schema?.properties?.annotations?.properties?.[ann.idShort];
      annotationsShape[ann.idShort] = buildNodeSchema(ann, annSchema);
    }
  }
  return z.object({
    first: aasReferenceSchema,
    second: aasReferenceSchema,
    annotations: Object.keys(annotationsShape).length > 0
      ? z.object(annotationsShape).passthrough()
      : z.record(z.string(), z.unknown()),
  });
}

/** Fallback: build Zod schema from UISchema alone */
function buildFromUISchema(schema: UISchema): ZodTypeAny {
  if (schema['x-multi-language']) return z.record(z.string(), z.string());
  if (schema['x-range']) return buildRangeSchema();
  if (schema['x-file-upload']) return buildFileSchema(schema);
  if (schema['x-reference']) return z.object({ type: z.string(), keys: z.array(z.unknown()) });
  if (schema['x-readonly'] || schema['x-blob']) return z.unknown();

  if (schema.enum && schema.enum.length > 0) {
    return z.enum(schema.enum as [string, ...string[]]);
  }

  switch (schema.type) {
    case 'object': {
      if (!schema.properties) return z.record(z.string(), z.unknown());
      const shape: Record<string, ZodTypeAny> = {};
      for (const [key, propSchema] of Object.entries(schema.properties)) {
        shape[key] = buildFromUISchema(propSchema);
      }
      return z.object(shape).passthrough();
    }
    case 'array': {
      const itemSchema = schema.items ? buildFromUISchema(schema.items) : z.unknown();
      let arr = z.array(itemSchema);
      if (schema.minItems !== undefined) arr = arr.min(schema.minItems);
      return arr;
    }
    case 'number':
    case 'integer': {
      let num = schema.type === 'integer' ? z.number().int() : z.number();
      if (schema.minimum !== undefined) num = num.min(schema.minimum);
      if (schema.maximum !== undefined) num = num.max(schema.maximum);
      return num.nullable();
    }
    case 'boolean':
      return z.boolean();
    default: {
      let str = z.string();
      if (schema.pattern) {
        try {
          str = str.regex(new RegExp(schema.pattern), 'Invalid format');
        } catch {
          // Ignore
        }
      }
      return str;
    }
  }
}
