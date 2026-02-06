import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { Plus, Eye, Edit, Upload, RefreshCcw, ChevronLeft, ChevronRight } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';

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

const PAGE_SIZE = 50;

async function fetchDPPs(token?: string, page = 0) {
  const offset = page * PAGE_SIZE;
  const response = await tenantApiFetch(
    `/dpps?limit=${PAGE_SIZE}&offset=${offset}`,
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

async function createDPP(data: any, token?: string) {
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
  const cloned = JSON.parse(JSON.stringify(payload)) as Record<string, any>;
  const env = (cloned.aasEnvironment ?? cloned) as Record<string, any>;
  const shells = env?.assetAdministrationShells;
  if (Array.isArray(shells)) {
    shells.forEach((shell) => {
      if (shell?.assetInformation && typeof shell.assetInformation === 'object') {
        delete shell.assetInformation.globalAssetId;
      }
    });
  }
  return cloned;
}

export default function DPPListPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
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
  const auth = useAuth();
  const token = auth.user?.access_token;
  const tenantSlug = getTenantSlug();

  const { data: dpps, isLoading, isError: dppsError, error: dppsErrorObj } = useQuery({
    queryKey: ['dpps', tenantSlug, page],
    queryFn: () => fetchDPPs(token, page),
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
    const available = templatesData?.templates?.map((template: any) => template.template_key) || [];
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

  const createMutation = useMutation({
    mutationFn: (data: any) => createDPP(data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpps', tenantSlug] });
      setShowCreateModal(false);
      const available = templatesData?.templates?.map((template: any) => template.template_key) || [];
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

  const handleTemplateToggle = (templateKey: string) => {
    setSelectedTemplates(prev =>
      prev.includes(templateKey)
        ? prev.filter(t => t !== templateKey)
        : [...prev, templateKey]
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Digital Product Passports</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your product passports
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
          data-testid="dpp-create-open"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create DPP
        </button>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Import from Master Template</h2>
            <p className="text-sm text-gray-500">
              Load a released master, fill placeholders, and import a serialized DPP in one step.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: ['masters', tenantSlug] });
            }}
            className="inline-flex items-center text-xs text-gray-500 hover:text-gray-700"
          >
            <RefreshCcw className="h-3 w-3 mr-1" />
            Refresh masters
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-xs font-medium text-gray-600">
            Master Product ID
            <select
              value={importProductId}
              onChange={(event) => setImportProductId(event.target.value)}
              className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
            >
              {(mastersData?.masters ?? []).map((master: MasterItem) => (
                <option key={master.id} value={master.product_id}>
                  {master.product_id} · {master.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">
            Version / Alias
            <input
              value={importVersion}
              onChange={(event) => setImportVersion(event.target.value)}
              className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleLoadTemplate}
              className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-gray-900 rounded-md hover:bg-gray-800"
              disabled={!importProductId || importPending}
            >
              {importPending ? 'Loading...' : 'Load Template'}
            </button>
          </div>
        </div>

        {importTemplate && (
          <div className="space-y-4">
            <div className="rounded-md border border-gray-100 bg-gray-50 p-3 text-xs text-gray-600">
              Loaded version {importTemplate.version} ({importTemplate.aliases.join(', ') || 'no aliases'})
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {importTemplate.variables.length === 0 && (
                <div className="text-xs text-gray-500">
                  No variables in this template. You can import as-is.
                </div>
              )}
              {importTemplate.variables.map((variable) => (
                <label key={variable.name} className="text-xs text-gray-600">
                  {variable.label || variable.name}
                  {variable.required ? ' *' : ''}
                  <input
                    value={importValues[variable.name] ?? ''}
                    onChange={(event) =>
                      setImportValues((prev) => ({ ...prev, [variable.name]: event.target.value }))
                    }
                    placeholder={variable.default_value != null ? String(variable.default_value) : ''}
                    className="mt-1 w-full rounded-md border border-gray-200 px-2 py-1 text-sm"
                  />
                </label>
              ))}
            </div>

            {missingRequired.length > 0 && (
              <div className="rounded-md border border-yellow-200 bg-yellow-50 p-2 text-xs text-yellow-800">
                Missing required values: {missingRequired.map((variable) => variable.name).join(', ')}
              </div>
            )}
            {unresolvedPlaceholders.length > 0 && (
              <div className="rounded-md border border-yellow-200 bg-yellow-50 p-2 text-xs text-yellow-800">
                Unresolved placeholders: {unresolvedPlaceholders.join(', ')}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleApplyVariables}
                className="inline-flex items-center px-3 py-2 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
              >
                Apply Values
              </button>
              <label className="flex items-center gap-2 text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={stripImportGlobalId}
                  onChange={(event) => setStripImportGlobalId(event.target.checked)}
                />
                Strip globalAssetId before import
              </label>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-600">
                Import Payload (JSON)
              </label>
              <textarea
                value={importPayload}
                onChange={(event) => setImportPayload(event.target.value)}
                className="mt-1 h-48 w-full rounded-md border border-gray-200 px-3 py-2 font-mono text-xs"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleImport}
                disabled={!importPayload || importPending || missingRequired.length > 0 || unresolvedPlaceholders.length > 0}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-gray-900 rounded-md hover:bg-gray-800 disabled:opacity-50"
              >
                <Upload className="h-4 w-4 mr-2" />
                {importPending ? 'Importing...' : 'Import DPP'}
              </button>
              {importError && (
                <span className="text-xs text-red-600">{importError}</span>
              )}
              {importSuccess && (
                <span className="text-xs text-green-600">{importSuccess}</span>
              )}
            </div>
          </div>
        )}
      </div>

      {pageError && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <div className="flex items-center justify-between gap-3">
            <span>{pageError.message || 'Failed to load data.'}</span>
            {pageSessionExpired && (
              <button
                type="button"
                onClick={() => { void auth.signinRedirect(); }}
                className="text-xs font-medium text-red-700 underline"
              >
                Sign in
              </button>
            )}
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg" data-testid="dpp-create-modal">
            <h2 className="text-lg font-semibold mb-4">Create New DPP</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Manufacturer Part ID
                </label>
                <input
                  name="manufacturerPartId"
                  type="text"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Serial Number
                </label>
                <input
                  name="serialNumber"
                  type="text"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Templates
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded-md p-3">
                  {templatesData?.templates?.map((template: any) => (
                    <label key={template.id} className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedTemplates.includes(template.template_key)}
                        onChange={() => handleTemplateToggle(template.template_key)}
                        className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-900">{template.template_key}</span>
                      <span className="text-xs text-gray-500">v{template.idta_version}</span>
                    </label>
                  ))}
                  {(!templatesData?.templates || templatesData.templates.length === 0) && (
                    <p className="text-sm text-gray-500">No templates available. Please refresh templates first.</p>
                  )}
                </div>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                {sessionExpired && (
                  <button
                    type="button"
                    onClick={() => { void auth.signinRedirect(); }}
                    className="mr-auto text-sm text-red-600 underline"
                  >
                    Sign in
                  </button>
                )}
                {createMutation.isError && (
                  <p className="mr-auto text-sm text-red-600">
                    {createError?.message || 'Failed to create DPP.'}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 border rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || selectedTemplates.length === 0}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-md disabled:opacity-50"
                  data-testid="dpp-create-submit"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DPP List */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Product ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {dpps?.dpps?.map((dpp: any) => (
                <tr key={dpp.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8)}
                    </div>
                    <div className="text-sm text-gray-500">
                      {dpp.asset_ids?.serialNumber || '-'}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${dpp.status === 'published'
                        ? 'bg-green-100 text-green-800'
                        : dpp.status === 'archived'
                          ? 'bg-gray-100 text-gray-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                      {dpp.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(dpp.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex justify-end space-x-2">
                      <Link
                        to={`/t/${tenantSlug}/dpp/${dpp.id}`}
                        className="text-gray-400 hover:text-gray-600"
                        title="View"
                        data-testid={`dpp-view-${dpp.id}`}
                      >
                        <Eye className="h-5 w-5" />
                      </Link>
                      <Link
                        to={`/console/dpps/${dpp.id}`}
                        className="text-primary-400 hover:text-primary-600"
                        title="Edit"
                        data-testid={`dpp-edit-${dpp.id}`}
                      >
                        <Edit className="h-5 w-5" />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!dpps?.dpps || dpps.dpps.length === 0) && (
            <div className="text-center py-12 text-gray-500">
              No DPPs yet. Create your first one!
            </div>
          )}
          {dpps?.total_count != null && dpps.total_count > 0 && (
            <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 bg-gray-50 text-sm text-gray-600">
              <span>
                Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + (dpps.dpps?.length ?? 0)} of {dpps.total_count}
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="inline-flex items-center px-2 py-1 rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={(page + 1) * PAGE_SIZE >= dpps.total_count}
                  className="inline-flex items-center px-2 py-1 rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
