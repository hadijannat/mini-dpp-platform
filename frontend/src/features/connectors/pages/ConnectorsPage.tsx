import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, TestTube, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

async function fetchConnectors() {
  const response = await fetch('/api/v1/connectors');
  if (!response.ok) throw new Error('Failed to fetch connectors');
  return response.json();
}

async function createConnector(data: any) {
  const response = await fetch('/api/v1/connectors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create connector');
  return response.json();
}

async function testConnector(connectorId: string) {
  const response = await fetch(`/api/v1/connectors/${connectorId}/test`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to test connector');
  return response.json();
}

export default function ConnectorsPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: connectors, isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: fetchConnectors,
  });

  const createMutation = useMutation({
    mutationFn: createConnector,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
      setShowCreateModal(false);
    },
  });

  const testMutation = useMutation({
    mutationFn: testConnector,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    createMutation.mutate({
      name: formData.get('name'),
      config: {
        dtr_base_url: formData.get('dtr_base_url'),
        auth_type: 'token',
        token: formData.get('token'),
        bpn: formData.get('bpn'),
        submodel_base_url: formData.get('submodel_base_url'),
      },
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Connectors</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage Catena-X DTR and EDC integrations
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Connector
        </button>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h2 className="text-lg font-semibold mb-4">Add Catena-X Connector</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Name</label>
                <input
                  name="name"
                  type="text"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">DTR Base URL</label>
                <input
                  name="dtr_base_url"
                  type="url"
                  required
                  placeholder="https://dtr.catena-x.net/api/v3"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Access Token</label>
                <input
                  name="token"
                  type="password"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">BPN</label>
                <input
                  name="bpn"
                  type="text"
                  placeholder="BPNL00000001TEST"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Submodel Base URL</label>
                <input
                  name="submodel_base_url"
                  type="url"
                  placeholder="https://your-domain.com/api/v1"
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

      {/* Connectors List */}
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
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Tested
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {connectors?.connectors?.map((connector: any) => (
                <tr key={connector.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {connector.name}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {connector.connector_type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(connector.status)}
                      <span className="ml-2 text-sm text-gray-900">{connector.status}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {connector.last_tested_at
                      ? new Date(connector.last_tested_at).toLocaleString()
                      : 'Never'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => testMutation.mutate(connector.id)}
                      disabled={testMutation.isPending}
                      className="inline-flex items-center text-primary-600 hover:text-primary-900"
                    >
                      <TestTube className="h-4 w-4 mr-1" />
                      Test
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!connectors?.connectors || connectors.connectors.length === 0) && (
            <div className="text-center py-12 text-gray-500">
              No connectors configured. Add one to integrate with Catena-X.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
