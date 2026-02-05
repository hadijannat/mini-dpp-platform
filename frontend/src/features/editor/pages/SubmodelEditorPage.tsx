import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { buildSubmodelData } from '@/features/editor/utils/submodelData';

type TemplateResponse = {
  semantic_id: string;
};

type LangStringSet = Record<string, string>;

type SmtQualifiers = {
  cardinality?: string | null;
  form_title?: string | null;
  form_info?: string | null;
  form_url?: string | null;
  access_mode?: string | null;
  required_lang?: string[];
  either_or?: string | null;
};

type DefinitionNode = {
  path?: string;
  idShort?: string;
  modelType: string;
  semanticId?: string | null;
  displayName?: LangStringSet;
  description?: LangStringSet;
  smt?: SmtQualifiers;
  children?: DefinitionNode[];
  items?: DefinitionNode | null;
};

type TemplateDefinition = {
  template_key?: string;
  semantic_id?: string | null;
  submodel?: {
    idShort?: string;
    elements?: DefinitionNode[];
  };
};

type SubmodelDefinitionResponse = {
  dpp_id: string;
  template_key: string;
  revision_id: string;
  revision_no: number;
  state: string;
  definition: TemplateDefinition;
};

type UISchema = {
  type?: string;
  title?: string;
  description?: string;
  properties?: Record<string, UISchema>;
  items?: UISchema;
  required?: string[];
  minItems?: number;
  minimum?: number;
  maximum?: number;
  pattern?: string;
  enum?: string[];
  format?: string;
  default?: unknown;
  readOnly?: boolean;
  writeOnly?: boolean;
  additionalProperties?: UISchema;
  'x-multi-language'?: boolean;
  'x-range'?: boolean;
  'x-file-upload'?: boolean;
  'x-reference'?: boolean;
  'x-entity'?: boolean;
  'x-relationship'?: boolean;
  'x-annotated-relationship'?: boolean;
  'x-readonly'?: boolean;
  'x-blob'?: boolean;
  'x-form-url'?: string;
  'x-required-languages'?: string[];
};

type FormData = Record<string, unknown>;

async function fetchDpp(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
  }
  return response.json();
}

async function fetchTemplate(templateKey: string, token?: string) {
  const response = await apiFetch(`/api/v1/templates/${templateKey}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch template'));
  }
  return response.json();
}

async function fetchTemplateSchema(templateKey: string, token?: string) {
  const response = await apiFetch(`/api/v1/templates/${templateKey}/schema`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch template schema'));
  }
  return response.json();
}

async function fetchSubmodelDefinition(dppId: string, templateKey: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}/submodels/${templateKey}/definition`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch submodel definition'));
  }
  return response.json();
}

async function updateSubmodel(
  dppId: string,
  templateKey: string,
  data: Record<string, unknown>,
  token?: string,
  rebuildFromTemplate = false,
) {
  const response = await tenantApiFetch(`/dpps/${dppId}/submodel`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_key: templateKey,
      data,
      rebuild_from_template: rebuildFromTemplate,
    }),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to update submodel'));
  }
  return response.json();
}

function extractSemanticId(submodel: any): string | null {
  const semanticId = submodel?.semanticId;
  if (semanticId && Array.isArray(semanticId.keys) && semanticId.keys[0]?.value) {
    return String(semanticId.keys[0].value);
  }
  return null;
}

function pathToKey(path: Array<string | number>): string {
  return path.map(String).join('.');
}

function getValueAtPath(data: unknown, path: Array<string | number>): unknown {
  let current: any = data;
  for (const segment of path) {
    if (current == null) return undefined;
    current = current[segment as any];
  }
  return current;
}

function setValueAtPath<T>(data: T, path: Array<string | number>, value: unknown): T {
  if (path.length === 0) return data;
  const [head, ...tail] = path;
  const key = typeof head === 'number' ? head : String(head);
  const clone: any = Array.isArray(data) ? [...(data as any[])] : { ...(data as any) };
  if (tail.length === 0) {
    clone[key] = value;
    return clone as T;
  }
  const existing = clone[key];
  const nextContainer =
    existing && typeof existing === 'object'
      ? existing
      : typeof tail[0] === 'number'
        ? []
        : {};
  clone[key] = setValueAtPath(nextContainer, tail, value);
  return clone as T;
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((item, idx) => deepEqual(item, b[idx]));
  }
  if (typeof a === 'object' && typeof b === 'object') {
    const aObj = a as Record<string, unknown>;
    const bObj = b as Record<string, unknown>;
    const aKeys = Object.keys(aObj);
    const bKeys = Object.keys(bObj);
    if (aKeys.length !== bKeys.length) return false;
    return aKeys.every((key) => deepEqual(aObj[key], bObj[key]));
  }
  return false;
}

