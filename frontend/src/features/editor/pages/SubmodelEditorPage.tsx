import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch } from '@/lib/api';

type TemplateResponse = {
  semantic_id: string;
};

type UISchema = {
  type?: string;
  title?: string;
  description?: string;
  properties?: Record<string, UISchema>;
  items?: UISchema;
  required?: string[];
  'x-multi-language'?: boolean;
  'x-range'?: boolean;
  'x-file-upload'?: boolean;
};

type FormData = Record<string, unknown>;

async function fetchDpp(dppId: string, token?: string) {
  const response = await apiFetch(`/api/v1/dpps/${dppId}`, {}, token);
  if (!response.ok) throw new Error('Failed to fetch DPP');
  return response.json();
}

async function fetchTemplate(templateKey: string, token?: string) {
  const response = await apiFetch(`/api/v1/templates/${templateKey}`, {}, token);
  if (!response.ok) throw new Error('Failed to fetch template');
  return response.json();
}

async function fetchTemplateSchema(templateKey: string, token?: string) {
  const response = await apiFetch(`/api/v1/templates/${templateKey}/schema`, {}, token);
  if (!response.ok) throw new Error('Failed to fetch template schema');
  return response.json();
}

async function updateSubmodel(
  dppId: string,
  templateKey: string,
  data: Record<string, unknown>,
  token?: string,
) {
  const response = await apiFetch(`/api/v1/dpps/${dppId}/submodel`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_key: templateKey, data }),
  }, token);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to update submodel');
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

function extractElementValue(element: any): unknown {
  const type = element?.modelType?.name;
  if (type === 'SubmodelElementCollection') {
    return extractElements(element.value || []);
  }
  if (type === 'MultiLanguageProperty') {
    const value = element.value;
    if (Array.isArray(value)) {
      return value.reduce<Record<string, string>>((acc, entry) => {
        if (entry?.language) acc[String(entry.language)] = String(entry.text ?? '');
        return acc;
      }, {});
    }
  }
  if (type === 'Range') {
    return { min: element.min ?? null, max: element.max ?? null };
  }
  if (type === 'File') {
    return { contentType: element.contentType ?? '', value: element.value ?? '' };
  }
  return element?.value ?? '';
}

function extractElements(elements: any[]): Record<string, unknown> {
  return elements.reduce<Record<string, unknown>>((acc, element) => {
    const idShort = element?.idShort;
    if (!idShort) return acc;
    acc[String(idShort)] = extractElementValue(element);
    return acc;
  }, {});
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

function defaultValueForSchema(schema?: UISchema): unknown {
  if (!schema) return '';
  if (schema['x-multi-language']) return {};
  if (schema['x-range']) return { min: null, max: null };
  if (schema['x-file-upload']) return { contentType: '', value: '' };
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

function validateSchema(
  schema: UISchema | undefined,
  data: unknown,
  path: Array<string | number> = [],
): Record<string, string> {
  if (!schema) return {};
  const errors: Record<string, string> = {};

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
      data.forEach((item, index) => {
        const nested = validateSchema(schema.items, item, [...path, index]);
        Object.assign(errors, nested);
      });
    }
  }

  return errors;
}

export default function SubmodelEditorPage() {
  const { dppId, templateKey } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data: dpp, isLoading: loadingDpp } = useQuery({
    queryKey: ['dpp', dppId],
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

  const submodel = useMemo(() => {
    if (!dpp || !template?.semantic_id) return null;
    const submodels = dpp.aas_environment?.submodels || [];
    return submodels.find((sm: any) => extractSemanticId(sm) === template.semantic_id) || null;
  }, [dpp, template?.semantic_id]);

  const initialData = useMemo(() => {
    if (!submodel) return {};
    return extractElements(submodel.submodelElements || []);
  }, [submodel]);

  const [rawJson, setRawJson] = useState('');
  const [formData, setFormData] = useState<FormData>({});
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [activeView, setActiveView] = useState<'form' | 'json'>('form');
  const [hasEdited, setHasEdited] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      updateSubmodel(dppId!, templateKey!, payload, token),
    onSuccess: () => {
      navigate(`/console/dpps/${dppId}`);
    },
  });

  useEffect(() => {
    if (!hasEdited) {
      setRawJson(JSON.stringify(initialData, null, 2));
      setFormData(initialData as FormData);
      setFormErrors({});
    }
  }, [initialData, hasEdited]);

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
        if (Object.keys(schemaErrors).length > 0) {
          setFormErrors(schemaErrors);
          setError('Please fill out required fields.');
          return;
        }
        setError(null);
        updateMutation.mutate(parsed);
      } catch {
        setError('Invalid JSON. Please fix formatting before saving.');
      }
      return;
    }

    const schemaErrors = validateSchema(schema?.schema as UISchema | undefined, formData);
    if (Object.keys(schemaErrors).length > 0) {
      setFormErrors(schemaErrors);
      setError('Please fill out required fields.');
      return;
    }

    setError(null);
    updateMutation.mutate(formData);
  };

  const isLoading = loadingDpp || loadingTemplate || loadingSchema;
  const uiSchema = schema?.schema as UISchema | undefined;

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
  ) {
    const fieldKey = pathToKey(path);
    const fieldError = formErrors[fieldKey];
    const value = getValueAtPath(formData, path);
    const description = fieldSchema.description;

    if (fieldSchema['x-multi-language']) {
      const languages = ['en', 'de', 'fr', 'es', 'it'];
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
          <div className="mt-4 space-y-3">
            {list.length === 0 && (
              <p className="text-xs text-gray-400">No items yet.</p>
            )}
            {list.map((item, index) => {
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
                  {itemsSchema?.type === 'object' && itemsSchema.properties ? (
                    <div className="mt-2">
                      {renderObjectFields(itemsSchema, itemPath)}
                    </div>
                  ) : (
                    <input
                      type="text"
                      className="w-full border rounded-md px-3 py-2 text-sm"
                      value={item as any}
                      onChange={(event) => {
                        const next = [...list];
                        next[index] = event.target.value;
                        updateValue(path, next);
                      }}
                    />
                  )}
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

    const inputType = fieldSchema.type === 'number' || fieldSchema.type === 'integer' ? 'number' : 'text';
    const numericValue =
      inputType === 'number' ? (typeof value === 'number' ? value : value ?? '') : value ?? '';

    return (
      <div key={fieldKey} className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          {fieldSchema.title || label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {description && <p className="text-xs text-gray-500">{description}</p>}
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
        </div>
        <button
          onClick={() => navigate(`/console/dpps/${dppId}`)}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
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

        {activeView === 'form' ? (
          uiSchema?.type === 'object' ? (
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
        {updateMutation.isError && (
          <p className="text-sm text-red-600">
            {(updateMutation.error as Error)?.message || 'Failed to save changes.'}
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
    </div>
  );
}
