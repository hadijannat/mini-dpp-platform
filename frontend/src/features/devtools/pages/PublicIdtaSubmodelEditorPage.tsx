import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Download, FileUp, RefreshCw } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useSubmodelForm } from '@/features/editor/hooks/useSubmodelForm';
import { AASRendererList } from '@/features/editor/components/AASRenderer';
import { JsonEditor } from '@/features/editor/components/JsonEditor';
import { SubmodelEditorShell } from '@/features/editor/components/SubmodelEditorShell';
import type { TemplateContractResponse, TemplateDefinition } from '@/features/editor/types/definition';
import type { UISchema } from '@/features/editor/types/uiSchema';
import {
  createSmtDraftId,
  deleteSmtDraft,
  exportSmtDraftRecord,
  getSmtDraft,
  listSmtDrafts,
  parseSmtDraftRecord,
  saveSmtDraft,
  type SmtDraftRecord,
} from '../lib/smtDraftStorage';
import {
  exportPublicTemplate,
  getPublicTemplate,
  getPublicTemplateContract,
  listPublicTemplateVersions,
  listPublicTemplates,
  previewPublicTemplate,
  type PublicExportFormat,
  type PublicTemplateStatus,
} from '../lib/publicSmtApi';

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function sanitizeDraftFilename(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]/g, '-');
}

function normalizeDiagnosticEntry(entry: string): string | null {
  const compact = entry.replace(/\s+/g, ' ').trim();
  if (!compact) return null;
  if (/^root$/i.test(compact)) return null;
  if (/^root(?:\s*[|/,:>]\s*root)+$/i.test(compact)) return null;
  if (/^root[.:]\s*/i.test(compact)) {
    const withoutRoot = compact.replace(/^root[.:]\s*/i, '').trim();
    return withoutRoot || null;
  }
  return compact;
}

function normalizeDiagnosticMessages(values: string[]): string[] {
  const deduped = new Set<string>();
  for (const value of values) {
    for (const segment of value.split('|')) {
      const normalized = normalizeDiagnosticEntry(segment);
      if (normalized) {
        deduped.add(normalized);
      }
    }
  }
  return Array.from(deduped);
}

function normalizeErrorMessage(value: string): string {
  const messages = normalizeDiagnosticMessages([value]);
  if (messages.length === 0) {
    return 'Validation failed. Review required fields and try again.';
  }
  return messages.join(' • ');
}

function buildWarningNotice(warnings: string[]): string | null {
  const messages = normalizeDiagnosticMessages(warnings);
  if (messages.length === 0) return null;
  if (messages.length === 1) return messages[0];
  return `${messages.length} notices: ${messages.join(' • ')}`;
}

