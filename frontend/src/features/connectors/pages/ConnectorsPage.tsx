import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Plus, TestTube, CheckCircle, XCircle, AlertCircle, Link2 } from 'lucide-react';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card } from '@/components/ui/card';

async function fetchConnectors(token?: string) {
  const response = await tenantApiFetch('/connectors', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch connectors'));
  }
  return response.json();
}

async function createConnector(data: any, token?: string) {
  const response = await tenantApiFetch('/connectors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to create connector'));
  }
  return response.json();
}

async function testConnector(connectorId: string, token?: string) {
  const response = await tenantApiFetch(`/connectors/${connectorId}/test`, {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to test connector'));
  }
  return response.json();
}

export default function ConnectorsPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();

  const { data: connectors, isLoading, isError, error } = useQuery({
    queryKey: ['connectors', tenantSlug],
    queryFn: () => fetchConnectors(token),
    enabled: Boolean(token),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => createConnector(data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', tenantSlug] });
      setShowCreateModal(false);
    },
  });

  const testMutation = useMutation({
    mutationFn: (connectorId: string) => testConnector(connectorId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', tenantSlug] });
    },
  });

  const pageError =
    (testMutation.error as Error | undefined) ??
    (createMutation.error as Error | undefined) ??
    (isError ? (error as Error) : undefined);
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const name = String(formData.get('name') ?? '').trim();
    const dtrBaseUrl = String(formData.get('dtr_base_url') ?? '').trim();
    const accessToken = String(formData.get('token') ?? '').trim();
    const bpn = String(formData.get('bpn') ?? '').trim();
    const submodelBaseUrl = String(formData.get('submodel_base_url') ?? '').trim();
    createMutation.mutate({
      name,
      config: {
        dtr_base_url: dtrBaseUrl,
        auth_type: 'token',
        token: accessToken,
        bpn: bpn || undefined,
        submodel_base_url: submodelBaseUrl || undefined,
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
      <PageHeader
        title="Connectors"
        description="Manage Catena-X DTR publishing"
        actions={
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Connector
          </Button>
        }
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Catena-X Connector</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="connector-name">Name</Label>
              <Input id="connector-name" name="name" type="text" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="connector-dtr-url">DTR Base URL</Label>
              <Input
                id="connector-dtr-url"
                name="dtr_base_url"
                type="url"
                required
                placeholder="https://dtr.catena-x.net/api/v3"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="connector-token">Access Token</Label>
              <Input id="connector-token" name="token" type="password" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="connector-bpn">BPN</Label>
              <Input
                id="connector-bpn"
                name="bpn"
                type="text"
                placeholder="BPNL00000001TEST"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="connector-submodel-url">Submodel Base URL</Label>
              <Input
                id="connector-submodel-url"
                name="submodel_base_url"
                type="url"
                placeholder="https://your-domain.com/api/v1/tenants/<tenant>/dpps"
              />
            </div>
            <DialogFooter>
              {createMutation.isError && (
                <p className="mr-auto text-sm text-destructive">
                  {(createMutation.error as Error)?.message || 'Failed to create connector.'}
                </p>
              )}
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreateModal(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Tested</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {connectors?.connectors?.map((connector: any) => (
                <TableRow key={connector.id}>
                  <TableCell className="font-medium">
                    {connector.name}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {connector.connector_type}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center">
                      {getStatusIcon(connector.status)}
                      <span className="ml-2">{connector.status}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {connector.last_tested_at
                      ? new Date(connector.last_tested_at).toLocaleString()
                      : 'Never'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => testMutation.mutate(connector.id)}
                      disabled={testMutation.isPending}
                    >
                      <TestTube className="h-4 w-4 mr-1" />
                      Test
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {(!connectors?.connectors || connectors.connectors.length === 0) && (
            <EmptyState
              icon={Link2}
              title="No connectors configured"
              description="Add a connector to integrate with Catena-X."
            />
          )}
        </Card>
      )}
    </div>
  );
}
