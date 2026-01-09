import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { FileText, Plus, ArrowRight } from 'lucide-react';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

async function fetchDPPs(token?: string) {
  const response = await apiFetch('/api/v1/dpps', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPPs'));
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

export default function DashboardPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data: dpps } = useQuery({
    queryKey: ['dpps'],
    queryFn: () => fetchDPPs(token),
  });

  const { data: templates } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
  });

  const stats = [
    { name: 'Total DPPs', value: dpps?.count || 0 },
    { name: 'Published', value: dpps?.dpps?.filter((d: any) => d.status === 'published').length || 0 },
    { name: 'Drafts', value: dpps?.dpps?.filter((d: any) => d.status === 'draft').length || 0 },
    { name: 'Templates', value: templates?.count || 0 },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your Digital Product Passports
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="bg-white overflow-hidden shadow rounded-lg"
          >
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <FileText className="h-6 w-6 text-gray-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      {stat.name}
                    </dt>
                    <dd className="text-lg font-semibold text-gray-900">
                      {stat.value}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Link
            to="/console/dpps"
            className="flex items-center p-4 border rounded-lg hover:bg-gray-50"
          >
            <Plus className="h-8 w-8 text-primary-500" />
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">Create DPP</h3>
              <p className="text-sm text-gray-500">Create a new Digital Product Passport</p>
            </div>
            <ArrowRight className="ml-auto h-5 w-5 text-gray-400" />
          </Link>

          <Link
            to="/console/templates"
            className="flex items-center p-4 border rounded-lg hover:bg-gray-50"
          >
            <FileText className="h-8 w-8 text-primary-500" />
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">View Templates</h3>
              <p className="text-sm text-gray-500">Browse available DPP4.0 templates</p>
            </div>
            <ArrowRight className="ml-auto h-5 w-5 text-gray-400" />
          </Link>

          <Link
            to="/console/connectors"
            className="flex items-center p-4 border rounded-lg hover:bg-gray-50"
          >
            <FileText className="h-8 w-8 text-primary-500" />
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">Manage Connectors</h3>
              <p className="text-sm text-gray-500">Configure Catena-X integrations</p>
            </div>
            <ArrowRight className="ml-auto h-5 w-5 text-gray-400" />
          </Link>
        </div>
      </div>

      {/* Recent DPPs */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent DPPs</h2>
        {dpps?.dpps?.length > 0 ? (
          <ul className="divide-y divide-gray-200">
            {dpps.dpps.slice(0, 5).map((dpp: any) => (
              <li key={dpp.id} className="py-4">
                <Link to={`/console/dpps/${dpp.id}`} className="flex items-center justify-between hover:bg-gray-50 -mx-4 px-4 py-2 rounded">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {dpp.asset_ids?.manufacturerPartId || dpp.id}
                    </p>
                    <p className="text-sm text-gray-500">
                      Created: {new Date(dpp.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    dpp.status === 'published'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {dpp.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-500 text-sm">No DPPs yet. Create your first one!</p>
        )}
      </div>
    </div>
  );
}
