import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { ChevronRight } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { buildSubmodelData } from '@/features/editor/utils/submodelData';
import { buildDppActionState } from '@/features/submodels/policy/actionPolicy';
import type { DppAccessSummary, SubmodelBinding } from '@/features/submodels/types';
import { emitSubmodelUxMetric } from '@/features/submodels/telemetry/uxTelemetry';
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
import { cn } from '@/lib/utils';

function flattenFormErrors(
  errors: Record<string, unknown>,
  basePath = '',
): Array<{ path: string; message: string }> {
  const flattened: Array<{ path: string; message: string }> = [];
  for (const [key, value] of Object.entries(errors)) {
    const path = basePath ? `${basePath}.${key}` : key;
    if (!value || typeof value !== 'object') continue;
    const asRecord = value as Record<string, unknown>;
    const message = asRecord.message;
    if (typeof message === 'string' && message) {
      flattened.push({ path, message });
    }
    const nested = Object.fromEntries(
      Object.entries(asRecord).filter(([nestedKey]) => nestedKey !== 'message' && nestedKey !== 'type'),
    );
    flattened.push(...flattenFormErrors(nested, path));
  }
  return flattened;
}

// ── API functions (unchanged) ───────────────────────────────────

async function fetchDpp(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
  }
  return response.json() as Promise<{
    id: string;
    status: string;
    access?: DppAccessSummary;
    aas_environment?: { submodels?: Array<Record<string, unknown>> };
    submodel_bindings?: SubmodelBinding[];
  }>;
}

