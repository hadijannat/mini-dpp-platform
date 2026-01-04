import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { Plus, Eye, Edit } from 'lucide-react';
import { apiFetch } from '@/lib/api';

async function fetchDPPs(token?: string) {
  const response = await apiFetch('/api/v1/dpps', {}, token);
  if (!response.ok) throw new Error('Failed to fetch DPPs');
  return response.json();
}

async function createDPP(data: any, token?: string) {
  const response = await apiFetch('/api/v1/dpps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, token);
  if (!response.ok) throw new Error('Failed to create DPP');
  return response.json();
}

export default function DPPListPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data: dpps, isLoading } = useQuery({
    queryKey: ['dpps'],
    queryFn: () => fetchDPPs(token),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => createDPP(data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpps'] });
      setShowCreateModal(false);
    },
  });

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    createMutation.mutate({
      asset_ids: {
        manufacturerPartId: formData.get('manufacturerPartId'),
        serialNumber: formData.get('serialNumber'),
      },
      selected_templates: ['digital-nameplate'],
    });
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
        >
          <Plus className="h-4 w-4 mr-2" />
          Create DPP
        </button>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
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
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 border rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-md disabled:opacity-50"
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
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      dpp.status === 'published'
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
                        to={`/dpp/${dpp.id}`}
                        className="text-gray-400 hover:text-gray-600"
                        title="View"
                      >
                        <Eye className="h-5 w-5" />
                      </Link>
                      <Link
                        to={`/console/dpps/${dpp.id}`}
                        className="text-primary-400 hover:text-primary-600"
                        title="Edit"
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
        </div>
      )}
    </div>
  );
}
