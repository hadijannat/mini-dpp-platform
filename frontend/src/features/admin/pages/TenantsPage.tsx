import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Plus, Users, Trash2, Building2 } from 'lucide-react';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

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
    enabled: Boolean(token),
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
    enabled: Boolean(token && selectedTenant?.slug),
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
      <PageHeader
        title="Tenants"
        description="Manage tenant workspaces and memberships."
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Tenant
          </Button>
        }
      />

      {error && (
        <ErrorBanner
          message={(error as Error)?.message || 'Failed to load tenants.'}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Tenant List</CardTitle>
          </CardHeader>
          {isLoading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <ScrollArea className="max-h-[500px]">
              <div className="divide-y">
                {tenants.map((tenant) => (
                  <button
                    key={tenant.id}
                    type="button"
                    className={cn(
                      'w-full px-6 py-4 text-left transition-colors',
                      selectedTenant?.id === tenant.id
                        ? 'bg-primary/5'
                        : 'hover:bg-muted/50'
                    )}
                    onClick={() => setSelectedTenant(tenant)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">{tenant.name}</p>
                        <p className="text-xs text-muted-foreground">{tenant.slug}</p>
                      </div>
                      <Badge
                        variant="secondary"
                        className={cn(
                          tenant.status === 'active'
                            ? 'bg-green-100 text-green-700 hover:bg-green-100'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-100'
                        )}
                      >
                        {tenant.status}
                      </Badge>
                    </div>
                  </button>
                ))}
                {tenants.length === 0 && (
                  <EmptyState
                    icon={Building2}
                    title="No tenants yet"
                    description="Create a tenant to get started."
                  />
                )}
              </div>
            </ScrollArea>
          )}
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="text-sm">Tenant Members</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                {selectedTenant ? selectedTenant.name : 'Select a tenant to manage members'}
              </p>
            </div>
            <Users className="h-5 w-5 text-muted-foreground" />
          </CardHeader>

          {selectedTenant ? (
            <CardContent className="space-y-4">
              <form onSubmit={handleAddMember} className="grid gap-3 sm:grid-cols-[2fr_1fr_auto]">
                <Input
                  name="user_subject"
                  type="text"
                  placeholder="user subject (OIDC sub)"
                  required
                />
                <select
                  name="role"
                  defaultValue="viewer"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="viewer">viewer</option>
                  <option value="publisher">publisher</option>
                  <option value="tenant_admin">tenant_admin</option>
                </select>
                <Button
                  type="submit"
                  disabled={addMemberMutation.isPending}
                >
                  Add
                </Button>
              </form>

              {membersQuery.isError && (
                <ErrorBanner
                  message={(membersQuery.error as Error)?.message || 'Failed to load members.'}
                />
              )}

              {membersQuery.isLoading ? (
                <LoadingSpinner size="sm" />
              ) : (
                <div className="space-y-2">
                  {(membersQuery.data?.members || []).map((member: TenantMember) => (
                    <Card key={member.user_subject} className="p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                            {member.user_subject.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-sm">{member.user_subject}</p>
                            <p className="text-xs text-muted-foreground">{member.role}</p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeMemberMutation.mutate(member.user_subject)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4 mr-1" />
                          Remove
                        </Button>
                      </div>
                    </Card>
                  ))}
                  {(membersQuery.data?.members || []).length === 0 && (
                    <EmptyState
                      icon={Users}
                      title="No members yet"
                      description="Add members to this tenant."
                    />
                  )}
                </div>
              )}
            </CardContent>
          ) : (
            <CardContent>
              <p className="text-sm text-muted-foreground">Select a tenant to view members.</p>
            </CardContent>
          )}
        </Card>
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Tenant</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateTenant} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="tenant-slug">Slug</Label>
              <Input
                id="tenant-slug"
                name="slug"
                type="text"
                required
                placeholder="tenant-slug"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tenant-name">Name</Label>
              <Input
                id="tenant-name"
                name="name"
                type="text"
                required
              />
            </div>
            {createMutation.isError && (
              <p className="text-sm text-destructive">
                {(createMutation.error as Error)?.message || 'Failed to create tenant.'}
              </p>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
