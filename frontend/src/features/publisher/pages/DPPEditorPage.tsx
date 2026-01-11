import { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { ArrowLeft, Send, Download, QrCode, Edit3, RefreshCw } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { buildSubmodelData } from '@/features/editor/utils/submodelData';

type TemplateDescriptor = {
  template_key: string;
  semantic_id: string;
};

const ID_SHORT_TO_TEMPLATE_KEY: Record<string, string> = {
  Nameplate: 'digital-nameplate',
  ContactInformations: 'contact-information',
  TechnicalData: 'technical-data',
  CarbonFootprint: 'carbon-footprint',
  HandoverDocumentation: 'handover-documentation',
  HierarchicalStructures: 'hierarchical-structures',
};

function extractSemanticId(submodel: any): string | null {
  const semanticId = submodel?.semanticId;
  if (semanticId && Array.isArray(semanticId.keys) && semanticId.keys[0]?.value) {
    return String(semanticId.keys[0].value);
  }
  return null;
}

function resolveTemplateKey(submodel: any, templates: TemplateDescriptor[]): string | null {
  const semanticId = extractSemanticId(submodel);
  if (!semanticId) return null;
  if (!Array.isArray(templates)) return null;
  const direct = templates.find((template) => template.semantic_id === semanticId);
  if (direct) return direct.template_key;
  const partial = templates.find((template) =>
    semanticId.includes(template.semantic_id) || template.semantic_id.includes(semanticId)
  );
  if (partial) return partial.template_key;
  const idShort = submodel?.idShort;
  if (idShort && ID_SHORT_TO_TEMPLATE_KEY[idShort]) {
    return ID_SHORT_TO_TEMPLATE_KEY[idShort];
  }
  return null;
}

function formatElementValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return '[object]';
  }
}

async function fetchDPP(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
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

async function refreshTemplates(token?: string) {
  const response = await apiFetch('/api/v1/templates/refresh', {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to refresh templates'));
  }
  return response.json();
}

async function rebuildSubmodel(
  dppId: string,
  templateKey: string,
  data: Record<string, unknown>,
  token?: string,
) {
  const response = await tenantApiFetch(`/dpps/${dppId}/submodel`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_key: templateKey,
      data,
      rebuild_from_template: true,
    }),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to rebuild submodel'));
  }
  return response.json();
}

