import { useCallback, useEffect, useMemo, useState } from 'react';
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
import { resolveSubmodelUxRollout } from '@/features/submodels/featureFlags';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type {
  TemplateResponse,
  TemplateDefinition,
  TemplateContractResponse,
  DefinitionNode,
} from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import {
  extractSemanticIds,
  getNodeLabel,
  isEmptyValue,
  isNodeRequired,
} from '../utils/pathUtils';
import { validateSchema, validateReadOnly } from '../utils/validation';
import { useSubmodelForm } from '../hooks/useSubmodelForm';
import { useEitherOrGroups } from '../hooks/useEitherOrGroups';
import { AASRendererList } from '../components/AASRenderer';
import { JsonEditor } from '../components/JsonEditor';
import { FormToolbar } from '../components/FormToolbar';
import { cn } from '@/lib/utils';
import { DppOutlinePane } from '@/features/dpp-outline/components/DppOutlinePane';
import { buildSubmodelEditorOutline } from '@/features/dpp-outline/builders/buildSubmodelEditorOutline';
import { useOutlineScrollSync } from '@/features/dpp-outline/hooks/useOutlineScrollSync';
import type { DppOutlineNode } from '@/features/dpp-outline/types';

class AmbiguousBindingError extends Error {
  candidates: string[];
  templateKey: string;
  constructor(message: string, templateKey: string, candidates: string[]) {
    super(message);
    this.name = 'AmbiguousBindingError';
    this.templateKey = templateKey;
    this.candidates = candidates;
  }
}

type UnsupportedContractNode = {
  path?: string | null;
  idShort?: string | null;
  modelType?: string | null;
  semanticId?: string | null;
  reasons?: string[];
};

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

type SectionProgress = {
  id: string;
  label: string;
  totalRequired: number;
  completedRequired: number;
  percent: number;
};

function childNodes(node: DefinitionNode): DefinitionNode[] {
  const children = Array.isArray(node.children) ? node.children : [];
  const statements = Array.isArray(node.statements) ? node.statements : [];
  const annotations = Array.isArray(node.annotations) ? node.annotations : [];
  const items = node.items ? [node.items] : [];
  return [...children, ...statements, ...annotations, ...items];
}

function evaluateRequiredProgress(node: DefinitionNode, value: unknown): {
  totalRequired: number;
  completedRequired: number;
} {
  const children = childNodes(node);
  const nodeRequired = isNodeRequired(node);

  if (children.length === 0) {
    if (!nodeRequired) return { totalRequired: 0, completedRequired: 0 };
    return {
      totalRequired: 1,
      completedRequired: isEmptyValue(value) ? 0 : 1,
    };
  }

  let totalRequired = nodeRequired ? 1 : 0;
  let completedRequired = nodeRequired && !isEmptyValue(value) ? 1 : 0;

  if (node.modelType === 'SubmodelElementList' && node.items) {
    const list = Array.isArray(value) ? value : [];
    for (const item of list) {
      const itemProgress = evaluateRequiredProgress(node.items, item);
      totalRequired += itemProgress.totalRequired;
      completedRequired += itemProgress.completedRequired;
    }
    return { totalRequired, completedRequired };
  }

  const objectValue =
    value && typeof value === 'object' && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {};

  for (const child of children) {
    const childValue = child.idShort ? objectValue[child.idShort] : undefined;
    const childProgress = evaluateRequiredProgress(child, childValue);
    totalRequired += childProgress.totalRequired;
    completedRequired += childProgress.completedRequired;
  }

  return { totalRequired, completedRequired };
}

