import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Layers, Plus, RefreshCcw, Save, Tag } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

interface MasterItem {
  id: string;
  product_id: string;
  name: string;
  description?: string | null;
  selected_templates: string[];
  created_at: string;
  updated_at: string;
}

interface MasterDetail extends MasterItem {
  draft_template_json: Record<string, unknown>;
  draft_variables: Array<Record<string, unknown>>;
}

interface TemplateOption {
  id: string;
  template_key: string;
  idta_version: string;
  support_status?: 'supported' | 'experimental' | 'unavailable';
  refresh_enabled?: boolean;
}

function isTemplateSelectable(template: TemplateOption): boolean {
  return template.support_status !== 'unavailable' && template.refresh_enabled !== false;
}

type PlaceholderPaths = Record<string, string[]>;

interface VariableDraft {
  name: string;
  label?: string | null;
  description?: string | null;
  required?: boolean;
  default_value?: unknown;
  allow_default?: boolean;
  expected_type?: string;
  constraints?: Record<string, unknown> | null;
}

interface TemplatePackage {
  master_id: string;
  product_id: string;
  name: string;
  version: string;
  aliases: string[];
  template_string: string;
  variables: Array<VariableDraft & { paths?: Array<Record<string, string>> }>;
}

interface MasterVersion {
  id: string;
  version: string;
  aliases: string[];
  status: string;
  released_at: string;
}

async function fetchMasters(token?: string) {
  const response = await tenantApiFetch('/masters', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch masters'));
  }
  return response.json();
}

