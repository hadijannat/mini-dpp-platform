import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Plus, Users, Trash2 } from 'lucide-react';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

interface Tenant {
  id: string;
  slug: string;
  name: string;
  status: string;
}

interface TenantMember {
  user_subject: string;
  role: string;
  created_at: string;
}

async function fetchTenants(token?: string) {
  const response = await apiFetch('/api/v1/tenants', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load tenants'));
  }
  return response.json();
}

async function createTenant(payload: { slug: string; name: string }, token?: string) {
  const response = await apiFetch('/api/v1/tenants', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to create tenant'));
  }
  return response.json();
}

async function fetchMembers(tenantSlug: string, token?: string) {
  const response = await apiFetch(`/api/v1/tenants/${tenantSlug}/members`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load members'));
  }
  return response.json();
}

async function addMember(
  tenantSlug: string,
  payload: { user_subject: string; role: string },
  token?: string,
) {
  const response = await apiFetch(`/api/v1/tenants/${tenantSlug}/members`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to add member'));
  }
  return response.json();
}

async function removeMember(tenantSlug: string, userSubject: string, token?: string) {
  const response = await apiFetch(
    `/api/v1/tenants/${tenantSlug}/members/${encodeURIComponent(userSubject)}`,
    { method: 'DELETE' },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to remove member'));
  }
  return true;
}

export default function TenantsPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);

  const { data: tenantsData, isLoading, error } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => fetchTenants(token),
  });

  const createMutation = useMutation({
    mutationFn: (payload: { slug: string; name: string }) => createTenant(payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      setShowCreate(false);
    },
  });

  const membersQuery = useQuery({
    queryKey: ['tenant-members', selectedTenant?.slug],
    queryFn: () => fetchMembers(selectedTenant!.slug, token),
    enabled: !!selectedTenant?.slug,
  });

  const addMemberMutation = useMutation({
    mutationFn: (payload: { user_subject: string; role: string }) =>
      addMember(selectedTenant!.slug, payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-members', selectedTenant?.slug] });
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userSubject: string) => removeMember(selectedTenant!.slug, userSubject, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-members', selectedTenant?.slug] });
    },
  });

  const tenants: Tenant[] = useMemo(() => tenantsData?.tenants || [], [tenantsData]);

  const handleCreateTenant = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const slug = String(formData.get('slug') || '').trim().toLowerCase();
    const name = String(formData.get('name') || '').trim();
    if (!slug || !name) return;
    createMutation.mutate({ slug, name });
  };

  const handleAddMember = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTenant) return;
    const formData = new FormData(event.currentTarget);
    const userSubject = String(formData.get('user_subject') || '').trim();
    const role = String(formData.get('role') || 'viewer');
    if (!userSubject) return;
    addMemberMutation.mutate({ user_subject: userSubject, role });
    event.currentTarget.reset();
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tenants</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage tenant workspaces and memberships.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Tenant
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(error as Error)?.message || 'Failed to load tenants.'}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="text-sm font-semibold text-gray-700">Tenant List</h2>
          </div>
          {isLoading ? (
            <div className="p-6 text-sm text-gray-500">Loading tenants...</div>
          ) : (
            <ul className="divide-y">
              {tenants.map((tenant) => (
                <li
                  key={tenant.id}
                  className={`px-6 py-4 cursor-pointer ${
                    selectedTenant?.id === tenant.id ? 'bg-primary-50' : 'hover:bg-gray-50'
                  }`}
                  onClick={() => setSelectedTenant(tenant)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{tenant.name}</p>
                      <p className="text-xs text-gray-500">{tenant.slug}</p>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      tenant.status === 'active'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-200 text-gray-600'
                    }`}>
                      {tenant.status}
                    </span>
                  </div>
                </li>
              ))}
              {tenants.length === 0 && (
                <li className="px-6 py-6 text-sm text-gray-500">No tenants yet.</li>
              )}
            </ul>
          )}
        </div>

        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">Tenant Members</h2>
              <p className="text-xs text-gray-500">
                {selectedTenant ? selectedTenant.name : 'Select a tenant to manage members'}
              </p>
            </div>
            <Users className="h-5 w-5 text-gray-400" />
          </div>

          {selectedTenant ? (
            <div className="p-6 space-y-4">
              <form onSubmit={handleAddMember} className="grid gap-3 sm:grid-cols-[2fr_1fr_auto]">
                <input
                  name="user_subject"
                  type="text"
                  placeholder="user subject (OIDC sub)"
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm"
                  required
                />
                <select
                  name="role"
                  defaultValue="viewer"
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="viewer">viewer</option>
                  <option value="publisher">publisher</option>
                  <option value="tenant_admin">tenant_admin</option>
                </select>
                <button
                  type="submit"
                  className="inline-flex items-center justify-center rounded-md bg-primary-600 px-3 py-2 text-sm text-white hover:bg-primary-700"
                  disabled={addMemberMutation.isPending}
                >
                  Add
                </button>
              </form>

              {membersQuery.isError && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {(membersQuery.error as Error)?.message || 'Failed to load members.'}
                </div>
              )}

              {membersQuery.isLoading ? (
                <div className="text-sm text-gray-500">Loading members...</div>
              ) : (
                <div className="space-y-2">
                  {(membersQuery.data?.members || []).map((member: TenantMember) => (
                    <div
                      key={member.user_subject}
                      className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2"
                    >
                      <div>
                        <p className="text-sm text-gray-900">{member.user_subject}</p>
                        <p className="text-xs text-gray-500">{member.role}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeMemberMutation.mutate(member.user_subject)}
                        className="inline-flex items-center text-xs text-red-600 hover:text-red-800"
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        Remove
                      </button>
                    </div>
                  ))}
                  {(membersQuery.data?.members || []).length === 0 && (
                    <div className="text-sm text-gray-500">No members yet.</div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 text-sm text-gray-500">Select a tenant to view members.</div>
          )}
        </div>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h2 className="text-lg font-semibold mb-4">Create Tenant</h2>
            <form onSubmit={handleCreateTenant} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Slug</label>
                <input
                  name="slug"
                  type="text"
                  required
                  placeholder="tenant-slug"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Name</label>
                <input
                  name="name"
                  type="text"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              {createMutation.isError && (
                <p className="text-sm text-red-600">
                  {(createMutation.error as Error)?.message || 'Failed to create tenant.'}
                </p>
              )}
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
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
    </div>
  );
}
