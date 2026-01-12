import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Layers, Plus, RefreshCcw, Save, Tag } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';

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
    queryKey: ['masters'],
    queryFn: () => fetchMasters(token),
  });

  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
  });

  const templates: TemplateOption[] = templatesData?.templates ?? [];

  const { data: masterDetail, refetch: refetchDetail } = useQuery({
    queryKey: ['master', selectedMasterId],
    queryFn: () => fetchMasterDetail(selectedMasterId ?? '', token),
    enabled: Boolean(selectedMasterId),
  });

  const { data: masterVersions } = useQuery({
    queryKey: ['master-versions', selectedMasterId],
    queryFn: () => fetchMasterVersions(selectedMasterId ?? '', token),
    enabled: Boolean(selectedMasterId),
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
      queryClient.invalidateQueries({ queryKey: ['masters'] });
      setShowCreateModal(false);
      setCreateError(null);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      updateMaster(selectedMasterId ?? '', payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['masters'] });
      void refetchDetail();
    },
  });

  const releaseMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      releaseMasterVersion(selectedMasterId ?? '', payload, token),
    onSuccess: () => {
      setReleaseVersion('');
      setReleaseAliases('');
      queryClient.invalidateQueries({ queryKey: ['masters'] });
      if (selectedMasterId) {
        queryClient.invalidateQueries({ queryKey: ['master', selectedMasterId] });
        queryClient.invalidateQueries({ queryKey: ['master-versions', selectedMasterId] });
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

    const normalizedTemplates =
      selectedTemplates.length > 0
        ? selectedTemplates
        : templates.length > 0
          ? [templates[0].template_key]
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">DPP Masters</h1>
          <p className="mt-1 text-sm text-gray-500">
            Build product-level templates with placeholders and release versions for ERP integration.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create Master
        </button>
      </div>

      {isLoading && <div className="text-sm text-gray-500">Loading masters...</div>}
      {isError && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(error as Error)?.message ?? 'Failed to load masters'}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[320px,1fr] gap-6">
        <div className="space-y-3">
          {(mastersData?.masters ?? []).map((master: MasterItem) => (
            <button
              key={master.id}
              onClick={() => setSelectedMasterId(master.id)}
              className={`w-full text-left rounded-lg border px-4 py-3 ${
                master.id === selectedMasterId
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">{master.name}</span>
                <Layers className="h-4 w-4 text-gray-400" />
              </div>
              <div className="mt-1 text-xs text-gray-500">{master.product_id}</div>
              <div className="mt-2 text-xs text-gray-400">
                Templates: {master.selected_templates?.length ?? 0}
              </div>
            </button>
          ))}
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-5">
          {!selectedMaster && (
            <div className="text-sm text-gray-500">Select a master to edit and release versions.</div>
          )}

          {selectedMaster && masterDetail && (
            <div className="space-y-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{selectedMaster.name}</h2>
                  <p className="text-sm text-gray-500">{selectedMaster.product_id}</p>
                </div>
                <button
                  onClick={() => void handleRefreshDetail()}
                  className="inline-flex items-center text-xs text-gray-500 hover:text-gray-700"
                >
                  <RefreshCcw className="h-3 w-3 mr-1" />
                  Refresh
                </button>
              </div>

              <div className="grid gap-4">
                <label className="text-xs font-medium text-gray-500">Name</label>
                <input
                  value={draftName}
                  onChange={(event) => setDraftName(event.target.value)}
                  className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                />

                <label className="text-xs font-medium text-gray-500">Description</label>
                <textarea
                  value={draftDescription}
                  onChange={(event) => setDraftDescription(event.target.value)}
                  className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                  rows={2}
                />
              </div>

              <div className="grid gap-4">
                <label className="text-xs font-medium text-gray-500">Draft Template JSON</label>
                <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                  <span>Insert placeholder:</span>
                  <input
                    value={placeholderName}
                    onChange={(event) => setPlaceholderName(event.target.value)}
                    placeholder="SerialNumber"
                    className="rounded-md border border-gray-200 px-2 py-1 text-xs"
                  />
                  <button
                    type="button"
                    onClick={handleInsertPlaceholder}
                    className="rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                  >
                    Insert
                  </button>
                  <span className="text-[11px] text-gray-400">
                    Tip: placeholders should stay inside JSON string values.
                  </span>
                </div>
                {placeholderError && (
                  <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                    {placeholderError}
                  </div>
                )}
                <textarea
                  value={draftJson}
                  onChange={(event) => setDraftJson(event.target.value)}
                  ref={templateTextareaRef}
                  className="h-56 w-full rounded-md border border-gray-200 px-3 py-2 font-mono text-xs"
                />
              </div>

              <div className="border border-gray-100 rounded-md p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                    <Layers className="h-4 w-4" />
                    Draft Variables (Structured)
                  </h3>
                  <button
                    type="button"
                    onClick={handleSyncVariables}
                    className="text-xs font-medium text-primary-600 hover:text-primary-700"
                  >
                    Sync from template
                  </button>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {Object.keys(placeholderPaths).length} placeholder(s) detected in draft template.
                </p>
                {parsedDraftVariables.error ? (
                  <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                    {parsedDraftVariables.error}
                  </div>
                ) : (
                  <div className="mt-3 space-y-3">
                    {parsedDraftVariables.value.length === 0 ? (
                      <div className="text-xs text-gray-500">
                        No variables defined. Sync placeholders or edit JSON directly.
                      </div>
                    ) : (
                      parsedDraftVariables.value.map((variable, index) => (
                        <div
                          key={`${variable.name}-${index}`}
                          className="rounded-md border border-gray-200 p-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="text-xs font-semibold text-gray-800">
                              {variable.name || 'Unnamed variable'}
                            </div>
                            <button
                              type="button"
                              onClick={() => handleVariableRemove(index)}
                              className="text-xs text-red-600 hover:text-red-700"
                            >
                              Remove
                            </button>
                          </div>
                          {placeholderPaths[variable.name] && (
                            <div className="mt-1 text-[11px] text-gray-500">
                              Paths: {placeholderPaths[variable.name].join(', ')}
                            </div>
                          )}
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            <label className="text-xs text-gray-600">
                              Label
                              <input
                                value={variable.label ?? ''}
                                onChange={(event) =>
                                  handleVariableUpdate(index, 'label', event.target.value)
                                }
                                className="mt-1 w-full rounded-md border border-gray-200 px-2 py-1 text-xs"
                              />
                            </label>
                            <label className="text-xs text-gray-600">
                              Type
                              <select
                                value={variable.expected_type ?? 'string'}
                                onChange={(event) =>
                                  handleVariableUpdate(index, 'expected_type', event.target.value)
                                }
                                className="mt-1 w-full rounded-md border border-gray-200 px-2 py-1 text-xs"
                              >
                                <option value="string">string</option>
                                <option value="number">number</option>
                                <option value="boolean">boolean</option>
                                <option value="date">date</option>
                                <option value="datetime">datetime</option>
                              </select>
                            </label>
                            <label className="text-xs text-gray-600">
                              Default Value
                              <input
                                value={coerceInputValue(variable.default_value)}
                                onChange={(event) =>
                                  handleVariableUpdate(
                                    index,
                                    'default_value',
                                    event.target.value || null
                                  )
                                }
                                className="mt-1 w-full rounded-md border border-gray-200 px-2 py-1 text-xs"
                              />
                            </label>
                            <div className="flex items-center gap-4">
                              <label className="flex items-center gap-2 text-xs text-gray-600">
                                <input
                                  type="checkbox"
                                  checked={Boolean(variable.required)}
                                  onChange={(event) =>
                                    handleVariableUpdate(index, 'required', event.target.checked)
                                  }
                                />
                                Required
                              </label>
                              <label className="flex items-center gap-2 text-xs text-gray-600">
                                <input
                                  type="checkbox"
                                  checked={Boolean(variable.allow_default)}
                                  onChange={(event) =>
                                    handleVariableUpdate(index, 'allow_default', event.target.checked)
                                  }
                                />
                                Allow default
                              </label>
                            </div>
                          </div>
                          <label className="mt-2 block text-xs text-gray-600">
                            Description
                            <textarea
                              value={variable.description ?? ''}
                              onChange={(event) =>
                                handleVariableUpdate(index, 'description', event.target.value)
                              }
                              className="mt-1 w-full rounded-md border border-gray-200 px-2 py-1 text-xs"
                              rows={2}
                            />
                          </label>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              <div className="grid gap-4">
                <label className="text-xs font-medium text-gray-500">Draft Variables JSON (Raw)</label>
                <textarea
                  value={draftVariables}
                  onChange={(event) => setDraftVariables(event.target.value)}
                  className="h-48 w-full rounded-md border border-gray-200 px-3 py-2 font-mono text-xs"
                />
              </div>

              <div className="flex items-center justify-between">
                <button
                  onClick={handleSaveDraft}
                  className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Save Draft
                </button>
                {updateMutation.isError && (
                  <span className="text-xs text-red-600">
                    {(updateMutation.error as Error)?.message ?? 'Failed to save'}
                  </span>
                )}
              </div>
              {draftParseError && (
                <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                  {draftParseError}
                </div>
              )}

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  Release Version
                </h3>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium text-gray-500">Version</label>
                    <input
                      value={releaseVersion}
                      onChange={(event) => setReleaseVersion(event.target.value)}
                      placeholder="1.0.0"
                      className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500">Aliases (comma separated)</label>
                    <input
                      value={releaseAliases}
                      onChange={(event) => setReleaseAliases(event.target.value)}
                      placeholder="latest, stable"
                      className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <button
                    onClick={handleRelease}
                    className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-gray-900 rounded-md hover:bg-gray-800"
                    disabled={!releaseVersion}
                  >
                    Release
                  </button>
                  {releaseMutation.isError && (
                    <span className="text-xs text-red-600">
                      {(releaseMutation.error as Error)?.message ?? 'Failed to release'}
                    </span>
                  )}
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                  <Layers className="h-4 w-4" />
                  Latest Release Preview
                </h3>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <select
                    value={previewVersion}
                    onChange={(event) => setPreviewVersion(event.target.value)}
                    className="rounded-md border border-gray-200 px-3 py-2 text-xs"
                  >
                    <option value="latest">latest</option>
                    {(masterVersions ?? []).map((version) => (
                      <option key={version.id} value={version.version}>
                        {version.version}{version.aliases.length > 0 ? ` · ${version.aliases.join(', ')}` : ''}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={handleLoadPreview}
                    className="inline-flex items-center px-3 py-2 text-xs font-medium text-white bg-gray-900 rounded-md hover:bg-gray-800"
                  >
                    {previewLoading ? 'Loading...' : 'Load Preview'}
                  </button>
                  {previewError && (
                    <span className="text-xs text-red-600">{previewError}</span>
                  )}
                </div>
                {previewTemplate && (
                  <div className="mt-3 space-y-3">
                    <div className="text-xs text-gray-600">
                      Version: {previewTemplate.version} · Aliases:{' '}
                      {previewTemplate.aliases.join(', ') || 'none'}
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-500">Template JSON</label>
                      <textarea
                        value={previewTemplate.template_string}
                        readOnly
                        className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-xs font-mono"
                        rows={6}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-500">Variables</label>
                      <div className="mt-1 rounded-md border border-gray-200 p-2 text-xs text-gray-600">
                        {previewTemplate.variables.length === 0
                          ? 'No variables defined for this release.'
                          : previewTemplate.variables.map((variable) => (
                              <div key={variable.name} className="py-1">
                                <span className="font-semibold">{variable.name}</span>
                                {variable.label ? ` · ${variable.label}` : ''}{' '}
                                {variable.required ? '(required)' : '(optional)'}
                              </div>
                            ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-xl rounded-lg bg-white p-6">
            <h2 className="text-lg font-semibold text-gray-900">Create Master</h2>
            <form onSubmit={handleCreate} className="mt-4 space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700">Product ID</label>
                <input
                  name="productId"
                  required
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Name</label>
                <input
                  name="name"
                  required
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Description</label>
                <textarea
                  name="description"
                  rows={2}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Manufacturer Part ID</label>
                <input
                  name="manufacturerPartId"
                  placeholder="Defaults to Product ID"
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Select Templates</label>
                <div className="mt-2 max-h-48 space-y-2 overflow-y-auto rounded-md border border-gray-200 p-3">
                  {templates.map((template) => (
                    <label key={template.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        name={`tpl-${template.template_key}`}
                        className="h-4 w-4 rounded border-gray-300 text-primary-600"
                      />
                      <span>{template.template_key}</span>
                      <span className="text-xs text-gray-400">v{template.idta_version}</span>
                    </label>
                  ))}
                  {templates.length === 0 && (
                    <span className="text-sm text-gray-500">No templates available.</span>
                  )}
                </div>
              </div>
              {createMutation.isError && (
                <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                  {(createMutation.error as Error)?.message ?? 'Failed to create master'}
                </div>
              )}
              {createError && (
                <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                  {createError}
                </div>
              )}
              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
