import { useEffect, useState } from 'react';
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
import { SubmodelNodeTree } from '@/features/submodels/components/SubmodelNodeTree';
import { buildDppActionState } from '@/features/submodels/policy/actionPolicy';
import { buildSubmodelNodeTree, computeSubmodelHealth, flattenSubmodelNodes } from '@/features/submodels/utils/treeBuilder';
import type { DppAccessSummary, SubmodelBinding, SubmodelNode } from '@/features/submodels/types';
import { emitSubmodelUxMetric } from '@/features/submodels/telemetry/uxTelemetry';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { StatusBadge } from '@/components/status-badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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

type RefreshRebuildSummary = {
  attempted: number;
  succeeded: Array<{ template_key: string; submodel_id: string; submodel: string }>;
  failed: Array<{ template_key?: string; submodel_id?: string; submodel: string; error: string }>;
  skipped: Array<{ submodel: string; reason: string }>;
};

type DppDetail = {
  id: string;
  status: string;
  asset_ids?: Record<string, unknown>;
  owner_subject?: string;
  current_revision_no?: number | null;
  digest_sha256?: string | null;
  aas_environment?: { submodels?: AASSubmodel[] };
  submodel_bindings?: SubmodelBinding[];
  access?: DppAccessSummary;
};

function isTemplateSelectable(template: TemplateResponse): boolean {
  return template.support_status !== 'unavailable' && template.refresh_enabled !== false;
}

type AASSubmodel = Record<string, unknown> & {
  idShort?: string;
  id?: string;
  semanticId?: { keys?: Array<{ value?: string }> };
  submodelElements?: Array<Record<string, unknown>>;
};

function maxTreeDepth(node: SubmodelNode, depth = 0): number {
  if (node.children.length === 0) return depth;
  return Math.max(...node.children.map((child) => maxTreeDepth(child, depth + 1)));
}

async function fetchDPP(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
  }
  return response.json() as Promise<DppDetail>;
}

async function fetchTemplates(token?: string) {
  const response = await apiFetch('/api/v1/templates', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch templates'));
  }
  return response.json();
}