async function fetchMasterDetail(masterId: string, token?: string) {
  const response = await tenantApiFetch(`/masters/${masterId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch master detail'));
  }
  return response.json();
}

async function fetchTemplates(token?: string) {
  const response = await apiFetch('/api/v1/templates', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch templates'));
  }
  return response.json();
}

async function fetchMasterVersions(masterId: string, token?: string): Promise<MasterVersion[]> {
  const response = await tenantApiFetch(`/masters/${masterId}/versions`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch versions'));
  }
  return response.json();
}

async function fetchTemplatePackage(
  productId: string,
  version: string,
  token?: string
): Promise<TemplatePackage> {
  const response = await tenantApiFetch(
    `/masters/by-product/${encodeURIComponent(productId)}/versions/${encodeURIComponent(version)}/template`,
    {},
    token
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch template package'));
  }
  return response.json();
}

async function createMaster(payload: Record<string, unknown>, token?: string) {
  const response = await tenantApiFetch('/masters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to create master'));
  }
  return response.json();
}

async function updateMaster(masterId: string, payload: Record<string, unknown>, token?: string) {
  const response = await tenantApiFetch(`/masters/${masterId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to update master'));
  }
  return response.json();
}

async function releaseMasterVersion(masterId: string, payload: Record<string, unknown>, token?: string) {
  const response = await tenantApiFetch(`/masters/${masterId}/versions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to release version'));
  }
  return response.json();
}

const PLACEHOLDER_PATTERN = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function encodeJsonPointerSegment(segment: string) {
  return segment.replace(/~/g, '~0').replace(/\//g, '~1');
}

function extractPlaceholderPaths(value: unknown, pointer = ''): PlaceholderPaths {
  const paths: PlaceholderPaths = {};

  const walk = (node: unknown, path: string) => {
    if (Array.isArray(node)) {
      node.forEach((item, index) => walk(item, `${path}/${index}`));
      return;
    }
    if (node && typeof node === 'object') {
      Object.entries(node as Record<string, unknown>).forEach(([key, child]) => {
        walk(child, `${path}/${encodeJsonPointerSegment(key)}`);
      });
      return;
    }
    if (typeof node === 'string') {
      for (const match of node.matchAll(PLACEHOLDER_PATTERN)) {
        const name = match[1];
        if (!paths[name]) paths[name] = [];
        paths[name].push(path || '/');
      }
    }
  };

  walk(value, pointer);
  return paths;
}

function humanizePlaceholder(name: string) {
  if (!name) return '';
  return name
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .replace(/^./, (char) => char.toUpperCase());
}

function coerceInputValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return '';
  }
}

export default function MastersPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const tenantSlug = getTenantSlug();
  const queryClient = useQueryClient();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedMasterId, setSelectedMasterId] = useState<string | null>(null);
  const [releaseVersion, setReleaseVersion] = useState('');
  const [releaseAliases, setReleaseAliases] = useState('');

  const [draftJson, setDraftJson] = useState('');
  const [draftVariables, setDraftVariables] = useState('');
  const [draftName, setDraftName] = useState('');
  const [draftDescription, setDraftDescription] = useState('');
  const [draftParseError, setDraftParseError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [placeholderName, setPlaceholderName] = useState('');
  const [placeholderError, setPlaceholderError] = useState<string | null>(null);
  const [previewVersion, setPreviewVersion] = useState('latest');
  const [previewTemplate, setPreviewTemplate] = useState<TemplatePackage | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const templateTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  const { data: mastersData, isLoading, isError, error } = useQuery({
    queryKey: ['masters', tenantSlug],
    queryFn: () => fetchMasters(token),
    enabled: Boolean(token),
  });

  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
    enabled: Boolean(token),
  });

  const templates: TemplateOption[] = templatesData?.templates ?? [];

  const { data: masterDetail, refetch: refetchDetail } = useQuery({
    queryKey: ['master', tenantSlug, selectedMasterId],
    queryFn: () => fetchMasterDetail(selectedMasterId ?? '', token),
    enabled: Boolean(token && selectedMasterId),
  });

  const { data: masterVersions } = useQuery({
    queryKey: ['master-versions', tenantSlug, selectedMasterId],
    queryFn: () => fetchMasterVersions(selectedMasterId ?? '', token),
    enabled: Boolean(token && selectedMasterId),
  });

  const applyMasterDetail = useCallback((detail: MasterDetail) => {
    setDraftName(detail.name ?? '');
    setDraftDescription(detail.description ?? '');
    setDraftJson(JSON.stringify(detail.draft_template_json ?? {}, null, 2));
    setDraftVariables(JSON.stringify(detail.draft_variables ?? [], null, 2));
    setDraftParseError(null);
    setPreviewTemplate(null);
    setPreviewError(null);
    setPreviewVersion('latest');
  }, []);

  useEffect(() => {
    if (!masterDetail) return;
    applyMasterDetail(masterDetail);
  }, [masterDetail, applyMasterDetail]);

  const parsedDraftJson = useMemo(() => {
    try {
      return { value: JSON.parse(draftJson || '{}'), error: null as string | null };
    } catch {
      return { value: null, error: 'Draft template JSON is invalid.' };
    }
  }, [draftJson]);

  const parsedDraftVariables = useMemo(() => {
    try {
      const parsed = JSON.parse(draftVariables || '[]');
      if (Array.isArray(parsed)) {
        return { value: parsed as VariableDraft[], error: null as string | null };
      }
      return { value: [] as VariableDraft[], error: 'Draft variables JSON must be an array.' };
    } catch {
      return { value: [] as VariableDraft[], error: 'Draft variables JSON is invalid.' };
    }
  }, [draftVariables]);

  const placeholderPaths = useMemo(() => {
    if (!parsedDraftJson.value) return {};
    return extractPlaceholderPaths(parsedDraftJson.value);
  }, [parsedDraftJson.value]);

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => createMaster(payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['masters', tenantSlug] });
      setShowCreateModal(false);
      setCreateError(null);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      updateMaster(selectedMasterId ?? '', payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['masters', tenantSlug] });
      void refetchDetail();
    },
  });

  const releaseMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      releaseMasterVersion(selectedMasterId ?? '', payload, token),
    onSuccess: () => {
      setReleaseVersion('');
      setReleaseAliases('');
      queryClient.invalidateQueries({ queryKey: ['masters', tenantSlug] });
      if (selectedMasterId) {
        queryClient.invalidateQueries({ queryKey: ['master', tenantSlug, selectedMasterId] });
        queryClient.invalidateQueries({ queryKey: ['master-versions', tenantSlug, selectedMasterId] });
      }
    },
  });

  const handleSyncVariables = () => {
    if (parsedDraftJson.error) {
      setDraftParseError(parsedDraftJson.error);
      return;
    }
    const placeholders = Object.keys(placeholderPaths);
    const current = parsedDraftVariables.value;
    const existing = new Map(current.map((entry) => [entry.name, entry]));
    const next = [...current];
    placeholders.forEach((name) => {
      if (!existing.has(name)) {
        next.push({
          name,
          label: humanizePlaceholder(name),
          description: null,
          required: true,
          default_value: null,
          allow_default: true,
          expected_type: 'string',
          constraints: null,
        });
      }
    });
    setDraftVariables(JSON.stringify(next, null, 2));
    setDraftParseError(null);
  };

  const handleVariableUpdate = (
    index: number,
    field: keyof VariableDraft,
    value: VariableDraft[keyof VariableDraft]
  ) => {
    const next = parsedDraftVariables.value.map((entry, idx) => {
      if (idx !== index) return entry;
      return { ...entry, [field]: value };
    });
    setDraftVariables(JSON.stringify(next, null, 2));
  };

  const handleVariableRemove = (index: number) => {
    const next = parsedDraftVariables.value.filter((_, idx) => idx !== index);
    setDraftVariables(JSON.stringify(next, null, 2));
  };

  const handleLoadPreview = async () => {
    if (!selectedMaster || !token) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const data = await fetchTemplatePackage(selectedMaster.product_id, previewVersion, token);
      setPreviewTemplate(data);
    } catch (err) {
      setPreviewTemplate(null);
      setPreviewError((err as Error)?.message ?? 'Failed to load template preview.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleInsertPlaceholder = () => {
    const trimmed = placeholderName.trim();
    if (!trimmed) {
      setPlaceholderError('Enter a placeholder name to insert.');
      return;
    }
    const textarea = templateTextareaRef.current;
    const placeholder = `{{${trimmed}}}`;
    if (!textarea) {
      setPlaceholderError('Template editor is not ready.');
      return;
    }
    const start = textarea.selectionStart ?? draftJson.length;
    const end = textarea.selectionEnd ?? draftJson.length;
    const next = `${draftJson.slice(0, start)}${placeholder}${draftJson.slice(end)}`;
    setDraftJson(next);
    setPlaceholderError(null);
    setPlaceholderName('');
    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + placeholder.length;
      textarea.setSelectionRange(cursor, cursor);
    });
  };

  const handleRefreshDetail = async () => {
    const result = await refetchDetail();
    if (result.data) {
      applyMasterDetail(result.data);
    }
  };

  const handleCreate = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const productId = String(formData.get('productId') ?? '').trim();
    const name = String(formData.get('name') ?? '').trim();
    const description = String(formData.get('description') ?? '').trim();
    const manufacturerPartId =
      String(formData.get('manufacturerPartId') ?? '').trim() || productId;

    const selectedTemplates = templates
      .filter((template) => formData.get(`tpl-${template.template_key}`))
      .map((template) => template.template_key);

    const selectableTemplates = templates.filter((template) => isTemplateSelectable(template));
    const normalizedTemplates =
      selectedTemplates.length > 0
        ? selectedTemplates
        : selectableTemplates.length > 0
          ? [selectableTemplates[0].template_key]
          : [];

    if (normalizedTemplates.length === 0) {
      setCreateError('Select at least one template before creating a master.');
      return;
    }

    setCreateError(null);
    createMutation.mutate({
      product_id: productId,
      name,
      description: description || null,
      selected_templates: normalizedTemplates,
      asset_ids: { manufacturerPartId },
    });
  };

  const handleSaveDraft = () => {
    let templateJson: Record<string, unknown> = {};
    let variables: Array<Record<string, unknown>> = [];
    try {
      templateJson = JSON.parse(draftJson || '{}');
    } catch {
      setDraftParseError('Draft template JSON is invalid.');
      return;
    }
    try {
      variables = JSON.parse(draftVariables || '[]');
    } catch {
      setDraftParseError('Draft variables JSON is invalid.');
      return;
    }

    setDraftParseError(null);
    updateMutation.mutate({
      name: draftName,
      description: draftDescription,
      template_json: templateJson,
      variables,
    });
  };

  const handleRelease = () => {
    const aliases = releaseAliases
      .split(',')
      .map((alias) => alias.trim())
      .filter(Boolean);
    releaseMutation.mutate({
      version: releaseVersion,
      aliases,
      update_latest: true,
    });
  };

  const selectedMaster = useMemo(
    () => mastersData?.masters?.find((master: MasterItem) => master.id === selectedMasterId),
    [mastersData?.masters, selectedMasterId]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="DPP Masters"
        description="Build product-level templates with placeholders and release versions for ERP integration."
        actions={
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Master
          </Button>
        }
      />

      {isLoading && <LoadingSpinner />}
      {isError && (
        <ErrorBanner
          message={(error as Error)?.message ?? 'Failed to load masters'}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[320px,1fr] gap-6">
        <div className="space-y-3">
          {(mastersData?.masters ?? []).map((master: MasterItem) => (
            <Card
              key={master.id}
              className={cn(
                'cursor-pointer transition-colors',
                master.id === selectedMasterId
                  ? 'border-primary bg-primary/5'
                  : 'hover:border-muted-foreground/30'
              )}
              onClick={() => setSelectedMasterId(master.id)}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{master.name}</span>
                  <Layers className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{master.product_id}</div>
                <div className="mt-2 text-xs text-muted-foreground">
                  Templates: {master.selected_templates?.length ?? 0}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardContent className="p-5">
            {!selectedMaster && (
              <p className="text-sm text-muted-foreground">Select a master to edit and release versions.</p>
            )}

            {selectedMaster && masterDetail && (
              <div className="space-y-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedMaster.name}</h2>
                    <p className="text-sm text-muted-foreground">{selectedMaster.product_id}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleRefreshDetail()}
                  >
                    <RefreshCcw className="h-3 w-3 mr-1" />
                    Refresh
                  </Button>
                </div>

                <div className="grid gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Name</Label>
                    <Input
                      value={draftName}
                      onChange={(event) => setDraftName(event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Description</Label>
                    <Textarea
                      value={draftDescription}
                      onChange={(event) => setDraftDescription(event.target.value)}
                      rows={2}
                    />
                  </div>
                </div>

                <div className="grid gap-4">
                  <Label className="text-xs">Draft Template JSON</Label>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>Insert placeholder:</span>
                    <Input
                      value={placeholderName}
                      onChange={(event) => setPlaceholderName(event.target.value)}
                      placeholder="SerialNumber"
                      className="h-7 w-40 text-xs"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={handleInsertPlaceholder}
                    >
                      Insert
                    </Button>
                    <span className="text-[11px] text-muted-foreground">
                      Tip: placeholders should stay inside JSON string values.
                    </span>
                  </div>
                  {placeholderError && (
                    <ErrorBanner message={placeholderError} />
                  )}
                  <Textarea
                    value={draftJson}
                    onChange={(event) => setDraftJson(event.target.value)}
                    ref={templateTextareaRef}
                    className="h-56 font-mono text-xs"
                  />
                </div>

                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Layers className="h-4 w-4" />
                        Draft Variables (Structured)
                      </CardTitle>
                      <Button
                        type="button"
                        variant="link"
                        size="sm"
                        className="text-xs"
                        onClick={handleSyncVariables}
                      >
                        Sync from template
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {Object.keys(placeholderPaths).length} placeholder(s) detected in draft template.
                    </p>
                  </CardHeader>
                  <CardContent>
                    {parsedDraftVariables.error ? (
                      <ErrorBanner message={parsedDraftVariables.error} />
                    ) : (
                      <div className="space-y-3">
                        {parsedDraftVariables.value.length === 0 ? (
                          <div className="text-xs text-muted-foreground">
                            No variables defined. Sync placeholders or edit JSON directly.
                          </div>
                        ) : (
                          parsedDraftVariables.value.map((variable, index) => (
                            <Card
                              key={`${variable.name}-${index}`}
                              className="p-3"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="text-xs font-semibold">
                                  {variable.name || 'Unnamed variable'}
                                </div>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="text-xs text-destructive hover:text-destructive h-auto py-1"
                                  onClick={() => handleVariableRemove(index)}
                                >
                                  Remove
                                </Button>
                              </div>
                              {placeholderPaths[variable.name] && (
                                <div className="mt-1 text-[11px] text-muted-foreground">
                                  Paths: {placeholderPaths[variable.name].join(', ')}
                                </div>
                              )}
                              <div className="mt-2 grid gap-2 md:grid-cols-2">
                                <div className="space-y-1">
                                  <Label className="text-xs">Label</Label>
                                  <Input
                                    value={variable.label ?? ''}
                                    onChange={(event) =>
                                      handleVariableUpdate(index, 'label', event.target.value)
                                    }
                                    className="h-7 text-xs"
                                  />
                                </div>
                                <div className="space-y-1">
                                  <Label className="text-xs">Type</Label>
                                  <select
                                    value={variable.expected_type ?? 'string'}
                                    onChange={(event) =>
                                      handleVariableUpdate(index, 'expected_type', event.target.value)
                                    }
                                    className="flex h-7 w-full rounded-md border border-input bg-background px-2 py-1 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                                  >
                                    <option value="string">string</option>
                                    <option value="number">number</option>
                                    <option value="boolean">boolean</option>
                                    <option value="date">date</option>
                                    <option value="datetime">datetime</option>
                                  </select>
                                </div>
                                <div className="space-y-1">
                                  <Label className="text-xs">Default Value</Label>
                                  <Input
                                    value={coerceInputValue(variable.default_value)}
                                    onChange={(event) =>
                                      handleVariableUpdate(
                                        index,
                                        'default_value',
                                        event.target.value || null
                                      )
                                    }
                                    className="h-7 text-xs"
                                  />
                                </div>
                                <div className="flex items-center gap-4 pt-4">
                                  <div className="flex items-center gap-2">
                                    <Checkbox
                                      id={`required-${index}`}
                                      checked={Boolean(variable.required)}
                                      onCheckedChange={(checked) =>
                                        handleVariableUpdate(index, 'required', Boolean(checked))
                                      }
                                    />
                                    <Label htmlFor={`required-${index}`} className="text-xs">Required</Label>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <Checkbox
                                      id={`allow-default-${index}`}
                                      checked={Boolean(variable.allow_default)}
                                      onCheckedChange={(checked) =>
                                        handleVariableUpdate(index, 'allow_default', Boolean(checked))
                                      }
                                    />
                                    <Label htmlFor={`allow-default-${index}`} className="text-xs">Allow default</Label>
                                  </div>
                                </div>
                              </div>
                              <div className="mt-2 space-y-1">
                                <Label className="text-xs">Description</Label>
                                <Textarea
                                  value={variable.description ?? ''}
                                  onChange={(event) =>
                                    handleVariableUpdate(index, 'description', event.target.value)
                                  }
                                  className="text-xs"
                                  rows={2}
                                />
                              </div>
                            </Card>
                          ))
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <div className="grid gap-4">
                  <Label className="text-xs">Draft Variables JSON (Raw)</Label>
                  <Textarea
                    value={draftVariables}
                    onChange={(event) => setDraftVariables(event.target.value)}
                    className="h-48 font-mono text-xs"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Button onClick={handleSaveDraft}>
                    <Save className="h-4 w-4 mr-2" />
                    Save Draft
                  </Button>
                  {updateMutation.isError && (
                    <span className="text-xs text-destructive">
                      {(updateMutation.error as Error)?.message ?? 'Failed to save'}
                    </span>
                  )}
                </div>
                {draftParseError && (
                  <ErrorBanner message={draftParseError} />
                )}

                <Separator />

                <div className="space-y-3">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Tag className="h-4 w-4" />
                    Release Version
                  </h3>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-1">
                      <Label className="text-xs">Version</Label>
                      <Input
                        value={releaseVersion}
                        onChange={(event) => setReleaseVersion(event.target.value)}
                        placeholder="1.0.0"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Aliases (comma separated)</Label>
                      <Input
                        value={releaseAliases}
                        onChange={(event) => setReleaseAliases(event.target.value)}
                        placeholder="latest, stable"
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <Button
                      variant="secondary"
                      onClick={handleRelease}
                      disabled={!releaseVersion}
                    >
                      Release
                    </Button>
                    {releaseMutation.isError && (
                      <span className="text-xs text-destructive">
                        {(releaseMutation.error as Error)?.message ?? 'Failed to release'}
                      </span>
                    )}
                  </div>
                </div>

                <Separator />

                <div className="space-y-3">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Layers className="h-4 w-4" />
                    Latest Release Preview
                  </h3>
                  <div className="flex flex-wrap items-center gap-3">
                    <select
                      value={previewVersion}
                      onChange={(event) => setPreviewVersion(event.target.value)}
                      className="flex h-9 rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    >
                      <option value="latest">latest</option>
                      {(masterVersions ?? []).map((version) => (
                        <option key={version.id} value={version.version}>
                          {version.version}{version.aliases.length > 0 ? ` · ${version.aliases.join(', ')}` : ''}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleLoadPreview}
                    >
                      {previewLoading ? 'Loading...' : 'Load Preview'}
                    </Button>
                    {previewError && (
                      <span className="text-xs text-destructive">{previewError}</span>
                    )}
                  </div>
                  {previewTemplate && (
                    <div className="space-y-3">
                      <div className="text-xs text-muted-foreground">
                        Version: {previewTemplate.version} · Aliases:{' '}
                        {previewTemplate.aliases.join(', ') || 'none'}
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Template JSON</Label>
                        <Textarea
                          value={previewTemplate.template_string}
                          readOnly
                          className="font-mono text-xs"
                          rows={6}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Variables</Label>
                        <Card className="p-2 text-xs text-muted-foreground">
                          {previewTemplate.variables.length === 0
                            ? 'No variables defined for this release.'
                            : previewTemplate.variables.map((variable) => (
                                <div key={variable.name} className="py-1">
                                  <span className="font-semibold">{variable.name}</span>
                                  {variable.label ? ` · ${variable.label}` : ''}{' '}
                                  {variable.required ? '(required)' : '(optional)'}
                                </div>
                              ))}
                        </Card>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Create Master</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Product ID</Label>
              <Input name="productId" required />
            </div>
            <div className="space-y-2">
              <Label>Name</Label>
              <Input name="name" required />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea name="description" rows={2} />
            </div>
            <div className="space-y-2">
              <Label>Manufacturer Part ID</Label>
              <Input name="manufacturerPartId" placeholder="Defaults to Product ID" />
            </div>
            <div className="space-y-2">
              <Label>Select Templates</Label>
              <div className="max-h-48 space-y-2 overflow-y-auto rounded-md border p-3">
                {templates.map((template) => (
                  <label key={template.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      name={`tpl-${template.template_key}`}
                      disabled={!isTemplateSelectable(template)}
                      className="h-4 w-4 rounded border-gray-300 text-primary"
                    />
                    <span>{template.template_key}</span>
                    <span className="text-xs text-muted-foreground">v{template.idta_version}</span>
                    {template.support_status === 'unavailable' && (
                      <span className="text-xs text-destructive">unavailable</span>
                    )}
                  </label>
                ))}
                {templates.length === 0 && (
                  <span className="text-sm text-muted-foreground">No templates available.</span>
                )}
              </div>
            </div>
            {createMutation.isError && (
              <ErrorBanner
                message={(createMutation.error as Error)?.message ?? 'Failed to create master'}
              />
            )}
            {createError && (
              <ErrorBanner message={createError} />
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreateModal(false)}
              >
                Cancel
              </Button>
              <Button type="submit">
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
