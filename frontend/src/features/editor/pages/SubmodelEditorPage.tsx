import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { buildSubmodelData } from '@/features/editor/utils/submodelData';
import type {
  TemplateResponse,
  TemplateDefinition,
  SubmodelDefinitionResponse,
} from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import { extractSemanticId } from '../utils/pathUtils';
import { validateSchema, validateReadOnly } from '../utils/validation';
import { useSubmodelForm } from '../hooks/useSubmodelForm';
import { useEitherOrGroups } from '../hooks/useEitherOrGroups';
import { AASRendererList } from '../components/AASRenderer';
import { FormJsonToggle } from '../components/FormJsonToggle';
import { JsonEditor } from '../components/JsonEditor';
import { FormToolbar } from '../components/FormToolbar';

// ── API functions (unchanged) ───────────────────────────────────

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
  const response = await tenantApiFetch(
    `/dpps/${dppId}/submodels/${templateKey}/definition`,
    {},
    token,
  );
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
  const response = await tenantApiFetch(
    `/dpps/${dppId}/submodel`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_key: templateKey,
        data,
        rebuild_from_template: rebuildFromTemplate,
      }),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to update submodel'));
  }
  return response.json();
}

// ── Page Component ──────────────────────────────────────────────

export default function SubmodelEditorPage() {
  const { dppId, templateKey } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const queryClient = useQueryClient();

  // ── Data fetching ──

  const { data: dpp, isLoading: loadingDpp } = useQuery({
    queryKey: ['dpp', tenantSlug, dppId],
    queryFn: () => fetchDpp(dppId!, token),
    enabled: Boolean(token && dppId),
  });

  const { data: template, isLoading: loadingTemplate } = useQuery<TemplateResponse>({
    queryKey: ['template', templateKey],
    queryFn: () => fetchTemplate(templateKey!, token),
    enabled: Boolean(token && templateKey),
  });

  const { data: schema, isLoading: loadingSchema } = useQuery({
    queryKey: ['template-schema', templateKey],
    queryFn: () => fetchTemplateSchema(templateKey!, token),
    enabled: Boolean(token && templateKey),
  });

  const { data: definition, isLoading: loadingDefinition } =
    useQuery<SubmodelDefinitionResponse>({
      queryKey: ['submodel-definition', tenantSlug, dppId, templateKey],
      queryFn: () => fetchSubmodelDefinition(dppId!, templateKey!, token),
      enabled: Boolean(token && templateKey && dppId),
    });

  // ── Derived state ──

  const submodel = useMemo(() => {
    if (!dpp) return null;
    const submodels = dpp.aas_environment?.submodels || [];
    const semanticId = template?.semantic_id;
    if (semanticId) {
      const bySemantic = submodels.find(
        (sm: Record<string, unknown>) => extractSemanticId(sm) === semanticId,
      );
      if (bySemantic) return bySemantic;
    }
    const definitionIdShort = definition?.definition?.submodel?.idShort;
    if (definitionIdShort) {
      const byIdShort = submodels.find(
        (sm: Record<string, unknown>) => sm?.idShort === definitionIdShort,
      );
      if (byIdShort) return byIdShort;
    }
    return null;
  }, [dpp, template?.semantic_id, definition?.definition?.submodel?.idShort]);

  const initialData = useMemo(() => {
    if (!submodel) return {};
    return buildSubmodelData(submodel);
  }, [submodel]);

  const uiSchema = schema?.schema as UISchema | undefined;
  const templateDefinition = definition?.definition as TemplateDefinition | undefined;

  // ── React Hook Form ──

  const { form } = useSubmodelForm(templateDefinition, uiSchema, initialData);
  const { validate: validateEitherOrGroups } = useEitherOrGroups(templateDefinition);

  // ── View state (form vs JSON) ──

  const [rawJson, setRawJson] = useState('');
  const [activeView, setActiveView] = useState<'form' | 'json'>('form');
  const [error, setError] = useState<string | null>(null);
  const [hasEdited, setHasEdited] = useState(false);

  // Sync RHF defaults when initial data loads
  useEffect(() => {
    if (!hasEdited) {
      form.reset(initialData);
      setRawJson(JSON.stringify(initialData, null, 2));
    }
  }, [initialData, hasEdited, form]);

  useEffect(() => {
    setHasEdited(false);
  }, [dppId, templateKey]);

  // ── Mutation ──

  const updateMutation = useMutation({
    mutationFn: (payload: { data: Record<string, unknown>; rebuildFromTemplate?: boolean }) =>
      updateSubmodel(dppId!, templateKey!, payload.data, token, payload.rebuildFromTemplate ?? false),
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

  // ── Handlers ──

  const handleViewChange = (view: 'form' | 'json') => {
    if (view === activeView) return;
    if (view === 'form') {
      try {
        const parsed = JSON.parse(rawJson || '{}') as Record<string, unknown>;
        form.reset(parsed);
        setError(null);
        setActiveView('form');
        setHasEdited(true);
      } catch {
        setError('Invalid JSON. Fix it before switching to form view.');
      }
    } else {
      setRawJson(JSON.stringify(form.getValues(), null, 2));
      setError(null);
      setActiveView('json');
    }
  };

  const handleSave = () => {
    if (activeView === 'json') {
      try {
        const parsed = JSON.parse(rawJson) as Record<string, unknown>;
        const schemaErrors = validateSchema(uiSchema, parsed);
        const readOnlyErrors = validateReadOnly(uiSchema, parsed, initialData);
        const eitherOrErrors = validateEitherOrGroups(parsed);
        const mergedErrors = { ...schemaErrors, ...readOnlyErrors };
        if (Object.keys(mergedErrors).length > 0 || eitherOrErrors.length > 0) {
          setError(
            eitherOrErrors.length > 0
              ? eitherOrErrors.join(' ')
              : 'Please resolve the highlighted validation errors.',
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

    // Form view: RHF validates via Zod, plus legacy validation
    const formData = form.getValues();
    const schemaErrors = validateSchema(uiSchema, formData);
    const readOnlyErrors = validateReadOnly(uiSchema, formData, initialData);
    const eitherOrErrors = validateEitherOrGroups(formData);
    const mergedErrors = { ...schemaErrors, ...readOnlyErrors };
    if (Object.keys(mergedErrors).length > 0 || eitherOrErrors.length > 0) {
      setError(
        eitherOrErrors.length > 0
          ? eitherOrErrors.join(' ')
          : 'Please resolve the highlighted validation errors.',
      );
      return;
    }
    setError(null);
    updateMutation.mutate({ data: formData });
  };

  const handleReset = () => {
    form.reset(initialData);
    setRawJson(JSON.stringify(initialData, null, 2));
    setHasEdited(false);
    setError(null);
  };

  const handleRebuild = () => {
    updateMutation.mutate({ data: form.getValues(), rebuildFromTemplate: true });
  };

  // ── Loading / error states ──

  const isLoading = loadingDpp || loadingTemplate || loadingSchema || loadingDefinition;

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
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

  // ── Render ──

  const hasDefinitionElements = Boolean(
    templateDefinition?.submodel?.elements?.length,
  );
  const hasSchemaForm = uiSchema?.type === 'object';

  return (
    <div className="space-y-6">
      {/* Header */}
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

      {/* Editor Card */}
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
          <FormJsonToggle
            activeView={activeView}
            onViewChange={handleViewChange}
            formDisabled={!uiSchema}
          />
        </div>

        {!submodel && (
          <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-xs text-yellow-800">
            This template is not initialized yet. Saving will add it to the DPP.
          </div>
        )}

        {activeView === 'form' ? (
          hasDefinitionElements ? (
            <AASRendererList
              nodes={templateDefinition!.submodel!.elements!}
              basePath=""
              depth={0}
              rootSchema={uiSchema}
              control={form.control}
            />
          ) : hasSchemaForm ? (
            <AASRendererList
              nodes={Object.entries(uiSchema!.properties ?? {}).map(([key]) => ({
                modelType: 'Property',
                idShort: key,
              }))}
              basePath=""
              depth={0}
              rootSchema={uiSchema}
              control={form.control}
            />
          ) : (
            <div className="rounded-md border border-dashed border-gray-300 p-4 text-sm text-gray-500">
              Form view is unavailable for this template. Switch to JSON.
            </div>
          )
        ) : (
          <JsonEditor
            value={rawJson}
            onChange={(val) => {
              setRawJson(val);
              setHasEdited(true);
            }}
          />
        )}

        {/* Error banners */}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {sessionExpired && (
          <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <span>Session expired. Please sign in again.</span>
            <button
              type="button"
              className="text-sm font-medium text-red-700 underline"
              onClick={() => {
                void auth.signinRedirect();
              }}
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

        <FormToolbar
          onSave={handleSave}
          onReset={handleReset}
          onRebuild={handleRebuild}
          isSaving={updateMutation.isPending}
        />
      </div>

      {/* Debug panels */}
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
