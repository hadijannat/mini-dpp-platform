import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  Plus,
  TestTube,
  Send,
  CheckCircle,
  XCircle,
  AlertCircle,
  Link2,
  History,
} from 'lucide-react';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { ActorBadge } from '@/components/actor-badge';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { hasRole } from '@/lib/auth';

async function fetchConnectors(token?: string, scope: 'mine' | 'shared' | 'all' = 'mine') {
  const response = await tenantApiFetch(`/connectors?scope=${scope}`, {}, token);
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

async function publishToConnector(connectorId: string, dppId: string, token?: string) {
  const response = await tenantApiFetch(`/connectors/${connectorId}/publish/${dppId}`, {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to publish to DTR'));
  }
  return response.json();
}

interface DPPSummary {
  id: string;
  status: string;
  asset_ids?: { manufacturerPartId?: string };
}

interface ActorSummary {
  subject: string;
  display_name?: string | null;
  email_masked?: string | null;
}

interface ConnectorAccessSummary {
  can_read: boolean;
  can_update: boolean;
  can_publish: boolean;
  can_archive: boolean;
  source: 'owner' | 'share' | 'tenant_admin';
}

interface ConnectorItem {
  id: string;
  name: string;
  connector_type: string;
  status: string;
  created_by_subject?: string;
  created_by?: ActorSummary;
  visibility_scope?: 'owner_team' | 'tenant';
  access?: ConnectorAccessSummary;
  last_tested_at?: string | null;
  last_test_result?: Record<string, unknown> | null;
  created_at: string;
}

async function fetchPublishedDPPs(token?: string) {
  const response = await tenantApiFetch('/dpps?status=published&limit=200', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load DPPs'));
  }
  return response.json() as Promise<{ dpps: DPPSummary[] }>;
}

export default function ConnectorsPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [publishConnectorId, setPublishConnectorId] = useState<string | null>(null);
  const [selectedDppId, setSelectedDppId] = useState('');
  const [scope, setScope] = useState<'mine' | 'shared' | 'all'>('mine');
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const userIsTenantAdmin = hasRole(auth.user, 'tenant_admin') || hasRole(auth.user, 'admin');

  const { data: connectors, isLoading, isError, error } = useQuery({
    queryKey: ['connectors', tenantSlug, scope],
    queryFn: () => fetchConnectors(token, scope),
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

  const publishMutation = useMutation({
    mutationFn: ({ connectorId, dppId }: { connectorId: string; dppId: string }) =>
      publishToConnector(connectorId, dppId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', tenantSlug] });
      setPublishConnectorId(null);
      setSelectedDppId('');
    },
  });

  const { data: publishedDppsData } = useQuery({
    queryKey: ['published-dpps-connectors', tenantSlug],
    queryFn: () => fetchPublishedDPPs(token),
    enabled: Boolean(token) && publishConnectorId !== null,
  });

  const pageError =
    (publishMutation.error as Error | undefined) ??
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
          <div className="flex gap-2">
            <Select
              value={scope}
              onValueChange={(value) => setScope(value as 'mine' | 'shared' | 'all')}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter ownership" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mine">Mine</SelectItem>
                <SelectItem value="shared">Shared with me</SelectItem>
                {userIsTenantAdmin && <SelectItem value="all">All (tenant admin)</SelectItem>}
              </SelectContent>
            </Select>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Connector
            </Button>
          </div>
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
                <TableHead>Created By</TableHead>
                <TableHead>Visibility</TableHead>
                <TableHead>Last Tested</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {connectors?.connectors?.map((connector: ConnectorItem) => (
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
                  <TableCell>
                    <ActorBadge
                      actor={connector.created_by}
                      fallbackSubject={connector.created_by_subject}
                    />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {connector.visibility_scope === 'tenant' ? 'Tenant' : 'Owner/team'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {connector.last_tested_at
                      ? new Date(connector.last_tested_at).toLocaleString()
                      : 'Never'}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => testMutation.mutate(connector.id)}
                      disabled={testMutation.isPending}
                    >
                      <TestTube className="h-4 w-4 mr-1" />
                      Test
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                      <Link to={`/console/activity?type=connector&id=${connector.id}`}>
                        <History className="h-4 w-4 mr-1" />
                        Activity
                      </Link>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPublishConnectorId(connector.id)}
                      disabled={connector.access?.can_publish === false}
                    >
                      <Send className="h-4 w-4 mr-1" />
                      Publish
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

      {/* Publish to DTR Dialog */}
      <Dialog
        open={publishConnectorId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPublishConnectorId(null);
            setSelectedDppId('');
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Publish DPP to DTR</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="publish-dpp">Published DPP</Label>
              <Select value={selectedDppId} onValueChange={setSelectedDppId}>
                <SelectTrigger id="publish-dpp">
                  <SelectValue placeholder="Select a published DPP" />
                </SelectTrigger>
                <SelectContent>
                  {(publishedDppsData?.dpps ?? []).map((dpp: DPPSummary) => (
                    <SelectItem key={dpp.id} value={dpp.id}>
                      {dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setPublishConnectorId(null);
                setSelectedDppId('');
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (publishConnectorId && selectedDppId) {
                  void publishMutation.mutateAsync({
                    connectorId: publishConnectorId,
                    dppId: selectedDppId,
                  });
                }
              }}
              disabled={!selectedDppId || publishMutation.isPending}
            >
              {publishMutation.isPending ? 'Publishing...' : 'Publish'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
