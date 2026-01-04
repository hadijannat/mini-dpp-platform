import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { RefreshCw } from 'lucide-react';
import { apiFetch } from '@/lib/api';

async function fetchTemplates(token?: string) {
  const response = await apiFetch('/api/v1/templates', {}, token);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

async function refreshTemplates(token?: string) {
  const response = await apiFetch('/api/v1/templates/refresh', {
    method: 'POST',
  }, token);
  if (!response.ok) throw new Error('Failed to refresh templates');
  return response.json();
}

export default function TemplatesPage() {
  const queryClient = useQueryClient();
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data: templates, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshTemplates(token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Templates</h1>
          <p className="mt-1 text-sm text-gray-500">
            DPP4.0 Submodel Templates from IDTA
          </p>
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
          {refreshMutation.isPending ? 'Refreshing...' : 'Refresh All'}
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {templates?.templates?.map((template: any) => (
            <div key={template.id} className="bg-white shadow rounded-lg p-6">
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
