import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { RefreshCw } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';

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
  const userRoles = (auth.user?.profile as any)?.realm_access?.roles || [];
  const isAdmin = userRoles.includes('admin');
  const [rebuildSummary, setRebuildSummary] = useState<RebuildSummary | null>(null);

  const {
    data: templates,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
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
      queryClient.invalidateQueries({ queryKey: ['dpps'] });
    },
  });

  if (isError) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900">Unable to load templates</h2>
        <p className="mt-2 text-sm text-gray-600">
          {(error as Error)?.message || 'Something went wrong.'}
        </p>
        <div className="mt-4 flex gap-3">
          <button
            type="button"
            onClick={() => auth.signinRedirect()}
            className="px-4 py-2 rounded-md text-sm text-white bg-primary-600 hover:bg-primary-700"
          >
            Sign in again
          </button>
          <button
            type="button"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['templates'] })}
            className="px-4 py-2 rounded-md text-sm text-gray-700 border border-gray-300 hover:bg-gray-50"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Templates</h1>
          <p className="mt-1 text-sm text-gray-500">
            DPP4.0 Submodel Templates from IDTA
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <button
              onClick={() => rebuildMutation.mutate()}
              disabled={rebuildMutation.isPending}
              className="inline-flex items-center px-4 py-2 border border-primary-300 rounded-md shadow-sm text-sm font-medium text-primary-700 bg-primary-50 hover:bg-primary-100 disabled:opacity-50"
              data-testid="templates-refresh-rebuild-all"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${rebuildMutation.isPending ? 'animate-spin' : ''}`} />
              {rebuildMutation.isPending ? 'Rebuilding...' : 'Refresh & Rebuild All'}
            </button>
          )}
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            data-testid="templates-refresh-all"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
            {refreshMutation.isPending ? 'Refreshing...' : 'Refresh All'}
          </button>
        </div>
      </div>
      {refreshMutation.isError && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(refreshMutation.error as Error)?.message || 'Failed to refresh templates.'}
        </div>
      )}
      {rebuildMutation.isError && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(rebuildMutation.error as Error)?.message || 'Failed to rebuild all DPPs.'}
        </div>
      )}
      {rebuildSummary && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          <div className="font-medium">Rebuild complete</div>
          <div className="mt-1">
            Updated: {rebuildSummary.updated} | Skipped: {rebuildSummary.skipped} | Total: {rebuildSummary.total}
          </div>
          {rebuildSummary.errors.length > 0 && (
            <div className="mt-2 text-red-700">
              {rebuildSummary.errors.length} errors. Check server logs for details.
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {templates?.templates?.map((template: any) => (
            <div
              key={template.id}
              className="bg-white shadow rounded-lg p-6"
              data-testid={`template-card-${template.template_key}`}
            >
              <h3 className="text-lg font-medium text-gray-900">
                {template.template_key}
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Version: {template.idta_version}
              </p>
              <div className="mt-4 pt-4 border-t">
                <dl className="text-xs space-y-1">
                  <div>
                    <dt className="text-gray-500">Semantic ID</dt>
                    <dd className="text-gray-700 truncate" title={template.semantic_id}>
                      {template.semantic_id}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Fetched</dt>
                    <dd className="text-gray-700">
                      {new Date(template.fetched_at).toLocaleString()}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          ))}
        </div>
      )}

      {templates?.count === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <p className="text-gray-500">
            No templates loaded. Click "Refresh All" to fetch templates from IDTA.
          </p>
        </div>
      )}
    </div>
  );
}
