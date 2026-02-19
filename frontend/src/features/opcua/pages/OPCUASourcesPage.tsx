import { useState } from 'react';
import { Plus, Server, Pencil, Trash2, Wifi } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { PageHeader } from '@/components/page-header';
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ConfirmDialog } from '@/components/confirm-dialog';
import { FeatureDisabledBanner } from '../components/FeatureDisabledBanner';
import { ConnectionStatusBadge } from '../components/ConnectionStatusBadge';
import { SourceFormDialog } from '../components/SourceFormDialog';
import {
  useOpcuaSources,
  useCreateSource,
  useUpdateSource,
  useDeleteSource,
  useTestConnection,
} from '../hooks/useOpcuaSources';
import {
  FeatureDisabledError,
  type OPCUASourceResponse,
  type OPCUASourceCreateInput,
} from '../lib/opcuaApi';

function authTypeBadgeVariant(
  authType: string,
): 'default' | 'secondary' | 'outline' {
  switch (authType) {
    case 'username_password':
      return 'default';
    case 'certificate':
      return 'secondary';
    default:
      return 'outline';
  }
}

function authTypeLabel(authType: string): string {
  switch (authType) {
    case 'anonymous':
      return 'Anonymous';
    case 'username_password':
      return 'Username/Password';
    case 'certificate':
      return 'Certificate';
    default:
      return authType;
  }
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function OPCUASourcesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editSource, setEditSource] = useState<OPCUASourceResponse | null>(null);
  const [deleteSource, setDeleteSource] = useState<OPCUASourceResponse | null>(null);
  const [testResult, setTestResult] = useState<{
    sourceId: string;
    message: string;
    success: boolean;
  } | null>(null);

  const { data, isLoading, error } = useOpcuaSources();
  const createMutation = useCreateSource();
  const updateMutation = useUpdateSource();
  const deleteMutation = useDeleteSource();
  const testMutation = useTestConnection();

  const isFeatureDisabled = error instanceof FeatureDisabledError;
  const sources = data?.items ?? [];

  function handleCreate(formData: OPCUASourceCreateInput) {
    createMutation.mutate(formData, {
      onSuccess: () => setCreateOpen(false),
    });
  }

  function handleUpdate(formData: OPCUASourceCreateInput) {
    if (!editSource) return;
    updateMutation.mutate(
      { sourceId: editSource.id, data: formData },
      { onSuccess: () => setEditSource(null) },
    );
  }

  function handleDelete() {
    if (!deleteSource) return;
    deleteMutation.mutate(deleteSource.id, {
      onSuccess: () => setDeleteSource(null),
    });
  }

  async function handleTestConnection(source: OPCUASourceResponse) {
    setTestResult(null);
    try {
      const result = await testMutation.mutateAsync(source.id);
      if (result.success) {
        setTestResult({
          sourceId: source.id,
          message: `Connected successfully (${result.latencyMs}ms)`,
          success: true,
        });
      } else {
        setTestResult({
          sourceId: source.id,
          message: result.error ?? 'Connection failed',
          success: false,
        });
      }
    } catch (err) {
      setTestResult({
        sourceId: source.id,
        message: err instanceof Error ? err.message : 'Connection test failed',
        success: false,
      });
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="OPC UA Sources"
        description="Manage OPC UA server connections for industrial data ingestion"
        actions={
          <Button onClick={() => setCreateOpen(true)} disabled={isFeatureDisabled}>
            <Plus className="h-4 w-4 mr-2" />
            Add Source
          </Button>
        }
      />

      {isFeatureDisabled && <FeatureDisabledBanner />}

      {error && !isFeatureDisabled && (
        <ErrorBanner message={error.message} />
      )}

      {isLoading && <LoadingSpinner size="lg" />}

      {!isLoading && !isFeatureDisabled && sources.length === 0 && (
        <EmptyState
          icon={Server}
          title="No OPC UA sources"
          description="Add a source to start ingesting industrial data."
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Source
            </Button>
          }
        />
      )}

      {!isLoading && sources.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Endpoint URL</TableHead>
                <TableHead>Auth Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Seen</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sources.map((source) => (
                <TableRow key={source.id}>
                  <TableCell className="font-medium">{source.name}</TableCell>
                  <TableCell className="font-mono text-xs max-w-[250px] truncate">
                    {source.endpoint_url}
                  </TableCell>
                  <TableCell>
                    <Badge variant={authTypeBadgeVariant(source.auth_type)}>
                      {authTypeLabel(source.auth_type)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <ConnectionStatusBadge status={source.connection_status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelativeTime(source.last_seen_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => void handleTestConnection(source)}
                        disabled={testMutation.isPending}
                        title="Test connection"
                      >
                        <Wifi className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setEditSource(source)}
                        title="Edit source"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteSource(source)}
                        title="Delete source"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                    {testResult && testResult.sourceId === source.id && (
                      <p
                        className={`mt-1 text-xs ${testResult.success ? 'text-green-700' : 'text-red-700'}`}
                      >
                        {testResult.message}
                      </p>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <SourceFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
        isPending={createMutation.isPending}
      />

      <SourceFormDialog
        open={!!editSource}
        onOpenChange={(open) => {
          if (!open) setEditSource(null);
        }}
        onSubmit={handleUpdate}
        initialData={editSource}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteSource}
        onOpenChange={(open) => {
          if (!open) setDeleteSource(null);
        }}
        title="Delete OPC UA Source"
        description={`This will permanently remove "${deleteSource?.name ?? ''}" and all associated configuration. This action cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        loading={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