function defaultValueForSchema(schema?: UISchema): unknown {
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

function definitionPathToSegments(path: string, rootIdShort?: string): Array<string | '[]'> {
  const parts = path.split('/').filter(Boolean);
  const trimmed = rootIdShort && parts[0] === rootIdShort ? parts.slice(1) : parts;
  const segments: Array<string | '[]'> = [];
  for (const part of trimmed) {
    if (part.endsWith('[]')) {
      segments.push(part.slice(0, -2));
      segments.push('[]');
    } else {
      segments.push(part);
    }
  }
  return segments;
}

function getValuesAtPattern(data: unknown, segments: Array<string | '[]'>): unknown[] {
  let current: unknown[] = [data];
  for (const segment of segments) {
    const next: unknown[] = [];
    if (segment === '[]') {
      for (const value of current) {
        if (Array.isArray(value)) {
          next.push(...value);
        }
      }
    } else {
      for (const value of current) {
        if (Array.isArray(value)) {
          value.forEach((entry) => {
            if (entry && typeof entry === 'object') {
              next.push((entry as Record<string, unknown>)[segment]);
            }
          });
        } else if (value && typeof value === 'object') {
          next.push((value as Record<string, unknown>)[segment]);
        }
      }
    }
    current = next;
    if (current.length === 0) break;
  }
  return current;
}

function validateReadOnly(
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
    const obj = data && typeof data === 'object' && !Array.isArray(data)
      ? (data as Record<string, unknown>)
      : {};
    const baseObj = baseline && typeof baseline === 'object' && !Array.isArray(baseline)
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

function validateEitherOr(
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
    (node as any).statements?.forEach?.(visit);
    (node as any).annotations?.forEach?.(visit);
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

function validateSchema(
  schema: UISchema | undefined,
  data: unknown,
  path: Array<string | number> = [],
): Record<string, string> {
  if (!schema) return {};
  const errors: Record<string, string> = {};
  const pathKey = pathToKey(path);

  if (schema.enum && data !== undefined && data !== null && data !== '') {
    if (!schema.enum.includes(data as any)) {
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

function pickLangValue(value?: LangStringSet): string | undefined {
  if (!value) return undefined;
  if (value.en) return value.en;
  const first = Object.values(value)[0];
  return first ?? undefined;
}

function getNodeLabel(node: DefinitionNode, fallback: string) {
  return (
    node.smt?.form_title ??
    pickLangValue(node.displayName) ??
    node.idShort ??
    fallback
  );
}

function getNodeDescription(node: DefinitionNode) {
  return node.smt?.form_info ?? pickLangValue(node.description);
}

function isNodeRequired(node: DefinitionNode) {
  return node.smt?.cardinality === 'One' || node.smt?.cardinality === 'OneToMany';
}

function getSchemaAtPath(schema: UISchema | undefined, path: Array<string | number>): UISchema | undefined {
  let current: UISchema | undefined = schema;
  for (const segment of path) {
    if (!current) return undefined;
    if (typeof segment === 'number') {
      current = current.items;
      continue;
    }
    if (current.type === 'object' && current.properties) {
      current = current.properties[segment];
      continue;
    }
    if (current.type === 'array') {
      current = current.items;
      continue;
    }
    return current;
  }
  return current;
}

export default function SubmodelEditorPage() {
  const { dppId, templateKey } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const queryClient = useQueryClient();

  const { data: dpp, isLoading: loadingDpp } = useQuery({
    queryKey: ['dpp', tenantSlug, dppId],
    queryFn: () => fetchDpp(dppId!, token),
    enabled: !!dppId,
  });

  const { data: template, isLoading: loadingTemplate } = useQuery<TemplateResponse>({
    queryKey: ['template', templateKey],
    queryFn: () => fetchTemplate(templateKey!, token),
    enabled: !!templateKey,
  });

  const { data: schema, isLoading: loadingSchema } = useQuery({
    queryKey: ['template-schema', templateKey],
    queryFn: () => fetchTemplateSchema(templateKey!, token),
    enabled: !!templateKey,
  });

  const { data: definition, isLoading: loadingDefinition } = useQuery<SubmodelDefinitionResponse>({
    queryKey: ['submodel-definition', tenantSlug, dppId, templateKey],
    queryFn: () => fetchSubmodelDefinition(dppId!, templateKey!, token),
    enabled: !!templateKey && !!dppId,
  });

  const submodel = useMemo(() => {
    if (!dpp) return null;
    const submodels = dpp.aas_environment?.submodels || [];
    const semanticId = template?.semantic_id;
    if (semanticId) {
      const bySemantic = submodels.find((sm: any) => extractSemanticId(sm) === semanticId);
      if (bySemantic) return bySemantic;
    }
    const definitionIdShort = definition?.definition?.submodel?.idShort;
    if (definitionIdShort) {
      const byIdShort = submodels.find((sm: any) => sm?.idShort === definitionIdShort);
      if (byIdShort) return byIdShort;
    }
    return null;
  }, [dpp, template?.semantic_id, definition?.definition?.submodel?.idShort]);

  const initialData = useMemo(() => {
    if (!submodel) return {};
    return buildSubmodelData(submodel);
  }, [submodel]);

  const [rawJson, setRawJson] = useState('');
  const [formData, setFormData] = useState<FormData>({});
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [activeView, setActiveView] = useState<'form' | 'json'>('form');
  const [hasEdited, setHasEdited] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: (payload: { data: Record<string, unknown>; rebuildFromTemplate?: boolean }) =>
      updateSubmodel(
        dppId!,
        templateKey!,
        payload.data,
        token,
        payload.rebuildFromTemplate ?? false,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpp', tenantSlug, dppId] });
      queryClient.invalidateQueries({
        queryKey: ['submodel-definition', tenantSlug, dppId, templateKey],
      });
      navigate(`/console/dpps/${dppId}`);
    },
  });

  const updateError = updateMutation.isError ? (updateMutation.error as Error) : null;
  const sessionExpired = Boolean(updateError?.message?.includes('Session expired'));

  useEffect(() => {
    if (!hasEdited) {
      setRawJson(JSON.stringify(initialData, null, 2));
      setFormData(initialData as FormData);
      setFormErrors({});
    }
  }, [initialData, hasEdited]);

  // Reset edit state when navigating to a different DPP or template
  useEffect(() => {
    setHasEdited(false);
  }, [dppId, templateKey]);

  const handleViewChange = (view: 'form' | 'json') => {
    if (view === activeView) return;
    if (view === 'form') {
      try {
        const parsed = JSON.parse(rawJson || '{}') as Record<string, unknown>;
        setFormData(parsed);
        setFormErrors({});
        setError(null);
        setActiveView('form');
        setHasEdited(true);
      } catch {
        setError('Invalid JSON. Fix it before switching to form view.');
      }
    } else {
      setRawJson(JSON.stringify(formData, null, 2));
      setError(null);
      setActiveView('json');
    }
  };

  const updateValue = (path: Array<string | number>, value: unknown) => {
    const key = pathToKey(path);
    setFormData((prev) => {
      const next = setValueAtPath(prev, path, value);
      if (activeView === 'form') {
        setRawJson(JSON.stringify(next, null, 2));
      }
      return next;
    });
    setHasEdited(true);
    setFormErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = () => {
    if (activeView === 'json') {
      try {
        const parsed = JSON.parse(rawJson) as Record<string, unknown>;
        const schemaErrors = validateSchema(schema?.schema as UISchema | undefined, parsed);
        const readOnlyErrors = validateReadOnly(
          schema?.schema as UISchema | undefined,
          parsed,
          initialData,
        );
        const eitherOrErrors = validateEitherOr(templateDefinition, parsed);
        const mergedErrors = { ...schemaErrors, ...readOnlyErrors };
        if (Object.keys(mergedErrors).length > 0 || eitherOrErrors.length > 0) {
          setFormErrors(mergedErrors);
          setError(
            eitherOrErrors.length > 0
              ? eitherOrErrors.join(' ')
              : 'Please resolve the highlighted validation errors.'
          );
          return;
        }
        setError(null);
        updateMutation.mutate({ data: parsed });
      } catch {
        setError('Invalid JSON. Please fix formatting before saving.');
      }
      return;
    }

    const schemaErrors = validateSchema(schema?.schema as UISchema | undefined, formData);
    const readOnlyErrors = validateReadOnly(
      schema?.schema as UISchema | undefined,
      formData,
      initialData,
    );
    const eitherOrErrors = validateEitherOr(templateDefinition, formData);
    const mergedErrors = { ...schemaErrors, ...readOnlyErrors };
    if (Object.keys(mergedErrors).length > 0 || eitherOrErrors.length > 0) {
      setFormErrors(mergedErrors);
      setError(
        eitherOrErrors.length > 0
          ? eitherOrErrors.join(' ')
          : 'Please resolve the highlighted validation errors.'
      );
      return;
    }

    setError(null);
    updateMutation.mutate({ data: formData });
  };

  const isLoading = loadingDpp || loadingTemplate || loadingSchema || loadingDefinition;
  const uiSchema = schema?.schema as UISchema | undefined;
  const templateDefinition = definition?.definition as TemplateDefinition | undefined;

  function renderObjectFields(objectSchema: UISchema, basePath: Array<string | number>) {
    const properties = objectSchema.properties ?? {};
    return (
      <div className="space-y-4">
        {Object.entries(properties).map(([key, fieldSchema]) => {
          const required = objectSchema.required?.includes(key) ?? false;
          return renderField(fieldSchema, [...basePath, key], key, required);
        })}
      </div>
    );
  }

function renderField(
    fieldSchema: UISchema,
    path: Array<string | number>,
    label: string,
    required: boolean,
    descriptionOverride?: string,
    forceReadOnly?: boolean,
    formUrlOverride?: string,
    requiredLanguagesOverride?: string[],
  ) {
    const fieldKey = pathToKey(path);
    const fieldError = formErrors[fieldKey];
    const value = getValueAtPath(formData, path);
    const description = descriptionOverride ?? fieldSchema.description;
    const readOnly = Boolean(forceReadOnly || fieldSchema['x-readonly'] || fieldSchema['x-blob']);
    const formUrl = formUrlOverride ?? fieldSchema['x-form-url'];
    const requiredLanguages =
      requiredLanguagesOverride ?? fieldSchema['x-required-languages'] ?? [];

    if (readOnly) {
      return (
        <div key={fieldKey} className="border rounded-md p-4 bg-gray-50">
          <p className="text-sm font-medium text-gray-800">
            {fieldSchema.title || label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          <pre className="mt-3 text-xs text-gray-600 whitespace-pre-wrap">
            {value === undefined || value === null || value === ''
              ? 'Read-only'
              : JSON.stringify(value, null, 2)}
          </pre>
        </div>
      );
    }

    if (fieldSchema['x-multi-language']) {
      const languages = Array.from(
        new Set([...(requiredLanguages || []), 'en', 'de', 'fr', 'es', 'it']),
      );
      const current =
        value && typeof value === 'object' && !Array.isArray(value)
          ? (value as Record<string, string>)
          : {};
      return (
        <div key={fieldKey} className="border rounded-md p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-800">
              {fieldSchema.title || label}
              {required && <span className="text-red-500 ml-1">*</span>}
            </p>
          </div>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          {requiredLanguages.length > 0 && (
            <p className="text-xs text-gray-400 mt-1">
              Required languages: {requiredLanguages.join(', ')}
            </p>
          )}
          {formUrl && (
            <a
              className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
              href={formUrl}
              target="_blank"
              rel="noreferrer"
            >
              Learn more
            </a>
          )}
          <div className="mt-3 space-y-2">
            {languages.map((lang) => (
              <div key={`${fieldKey}-${lang}`} className="flex items-center gap-2">
                <span className="w-10 text-xs font-medium uppercase text-gray-500">{lang}</span>
                <input
                  type="text"
                  className="flex-1 border rounded-md px-3 py-2 text-sm"
                  value={current[lang] ?? ''}
                  onChange={(event) => {
                    updateValue(path, { ...current, [lang]: event.target.value });
                  }}
                />
              </div>
            ))}
          </div>
          {fieldError && <p className="text-xs text-red-600 mt-2">{fieldError}</p>}
        </div>
      );
    }

    if (fieldSchema['x-reference']) {
      const current =
        value && typeof value === 'object' && !Array.isArray(value)
          ? (value as { type?: string; keys?: Array<{ type?: string; value?: string }> })
          : { type: 'ModelReference', keys: [] };
      const keys = Array.isArray(current.keys) ? current.keys : [];

      return (
        <div key={fieldKey} className="border rounded-md p-4">
          <p className="text-sm font-medium text-gray-800">
            {fieldSchema.title || label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          {formUrl && (
            <a
              className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
              href={formUrl}
              target="_blank"
              rel="noreferrer"
            >
              Learn more
            </a>
          )}
          <div className="mt-3 space-y-3">
            <div>
              <label className="text-xs text-gray-500">Reference Type</label>
              <select
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                value={current.type ?? 'ModelReference'}
                onChange={(event) => {
                  updateValue(path, { ...current, type: event.target.value, keys });
                }}
              >
                {(fieldSchema.properties?.type?.enum ?? ['ModelReference', 'ExternalReference']).map(
                  (option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  )
                )}
              </select>
            </div>
            <div className="space-y-2">
              {keys.map((key, index) => (
                <div key={`${fieldKey}-key-${index}`} className="flex items-center gap-2">
                  <input
                    type="text"
                    className="w-32 border rounded-md px-2 py-1 text-sm"
                    placeholder="Type"
                    value={key?.type ?? ''}
                    onChange={(event) => {
                      const next = keys.map((entry, idx) =>
                        idx === index ? { ...entry, type: event.target.value } : entry
                      );
                      updateValue(path, { ...current, keys: next });
                    }}
                  />
                  <input
                    type="text"
                    className="flex-1 border rounded-md px-2 py-1 text-sm"
                    placeholder="Value"
                    value={key?.value ?? ''}
                    onChange={(event) => {
                      const next = keys.map((entry, idx) =>
                        idx === index ? { ...entry, value: event.target.value } : entry
                      );
                      updateValue(path, { ...current, keys: next });
                    }}
                  />
                  <button
                    type="button"
                    className="text-xs text-red-500 hover:text-red-600"
                    onClick={() => {
                      const next = keys.filter((_, idx) => idx !== index);
                      updateValue(path, { ...current, keys: next });
                    }}
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="text-sm text-primary-600 hover:text-primary-700"
                onClick={() => {
                  const next = [...keys, { type: '', value: '' }];
                  updateValue(path, { ...current, keys: next });
                }}
              >
                Add key
              </button>
            </div>
          </div>
          {fieldError && <p className="text-xs text-red-600 mt-2">{fieldError}</p>}
        </div>
      );
    }

    if (fieldSchema['x-range']) {
      const current =
        value && typeof value === 'object' && !Array.isArray(value)
          ? (value as Record<string, number | null>)
          : { min: null, max: null };
      return (
        <div key={fieldKey} className="border rounded-md p-4">
          <p className="text-sm font-medium text-gray-800">
            {fieldSchema.title || label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          {formUrl && (
            <a
              className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
              href={formUrl}
              target="_blank"
              rel="noreferrer"
            >
              Learn more
            </a>
          )}
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs text-gray-500">Min</label>
              <input
                type="number"
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={current.min ?? ''}
                onChange={(event) => {
                  const next = event.target.value === '' ? null : Number(event.target.value);
                  updateValue(path, { ...current, min: next });
                }}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">Max</label>
              <input
                type="number"
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={current.max ?? ''}
                onChange={(event) => {
                  const next = event.target.value === '' ? null : Number(event.target.value);
                  updateValue(path, { ...current, max: next });
                }}
              />
            </div>
          </div>
          {fieldError && <p className="text-xs text-red-600 mt-2">{fieldError}</p>}
        </div>
      );
    }

    if (fieldSchema['x-file-upload']) {
      const current =
        value && typeof value === 'object' && !Array.isArray(value)
          ? (value as Record<string, string>)
          : { contentType: '', value: '' };
      return (
        <div key={fieldKey} className="border rounded-md p-4">
          <p className="text-sm font-medium text-gray-800">
            {fieldSchema.title || label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          {formUrl && (
            <a
              className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
              href={formUrl}
              target="_blank"
              rel="noreferrer"
            >
              Learn more
            </a>
          )}
          <div className="mt-3 space-y-2">
            <input
              type="text"
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="Content type (e.g. application/pdf)"
              value={current.contentType ?? ''}
              onChange={(event) => updateValue(path, { ...current, contentType: event.target.value })}
            />
            <input
              type="text"
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="File URL or reference"
              value={current.value ?? ''}
              onChange={(event) => updateValue(path, { ...current, value: event.target.value })}
            />
          </div>
          {fieldError && <p className="text-xs text-red-600 mt-2">{fieldError}</p>}
        </div>
      );
    }

    if (fieldSchema.type === 'object' && fieldSchema.properties) {
      return (
        <div key={fieldKey} className="border rounded-md p-4">
          <p className="text-sm font-medium text-gray-800">
            {fieldSchema.title || label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          {formUrl && (
            <a
              className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
              href={formUrl}
              target="_blank"
              rel="noreferrer"
            >
              Learn more
            </a>
          )}
          <div className="mt-4">
            {renderObjectFields(fieldSchema, path)}
          </div>
        </div>
      );
    }

    if (fieldSchema.type === 'array') {
      const itemsSchema = fieldSchema.items;
      const list = Array.isArray(value) ? value : [];
      return (
        <div key={fieldKey} className="border rounded-md p-4">
          <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-gray-800">
            {fieldSchema.title || label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
            <button
              type="button"
              className="text-sm text-primary-600 hover:text-primary-700"
              onClick={() => {
                const next = [...list, defaultValueForSchema(itemsSchema)];
                updateValue(path, next);
              }}
            >
              Add item
            </button>
          </div>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          {formUrl && (
            <a
              className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
              href={formUrl}
              target="_blank"
              rel="noreferrer"
            >
              Learn more
            </a>
          )}
          <div className="mt-4 space-y-3">
            {list.length === 0 && (
              <p className="text-xs text-gray-400">No items yet.</p>
            )}
            {list.map((_, index) => {
              const itemPath = [...path, index];
              const itemKey = pathToKey(itemPath);
              return (
                <div key={itemKey} className="border rounded-md p-3">
                  <div className="flex justify-end">
                    <button
                      type="button"
                      className="text-xs text-red-500 hover:text-red-600"
                      onClick={() => {
                        const next = list.filter((_, idx) => idx !== index);
                        updateValue(path, next);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                  <div className="mt-2">
                    {renderField(
                      itemsSchema || { type: 'string' },
                      itemPath,
                      `${label} ${index + 1}`,
                      false
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {fieldError && <p className="text-xs text-red-600 mt-2">{fieldError}</p>}
        </div>
      );
    }

    if (fieldSchema.type === 'boolean') {
      return (
        <div key={fieldKey} className="flex items-center gap-3">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={Boolean(value)}
            onChange={(event) => updateValue(path, event.target.checked)}
          />
          <div>
            <span className="text-sm text-gray-800">
              {fieldSchema.title || label}
              {required && <span className="text-red-500 ml-1">*</span>}
            </span>
            {description && <p className="text-xs text-gray-500">{description}</p>}
          </div>
          {fieldError && <p className="text-xs text-red-600">{fieldError}</p>}
        </div>
      );
    }

    if (fieldSchema.enum && fieldSchema.enum.length > 0) {
      return (
        <div key={fieldKey} className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          {fieldSchema.title || label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {description && <p className="text-xs text-gray-500">{description}</p>}
        {formUrl && (
          <a
            className="text-xs text-primary-600 hover:text-primary-700 inline-block mt-1"
            href={formUrl}
            target="_blank"
            rel="noreferrer"
          >
            Learn more
          </a>
        )}
          <select
            className={`w-full border rounded-md px-3 py-2 text-sm ${
              fieldError ? 'border-red-500' : ''
            }`}
            value={(value as string) ?? ''}
            onChange={(event) => updateValue(path, event.target.value)}
          >
            {fieldSchema.enum.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {fieldError && <p className="text-xs text-red-600">{fieldError}</p>}
        </div>
      );
    }

    const isNumber = fieldSchema.type === 'number' || fieldSchema.type === 'integer';
    let inputType = isNumber ? 'number' : 'text';
    if (fieldSchema.format === 'date') inputType = 'date';
    if (fieldSchema.format === 'date-time') inputType = 'datetime-local';
    const numericValue =
      inputType === 'number' ? (typeof value === 'number' ? value : value ?? '') : value ?? '';

    return (
      <div key={fieldKey} className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          {fieldSchema.title || label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {description && <p className="text-xs text-gray-500">{description}</p>}
        {formUrl && (
          <a
            className="text-xs text-primary-600 hover:text-primary-700 inline-block"
            href={formUrl}
            target="_blank"
            rel="noreferrer"
          >
            Learn more
          </a>
        )}
        <input
          type={inputType}
          className={`w-full border rounded-md px-3 py-2 text-sm ${
            fieldError ? 'border-red-500' : ''
          }`}
          value={numericValue as any}
          onChange={(event) => {
            if (inputType === 'number') {
              const raw = event.target.value;
              const next = raw === '' ? null : Number(raw);
              updateValue(path, next);
            } else {
              updateValue(path, event.target.value);
            }
          }}
        />
        {fieldError && <p className="text-xs text-red-600">{fieldError}</p>}
      </div>
    );
  }

  function renderDefinitionNodes(
    nodes: DefinitionNode[],
    basePath: Array<string | number>,
  ) {
    return (
      <div className="space-y-4">
        {nodes.map((node, index) =>
          renderDefinitionNode(node, basePath, index)
        )}
      </div>
    );
  }

  function renderDefinitionNode(
    node: DefinitionNode,
    basePath: Array<string | number>,
    index: number,
    options?: { useBasePath?: boolean; schemaOverride?: UISchema },
  ) {
    const nodeId = node.idShort ?? `Item${index + 1}`;
    const fieldPath = options?.useBasePath ? basePath : [...basePath, nodeId];
    const schemaNode = options?.schemaOverride ?? getSchemaAtPath(uiSchema, fieldPath);
    const label = getNodeLabel(node, nodeId);
    const description = getNodeDescription(node);
    const required = isNodeRequired(node);
    const accessMode = node.smt?.access_mode?.toLowerCase();
    const forceReadOnly = accessMode === 'readonly' || accessMode === 'read-only';
    const formUrl = node.smt?.form_url ?? undefined;
    const requiredLanguages = node.smt?.required_lang ?? undefined;

    if (node.modelType === 'SubmodelElementCollection') {
      const children = node.children ?? [];
      return (
        <div key={pathToKey(fieldPath)} className="border rounded-md p-4">
          <p className="text-sm font-medium text-gray-800">
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          <div className="mt-4">
            {children.length > 0
              ? renderDefinitionNodes(children, fieldPath)
              : schemaNode?.properties
                ? renderObjectFields(schemaNode, fieldPath)
                : null}
          </div>
        </div>
      );
    }

    if (node.modelType === 'SubmodelElementList') {
      const list = Array.isArray(getValueAtPath(formData, fieldPath))
        ? (getValueAtPath(formData, fieldPath) as unknown[])
        : [];
      const itemsSchema = schemaNode?.items;
      const itemDefinition = node.items ?? undefined;

      return (
        <div key={pathToKey(fieldPath)} className="border rounded-md p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-800">
              {label}
              {required && <span className="text-red-500 ml-1">*</span>}
            </p>
            <button
              type="button"
              className="text-sm text-primary-600 hover:text-primary-700"
              onClick={() => {
                const next = [...list, defaultValueForSchema(itemsSchema)];
                updateValue(fieldPath, next);
              }}
            >
              Add item
            </button>
          </div>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          <div className="mt-4 space-y-3">
            {list.length === 0 && (
              <p className="text-xs text-gray-400">No items yet.</p>
            )}
            {list.map((_, itemIndex) => {
              const itemPath = [...fieldPath, itemIndex];
              const itemKey = pathToKey(itemPath);
              return (
                <div key={itemKey} className="border rounded-md p-3">
                  <div className="flex justify-end">
                    <button
                      type="button"
                      className="text-xs text-red-500 hover:text-red-600"
                      onClick={() => {
                        const next = list.filter((_, idx) => idx !== itemIndex);
                        updateValue(fieldPath, next);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                  <div className="mt-2">
                    {itemDefinition ? (
                      renderDefinitionNode(
                        itemDefinition,
                        itemPath,
                        itemIndex,
                        { useBasePath: true, schemaOverride: itemsSchema },
                      )
                    ) : (
                      renderField(
                        itemsSchema || { type: 'string' },
                        itemPath,
                        `${label} ${itemIndex + 1}`,
                        false,
                      )
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    if (schemaNode) {
      return renderField(
        schemaNode,
        fieldPath,
        label,
        required,
        description,
        forceReadOnly,
        formUrl,
        requiredLanguages,
      );
    }

    return renderField(
      { type: 'string' },
      fieldPath,
      label,
      required,
      description,
      forceReadOnly,
      formUrl,
      requiredLanguages,
    );
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    );
  }

  if (!dpp || !templateKey) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Submodel not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Edit Submodel</h1>
          <p className="text-sm text-gray-500">Template: {templateKey}</p>
          {definition && (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-600">
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5">
                Revision #{definition.revision_no}
              </span>
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5">
                {definition.state}
              </span>
            </div>
          )}
        </div>
        <button
          onClick={() => navigate(`/console/dpps/${dppId}`)}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
          data-testid="submodel-back"
        >
          Back
        </button>
      </div>

      <div className="bg-white shadow rounded-lg p-6 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <label className="block text-sm font-medium text-gray-700">Submodel Data</label>
            <p className="text-xs text-gray-500">
              {activeView === 'form'
                ? 'Edit values using the schema-driven form.'
                : 'Edit raw JSON for advanced tweaks.'}
            </p>
          </div>
          <div className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-1 text-xs">
            <button
              type="button"
              className={`px-3 py-1 rounded-md ${
                activeView === 'form' ? 'bg-white shadow text-gray-900' : 'text-gray-500'
              }`}
              onClick={() => handleViewChange('form')}
              disabled={!uiSchema}
            >
              Form
            </button>
            <button
              type="button"
              className={`px-3 py-1 rounded-md ${
                activeView === 'json' ? 'bg-white shadow text-gray-900' : 'text-gray-500'
              }`}
              onClick={() => handleViewChange('json')}
            >
              JSON
            </button>
          </div>
        </div>
        {!submodel && (
          <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-xs text-yellow-800">
            This template is not initialized yet. Saving will add it to the DPP.
          </div>
        )}

        {activeView === 'form' ? (
          templateDefinition?.submodel?.elements?.length ? (
            <div className="space-y-4">
              {renderDefinitionNodes(templateDefinition.submodel.elements, [])}
            </div>
          ) : uiSchema?.type === 'object' ? (
            <div className="space-y-4">{renderObjectFields(uiSchema, [])}</div>
          ) : (
            <div className="rounded-md border border-dashed border-gray-300 p-4 text-sm text-gray-500">
              Form view is unavailable for this template. Switch to JSON.
            </div>
          )
        ) : (
          <textarea
            className="w-full min-h-[300px] border rounded-md p-3 font-mono text-xs"
            value={rawJson}
            onChange={(event) => {
              setRawJson(event.target.value);
              setHasEdited(true);
            }}
          />
        )}
        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
        {sessionExpired && (
          <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <span>Session expired. Please sign in again.</span>
            <button
              type="button"
              className="text-sm font-medium text-red-700 underline"
              onClick={() => { void auth.signinRedirect(); }}
            >
              Sign in
            </button>
          </div>
        )}
        {updateMutation.isError && !sessionExpired && (
          <p className="text-sm text-red-600">
            {updateError?.message || 'Failed to save changes.'}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => {
              setRawJson(JSON.stringify(initialData, null, 2));
              setHasEdited(false);
            }}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
          >
            Reset
          </button>
          {!updateMutation.isPending && (
            <button
              type="button"
              onClick={() => updateMutation.mutate({ data: formData, rebuildFromTemplate: true })}
              className="px-4 py-2 border border-primary-200 text-primary-700 rounded-md text-sm hover:bg-primary-50"
            >
              Rebuild from template
            </button>
          )}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={updateMutation.isPending}
            className="px-4 py-2 rounded-md text-sm text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>

      {schema?.schema && (
        <details className="bg-white shadow rounded-lg p-6">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            Template Schema (read-only)
          </summary>
          <pre className="mt-4 text-xs bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(schema.schema, null, 2)}
          </pre>
        </details>
      )}
      {templateDefinition && (
        <details className="bg-white shadow rounded-lg p-6">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            Template Definition (read-only)
          </summary>
          <pre className="mt-4 text-xs bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(templateDefinition, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