export default function PublicIdtaSubmodelEditorPage() {
  const [statusFilter, setStatusFilter] = useState<PublicTemplateStatus>('published');
  const [search, setSearch] = useState('');
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string>('');
  const [selectedVersion, setSelectedVersion] = useState<string>('');
  const [activeView, setActiveView] = useState<'form' | 'json' | 'preview'>('form');
  const [rawJson, setRawJson] = useState('{}');
  const [previewText, setPreviewText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [hasUserInteracted, setHasUserInteracted] = useState(false);
  const [drafts, setDrafts] = useState<SmtDraftRecord[]>(() => listSmtDrafts());
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);
  const pendingDraftRef = useRef<SmtDraftRecord | null>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const templatesQuery = useQuery({
    queryKey: ['public-smt-templates', statusFilter, search],
    queryFn: () => listPublicTemplates({ status: statusFilter, search }),
  });

  const selectedTemplate = useMemo(
    () => templatesQuery.data?.templates.find((template) => template.template_key === selectedTemplateKey) ?? null,
    [templatesQuery.data?.templates, selectedTemplateKey],
  );

  const templateDetailQuery = useQuery({
    queryKey: ['public-smt-template', selectedTemplateKey],
    queryFn: () => getPublicTemplate(selectedTemplateKey),
    enabled: Boolean(selectedTemplateKey),
  });

  const versionsQuery = useQuery({
    queryKey: ['public-smt-versions', selectedTemplateKey],
    queryFn: () => listPublicTemplateVersions(selectedTemplateKey),
    enabled: Boolean(selectedTemplateKey),
  });

  const contractQuery = useQuery<TemplateContractResponse>({
    queryKey: ['public-smt-contract', selectedTemplateKey, selectedVersion],
    queryFn: () => getPublicTemplateContract(selectedTemplateKey, selectedVersion || undefined),
    enabled: Boolean(selectedTemplateKey),
  });

  useEffect(() => {
    if (selectedTemplateKey) return;
    const first = templatesQuery.data?.templates[0];
    if (first) {
      setSelectedTemplateKey(first.template_key);
      setSelectedVersion(first.latest_version);
    }
  }, [selectedTemplateKey, templatesQuery.data?.templates]);

  useEffect(() => {
    if (!versionsQuery.data?.versions?.length) return;
    if (selectedVersion && versionsQuery.data.versions.some((version) => version.version === selectedVersion)) {
      return;
    }
    const preferred = versionsQuery.data.versions.find((version) => version.is_default);
    setSelectedVersion(preferred?.version ?? versionsQuery.data.versions[0].version);
  }, [selectedVersion, versionsQuery.data?.versions]);

  const templateDefinition = contractQuery.data?.definition as TemplateDefinition | undefined;
  const uiSchema = contractQuery.data?.schema as UISchema | undefined;
  const { form } = useSubmodelForm(templateDefinition, uiSchema, {});
  const hasDefinitionElements = Boolean(templateDefinition?.submodel?.elements?.length);
  const diagnostics = useMemo(() => {
    const unsupported = contractQuery.data?.unsupported_nodes ?? [];
    const report = contractQuery.data?.dropin_resolution_report ?? [];
    const unresolved = report.filter((entry) => {
      if (!entry || typeof entry !== 'object') return false;
      const statusValue = (entry as { status?: unknown }).status;
      const status = typeof statusValue === 'string' ? statusValue.toLowerCase() : '';
      return status !== 'resolved' && status !== 'skipped';
    });
    return { unsupported, unresolved };
  }, [contractQuery.data?.dropin_resolution_report, contractQuery.data?.unsupported_nodes]);

  const syncDraftList = () => setDrafts(listSmtDrafts());

  const applyDraft = (draft: SmtDraftRecord) => {
    pendingDraftRef.current = draft;
    setHasUserInteracted(false);
    setActiveDraftId(draft.draftId);
    if (selectedTemplateKey !== draft.templateKey) {
      setSelectedTemplateKey(draft.templateKey);
    }
    if (selectedVersion !== draft.version) {
      setSelectedVersion(draft.version);
    }

    if (selectedTemplateKey === draft.templateKey && selectedVersion === draft.version) {
      form.reset(draft.data);
      setRawJson(JSON.stringify(draft.data, null, 2));
      pendingDraftRef.current = null;
    }
  };

  useEffect(() => {
    if (!pendingDraftRef.current) return;
    if (!contractQuery.data) return;
    const pending = pendingDraftRef.current;
    if (pending.templateKey !== selectedTemplateKey || pending.version !== selectedVersion) return;
    form.reset(pending.data);
    setRawJson(JSON.stringify(pending.data, null, 2));
    pendingDraftRef.current = null;
  }, [contractQuery.data, form, selectedTemplateKey, selectedVersion]);

  useEffect(() => {
    if (!contractQuery.data || pendingDraftRef.current) return;
    const matching = drafts.find(
      (draft) => draft.templateKey === selectedTemplateKey && draft.version === selectedVersion,
    );
    if (matching) {
      if (activeDraftId === matching.draftId) return;
      setActiveDraftId(matching.draftId);
      form.reset(matching.data);
      setRawJson(JSON.stringify(matching.data, null, 2));
      return;
    }
    setActiveDraftId(null);
    form.reset({});
    setRawJson('{}');
  }, [activeDraftId, contractQuery.data, drafts, form, selectedTemplateKey, selectedVersion]);

  useEffect(() => {
    setHasUserInteracted(false);
    setPreviewText('');
  }, [selectedTemplateKey, selectedVersion]);

  const [debouncedFormValues, setDebouncedFormValues] = useState(() => form.getValues());
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    const subscription = form.watch((values, meta) => {
      if (meta?.type === 'change' || meta?.type === 'blur') {
        setHasUserInteracted(true);
      }
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        setDebouncedFormValues({ ...values } as Record<string, unknown>);
      }, 350);
    });
    return () => {
      clearTimeout(debounceRef.current);
      subscription.unsubscribe();
    };
  }, [form]);

  const saveDraftInternal = useCallback(
    (options: { forceNew?: boolean; providedName?: string } = {}): SmtDraftRecord | null => {
      if (!selectedTemplateKey || !selectedVersion) return null;
      const values = form.getValues();
      const name =
        options.providedName?.trim() ||
        selectedTemplate?.display_name ||
        `${selectedTemplateKey} ${selectedVersion}`;
      const draftId =
        options.forceNew || !activeDraftId
          ? createSmtDraftId(selectedTemplateKey, selectedVersion)
          : activeDraftId;
      const record = saveSmtDraft({
        draftId,
        name,
        templateKey: selectedTemplateKey,
        version: selectedVersion,
        data: values,
      });
      setActiveDraftId(record.draftId);
      syncDraftList();
      return record;
    },
    [activeDraftId, form, selectedTemplate?.display_name, selectedTemplateKey, selectedVersion],
  );

  const autosaveRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    if (!selectedTemplateKey || !selectedVersion || !contractQuery.data) return;
    clearTimeout(autosaveRef.current);
    autosaveRef.current = setTimeout(() => {
      saveDraftInternal();
    }, 2000);
    return () => clearTimeout(autosaveRef.current);
  }, [contractQuery.data, debouncedFormValues, saveDraftInternal, selectedTemplateKey, selectedVersion]);

  const previewMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      previewPublicTemplate({
        template_key: selectedTemplateKey,
        version: selectedVersion || undefined,
        data: payload,
      }),
    onSuccess: (result) => {
      if (!result || typeof result !== 'object') return;
      setPreviewText(JSON.stringify(result.aas_environment, null, 2));
      setError(null);
      setNotice(buildWarningNotice(result.warnings));
    },
    onError: (previewError) => {
      const rawMessage = previewError instanceof Error ? previewError.message : 'Failed to generate preview';
      setError(normalizeErrorMessage(rawMessage));
      setNotice(null);
    },
  });

  useEffect(() => {
    if (!hasUserInteracted) return;
    if (!selectedTemplateKey || !contractQuery.data || activeView === 'json') return;
    if (previewMutation.isPending) return;
    void previewMutation.mutateAsync(debouncedFormValues);
    // previewMutation object identity may change between renders; triggering on
    // form/template state keeps this effect stable for autosync preview.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeView,
    contractQuery.data,
    debouncedFormValues,
    hasUserInteracted,
    selectedTemplateKey,
    selectedVersion,
  ]);

  const handleRawJsonChange = (value: string) => {
    setRawJson(value);
    setHasUserInteracted(true);
  };

  const resolveCurrentData = (): Record<string, unknown> | null => {
    if (activeView === 'json') {
      try {
        return JSON.parse(rawJson) as Record<string, unknown>;
      } catch {
        setError('Raw JSON is invalid. Fix formatting before exporting.');
        return null;
      }
    }
    return form.getValues();
  };

  const exportMutation = useMutation({
    mutationFn: async ({ format, payload }: { format: PublicExportFormat; payload: Record<string, unknown> }) =>
      exportPublicTemplate({
        template_key: selectedTemplateKey,
        version: selectedVersion || undefined,
        data: payload,
        format,
      }),
    onSuccess: (result) => {
      downloadBlob(result.blob, result.filename);
      setError(null);
      setNotice(`Exported ${result.filename}`);
    },
    onError: (exportError) => {
      const rawMessage = exportError instanceof Error ? exportError.message : 'Failed to export';
      setError(normalizeErrorMessage(rawMessage));
    },
  });

  const handleExport = async (format: PublicExportFormat) => {
    const payload = resolveCurrentData();
    if (!payload) return;
    await exportMutation.mutateAsync({ format, payload });
  };

  const handleViewChange = (view: 'form' | 'json' | 'preview') => {
    if (view === activeView) return;
    if (view === 'form') {
      try {
        const parsed = JSON.parse(rawJson) as Record<string, unknown>;
        form.reset(parsed);
        setError(null);
      } catch {
        setError('Invalid JSON. Fix it before switching to form view.');
        return;
      }
    }
    if (view === 'json') {
      setRawJson(JSON.stringify(form.getValues(), null, 2));
    }
    if (view === 'preview') {
      setHasUserInteracted(true);
      const payload = resolveCurrentData();
      if (payload) {
        void previewMutation.mutateAsync(payload);
      }
    }
    setActiveView(view);
  };

  const handleSaveDraft = () => {
    const record = saveDraftInternal();
    if (!record) return;
    setNotice(`Draft saved: ${record.name}`);
  };

  const handleSaveAs = () => {
    const name = window.prompt('Draft name', selectedTemplate?.display_name ?? 'Sandbox Draft');
    if (!name) return;
    const record = saveDraftInternal({ forceNew: true, providedName: name });
    if (!record) return;
    setNotice(`Draft saved as: ${record.name}`);
  };

  const handleDeleteDraft = () => {
    if (!activeDraftId) return;
    deleteSmtDraft(activeDraftId);
    setActiveDraftId(null);
    syncDraftList();
    setNotice('Draft deleted.');
  };

  const handleDownloadDraft = () => {
    const record =
      (activeDraftId ? getSmtDraft(activeDraftId) : null) ??
      saveDraftInternal({ forceNew: true, providedName: 'Sandbox Draft' });
    if (!record) return;
    const blob = new Blob([exportSmtDraftRecord(record)], { type: 'application/json' });
    downloadBlob(blob, `${sanitizeDraftFilename(record.name)}.json`);
  };

  const handleUploadDraft = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = parseSmtDraftRecord(text);
      saveSmtDraft(parsed);
      syncDraftList();
      applyDraft(parsed);
      setNotice(`Loaded draft: ${parsed.name}`);
      setError(null);
    } catch (uploadError) {
      const rawMessage = uploadError instanceof Error ? uploadError.message : 'Invalid draft file';
      setError(normalizeErrorMessage(rawMessage));
    } finally {
      event.target.value = '';
    }
  };

  const loading = templatesQuery.isLoading || (Boolean(selectedTemplateKey) && contractQuery.isLoading);

  return (
    <div className="space-y-6">
      <PageHeader
        title="IDTA Submodel Template Editor"
        description="Anonymous AAS developer sandbox for cached IDTA templates"
        breadcrumb={<span className="text-xs text-muted-foreground">Tools / IDTA Submodel Editor</span>}
      />

      <Alert>
        <AlertDescription className="text-xs">
          Template content source: IDTA Submodel Templates repository (CC-BY-4.0).{' '}
          <a
            href="https://github.com/admin-shell-io/submodel-templates"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            View source
          </a>
        </AlertDescription>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4 rounded-lg border p-4">
          <div className="space-y-2">
            <Label htmlFor="template-search">Search templates</Label>
            <Input
              id="template-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Find by key or display name"
            />
          </div>

          <div className="space-y-2">
            <Label>Status filter</Label>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as PublicTemplateStatus)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="published">Published</SelectItem>
                <SelectItem value="deprecated">Deprecated</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Template</Label>
            <Select value={selectedTemplateKey} onValueChange={setSelectedTemplateKey}>
              <SelectTrigger>
                <SelectValue placeholder="Select template" />
              </SelectTrigger>
              <SelectContent>
                {templatesQuery.data?.templates.map((template) => (
                  <SelectItem key={template.template_key} value={template.template_key}>
                    {template.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Version</Label>
            <Select value={selectedVersion} onValueChange={setSelectedVersion}>
              <SelectTrigger>
                <SelectValue placeholder="Select version" />
              </SelectTrigger>
              <SelectContent>
                {versionsQuery.data?.versions.map((version) => (
                  <SelectItem key={version.version} value={version.version}>
                    {version.version}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {templateDetailQuery.data && (
            <div className="space-y-2 rounded-md border bg-muted/25 p-3 text-xs">
              <div className="flex items-center gap-2">
                <Badge variant="outline">{templateDetailQuery.data.catalog_status}</Badge>
                <Badge variant="secondary">v{templateDetailQuery.data.latest_version}</Badge>
              </div>
              <p>
                <span className="font-medium">Semantic ID:</span> {templateDetailQuery.data.semantic_id}
              </p>
              <p>
                <span className="font-medium">Repo ref:</span>{' '}
                {templateDetailQuery.data.source_metadata.source_repo_ref}
              </p>
              <p>
                <span className="font-medium">Source SHA:</span>{' '}
                {templateDetailQuery.data.source_metadata.source_file_sha ?? 'n/a'}
              </p>
            </div>
          )}

          {contractQuery.data && (
            <div className="space-y-2 rounded-md border bg-muted/25 p-3 text-xs">
              <p className="font-medium">Template diagnostics</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant={diagnostics.unsupported.length > 0 ? 'destructive' : 'secondary'}>
                  Unsupported nodes: {diagnostics.unsupported.length}
                </Badge>
                <Badge variant={diagnostics.unresolved.length > 0 ? 'destructive' : 'secondary'}>
                  Unresolved drop-ins: {diagnostics.unresolved.length}
                </Badge>
              </div>
              {diagnostics.unsupported.slice(0, 3).map((entry, index) => (
                <p key={`unsupported-${entry.path ?? 'root'}-${index}`} className="text-muted-foreground">
                  {(entry.path ?? 'root')}: {(entry.reasons ?? []).join(', ') || 'unsupported'}
                </p>
              ))}
              {diagnostics.unresolved.slice(0, 3).map((entry, index) => {
                const record = entry as Record<string, unknown>;
                const pathValue = typeof record.path === 'string' ? record.path : 'root';
                const reasonValue = typeof record.reason === 'string' ? record.reason : 'unresolved';
                return (
                  <p key={`unresolved-${pathValue}-${index}`} className="text-muted-foreground">
                    {pathValue}: {reasonValue}
                  </p>
                );
              })}
            </div>
          )}

          <div className="space-y-2 rounded-md border p-3">
            <Label>Drafts</Label>
            <Select
              value={activeDraftId ?? ''}
              onValueChange={(value) => {
                if (!value) return;
                const draft = getSmtDraft(value);
                if (draft) {
                  applyDraft(draft);
                }
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Load draft" />
              </SelectTrigger>
              <SelectContent>
                {drafts.map((draft) => (
                  <SelectItem key={draft.draftId} value={draft.draftId}>
                    {draft.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={handleSaveDraft}>Save Draft</Button>
              <Button size="sm" variant="outline" onClick={handleSaveAs}>Save As</Button>
              <Button size="sm" variant="outline" onClick={handleDeleteDraft} disabled={!activeDraftId}>
                Delete
              </Button>
              <Button size="sm" variant="outline" onClick={handleDownloadDraft}>
                <Download className="mr-1 h-4 w-4" />
                Draft JSON
              </Button>
              <Button size="sm" variant="outline" onClick={() => uploadInputRef.current?.click()}>
                <FileUp className="mr-1 h-4 w-4" />
                Upload Draft
              </Button>
              <input
                ref={uploadInputRef}
                type="file"
                accept="application/json"
                className="hidden"
                onChange={(event) => {
                  void handleUploadDraft(event);
                }}
              />
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {loading ? (
            <div className="rounded-md border p-8 text-sm text-muted-foreground">Loading template editor…</div>
          ) : !contractQuery.data ? (
            <div className="rounded-md border p-8 text-sm text-muted-foreground">Select a template to start.</div>
          ) : (
            <SubmodelEditorShell title="Sandbox Workspace" activeViewLabel={activeView === 'preview' ? 'json' : activeView}>
              {error && (
                <Alert variant="destructive">
                  <AlertDescription className="text-xs">{error}</AlertDescription>
                </Alert>
              )}
              {notice && (
                <Alert>
                  <AlertDescription className="text-xs">{notice}</AlertDescription>
                </Alert>
              )}

              <Tabs value={activeView} onValueChange={(value) => handleViewChange(value as 'form' | 'json' | 'preview')}>
                <TabsList>
                  <TabsTrigger value="form" disabled={!uiSchema}>Form</TabsTrigger>
                  <TabsTrigger value="json">Raw JSON</TabsTrigger>
                  <TabsTrigger value="preview">AAS JSON Preview</TabsTrigger>
                </TabsList>
                <TabsContent value="form">
                  {hasDefinitionElements ? (
                    <AASRendererList
                      nodes={templateDefinition!.submodel!.elements!}
                      basePath=""
                      depth={0}
                      rootSchema={uiSchema}
                      control={form.control}
                      editorContext={undefined}
                    />
                  ) : (
                    <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                      Form view is unavailable for this template. Use raw JSON mode.
                    </div>
                  )}
                </TabsContent>
                <TabsContent value="json">
                  <JsonEditor value={rawJson} onChange={handleRawJsonChange} />
                </TabsContent>
                <TabsContent value="preview">
                  <div className="mb-3 flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setHasUserInteracted(true);
                        const payload = resolveCurrentData();
                        if (payload) {
                          void previewMutation.mutateAsync(payload);
                        }
                      }}
                      disabled={previewMutation.isPending}
                    >
                      <RefreshCw className="mr-1 h-4 w-4" />
                      Refresh Preview
                    </Button>
                  </div>
                  <pre className="max-h-[520px] overflow-auto rounded-md border bg-muted/20 p-3 text-xs">
                    {previewText || '{}'}
                  </pre>
                </TabsContent>
              </Tabs>

              <div className="flex flex-wrap items-center gap-2 border-t pt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    form.reset({});
                    setHasUserInteracted(false);
                    setPreviewText('');
                  }}
                >
                  Reset
                </Button>
                <Button size="sm" variant="outline" onClick={handleSaveDraft}>Save Draft</Button>
                <Button size="sm" variant="outline" onClick={handleSaveAs}>Save As</Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void handleExport('json');
                  }}
                  disabled={exportMutation.isPending}
                >
                  Export JSON
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void handleExport('aasx');
                  }}
                  disabled={exportMutation.isPending}
                >
                  Export AASX
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void handleExport('pdf');
                  }}
                  disabled={exportMutation.isPending}
                >
                  Export PDF
                </Button>
              </div>
            </SubmodelEditorShell>
          )}
        </div>
      </div>
    </div>
  );
}