async function fetchTemplate(templateKey: string, token?: string) {
  const response = await apiFetch(`/api/v1/templates/${templateKey}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch template'));
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
  submodelId: string | undefined,
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
        ...(submodelId ? { submodel_id: submodelId } : {}),
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
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const queryClient = useQueryClient();
  const requestedSubmodelId = searchParams.get('submodel_id');

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

  const { data: contract, isLoading: loadingContract } = useQuery<TemplateContractResponse>({
    queryKey: ['template-contract', templateKey],
    queryFn: () => fetchTemplateContract(templateKey!, token),
    enabled: Boolean(token && templateKey),
  });


  // ── Derived state ──

  const submodel = useMemo(() => {
    if (!dpp) return null;
    const submodels = dpp.aas_environment?.submodels || [];
    const bindings = Array.isArray(dpp.submodel_bindings) ? dpp.submodel_bindings : [];
    const templateBindings = bindings.filter((binding) => binding.template_key === templateKey);
    const selectedBinding = requestedSubmodelId
      ? templateBindings.find((binding) => binding.submodel_id === requestedSubmodelId)
      : templateBindings[0];

    const resolvedSubmodelId = requestedSubmodelId ?? selectedBinding?.submodel_id ?? null;
    if (resolvedSubmodelId) {
      const byId = submodels.find((sm: Record<string, unknown>) => sm?.id === resolvedSubmodelId);
      if (byId) return byId;
    }

    const semanticId = selectedBinding?.semantic_id ?? contract?.semantic_id ?? template?.semantic_id;
    if (semanticId) {
      const bySemantic = submodels.find((sm: Record<string, unknown>) => extractSemanticId(sm) === semanticId);
      if (bySemantic) return bySemantic;
    }

    const definitionIdShort = contract?.definition?.submodel?.idShort;
    if (definitionIdShort) {
      const byIdShort = submodels.find(
        (sm: Record<string, unknown>) => sm?.idShort === definitionIdShort,
      );
      if (byIdShort) return byIdShort;
    }
    return null;
  }, [
    dpp,
    requestedSubmodelId,
    templateKey,
    template?.semantic_id,
    contract?.semantic_id,
    contract?.definition?.submodel?.idShort,
  ]);

  const templateBindings = useMemo(() => {
    if (!dpp || !templateKey) return [];
    const bindings = Array.isArray(dpp.submodel_bindings) ? dpp.submodel_bindings : [];
    return bindings.filter((binding) => binding.template_key === templateKey);
  }, [dpp, templateKey]);

  const selectedBinding = useMemo(() => {
    if (templateBindings.length === 0) return null;
    if (requestedSubmodelId) {
      return (
        templateBindings.find((binding) => binding.submodel_id === requestedSubmodelId) ?? null
      );
    }
    return templateBindings[0];
  }, [requestedSubmodelId, templateBindings]);

  const selectedSubmodelId = requestedSubmodelId ?? selectedBinding?.submodel_id ?? undefined;
  const hasAmbiguousTemplateBindings = templateBindings.length > 1 && !requestedSubmodelId;

  const initialData = useMemo(() => {
    if (!submodel) return {};
    return buildSubmodelData(submodel);
  }, [submodel]);

  const uiSchema = contract?.schema as UISchema | undefined;
  const templateDefinition = contract?.definition as TemplateDefinition | undefined;

  // ── React Hook Form ──

  const { form } = useSubmodelForm(templateDefinition, uiSchema, initialData);
  const { validate: validateEitherOrGroups } = useEitherOrGroups(templateDefinition);

  // ── View state (form vs JSON) ──

  const [rawJson, setRawJson] = useState('');
  const [activeView, setActiveView] = useState<'form' | 'json'>('form');
  const [error, setError] = useState<string | null>(null);
  const [hasEdited, setHasEdited] = useState(false);
  const [pendingAction, setPendingAction] = useState<'save' | 'rebuild' | null>(null);

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
      updateSubmodel(
        dppId!,
        templateKey!,
        payload.data,
        selectedSubmodelId,
        token,
        payload.rebuildFromTemplate ?? false,
      ),
    onSuccess: () => {
      setPendingAction(null);
      queryClient.invalidateQueries({ queryKey: ['dpp', tenantSlug, dppId] });
      navigate(`/console/dpps/${dppId}`);
    },
    onError: (mutationError) => {
      const message = mutationError instanceof Error ? mutationError.message : 'unknown-error';
      emitSubmodelUxMetric(
        pendingAction === 'rebuild' ? 'rebuild_failure_class' : 'save_failure_class',
        {
          dpp_id: dppId,
          template_key: templateKey,
          reason:
            message.includes('409') || message.toLowerCase().includes('ambiguous')
              ? 'ambiguous-binding'
              : message.includes('403')
                ? 'forbidden'
                : message.includes('400')
                  ? 'bad-request'
                  : 'backend-error',
          message,
        },
      );
      setPendingAction(null);
    },
  });

  const updateError = updateMutation.isError ? (updateMutation.error as Error) : null;
  const sessionExpired = Boolean(updateError?.message?.includes('Session expired'));
  const actionState = buildDppActionState(
    dpp?.access as DppAccessSummary | undefined,
    dpp?.status ?? '',
  );
  const fieldErrors = flattenFormErrors(form.formState.errors as Record<string, unknown>);

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
    if (!actionState.canUpdate) {
      setError('You do not have update access for this DPP.');
      emitSubmodelUxMetric('save_failure_class', {
        dpp_id: dppId,
        template_key: templateKey,
        reason: 'ui-no-update-access',
      });
      return;
    }
    if (hasAmbiguousTemplateBindings) {
      setError(
        'Multiple submodels are bound to this template. Open this editor from the DPP page so a specific submodel can be selected.',
      );
      emitSubmodelUxMetric('save_failure_class', {
        dpp_id: dppId,
        template_key: templateKey,
        reason: 'ui-ambiguous-binding',
      });
      return;
    }

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
          emitSubmodelUxMetric('save_failure_class', {
            dpp_id: dppId,
            template_key: templateKey,
            reason: eitherOrErrors.length > 0 ? 'ui-either-or-validation' : 'ui-schema-validation',
          });
          return;
        }
        setError(null);
        setPendingAction('save');
        updateMutation.mutate({ data: parsed });
      } catch {
        setError('Invalid JSON. Please fix formatting before saving.');
        emitSubmodelUxMetric('save_failure_class', {
          dpp_id: dppId,
          template_key: templateKey,
          reason: 'ui-invalid-json',
        });
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
      emitSubmodelUxMetric('save_failure_class', {
        dpp_id: dppId,
        template_key: templateKey,
        reason: eitherOrErrors.length > 0 ? 'ui-either-or-validation' : 'ui-schema-validation',
      });
      return;
    }
    setError(null);
    setPendingAction('save');
    updateMutation.mutate({ data: formData });
  };

  const handleReset = () => {
    if (!actionState.canUpdate) return;
    form.reset(initialData);
    setRawJson(JSON.stringify(initialData, null, 2));
    setHasEdited(false);
    setError(null);
  };

  const handleRebuild = () => {
    if (!actionState.canUpdate) {
      emitSubmodelUxMetric('rebuild_failure_class', {
        dpp_id: dppId,
        template_key: templateKey,
        reason: 'ui-no-update-access',
      });
      return;
    }
    if (hasAmbiguousTemplateBindings) {
      setError(
        'Multiple submodels are bound to this template. Open this editor from the DPP page so a specific submodel can be selected.',
      );
      emitSubmodelUxMetric('rebuild_failure_class', {
        dpp_id: dppId,
        template_key: templateKey,
        reason: 'ui-ambiguous-binding',
      });
      return;
    }
    setPendingAction('rebuild');
    updateMutation.mutate({ data: form.getValues(), rebuildFromTemplate: true });
  };

  // ── Loading / error states ──

  const isLoading = loadingDpp || loadingTemplate || loadingContract;

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
          contract ? (
            <Badge variant="secondary">{contract.idta_version}</Badge>
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
          <p className="sr-only" aria-live="polite">
            {updateMutation.isPending ? 'Saving submodel changes' : ''}
          </p>
          {!submodel && (
            <Alert>
              <AlertDescription className="text-xs">
                This template is not initialized yet. Saving will add it to the DPP.
              </AlertDescription>
            </Alert>
          )}
          {!actionState.canUpdate && (
            <Alert>
              <AlertDescription className="text-xs">
                Read-only access. You can inspect this submodel but cannot save or rebuild.
              </AlertDescription>
            </Alert>
          )}
          {hasAmbiguousTemplateBindings && (
            <Alert variant="destructive">
              <AlertDescription className="text-xs">
                Multiple submodels match this template key. Use the DPP Submodels section to open the exact target.
              </AlertDescription>
            </Alert>
          )}

          <Tabs value={activeView} onValueChange={(v) => handleViewChange(v as 'form' | 'json')}>
            <TabsList>
              <TabsTrigger value="form" disabled={!uiSchema}>Form</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>
            <TabsContent value="form">
              <div className={cn(!actionState.canUpdate && 'opacity-90')}>
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
              </div>
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
          {(fieldErrors.length > 0 || error) && (
            <Alert variant="destructive">
              <AlertDescription>
                <div className="space-y-1">
                  {error && <p className="text-sm">{error}</p>}
                  {fieldErrors.length > 0 && (
                    <div className="text-xs">
                      {fieldErrors.slice(0, 6).map((entry) => (
                        <p key={entry.path}>
                          {entry.path}: {entry.message}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </AlertDescription>
            </Alert>
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
            canUpdate={actionState.canUpdate}
            canReset={hasEdited || form.formState.isDirty}
          />
        </CardContent>
      </Card>

      {/* Debug panels */}
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
