import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import {
  Plus,
  Eye,
  Edit,
  Upload,
  Download,
  RefreshCcw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  FileText,
  History,
  AlertTriangle,
} from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PageHeader } from '@/components/page-header';
import { StatusBadge } from '@/components/status-badge';
import { ActorBadge } from '@/components/actor-badge';
import { ErrorBanner } from '@/components/error-banner';
import { EmptyState } from '@/components/empty-state';
import { LoadingSpinner } from '@/components/loading-spinner';
import { toast } from 'sonner';
import type { DPPResponse, TemplateResponse } from '@/api/types';
import { hasRole } from '@/lib/auth';
import { cn } from '@/lib/utils';

interface MasterItem {
  id: string;
  product_id: string;
  name: string;
}

interface TemplateVariable {
  name: string;
  label?: string | null;
  description?: string | null;
  required?: boolean;
  default_value?: unknown;
  allow_default?: boolean;
  expected_type?: string;
}

interface TemplatePackage {
  version: string;
  aliases: string[];
  template_string: string;
  variables: TemplateVariable[];
}

interface ActorSummary {
  subject: string;
  display_name?: string | null;
  email_masked?: string | null;
}

interface AccessSummary {
  can_read: boolean;
  can_update: boolean;
  can_publish: boolean;
  can_archive: boolean;
  source: 'owner' | 'share' | 'tenant_admin';
}

interface DPPListItem extends DPPResponse {
  visibility_scope?: 'owner_team' | 'tenant';
  owner?: ActorSummary;
  access?: AccessSummary;
}

type DppScopeFilter = 'mine' | 'shared' | 'all';

function isTemplateSelectable(template: TemplateResponse): boolean {
  return template.support_status !== 'unavailable' && template.refresh_enabled !== false;
}

const PAGE_SIZE = 50;

async function fetchDPPs(token?: string, page = 0, scope: DppScopeFilter = 'mine') {
  const offset = page * PAGE_SIZE;
  const response = await tenantApiFetch(
    `/dpps?limit=${PAGE_SIZE}&offset=${offset}&scope=${scope}`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPPs'));
  }
  return response.json();
}

async function fetchMasters(token?: string) {
  const response = await tenantApiFetch('/masters', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch masters'));
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
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch template'));
  }
  return response.json();
}

async function createDPP(data: Record<string, unknown>, token?: string) {
  const response = await tenantApiFetch('/dpps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to create DPP'));
  }
  return response.json();
}

