import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch } from '@/lib/api';

type TemplateResponse = {
  semantic_id: string;
};

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
    }
  }, [initialData, hasEdited]);

  const handleSubmit = () => {
    try {
      const parsed = JSON.parse(rawJson) as Record<string, unknown>;
      setError(null);
      updateMutation.mutate(parsed);
    } catch (err) {
      setError('Invalid JSON. Please fix formatting before saving.');
    }
  };

  const isLoading = loadingDpp || loadingTemplate || loadingSchema;

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
        <label className="block text-sm font-medium text-gray-700">
          Submodel Data (JSON)
        </label>
        <textarea
          className="w-full min-h-[300px] border rounded-md p-3 font-mono text-xs"
          value={rawJson}
          onChange={(event) => {
            setRawJson(event.target.value);
            setHasEdited(true);
          }}
        />
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
