import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { ChevronRight } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { buildSubmodelData } from '@/features/editor/utils/submodelData';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type {
  TemplateResponse,
  TemplateDefinition,
  SubmodelDefinitionResponse,
  TemplateContractResponse,
} from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import { extractSemanticId } from '../utils/pathUtils';
import { validateSchema, validateReadOnly } from '../utils/validation';
import { useSubmodelForm } from '../hooks/useSubmodelForm';
import { useEitherOrGroups } from '../hooks/useEitherOrGroups';
import { AASRendererList } from '../components/AASRenderer';
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

async function fetchTemplateContract(templateKey: string, token?: string) {
  const response = await apiFetch(`/api/v1/templates/${templateKey}/contract`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch template contract'));
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
  const useTemplateContractV2 = import.meta.env.VITE_TEMPLATE_CONTRACT_V2 === 'true';

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
    enabled: Boolean(token && templateKey && !useTemplateContractV2),
  });

  const { data: definition, isLoading: loadingDefinition } =
    useQuery<SubmodelDefinitionResponse>({
      queryKey: ['submodel-definition', tenantSlug, dppId, templateKey],
      queryFn: () => fetchSubmodelDefinition(dppId!, templateKey!, token),
      enabled: Boolean(token && templateKey && dppId && !useTemplateContractV2),
    });

  const { data: contract, isLoading: loadingContract } = useQuery<TemplateContractResponse>({
    queryKey: ['template-contract', templateKey],
    queryFn: () => fetchTemplateContract(templateKey!, token),
    enabled: Boolean(token && templateKey && useTemplateContractV2),
  });

  // ── Derived state ──

  const submodel = useMemo(() => {
    if (!dpp) return null;
    const submodels = dpp.aas_environment?.submodels || [];
    const semanticId = contract?.semantic_id ?? template?.semantic_id;
    if (semanticId) {
      const bySemantic = submodels.find(
        (sm: Record<string, unknown>) => extractSemanticId(sm) === semanticId,
      );
      if (bySemantic) return bySemantic;
    }
    const definitionIdShort =
      contract?.definition?.submodel?.idShort ?? definition?.definition?.submodel?.idShort;
    if (definitionIdShort) {
      const byIdShort = submodels.find(
        (sm: Record<string, unknown>) => sm?.idShort === definitionIdShort,
      );
      if (byIdShort) return byIdShort;
    }
    return null;
  }, [
    dpp,
    template?.semantic_id,
    contract?.semantic_id,
    definition?.definition?.submodel?.idShort,
    contract?.definition?.submodel?.idShort,
  ]);

  const initialData = useMemo(() => {
    if (!submodel) return {};
    return buildSubmodelData(submodel);
  }, [submodel]);

  const uiSchema = (contract?.schema ?? schema?.schema) as UISchema | undefined;
  const templateDefinition = (
    contract?.definition ?? definition?.definition
  ) as TemplateDefinition | undefined;

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

  const isLoading =
    loadingDpp ||
    loadingTemplate ||
    (!useTemplateContractV2 && (loadingSchema || loadingDefinition)) ||
    (useTemplateContractV2 && loadingContract);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!dpp || !templateKey) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Submodel not found</p>
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
      <PageHeader
        title="Edit Submodel"
        description={`Template: ${templateKey}`}
        breadcrumb={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/console/dpps/${dppId}`)}
            data-testid="submodel-back"
          >
            Back
          </Button>
        }
        actions={
          definition ? (
            <div className="flex items-center gap-2">
              <Badge variant="secondary">Revision #{definition.revision_no}</Badge>
              <Badge variant="secondary">{definition.state}</Badge>
            </div>
          ) : undefined
        }
      />

      {/* Editor Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base">Submodel Data</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                {activeView === 'form'
                  ? 'Edit values using the schema-driven form.'
                  : 'Edit raw JSON for advanced tweaks.'}
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!submodel && (
            <Alert>
              <AlertDescription className="text-xs">
                This template is not initialized yet. Saving will add it to the DPP.
              </AlertDescription>
            </Alert>
          )}

          <Tabs value={activeView} onValueChange={(v) => handleViewChange(v as 'form' | 'json')}>
            <TabsList>
              <TabsTrigger value="form" disabled={!uiSchema}>Form</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>
            <TabsContent value="form">
              {hasDefinitionElements ? (
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
                <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  Form view is unavailable for this template. Switch to JSON.
                </div>
              )}
            </TabsContent>
            <TabsContent value="json">
              <JsonEditor
                value={rawJson}
                onChange={(val) => {
                  setRawJson(val);
                  setHasEdited(true);
                }}
              />
            </TabsContent>
          </Tabs>

          {/* Error banners */}
          {error && (
            <ErrorBanner message={error} />
          )}
          {sessionExpired && (
            <ErrorBanner
              message="Session expired. Please sign in again."
              showSignIn
              onSignIn={() => { void auth.signinRedirect(); }}
            />
          )}
          {updateMutation.isError && !sessionExpired && (
            <ErrorBanner
              message={updateError?.message || 'Failed to save changes.'}
            />
          )}

          <FormToolbar
            onSave={handleSave}
            onReset={handleReset}
            onRebuild={handleRebuild}
            isSaving={updateMutation.isPending}
          />
        </CardContent>
      </Card>

      {/* Debug panels */}
      {schema?.schema && (
        <Card>
          <Collapsible>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between p-6">
                Template Schema (read-only)
                <ChevronRight className="h-4 w-4" />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <pre className="text-xs bg-muted p-3 rounded overflow-auto">
                  {JSON.stringify(schema.schema, null, 2)}
                </pre>
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </Card>
      )}
      {templateDefinition && (
        <Card>
          <Collapsible>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between p-6">
                Template Definition (read-only)
                <ChevronRight className="h-4 w-4" />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <pre className="text-xs bg-muted p-3 rounded overflow-auto">
                  {JSON.stringify(templateDefinition, null, 2)}
                </pre>
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </Card>
      )}
    </div>
  );
}