async function publishDPP(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}/publish`, {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to publish DPP'));
  }
  return response.json();
}

async function downloadExport(dppId: string, format: 'json' | 'aasx' | 'pdf', token?: string) {
  const response = await tenantApiFetch(`/export/${dppId}?format=${format}`, {}, token);
  if (!response.ok) {
    throw new Error(
      await getApiErrorMessage(response, `Failed to export ${format.toUpperCase()}`)
    );
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `dpp-${dppId}.${format === 'json' ? 'json' : format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function openQrCode(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/qr/${dppId}?format=png`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to generate QR code'));
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 1000);
}

export default function DPPEditorPage() {
  const { dppId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: dpp, isLoading } = useQuery({
    queryKey: ['dpp', dppId],
    queryFn: () => fetchDPP(dppId!, token),
    enabled: !!dppId,
  });

  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
  });

  const publishMutation = useMutation({
    mutationFn: () => publishDPP(dppId!, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpp', dppId] });
    },
  });

  const publishError = publishMutation.isError ? (publishMutation.error as Error) : null;
  const bannerMessage = actionError ?? publishError?.message ?? null;
  const sessionExpired = Boolean(bannerMessage?.includes('Session expired'));

  const refreshRebuildMutation = useMutation({
    mutationFn: async () => {
      if (!dppId) return;
      await refreshTemplates(token);

      const submodels = dpp?.aas_environment?.submodels || [];
      const seen = new Set<string>();
      const rebuildTasks: Promise<unknown>[] = [];

      for (const submodel of submodels) {
        const templateKey = resolveTemplateKey(submodel, availableTemplates);
        if (!templateKey || seen.has(templateKey)) continue;
        seen.add(templateKey);
        const data = buildSubmodelData(submodel);
        rebuildTasks.push(rebuildSubmodel(dppId, templateKey, data, token));
      }

      if (rebuildTasks.length > 0) {
        await Promise.all(rebuildTasks);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpp', dppId] });
      queryClient.invalidateQueries({ queryKey: ['templates'] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    );
  }

  if (!dpp) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">DPP not found</p>
      </div>
    );
  }

  const handleExport = async (format: 'json' | 'aasx' | 'pdf') => {
    setActionError(null);
    try {
      await downloadExport(dpp.id, format, token);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to export');
      // eslint-disable-next-line no-console
      console.error(error);
    }
  };

  const handleQrCode = async () => {
    setActionError(null);
    try {
      await openQrCode(dpp.id, token);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to generate QR code');
      // eslint-disable-next-line no-console
      console.error(error);
    }
  };

  const submodels: Array<Record<string, any>> = dpp.aas_environment?.submodels || [];
  const availableTemplates: TemplateDescriptor[] = templatesData?.templates || [];
  const existingTemplateKeys = new Set(
    submodels
      .map((submodel) => resolveTemplateKey(submodel, availableTemplates))
      .filter((value: string | null): value is string => Boolean(value))
  );
  const missingTemplates = availableTemplates.filter(
    (template: any) => !existingTemplateKeys.has(template.template_key)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/console/dpps')}
            className="text-gray-400 hover:text-gray-600"
            data-testid="dpp-back"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {dpp.asset_ids?.manufacturerPartId || 'DPP Editor'}
            </h1>
            <p className="text-sm text-gray-500">ID: {dpp.id}</p>
          </div>
        </div>
        <div className="flex space-x-3">
          {dpp.status === 'published' && (
            <button
              onClick={() => { void handleQrCode(); }}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              type="button"
            >
              <QrCode className="h-4 w-4 mr-2" />
              QR Code
            </button>
          )}
          <button
            onClick={() => { void handleExport('json'); }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export JSON
          </button>
          <button
            onClick={() => { void handleExport('pdf'); }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export PDF
          </button>
          <button
            onClick={() => { void handleExport('aasx'); }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export AASX
          </button>
          {dpp.status === 'draft' && (
            <button
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50"
            >
              <Send className="h-4 w-4 mr-2" />
              {publishMutation.isPending ? 'Publishing...' : 'Publish'}
            </button>
          )}
        </div>
      </div>

      {bannerMessage && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <div className="flex items-center justify-between gap-3">
            <span>{bannerMessage}</span>
            {sessionExpired && (
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

      {/* Status */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Status</h2>
            <span className={`mt-2 inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              dpp.status === 'published'
                ? 'bg-green-100 text-green-800'
                : dpp.status === 'archived'
                ? 'bg-gray-100 text-gray-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}>
              {dpp.status}
            </span>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">Revision</p>
            <p className="text-lg font-medium text-gray-900">
              #{dpp.current_revision_no || 1}
            </p>
          </div>
        </div>
      </div>

      {/* Asset Information */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Asset Information</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {(Object.entries(dpp.asset_ids || {}) as Array<[string, unknown]>).map(([key, value]) => (
            <div key={key}>
              <dt className="text-sm font-medium text-gray-500">{key}</dt>
              <dd className="mt-1 text-sm text-gray-900">{String(value)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Submodels */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Submodels</h2>
          <button
            type="button"
            onClick={() => refreshRebuildMutation.mutate()}
            disabled={refreshRebuildMutation.isPending}
            className="inline-flex items-center rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            data-testid="dpp-refresh-rebuild"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshRebuildMutation.isPending ? 'animate-spin' : ''}`} />
            {refreshRebuildMutation.isPending ? 'Refreshing...' : 'Refresh & Rebuild'}
          </button>
        </div>
        {refreshRebuildMutation.isError && (
          <p className="mb-4 text-sm text-red-600">
            {(refreshRebuildMutation.error as Error)?.message || 'Failed to refresh templates.'}
          </p>
        )}
        <div className="space-y-4">
          {submodels.length === 0 && (
            <p className="text-sm text-gray-500">
              No submodels yet. Add one from the templates below.
            </p>
          )}
          {submodels.map((submodel: any, index: number) => {
            const templateKey = resolveTemplateKey(submodel, availableTemplates);
            return (
            <div key={index} className="border rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-gray-900">{submodel.idShort}</h3>
                  <p className="text-sm text-gray-500">{submodel.id}</p>
                </div>
                {templateKey && (
                  <Link
                    to={`/console/dpps/${dpp.id}/edit/${templateKey}`}
                    className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700"
                    data-testid={`submodel-edit-${templateKey}`}
                  >
                    <Edit3 className="h-4 w-4 mr-1" />
                    Edit
                  </Link>
                )}
              </div>
              {submodel.submodelElements && (
                <div className="mt-4 space-y-2">
                  {submodel.submodelElements.map((element: any, idx: number) => (
                    <div key={idx} className="flex justify-between text-sm border-b pb-2">
                      <span className="text-gray-600">{element.idShort}</span>
                      <span className="text-gray-900">
                        {formatElementValue(element.value)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            );
          })}
        </div>
        {availableTemplates.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">
            No templates available. Refresh templates first.
          </p>
        ) : (
          missingTemplates.length > 0 && (
            <div className="mt-6 border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700">Available templates</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {missingTemplates.map((template: any) => (
                  <div
                    key={template.id}
                    className="flex items-center justify-between rounded-md border border-gray-200 p-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {template.template_key}
                      </p>
                      <p className="text-xs text-gray-500">v{template.idta_version}</p>
                    </div>
                    <Link
                      to={`/console/dpps/${dpp.id}/edit/${template.template_key}`}
                      className="text-sm text-primary-600 hover:text-primary-700"
                      data-testid={`submodel-add-${template.template_key}`}
                    >
                      Add
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )
        )}
      </div>

      {/* Integrity */}
      {dpp.digest_sha256 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Integrity</h2>
          <div>
            <dt className="text-sm font-medium text-gray-500">SHA-256 Digest</dt>
            <dd className="mt-1 text-xs font-mono text-gray-900 break-all bg-gray-50 p-2 rounded">
              {dpp.digest_sha256}
            </dd>
          </div>
        </div>
      )}
    </div>
  );
}