async function importDPP(
  productId: string,
  version: string,
  payload: Record<string, unknown>,
  token?: string
) {
  const response = await tenantApiFetch(
    `/dpps/import?master_product_id=${encodeURIComponent(productId)}&master_version=${encodeURIComponent(version)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    token
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to import DPP'));
  }
  return response.json();
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function renderTemplateString(
  template: string,
  variables: TemplateVariable[],
  values: Record<string, string>
) {
  let rendered = template;
  variables.forEach((variable) => {
    const rawValue = values[variable.name];
    const hasValue = rawValue !== undefined && rawValue !== null && rawValue !== '';
    const candidate =
      hasValue
        ? rawValue
        : variable.allow_default && variable.default_value != null
          ? String(variable.default_value)
          : '';
    const regex = new RegExp(`\\{\\{\\s*${escapeRegExp(variable.name)}\\s*\\}\\}`, 'g');
    rendered = rendered.replace(regex, candidate);
  });
  return rendered;
}

function findUnresolvedPlaceholders(payload: string, variables: TemplateVariable[]) {
  if (!payload) return [];
  return variables
    .map((variable) => {
      const regex = new RegExp(`\\{\\{\\s*${escapeRegExp(variable.name)}\\s*\\}\\}`, 'g');
      return regex.test(payload) ? variable.name : null;
    })
    .filter((name): name is string => Boolean(name));
}

function stripGlobalAssetId(payload: Record<string, unknown>) {
  const cloned = JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
  const env = (cloned.aasEnvironment ?? cloned) as Record<string, unknown>;
  const shells = env?.assetAdministrationShells;
  if (Array.isArray(shells)) {
    shells.forEach((shell: Record<string, unknown>) => {
      const info = shell?.assetInformation;
      if (info && typeof info === 'object') {
        delete (info as Record<string, unknown>).globalAssetId;
      }
    });
  }
  return cloned;
}

export default function DPPListPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [scope, setScope] = useState<DppScopeFilter>('mine');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTemplates, setSelectedTemplates] = useState<string[]>([]);
  const [importProductId, setImportProductId] = useState('');
  const [importVersion, setImportVersion] = useState('latest');
  const [importTemplate, setImportTemplate] = useState<TemplatePackage | null>(null);
  const [importValues, setImportValues] = useState<Record<string, string>>({});
  const [importPayload, setImportPayload] = useState('');
  const [stripImportGlobalId, setStripImportGlobalId] = useState(true);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  const [importPending, setImportPending] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [selectedDpps, setSelectedDpps] = useState<Set<string>>(new Set());
  const [batchExporting, setBatchExporting] = useState(false);
  const auth = useAuth();
  const token = auth.user?.access_token;
  const tenantSlug = getTenantSlug();
  const userIsTenantAdmin = hasRole(auth.user, 'tenant_admin') || hasRole(auth.user, 'admin');

  const { data: dpps, isLoading, isError: dppsError, error: dppsErrorObj } = useQuery({
    queryKey: ['dpps', tenantSlug, page, scope],
    queryFn: () => fetchDPPs(token, page, scope),
    enabled: Boolean(token),
  });

  const { data: templatesData, isError: templatesError, error: templatesErrorObj } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
    enabled: Boolean(token),
  });

  const { data: mastersData } = useQuery({
    queryKey: ['masters', tenantSlug],
    queryFn: () => fetchMasters(token),
    enabled: Boolean(token),
  });

  useEffect(() => {
    const available = templatesData?.templates
      ?.filter((template: TemplateResponse) => isTemplateSelectable(template))
      .map((template: TemplateResponse) => template.template_key) || [];
    setSelectedTemplates((prev) => {
      const filtered = prev.filter((key) => available.includes(key));
      if (filtered.length > 0) return filtered;
      if (available.length > 0) return [available[0]];
      return [];
    });
  }, [templatesData?.templates]);

  useEffect(() => {
    const masters: MasterItem[] = mastersData?.masters ?? [];
    if (!importProductId && masters.length > 0) {
      setImportProductId(masters[0].product_id);
    }
  }, [mastersData?.masters, importProductId]);

  useEffect(() => {
    setImportTemplate(null);
    setImportPayload('');
    setImportValues({});
    setImportError(null);
    setImportSuccess(null);
  }, [importProductId, importVersion]);

  useEffect(() => {
    setSelectedDpps(new Set());
  }, [scope, page]);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createDPP(data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpps', tenantSlug] });
      setShowCreateModal(false);
      const available = templatesData?.templates
        ?.filter((template: TemplateResponse) => isTemplateSelectable(template))
        .map((template: TemplateResponse) => template.template_key) || [];
      setSelectedTemplates(available.length > 0 ? [available[0]] : []);
    },
  });

  const handleLoadTemplate = async () => {
    if (!importProductId || !token) return;
    setImportPending(true);
    setImportError(null);
    setImportSuccess(null);
    try {
      const data = await fetchTemplatePackage(importProductId, importVersion, token);
      setImportTemplate(data);
      setImportPayload(data.template_string);
      const defaults: Record<string, string> = {};
      data.variables.forEach((variable) => {
        if (variable.allow_default && variable.default_value != null) {
          defaults[variable.name] = String(variable.default_value);
        }
      });
      setImportValues(defaults);
    } catch (err) {
      setImportTemplate(null);
      setImportPayload('');
      setImportError((err as Error)?.message ?? 'Failed to load template.');
    } finally {
      setImportPending(false);
    }
  };

  const handleApplyVariables = () => {
    if (!importTemplate) return;
    const rendered = renderTemplateString(
      importTemplate.template_string,
      importTemplate.variables,
      importValues
    );
    setImportPayload(rendered);
  };

  const handleImport = async () => {
    if (!importProductId || !importTemplate || !importPayload) return;
    if (missingRequired.length > 0 || unresolvedPlaceholders.length > 0) {
      const missingNames = missingRequired.map((variable) => variable.name);
      const unresolvedNames = unresolvedPlaceholders.filter(
        (name) => !missingNames.includes(name)
      );
      const messageParts = [];
      if (missingNames.length > 0) {
        messageParts.push(`Missing required values: ${missingNames.join(', ')}`);
      }
      if (unresolvedNames.length > 0) {
        messageParts.push(`Unresolved placeholders: ${unresolvedNames.join(', ')}`);
      }
      setImportError(messageParts.join(' · '));
      return;
    }
    setImportPending(true);
    setImportError(null);
    setImportSuccess(null);
    try {
      const parsed = JSON.parse(importPayload) as Record<string, unknown>;
      const prepared = stripImportGlobalId ? stripGlobalAssetId(parsed) : parsed;
      const result = await importDPP(importProductId, importVersion, prepared, token);
      setImportSuccess(`Imported DPP ${result.id}`);
      queryClient.invalidateQueries({ queryKey: ['dpps', tenantSlug] });
    } catch (err) {
      setImportError((err as Error)?.message ?? 'Failed to import DPP.');
    } finally {
      setImportPending(false);
    }
  };

  const createError = createMutation.isError ? (createMutation.error as Error) : null;
  const sessionExpired = Boolean(createError?.message?.includes('Session expired'));
  const pageError =
    (dppsError ? (dppsErrorObj as Error) : null) ??
    (templatesError ? (templatesErrorObj as Error) : null);
  const pageSessionExpired = Boolean(pageError?.message?.includes('Session expired'));
  const missingRequired =
    importTemplate?.variables?.filter(
      (variable) =>
        variable.required &&
        (importValues[variable.name] === undefined ||
          importValues[variable.name] === null ||
          importValues[variable.name] === '') &&
        !(variable.allow_default && variable.default_value != null)
    ) ?? [];
  const unresolvedPlaceholders = importTemplate
    ? findUnresolvedPlaceholders(importPayload, importTemplate.variables)
    : [];

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    createMutation.mutate({
      asset_ids: {
        manufacturerPartId: formData.get('manufacturerPartId'),
        serialNumber: formData.get('serialNumber'),
      },
      selected_templates: selectedTemplates,
    });
  };

  const handleTemplateToggle = (template: TemplateResponse) => {
    if (!isTemplateSelectable(template)) return;
    const templateKey = template.template_key;
    setSelectedTemplates(prev =>
      prev.includes(templateKey)
        ? prev.filter(t => t !== templateKey)
        : [...prev, templateKey]
    );
  };

  const toggleDppSelection = (dppId: string) => {
    setSelectedDpps((prev) => {
      const next = new Set(prev);
      if (next.has(dppId)) next.delete(dppId);
      else next.add(dppId);
      return next;
    });
  };

  const toggleAllDpps = () => {
    const allIds = dpps?.dpps?.map((d: DPPListItem) => d.id) ?? [];
    if (selectedDpps.size === allIds.length) {
      setSelectedDpps(new Set());
    } else {
      setSelectedDpps(new Set(allIds));
    }
  };

  const handleBatchExport = async () => {
    if (selectedDpps.size === 0 || !token) return;
    setBatchExporting(true);
    try {
      const response = await tenantApiFetch('/export/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dpp_ids: Array.from(selectedDpps),
          format: 'json',
        }),
      }, token);
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'dpp-batch-export.zip';
      a.click();
      URL.revokeObjectURL(url);
      setSelectedDpps(new Set());
    } catch {
      toast.error('Batch export failed');
    } finally {
      setBatchExporting(false);
    }
  };

  const masters: MasterItem[] = mastersData?.masters ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Digital Product Passports"
        description="Manage your product passports"
        actions={
          <div className="flex gap-2">
            <Select
              value={scope}
              onValueChange={(value) => {
                setScope(value as DppScopeFilter);
                setPage(0);
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter ownership" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mine">Mine</SelectItem>
                <SelectItem value="shared">Shared with me</SelectItem>
                {userIsTenantAdmin && <SelectItem value="all">All (tenant admin)</SelectItem>}
              </SelectContent>
            </Select>
            {selectedDpps.size > 0 && (
              <Button
                variant="outline"
                onClick={() => { void handleBatchExport(); }}
                disabled={batchExporting}
              >
                <Download className="h-4 w-4 mr-2" />
                {batchExporting ? 'Exporting...' : `Export ${selectedDpps.size} selected`}
              </Button>
            )}
            <Button onClick={() => setShowCreateModal(true)} data-testid="dpp-create-open">
              <Plus className="h-4 w-4 mr-2" />
              Create DPP
            </Button>
          </div>
        }
      />

      {/* Import from Master Template */}
      <Collapsible open={importOpen} onOpenChange={setImportOpen}>
        <Card>
          <CardContent className="p-4">
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex w-full items-center justify-between"
              >
                <div className="text-left">
                  <h2 className="text-lg font-semibold">Import from Master Template</h2>
                  <p className="text-sm text-muted-foreground">
                    Load a released master, fill placeholders, and import a serialized DPP in one step.
                  </p>
                </div>
                <ChevronDown
                  className={cn(
                    'h-5 w-5 text-muted-foreground transition-transform',
                    importOpen && 'rotate-180',
                  )}
                />
              </button>
            </CollapsibleTrigger>

            <CollapsibleContent className="mt-4 space-y-4">
              <div className="flex justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    void queryClient.invalidateQueries({ queryKey: ['masters', tenantSlug] });
                  }}
                >
                  <RefreshCcw className="h-3 w-3 mr-1" />
                  Refresh masters
                </Button>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <Label className="text-xs">Master Product ID</Label>
                  <Select
                    value={importProductId}
                    onValueChange={setImportProductId}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a master" />
                    </SelectTrigger>
                    <SelectContent>
                      {masters.map((master) => (
                        <SelectItem key={master.id} value={master.product_id}>
                          {master.product_id} · {master.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Version / Alias</Label>
                  <Input
                    value={importVersion}
                    onChange={(event) => setImportVersion(event.target.value)}
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    onClick={handleLoadTemplate}
                    disabled={!importProductId || importPending}
                  >
                    {importPending ? 'Loading...' : 'Load Template'}
                  </Button>
                </div>
              </div>

              {importTemplate && (
                <div className="space-y-4">
                  <div className="rounded-md border bg-muted/50 p-3 text-xs text-muted-foreground">
                    Loaded version {importTemplate.version} ({importTemplate.aliases.join(', ') || 'no aliases'})
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    {importTemplate.variables.length === 0 && (
                      <p className="text-xs text-muted-foreground">
                        No variables in this template. You can import as-is.
                      </p>
                    )}
                    {importTemplate.variables.map((variable) => (
                      <div key={variable.name} className="space-y-1">
                        <Label className="text-xs">
                          {variable.label || variable.name}
                          {variable.required ? ' *' : ''}
                        </Label>
                        <Input
                          value={importValues[variable.name] ?? ''}
                          onChange={(event) =>
                            setImportValues((prev) => ({ ...prev, [variable.name]: event.target.value }))
                          }
                          placeholder={variable.default_value != null ? String(variable.default_value) : ''}
                          className="text-sm"
                        />
                      </div>
                    ))}
                  </div>

                  {missingRequired.length > 0 && (
                    <Alert>
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        Missing required values: {missingRequired.map((variable) => variable.name).join(', ')}
                      </AlertDescription>
                    </Alert>
                  )}
                  {unresolvedPlaceholders.length > 0 && (
                    <Alert>
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        Unresolved placeholders: {unresolvedPlaceholders.join(', ')}
                      </AlertDescription>
                    </Alert>
                  )}

                  <div className="flex flex-wrap items-center gap-3">
                    <Button size="sm" onClick={handleApplyVariables}>
                      Apply Values
                    </Button>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="strip-global-id"
                        checked={stripImportGlobalId}
                        onCheckedChange={(checked) => setStripImportGlobalId(checked === true)}
                      />
                      <Label htmlFor="strip-global-id" className="text-xs font-normal">
                        Strip globalAssetId before import
                      </Label>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <Label className="text-xs">Import Payload (JSON)</Label>
                    <textarea
                      value={importPayload}
                      onChange={(event) => setImportPayload(event.target.value)}
                      className="h-48 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      onClick={handleImport}
                      disabled={!importPayload || importPending || missingRequired.length > 0 || unresolvedPlaceholders.length > 0}
                    >
                      <Upload className="h-4 w-4 mr-2" />
                      {importPending ? 'Importing...' : 'Import DPP'}
                    </Button>
                    {importError && (
                      <span className="text-xs text-destructive">{importError}</span>
                    )}
                    {importSuccess && (
                      <span className="text-xs text-green-600">{importSuccess}</span>
                    )}
                  </div>
                </div>
              )}
            </CollapsibleContent>
          </CardContent>
        </Card>
      </Collapsible>

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Failed to load data.'}
          showSignIn={pageSessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      {/* Create Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent data-testid="dpp-create-modal">
          <DialogHeader>
            <DialogTitle>Create New DPP</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Manufacturer Part ID</Label>
              <Input name="manufacturerPartId" required />
            </div>
            <div className="space-y-2">
              <Label>Serial Number</Label>
              <Input name="serialNumber" />
            </div>
            <div className="space-y-2">
              <Label>Select Templates</Label>
              <div className="space-y-2 max-h-48 overflow-y-auto rounded-md border p-3">
                {templatesData?.templates?.map((template: TemplateResponse) => (
                  <div key={template.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`template-${template.id}`}
                      disabled={!isTemplateSelectable(template)}
                      checked={selectedTemplates.includes(template.template_key)}
                      onCheckedChange={() => handleTemplateToggle(template)}
                    />
                    <label
                      htmlFor={`template-${template.id}`}
                      className={cn(
                        'flex items-center gap-2 text-sm',
                        isTemplateSelectable(template) ? 'cursor-pointer' : 'cursor-not-allowed text-muted-foreground'
                      )}
                    >
                      <span>{template.template_key}</span>
                      <span className="text-xs text-muted-foreground">v{template.idta_version}</span>
                      {template.support_status === 'unavailable' && (
                        <span className="text-xs text-destructive">unavailable</span>
                      )}
                    </label>
                  </div>
                ))}
                {(!templatesData?.templates || templatesData.templates.length === 0) && (
                  <p className="text-sm text-muted-foreground">No templates available. Please refresh templates first.</p>
                )}
              </div>
            </div>
            {createMutation.isError && (
              <ErrorBanner
                message={createError?.message || 'Failed to create DPP.'}
                showSignIn={sessionExpired}
                onSignIn={() => { void auth.signinRedirect(); }}
              />
            )}
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending || selectedTemplates.length === 0}
                data-testid="dpp-create-submit"
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* DPP List */}
      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={dpps?.dpps?.length > 0 && selectedDpps.size === dpps.dpps.length}
                    onCheckedChange={toggleAllDpps}
                  />
                </TableHead>
                <TableHead>Product ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Owner</TableHead>
                <TableHead>Visibility</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {dpps?.dpps?.map((dpp: DPPListItem) => (
                <TableRow key={dpp.id}>
                  <TableCell>
                    <Checkbox
                      checked={selectedDpps.has(dpp.id)}
                      onCheckedChange={() => toggleDppSelection(dpp.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">
                      {String(dpp.asset_ids?.manufacturerPartId || '') || dpp.id.slice(0, 8)}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {String(dpp.asset_ids?.serialNumber || '') || '-'}
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={dpp.status} />
                  </TableCell>
                  <TableCell>
                    <ActorBadge actor={dpp.owner} fallbackSubject={dpp.owner_subject} />
                  </TableCell>
                  <TableCell className="text-muted-foreground capitalize">
                    {dpp.visibility_scope === 'tenant' ? 'Tenant' : 'Owner/team'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(dpp.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        asChild
                        title="View"
                        data-testid={`dpp-view-${dpp.id}`}
                      >
                        <Link to={`/t/${tenantSlug}/dpp/${dpp.id}`}>
                          <Eye className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        asChild
                        title="Activity timeline"
                      >
                        <Link to={`/console/activity?type=dpp&id=${dpp.id}`}>
                          <History className="h-4 w-4" />
                        </Link>
                      </Button>
                      {dpp.access?.can_update !== false && (
                        <Button
                          variant="ghost"
                          size="icon"
                          asChild
                          title="Edit"
                          data-testid={`dpp-edit-${dpp.id}`}
                        >
                          <Link to={`/console/dpps/${dpp.id}`}>
                            <Edit className="h-4 w-4" />
                          </Link>
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {(!dpps?.dpps || dpps.dpps.length === 0) && (
            <EmptyState
              icon={FileText}
              title="No DPPs yet"
              description="Create your first Digital Product Passport to get started"
            />
          )}
          {dpps?.total_count != null && dpps.total_count > 0 && (
            <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
              <span>
                Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + (dpps.dpps?.length ?? 0)} of {dpps.total_count}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" /> Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={(page + 1) * PAGE_SIZE >= dpps.total_count}
                >
                  Next <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