async function refreshRebuildSubmodels(dppId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/${dppId}/submodels/refresh-rebuild`, {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to refresh and rebuild submodels'));
  }
  return response.json() as Promise<RefreshRebuildSummary>;
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
    mutationFn: async (): Promise<RefreshRebuildSummary> =>
      dppId
        ? refreshRebuildSubmodels(dppId, token)
        : { attempted: 0, succeeded: [], failed: [], skipped: [] },
    onSuccess: (summary) => {
      setRefreshRebuildSummary(summary);
      if (summary.failed.length > 0) {
        // eslint-disable-next-line no-console
        console.warn('dpp_refresh_rebuild_partial_failure', {
          failedTemplateKeys: summary.failed.map((entry) => entry.template_key),
          failedCount: summary.failed.length,
          succeededCount: summary.succeeded.length,
          skippedCount: summary.skipped.length,
        });
      }
      queryClient.invalidateQueries({ queryKey: ['dpp', tenantSlug, dppId] });
      queryClient.invalidateQueries({ queryKey: ['templates'] });
    },
  });

  const handleExport = async (format: ExportFormat) => {
    if (!dpp) return;
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
    if (!dpp) return;
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
    if (!dpp) return;
    if (!dpp.digest_sha256) return;
    await navigator.clipboard.writeText(dpp.digest_sha256);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const submodels: AASSubmodel[] = dpp?.aas_environment?.submodels || [];
  const availableTemplates: TemplateResponse[] = templatesData?.templates || [];
  const submodelBindings: SubmodelBinding[] = Array.isArray(dpp?.submodel_bindings)
    ? dpp.submodel_bindings
    : [];
  const bindingBySubmodelId = new Map(
    submodelBindings
      .filter((binding) => binding.submodel_id)
      .map((binding) => [String(binding.submodel_id), binding]),
  );
  const actionState = buildDppActionState(dpp?.access, dpp?.status ?? '');
  const manufacturerPartId =
    typeof dpp?.asset_ids?.manufacturerPartId === 'string'
      ? dpp.asset_ids.manufacturerPartId
      : null;
  const existingTemplateKeys = new Set(
    submodelBindings
      .map((binding) => binding.template_key ?? null)
      .filter((value: string | null): value is string => Boolean(value)),
  );
  const missingTemplates = availableTemplates.filter(
    (template: TemplateDescriptor) => !existingTemplateKeys.has(template.template_key),
  );

  useEffect(() => {
    if (!dppId || !dpp || submodels.length === 0) return;
    const roots = submodels.map((submodel) => buildSubmodelNodeTree(submodel));
    const maxDepth = Math.max(...roots.map((root) => maxTreeDepth(root, 0)));
    const totalNodes = roots.reduce((sum, root) => sum + flattenSubmodelNodes(root).length, 0);
    emitSubmodelUxMetric('render_depth_coverage', {
      dpp_id: dppId,
      submodel_count: submodels.length,
      max_depth: maxDepth,
      node_count: totalNodes,
    });
  }, [dppId, dpp, submodels]);

  useEffect(() => {
    if (!dppId || !dpp) return;
    const reasons: string[] = [];
    if (!actionState.canExport) reasons.push('export:requires-read');
    if (!actionState.canPublish && dpp.status === 'draft') reasons.push('publish:requires-can_publish');
    if (!actionState.canRefreshRebuild) reasons.push('refresh-rebuild:requires-update-non-archived');
    if (!actionState.canCaptureEvent && dpp.status === 'draft') reasons.push('capture-event:requires-update');
    if (reasons.length > 0) {
      emitSubmodelUxMetric('action_disabled_reason', {
        dpp_id: dppId,
        status: dpp.status,
        reasons,
      });
    }
  }, [actionState, dpp?.status, dppId]);

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={manufacturerPartId || 'DPP Editor'}
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
                <Button variant="outline" disabled={!actionState.canExport}>
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
                {actionState.canGenerateQr && (
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
                disabled={publishMutation.isPending || !actionState.canPublish}
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
            disabled={refreshRebuildMutation.isPending || !actionState.canRefreshRebuild}
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
                .map((entry) => entry.template_key ?? entry.submodel)
                .join(', ')}`}
            </p>
          )}
          {refreshRebuildSummary && refreshRebuildSummary.skipped.length > 0 && (
            <p className="mb-4 text-sm text-muted-foreground">
              {`Skipped submodels: ${refreshRebuildSummary.skipped
                .map((entry) => `${entry.submodel} (${entry.reason})`)
                .join(', ')}`}
            </p>
          )}
          {submodels.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No submodels yet. Add one from the templates below.
            </p>
          ) : (
            <div className="space-y-4">
              {submodels.map((submodel, index) => {
                const submodelId = String(submodel.id ?? `submodel-${index}`);
                const binding = bindingBySubmodelId.get(submodelId);
                const templateKey = binding?.template_key ?? null;
                const editHref =
                  templateKey && binding?.submodel_id
                    ? `/console/dpps/${dpp.id}/edit/${templateKey}?submodel_id=${encodeURIComponent(binding.submodel_id)}`
                    : templateKey
                      ? `/console/dpps/${dpp.id}/edit/${templateKey}`
                      : null;
                const rootNode = buildSubmodelNodeTree(submodel);
                const health = computeSubmodelHealth(rootNode);
                const requiredCompletion =
                  health.totalRequired === 0
                    ? 'No required fields'
                    : `${health.completedRequired}/${health.totalRequired} required`;

                return (
                  <Card key={submodelId} className="border bg-card/70">
                    <CardHeader className="pb-2">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <CardTitle className="text-base">{String(submodel.idShort ?? 'Submodel')}</CardTitle>
                            {templateKey && <Badge variant="secondary">{templateKey}</Badge>}
                            {binding?.support_status && (
                              <Badge
                                variant={binding.support_status === 'supported' ? 'outline' : 'destructive'}
                                className="text-[10px]"
                              >
                                {binding.support_status}
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground break-all">{String(submodel.id ?? '-')}</p>
                          {binding?.semantic_id && (
                            <p className="text-[11px] text-muted-foreground break-all">
                              semantic: {binding.semantic_id}
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{requiredCompletion}</Badge>
                          <Badge variant="outline">{health.leafCount} leaf fields</Badge>
                          <Badge variant="outline">{health.validationSignals} rule signals</Badge>
                          {binding?.binding_source && (
                            <Badge variant="outline" className="uppercase text-[10px]">
                              {binding.binding_source}
                            </Badge>
                          )}
                          {templateKey && (
                            <Button
                              variant="outline"
                              size="sm"
                              asChild={actionState.canUpdate}
                              disabled={!actionState.canUpdate}
                            >
                              {actionState.canUpdate ? (
                                <Link
                                  to={editHref!}
                                  data-testid={`submodel-edit-${templateKey}`}
                                >
                                  <Edit3 className="h-4 w-4 mr-1" />
                                  Edit
                                </Link>
                              ) : (
                                <span>
                                  <Edit3 className="h-4 w-4 mr-1 inline" />
                                  Edit
                                </span>
                              )}
                            </Button>
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <SubmodelNodeTree root={rootNode} showSemanticMeta />
                    </CardContent>
                  </Card>
                );
              })}
            </div>
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
                        <Button
                          variant="outline"
                          size="sm"
                          asChild={actionState.canUpdate && isTemplateSelectable(template)}
                          disabled={!actionState.canUpdate || !isTemplateSelectable(template)}
                        >
                          {actionState.canUpdate && isTemplateSelectable(template) ? (
                            <Link
                              to={`/console/dpps/${dpp.id}/edit/${template.template_key}`}
                              data-testid={`submodel-add-${template.template_key}`}
                            >
                              Add
                            </Link>
                          ) : (
                            <span>Add</span>
                          )}
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCaptureOpen(true)}
              disabled={!actionState.canCaptureEvent}
            >
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