function buildSectionProgress(
  templateDefinition: TemplateDefinition | undefined,
  formData: Record<string, unknown>,
): SectionProgress[] {
  const sections = templateDefinition?.submodel?.elements ?? [];
  return sections.map((section, index) => {
    const key = section.idShort ?? `Section${index + 1}`;
    const value = formData[key];
    const progress = evaluateRequiredProgress(section, value);
    const percent =
      progress.totalRequired === 0
        ? 100
        : Math.round((progress.completedRequired / progress.totalRequired) * 100);
    return {
      id: key,
      label: getNodeLabel(section, key),
      totalRequired: progress.totalRequired,
      completedRequired: progress.completedRequired,
      percent,
    };
  });
}

function focusFieldPath(path: string): boolean {
  const target = document.querySelector<HTMLElement>(`[data-field-path="${path}"]`);
  if (!target) return false;
  const input = target.querySelector<HTMLElement>(
    'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])',
  );
  if (input) {
    input.focus();
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return true;
  }
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  return false;
}

function focusFieldPathFallback(idShort: string): boolean {
  const normalized = idShort.trim();
  if (!normalized) return false;

  const candidates = Array.from(document.querySelectorAll<HTMLElement>('[data-field-path]'));
  const exact = candidates.find((element) => element.dataset.fieldPath === normalized);
  if (exact) {
    exact.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return true;
  }

  const suffixMatch = candidates.find((element) => {
    const path = element.dataset.fieldPath ?? '';
    return path.endsWith(`.${normalized}`);
  });
  if (suffixMatch) {
    suffixMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return true;
  }

  return false;
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
    if (response.status === 409) {
      const contentType = response.headers.get('content-type') ?? '';
      if (contentType.includes('application/json')) {
        try {
          const body = (await response.json()) as {
            detail?: {
              message?: string;
              template_key?: string;
              candidates?: string[];
            };
          };
          const detail = body?.detail;
          if (
            detail &&
            typeof detail === 'object' &&
            Array.isArray(detail.candidates) &&
            detail.candidates.length > 0
          ) {
            throw new AmbiguousBindingError(
              typeof detail.message === 'string'
                ? detail.message
                : 'Ambiguous template binding',
              typeof detail.template_key === 'string'
                ? detail.template_key
                : templateKey,
              detail.candidates,
            );
          }
        } catch (e) {
          if (e instanceof AmbiguousBindingError) throw e;
          // Fall through to generic error
        }
      }
    }
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
  const rollout = useMemo(() => resolveSubmodelUxRollout(tenantSlug), [tenantSlug]);
  const queryClient = useQueryClient();
  const requestedSubmodelId = searchParams.get('submodel_id');
  const requestedFocusPath = searchParams.get('focus_path');
  const requestedFocusIdShort = searchParams.get('focus_id_short');

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

  // Locate the submodel object in the AAS environment using backend-resolved
  // binding metadata. Priority: submodel_id (from binding) → semantic_id → idShort.
  // This does NOT re-resolve bindings; fallbacks only activate when the binding
  // lacks a submodel_id (rare for well-formed AAS submodels).
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
      const bySemantic = submodels.find((sm: Record<string, unknown>) =>
        extractSemanticIds(sm).includes(semanticId),
      );
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
  const editorContext = useMemo(() => {
    if (!dppId || !tenantSlug) return undefined;
    return {
      dppId,
      tenantSlug,
      token,
    };
  }, [dppId, tenantSlug, token]);

  const initialData = useMemo(() => {
    if (!submodel) return {};
    return buildSubmodelData(submodel);
  }, [submodel]);

  const uiSchema = contract?.schema as UISchema | undefined;
  const templateDefinition = contract?.definition as TemplateDefinition | undefined;
  const unsupportedNodes = useMemo<UnsupportedContractNode[]>(() => {
    const raw = contract?.unsupported_nodes;
    if (!Array.isArray(raw)) return [];
    return raw.filter((entry): entry is UnsupportedContractNode => typeof entry === 'object' && entry !== null);
  }, [contract?.unsupported_nodes]);
  const hasUnsupportedNodes = unsupportedNodes.length > 0;
  const saveDisabledReason = null;

  // ── React Hook Form ──

  const { form } = useSubmodelForm(templateDefinition, uiSchema, initialData);
  const { validate: validateEitherOrGroups } = useEitherOrGroups(templateDefinition);

  // ── View state (form vs JSON) ──

  const [rawJson, setRawJson] = useState('');
  const [activeView, setActiveView] = useState<'form' | 'json'>('form');
  const [selectedOutlineNodeId, setSelectedOutlineNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasEdited, setHasEdited] = useState(false);
  const [pendingAction, setPendingAction] = useState<'save' | 'rebuild' | null>(null);
  const [saveAttempted, setSaveAttempted] = useState(false);
  const [rebuildConfirmOpen, setRebuildConfirmOpen] = useState(false);
  const [hasAppliedInitialFocus, setHasAppliedInitialFocus] = useState(false);

  // Sync RHF defaults when initial data loads
  useEffect(() => {
    if (!hasEdited) {
      form.reset(initialData);
      setRawJson(JSON.stringify(initialData, null, 2));
    }
  }, [initialData, hasEdited, form]);

  useEffect(() => {
    setHasEdited(false);
    setSaveAttempted(false);
    setRebuildConfirmOpen(false);
    setHasAppliedInitialFocus(false);
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
      setSaveAttempted(false);
      queryClient.invalidateQueries({ queryKey: ['dpp', tenantSlug, dppId] });
      navigate(`/console/dpps/${dppId}`);
    },
    onError: (mutationError) => {
      const message = mutationError instanceof Error ? mutationError.message : 'unknown-error';
      if (mutationError instanceof AmbiguousBindingError) {
        const candidateList = mutationError.candidates.join(', ');
        setError(
          `Multiple submodels match this template. Candidates: ${candidateList}. Navigate to the DPP page to select a specific submodel.`,
        );
      }
      emitSubmodelUxMetric(
        pendingAction === 'rebuild' ? 'rebuild_failure_class' : 'save_failure_class',
        {
          dpp_id: dppId,
          template_key: templateKey,
          reason:
            mutationError instanceof AmbiguousBindingError ||
            message.includes('409') ||
            message.toLowerCase().includes('ambiguous')
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
  const liveFormValues = form.watch();
  const sectionProgress = useMemo(
    () => buildSectionProgress(templateDefinition, liveFormValues),
    [liveFormValues, templateDefinition],
  );
  const totalRequiredAcrossSections = sectionProgress.reduce(
    (sum, section) => sum + section.totalRequired,
    0,
  );
  const completedRequiredAcrossSections = sectionProgress.reduce(
    (sum, section) => sum + section.completedRequired,
    0,
  );
  const overallRequiredPercent =
    totalRequiredAcrossSections === 0
      ? 100
      : Math.round((completedRequiredAcrossSections / totalRequiredAcrossSections) * 100);
  const outlineNodes = useMemo(
    () =>
      buildSubmodelEditorOutline({
        templateDefinition,
        formData: liveFormValues,
        fieldErrors,
      }),
    [fieldErrors, liveFormValues, templateDefinition],
  );

  const findOutlineNodeByPath = useCallback(
    (path: string): DppOutlineNode | null => {
      let best: DppOutlineNode | null = null;
      const stack = [...outlineNodes];

      while (stack.length > 0) {
        const current = stack.pop()!;
        if (
          current.path === path ||
          path.startsWith(`${current.path}.`) ||
          current.path.startsWith(`${path}.`)
        ) {
          if (!best || current.path.length > best.path.length) {
            best = current;
          }
        }
        for (const child of current.children) {
          stack.push(child);
        }
      }

      return best;
    },
    [outlineNodes],
  );

  const handleOutlineNodeSelect = useCallback(
    (node: DppOutlineNode) => {
      setSelectedOutlineNodeId(node.id);
      if (node.target?.type === 'dom') {
        focusFieldPath(node.target.path);
      }
    },
    [],
  );

  useOutlineScrollSync({
    enabled: activeView === 'form' && outlineNodes.length > 0,
    attribute: 'data-field-path',
    onActivePathChange: (path) => {
      const target = findOutlineNodeByPath(path);
      if (target) {
        setSelectedOutlineNodeId(target.id);
      }
    },
  });

  useEffect(() => {
    if (hasAppliedInitialFocus || activeView !== 'form') return;
    if (!requestedFocusPath && !requestedFocusIdShort) return;

    let focused = false;
    if (requestedFocusPath) {
      focused = focusFieldPath(requestedFocusPath);
    }
    if (!focused && requestedFocusIdShort) {
      focused = focusFieldPathFallback(requestedFocusIdShort);
    }

    if (!focused && requestedFocusPath) {
      setError((previous) =>
        previous ?? `Could not focus requested field: ${requestedFocusPath}`,
      );
    }
    setHasAppliedInitialFocus(true);
  }, [
    activeView,
    hasAppliedInitialFocus,
    requestedFocusIdShort,
    requestedFocusPath,
    templateDefinition,
  ]);

  const canSave = useMemo(() => {
    if (!actionState.canUpdate || updateMutation.isPending) return false;
    if (hasAmbiguousTemplateBindings) return false;
    if (activeView === 'json') {
      try {
        const parsed = JSON.parse(rawJson || '{}') as Record<string, unknown>;
        const schemaErrors = validateSchema(uiSchema, parsed);
        const readOnlyErrors = validateReadOnly(uiSchema, parsed, initialData);
        const eitherOrErrors = validateEitherOrGroups(parsed);
        return (
          Object.keys(schemaErrors).length === 0 &&
          Object.keys(readOnlyErrors).length === 0 &&
          eitherOrErrors.length === 0
        );
      } catch {
        return false;
      }
    }
    const formData = form.getValues();
    const schemaErrors = validateSchema(uiSchema, formData);
    const readOnlyErrors = validateReadOnly(uiSchema, formData, initialData);
    const eitherOrErrors = validateEitherOrGroups(formData);
    return (
      form.formState.isValid &&
      Object.keys(schemaErrors).length === 0 &&
      Object.keys(readOnlyErrors).length === 0 &&
      eitherOrErrors.length === 0
    );
  }, [
    actionState.canUpdate,
    activeView,
    form,
    hasAmbiguousTemplateBindings,
    initialData,
    rawJson,
    uiSchema,
    updateMutation.isPending,
    validateEitherOrGroups,
  ]);

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
    setSaveAttempted(true);
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
    setSaveAttempted(false);
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
    if (!rollout.surfaces.editor) {
      setPendingAction('rebuild');
      updateMutation.mutate({ data: form.getValues(), rebuildFromTemplate: true });
      return;
    }
    setRebuildConfirmOpen(true);
  };

  const handleConfirmRebuild = () => {
    setRebuildConfirmOpen(false);
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
  const showErrorSummary = saveAttempted && (fieldErrors.length > 0 || Boolean(error));

  return (
    <div className="space-y-4">
      <DppOutlinePane
        context="submodel"
        mobile
        className="xl:hidden"
        nodes={outlineNodes}
        selectedId={selectedOutlineNodeId}
        onSelectNode={handleOutlineNodeSelect}
      />

      <div className="xl:grid xl:grid-cols-[minmax(260px,340px)_1fr] xl:gap-6">
        <DppOutlinePane
          context="submodel"
          className="hidden xl:block"
          nodes={outlineNodes}
          selectedId={selectedOutlineNodeId}
          onSelectNode={handleOutlineNodeSelect}
        />

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
          <p className="sr-only" aria-live="polite">
            {pendingAction === 'rebuild' && updateMutation.isPending ? 'Rebuilding submodel from template' : ''}
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
          {hasUnsupportedNodes && (
            <Alert>
              <AlertDescription className="text-xs">
                Unsupported template nodes detected ({unsupportedNodes.length}). Save and publish
                are blocked until renderer support is added for these nodes.
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

          {rollout.surfaces.editor && sectionProgress.length > 0 && (
            <section
              aria-label="Section completion progress"
              className="rounded-md border bg-muted/20 p-3"
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">Section Progress</p>
                <Badge variant="outline">
                  {completedRequiredAcrossSections}/{totalRequiredAcrossSections} required ({overallRequiredPercent}%)
                </Badge>
              </div>
              <Progress
                value={overallRequiredPercent}
                className="h-2"
                aria-label="Overall required section completion"
              />
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {sectionProgress.map((section) => (
                  <button
                    key={section.id}
                    type="button"
                    className="rounded-md border bg-background px-3 py-2 text-left text-xs hover:bg-accent/40"
                    onClick={() => {
                      const outlineNode = findOutlineNodeByPath(section.id);
                      if (outlineNode) {
                        setSelectedOutlineNodeId(outlineNode.id);
                      }
                      const focused = focusFieldPath(section.id);
                      if (!focused) {
                        const target = document.querySelector<HTMLElement>(`[data-field-path^="${section.id}."]`);
                        target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      }
                    }}
                  >
                    <p className="font-medium">{section.label}</p>
                    <p className="text-muted-foreground">
                      {section.totalRequired === 0
                        ? 'No required fields'
                        : `${section.completedRequired}/${section.totalRequired} required (${section.percent}%)`}
                    </p>
                  </button>
                ))}
              </div>
            </section>
          )}

          {showErrorSummary && (
            <section
              aria-label="Validation error summary"
              className="rounded-md border border-destructive/60 bg-destructive/5 p-3"
            >
              <h3 className="text-sm font-semibold text-destructive">Validation summary</h3>
              {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
              {fieldErrors.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs">
                  {fieldErrors.slice(0, 8).map((entry) => (
                    <li key={entry.path}>
                      <button
                        type="button"
                        className="text-left underline hover:no-underline"
                        onClick={() => {
                          const outlineNode = findOutlineNodeByPath(entry.path);
                          if (outlineNode) {
                            setSelectedOutlineNodeId(outlineNode.id);
                          }
                          void focusFieldPath(entry.path);
                        }}
                      >
                        {entry.path}: {entry.message}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <Tabs value={activeView} onValueChange={(v) => handleViewChange(v as 'form' | 'json')}>
            <TabsList>
              <TabsTrigger value="form" disabled={!uiSchema}>Form</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>
            <TabsContent value="form">
              <div className={cn(!actionState.canUpdate && 'opacity-90')}>
                <fieldset disabled={!actionState.canUpdate} className="space-y-4">
                  {hasDefinitionElements ? (
                    <AASRendererList
                      nodes={templateDefinition!.submodel!.elements!}
                      basePath=""
                      depth={0}
                      rootSchema={uiSchema}
                      control={form.control}
                      editorContext={editorContext}
                    />
                  ) : (
                    <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                      Form view is unavailable for this template. Switch to JSON.
                    </div>
                  )}
                </fieldset>
              </div>
            </TabsContent>
            <TabsContent value="json">
              <JsonEditor
                value={rawJson}
                readOnly={!actionState.canUpdate}
                onChange={(val) => {
                  setRawJson(val);
                  setHasEdited(true);
                }}
              />
            </TabsContent>
          </Tabs>
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
            canSave={canSave}
            saveDisabledReason={saveDisabledReason}
          />

          {rollout.surfaces.editor && (
            <Dialog open={rebuildConfirmOpen} onOpenChange={setRebuildConfirmOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Rebuild submodel from template?</DialogTitle>
                  <DialogDescription>
                    Rebuilding re-applies template defaults and can overwrite unsaved local edits.
                    This action creates a new DPP revision.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setRebuildConfirmOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleConfirmRebuild}
                    disabled={updateMutation.isPending}
                  >
                    Confirm rebuild
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
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
      </div>
    </div>
  );
}
