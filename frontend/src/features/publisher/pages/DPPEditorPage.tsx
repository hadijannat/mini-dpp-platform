import { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { ArrowLeft, Send, Download, QrCode, Edit3, RefreshCw, Copy, Check, Activity, Plus, History } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { fetchEPCISEvents } from '@/features/epcis/lib/epcisApi';
import { EPCISTimeline } from '@/features/epcis/components/EPCISTimeline';
import { CaptureDialog } from '@/features/epcis/components/CaptureDialog';
import { RevisionHistory } from '../components/RevisionHistory';
import { useTenantSlug } from '@/lib/tenant';
import { buildSubmodelData } from '@/features/editor/utils/submodelData';
import {
  summarizeRefreshRebuildSettled,
  type RefreshRebuildSummary,
  type RefreshRebuildTask,
} from '@/features/publisher/utils/refreshRebuildSummary';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { StatusBadge } from '@/components/status-badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { TemplateResponse } from '@/api/types';

type TemplateDescriptor = {
  template_key: string;
  semantic_id: string;
};

type AASSubmodel = Record<string, unknown> & {
  idShort?: string;
  id?: string;
  semanticId?: { keys?: Array<{ value?: string }> };
  submodelElements?: Array<Record<string, unknown>>;
};

function extractSemanticId(submodel: AASSubmodel): string | null {
  const semanticId = submodel?.semanticId;
  if (semanticId && Array.isArray(semanticId.keys) && semanticId.keys[0]?.value) {
    return String(semanticId.keys[0].value);
  }
  return null;
}

function resolveTemplateKey(submodel: AASSubmodel, templates: TemplateDescriptor[]): string | null {
  if (!Array.isArray(templates)) return null;
  const semanticId = extractSemanticId(submodel);
  if (semanticId) {
    const direct = templates.find((template) => template.semantic_id === semanticId);
    if (direct) return direct.template_key;
    const partial = templates.find((template) =>
      semanticId.includes(template.semantic_id) || template.semantic_id.includes(semanticId)
    );
    if (partial) return partial.template_key;
  }
  // Dynamic idShort fallback: match idShort against template keys (kebab-case)
  const idShort = submodel?.idShort;
  if (idShort) {
    const kebab = idShort.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
    const byKey = templates.find((t) =>
      t.template_key === kebab || t.template_key.includes(kebab) || kebab.includes(t.template_key)
    );
    if (byKey) return byKey.template_key;
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

type ExportFormat = 'json' | 'aasx' | 'pdf' | 'jsonld' | 'turtle' | 'xml';

const EXPORT_EXTENSIONS: Record<ExportFormat, string> = {
  json: 'json',
  aasx: 'aasx',
  pdf: 'pdf',
  jsonld: 'jsonld',
  turtle: 'ttl',
  xml: 'xml',
};

async function downloadExport(dppId: string, format: ExportFormat, token?: string) {
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
  link.download = `dpp-${dppId}.${EXPORT_EXTENSIONS[format]}`;
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
  const [tenantSlug] = useTenantSlug();
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshRebuildSummary, setRefreshRebuildSummary] = useState<RefreshRebuildSummary | null>(
    null,
  );
  const [copied, setCopied] = useState(false);
  const [captureOpen, setCaptureOpen] = useState(false);

  const { data: dpp, isLoading } = useQuery({
    queryKey: ['dpp', tenantSlug, dppId],
    queryFn: () => fetchDPP(dppId!, token),
    enabled: Boolean(token && dppId),
  });

  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
    enabled: Boolean(token),
  });

  const { data: epcisData, isLoading: epcisLoading, isError: epcisError } = useQuery({
    queryKey: ['epcis-events', dppId],
    queryFn: () => fetchEPCISEvents({ dpp_id: dppId!, limit: 50 }, token),
    enabled: Boolean(token && dppId),
  });

  const publishMutation = useMutation({
    mutationFn: () => publishDPP(dppId!, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpp', tenantSlug, dppId] });
    },
  });

  const publishError = publishMutation.isError ? (publishMutation.error as Error) : null;
  const bannerMessage = actionError ?? publishError?.message ?? null;
  const sessionExpired = Boolean(bannerMessage?.includes('Session expired'));

  const refreshRebuildMutation = useMutation({
    onMutate: () => {
      setRefreshRebuildSummary(null);
      setActionError(null);
    },
    mutationFn: async (): Promise<RefreshRebuildSummary> => {
      if (!dppId) {
        return { succeeded: [], failed: [], skipped: [] };
      }
      const refreshed = await refreshTemplates(token);
      const refreshedTemplates = Array.isArray(refreshed?.templates)
        ? (refreshed.templates as TemplateDescriptor[])
        : [];
      const templatesForRebuild =
        refreshedTemplates.length > 0 ? refreshedTemplates : availableTemplates;

      const submodels = dpp?.aas_environment?.submodels || [];
      const seen = new Set<string>();
      const rebuildTasks: Array<RefreshRebuildTask & { promise: Promise<unknown> }> = [];
      const skippedSubmodels = new Set<string>();

      for (const submodel of submodels) {
        const templateKey = resolveTemplateKey(submodel, templatesForRebuild);
        if (!templateKey) {
          skippedSubmodels.add(
            String(submodel.idShort ?? submodel.id ?? `submodel-${skippedSubmodels.size + 1}`),
          );
          continue;
        }
        if (seen.has(templateKey)) continue;
        seen.add(templateKey);
        const data = buildSubmodelData(submodel);
        rebuildTasks.push({
          templateKey,
          promise: rebuildSubmodel(dppId, templateKey, data, token),
        });
      }

      if (rebuildTasks.length === 0) {
        return {
          succeeded: [],
          failed: [],
          skipped: Array.from(skippedSubmodels).sort((a, b) => a.localeCompare(b)),
        };
      }

      const settled = await Promise.allSettled(rebuildTasks.map((task) => task.promise));
      return summarizeRefreshRebuildSettled(rebuildTasks, settled, skippedSubmodels);
    },
    onSuccess: (summary) => {
      setRefreshRebuildSummary(summary);
      if (summary.failed.length > 0) {
        // eslint-disable-next-line no-console
        console.warn('dpp_refresh_rebuild_partial_failure', {
          failedTemplateKeys: summary.failed.map((entry) => entry.templateKey),
          failedCount: summary.failed.length,
          succeededCount: summary.succeeded.length,
          skippedCount: summary.skipped.length,
        });
      }
      if (summary.succeeded.length > 0) {
        queryClient.invalidateQueries({ queryKey: ['dpp', tenantSlug, dppId] });
        queryClient.invalidateQueries({ queryKey: ['templates'] });
      }
    },
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!dpp) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">DPP not found</p>
      </div>
    );
  }

  const handleExport = async (format: ExportFormat) => {
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

  const handleCopyDigest = async () => {
    if (!dpp.digest_sha256) return;
    await navigator.clipboard.writeText(dpp.digest_sha256);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const submodels: AASSubmodel[] = dpp.aas_environment?.submodels || [];
  const availableTemplates: TemplateResponse[] = templatesData?.templates || [];
  const existingTemplateKeys = new Set(
    submodels
      .map((submodel) => resolveTemplateKey(submodel, availableTemplates))
      .filter((value: string | null): value is string => Boolean(value))
  );
  const missingTemplates = availableTemplates.filter(
    (template: TemplateDescriptor) => !existingTemplateKeys.has(template.template_key)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={dpp.asset_ids?.manufacturerPartId || 'DPP Editor'}
        description={`ID: ${dpp.id}`}
        breadcrumb={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/console/dpps')}
            data-testid="dpp-back"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
        }
        actions={
          <>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => { void handleExport('json'); }}>
                  Export JSON
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => { void handleExport('pdf'); }}>
                  Export PDF
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => { void handleExport('aasx'); }}>
                  Export AASX
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => { void handleExport('jsonld'); }}>
                  Export JSON-LD
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => { void handleExport('turtle'); }}>
                  Export Turtle
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => { void handleExport('xml'); }}>
                  Export XML
                </DropdownMenuItem>
                {dpp.status === 'published' && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => { void handleQrCode(); }}>
                      <QrCode className="h-4 w-4 mr-2" />
                      QR Code
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            {dpp.status === 'draft' && (
              <Button
                onClick={() => publishMutation.mutate()}
                disabled={publishMutation.isPending}
                className="bg-green-600 hover:bg-green-700"
              >
                <Send className="h-4 w-4 mr-2" />
                {publishMutation.isPending ? 'Publishing...' : 'Publish'}
              </Button>
            )}
          </>
        }
      />

      {bannerMessage && (
        <ErrorBanner
          message={bannerMessage}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      {/* Status */}
      <Card>
        <CardContent className="flex items-center justify-between p-6">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">Status</span>
            <StatusBadge status={dpp.status} />
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">Revision</p>
            <p className="text-lg font-bold">#{dpp.current_revision_no || 1}</p>
          </div>
        </CardContent>
      </Card>

      {/* Asset Information */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Asset Information</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {(Object.entries(dpp.asset_ids || {}) as Array<[string, unknown]>).map(([key, value]) => (
              <div key={key}>
                <dt className="text-sm font-medium text-muted-foreground">{key}</dt>
                <dd className="mt-1 text-sm">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {/* Submodels */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-lg">Submodels</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refreshRebuildMutation.mutate()}
            disabled={refreshRebuildMutation.isPending || dpp.status === 'archived'}
            data-testid="dpp-refresh-rebuild"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshRebuildMutation.isPending ? 'animate-spin' : ''}`} />
            {refreshRebuildMutation.isPending ? 'Refreshing...' : 'Refresh & Rebuild'}
          </Button>
        </CardHeader>
        <CardContent>
          {refreshRebuildMutation.isError && (
            <p className="mb-4 text-sm text-destructive">
              {(refreshRebuildMutation.error as Error)?.message || 'Failed to refresh templates.'}
            </p>
          )}
          {refreshRebuildSummary && refreshRebuildSummary.failed.length > 0 && (
            <p className="mb-4 text-sm text-destructive">
              {`Refresh & Rebuild partially failed for templates: ${refreshRebuildSummary.failed
                .map((entry) => entry.templateKey)
                .join(', ')}`}
            </p>
          )}
          {refreshRebuildSummary && refreshRebuildSummary.skipped.length > 0 && (
            <p className="mb-4 text-sm text-muted-foreground">
              {`Skipped submodels (no matching template): ${refreshRebuildSummary.skipped.join(
                ', ',
              )}`}
            </p>
          )}
          {submodels.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No submodels yet. Add one from the templates below.
            </p>
          ) : (
            <Accordion type="multiple" defaultValue={submodels.map((_, i) => `sm-${i}`)}>
              {submodels.map((submodel, index) => {
                const templateKey = resolveTemplateKey(submodel, availableTemplates);
                return (
                  <AccordionItem key={index} value={`sm-${index}`}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex items-center justify-between w-full pr-4">
                        <span>{submodel.idShort}</span>
                        {templateKey && <Badge variant="secondary">{templateKey}</Badge>}
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <p className="text-xs text-muted-foreground mb-3">{submodel.id}</p>
                      {submodel.submodelElements && (
                        <div className="space-y-2">
                          {submodel.submodelElements.map((element: Record<string, unknown>, idx: number) => (
                            <div key={idx} className="flex justify-between text-sm border-b pb-2">
                              <span className="text-muted-foreground">{String(element.idShort ?? '')}</span>
                              <span>{formatElementValue(element.value)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {templateKey && (
                        <Button variant="link" asChild className="mt-3 px-0">
                          <Link
                            to={`/console/dpps/${dpp.id}/edit/${templateKey}`}
                            data-testid={`submodel-edit-${templateKey}`}
                          >
                            <Edit3 className="h-4 w-4 mr-1" />
                            Edit
                          </Link>
                        </Button>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          )}

          {/* Missing templates */}
          {availableTemplates.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              No templates available. Refresh templates first.
            </p>
          ) : (
            missingTemplates.length > 0 && (
              <div className="mt-6 border-t pt-4">
                <h3 className="text-sm font-semibold mb-3">Available templates</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  {missingTemplates.map((template) => (
                    <Card key={template.id} className="p-0">
                      <CardContent className="flex items-center justify-between p-3">
                        <div>
                          <p className="text-sm font-medium">{template.template_key}</p>
                          <p className="text-xs text-muted-foreground">v{template.idta_version}</p>
                        </div>
                        <Button variant="outline" size="sm" asChild>
                          <Link
                            to={`/console/dpps/${dpp.id}/edit/${template.template_key}`}
                            data-testid={`submodel-add-${template.template_key}`}
                          >
                            Add
                          </Link>
                        </Button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )
          )}
        </CardContent>
      </Card>

      {/* Integrity */}
      {dpp.digest_sha256 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Integrity</CardTitle>
          </CardHeader>
          <CardContent>
            <dt className="text-sm font-medium text-muted-foreground">SHA-256 Digest</dt>
            <div className="mt-1 flex items-start gap-2">
              <dd className="text-xs font-mono break-all bg-muted p-2 rounded flex-1">
                {dpp.digest_sha256}
              </dd>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-8 w-8"
                onClick={() => { void handleCopyDigest(); }}
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Revision History */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <History className="h-5 w-5" />
            Revision History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <RevisionHistory dppId={dpp.id} token={token} />
        </CardContent>
      </Card>

      {/* Supply Chain Events */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Supply Chain
            {(epcisData?.eventList?.length ?? 0) > 0 && (
              <Badge variant="secondary" className="ml-1">
                {epcisData!.eventList.length}
              </Badge>
            )}
          </CardTitle>
          {dpp.status === 'draft' && (
            <Button variant="outline" size="sm" onClick={() => setCaptureOpen(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Capture Event
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {epcisLoading ? (
            <div className="flex justify-center py-4">
              <LoadingSpinner />
            </div>
          ) : epcisError ? (
            <p className="text-sm text-destructive">Failed to load supply chain events.</p>
          ) : (
            <>
              <EPCISTimeline events={epcisData?.eventList ?? []} />
              {dppId && (
                <Link
                  to={`/console/epcis?dpp_id=${dppId}`}
                  className="mt-3 inline-block text-sm text-muted-foreground hover:underline"
                >
                  View all events
                </Link>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {captureOpen && dppId && (
        <CaptureDialog
          open={captureOpen}
          onOpenChange={setCaptureOpen}
          dppId={dppId}
        />
      )}
    </div>
  );
}
