import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { FileCode, RefreshCw } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { hasRoleLevel } from '@/lib/auth';
import { getTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { TemplateResponse } from '@/api/types';

type RebuildSummary = {
  total: number;
  updated: number;
  skipped: number;
  errors: Array<{ dpp_id: string; error: string }>;
};

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

async function refreshAndRebuildAll(token?: string) {
  const response = await tenantApiFetch('/dpps/rebuild-all', {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to rebuild all DPPs'));
  }
  return response.json();
}

export default function TemplatesPage() {
  const queryClient = useQueryClient();
  const auth = useAuth();
  const token = auth.user?.access_token;
  const canRebuildAll = hasRoleLevel(auth.user, 'tenant_admin');
  const tenantSlug = getTenantSlug();
  const [rebuildSummary, setRebuildSummary] = useState<RebuildSummary | null>(null);

  const {
    data: templates,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
    enabled: Boolean(token),
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshTemplates(token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: () => refreshAndRebuildAll(token),
    onSuccess: (data: RebuildSummary) => {
      setRebuildSummary(data);
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      queryClient.invalidateQueries({ queryKey: ['dpps', tenantSlug] });
    },
  });

  if (isError) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Unable to load templates</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {(error as Error)?.message || 'Something went wrong.'}
        </p>
        <div className="mt-4 flex gap-3">
          <Button
            onClick={() => auth.signinRedirect()}
          >
            Sign in again
          </Button>
          <Button
            variant="outline"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['templates'] })}
          >
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Templates"
        description="DPP4.0 Submodel Templates from IDTA"
        actions={
          <>
            {canRebuildAll && (
              <Button
                variant="secondary"
                onClick={() => rebuildMutation.mutate()}
                disabled={rebuildMutation.isPending}
                data-testid="templates-refresh-rebuild-all"
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${rebuildMutation.isPending ? 'animate-spin' : ''}`} />
                {rebuildMutation.isPending ? 'Rebuilding...' : 'Refresh & Rebuild All'}
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
              data-testid="templates-refresh-all"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
              {refreshMutation.isPending ? 'Refreshing...' : 'Refresh All'}
            </Button>
          </>
        }
      />

      {refreshMutation.isError && (
        <ErrorBanner
          message={(refreshMutation.error as Error)?.message || 'Failed to refresh templates.'}
        />
      )}
      {rebuildMutation.isError && (
        <ErrorBanner
          message={(rebuildMutation.error as Error)?.message || 'Failed to rebuild all DPPs.'}
        />
      )}
      {rebuildSummary && (
        <Alert className="border-green-200 bg-green-50 text-green-800">
          <AlertTitle>Rebuild complete</AlertTitle>
          <AlertDescription>
            <div>
              Updated: {rebuildSummary.updated} | Skipped: {rebuildSummary.skipped} | Total: {rebuildSummary.total}
            </div>
            {rebuildSummary.errors.length > 0 && (
              <div className="mt-2 text-destructive">
                {rebuildSummary.errors.length} errors. Check server logs for details.
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {templates?.templates?.map((template: TemplateResponse) => (
            <Card
              key={template.id}
              data-testid={`template-card-${template.template_key}`}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{template.template_key}</CardTitle>
                  <Badge variant="secondary">{template.idta_version}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <dl className="text-xs space-y-1">
                  <div>
                    <dt className="text-muted-foreground">Semantic ID</dt>
                    <dd className="truncate" title={template.semantic_id}>
                      {template.semantic_id}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Fetched</dt>
                    <dd>
                      {new Date(template.fetched_at).toLocaleString()}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {templates?.count === 0 && (
        <EmptyState
          icon={FileCode}
          title="No templates loaded"
          description='Click "Refresh All" to fetch templates from IDTA.'
        />
      )}
    </div>
  );
}
