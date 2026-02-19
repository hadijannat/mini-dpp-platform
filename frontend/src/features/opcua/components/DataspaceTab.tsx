import { useState } from 'react';
import { Plus, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { FeatureDisabledBanner } from './FeatureDisabledBanner';
import {
  usePublicationJobs,
  usePublishToDataspace,
  useRetryPublicationJob,
} from '../hooks/useOpcuaDataspace';
import {
  FeatureDisabledError,
  DataspaceJobStatus,
  type DataspacePublicationJobResponse,
} from '../lib/opcuaApi';

function statusBadgeVariant(
  status: string,
): 'default' | 'secondary' | 'outline' | 'destructive' {
  switch (status) {
    case DataspaceJobStatus.SUCCEEDED:
      return 'default';
    case DataspaceJobStatus.IN_PROGRESS:
      return 'secondary';
    case DataspaceJobStatus.FAILED:
      return 'destructive';
    default:
      return 'outline';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case DataspaceJobStatus.QUEUED:
      return 'Queued';
    case DataspaceJobStatus.IN_PROGRESS:
      return 'Processing';
    case DataspaceJobStatus.SUCCEEDED:
      return 'Completed';
    case DataspaceJobStatus.FAILED:
      return 'Failed';
    default:
      return status;
  }
}

export function DataspaceTab() {
  const [publishOpen, setPublishOpen] = useState(false);
  const [dppId, setDppId] = useState('');
  const [target, setTarget] = useState('catena-x');
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  const { data, isLoading, error } = usePublicationJobs();
  const publishMutation = usePublishToDataspace();
  const retryMutation = useRetryPublicationJob();

  const isFeatureDisabled = error instanceof FeatureDisabledError;
  const jobs = data?.items ?? [];

  function handlePublish() {
    if (!dppId.trim()) return;
    publishMutation.mutate(
      { dppId: dppId.trim(), target },
      {
        onSuccess: () => {
          setPublishOpen(false);
          setDppId('');
          setTarget('catena-x');
        },
      },
    );
  }

  function handleRetry(jobId: string) {
    retryMutation.mutate(jobId);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <Button onClick={() => setPublishOpen(true)} disabled={isFeatureDisabled}>
          <Plus className="h-4 w-4 mr-2" />
          Publish to Dataspace
        </Button>
      </div>

      {isFeatureDisabled && <FeatureDisabledBanner />}

      {error && !isFeatureDisabled && <ErrorBanner message={error.message} />}

      {isLoading && <LoadingSpinner size="lg" />}

      {!isLoading && !isFeatureDisabled && jobs.length === 0 && (
        <EmptyState
          title="No publication jobs"
          description="Publish a DPP to a dataspace ecosystem like Catena-X."
          action={
            <Button onClick={() => setPublishOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Publish to Dataspace
            </Button>
          }
        />
      )}

      {!isLoading && jobs.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>DPP ID</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRowWithExpand
                  key={job.id}
                  job={job}
                  expanded={expandedJobId === job.id}
                  onToggle={() =>
                    setExpandedJobId((prev) => (prev === job.id ? null : job.id))
                  }
                  onRetry={() => handleRetry(job.id)}
                  retryPending={retryMutation.isPending}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={publishOpen} onOpenChange={setPublishOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Publish to Dataspace</DialogTitle>
            <DialogDescription>
              Submit a DPP for publication to a dataspace ecosystem.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="pub-dpp-id">DPP ID</Label>
              <Input
                id="pub-dpp-id"
                value={dppId}
                onChange={(e) => setDppId(e.target.value)}
                placeholder="UUID of the published DPP"
              />
            </div>
            <div>
              <Label htmlFor="pub-target">Target Ecosystem</Label>
              <Select value={target} onValueChange={setTarget}>
                <SelectTrigger id="pub-target">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="catena-x">Catena-X</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPublishOpen(false)}
              disabled={publishMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handlePublish}
              disabled={!dppId.trim() || publishMutation.isPending}
            >
              {publishMutation.isPending ? 'Publishing...' : 'Publish'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TableRowWithExpand({
  job,
  expanded,
  onToggle,
  onRetry,
  retryPending,
}: {
  job: DataspacePublicationJobResponse;
  expanded: boolean;
  onToggle: () => void;
  onRetry: () => void;
  retryPending: boolean;
}) {
  const isFailed = job.status === DataspaceJobStatus.FAILED;
  const hasArtifacts =
    job.artifact_refs && Object.keys(job.artifact_refs).length > 0;

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={onToggle}
      >
        <TableCell className="font-mono text-xs max-w-[200px] truncate">
          {job.dpp_id}
        </TableCell>
        <TableCell>
          <Badge variant="outline">{job.target}</Badge>
        </TableCell>
        <TableCell>
          <Badge variant={statusBadgeVariant(job.status)}>
            {statusLabel(job.status)}
          </Badge>
        </TableCell>
        <TableCell className="text-sm text-muted-foreground">
          {new Date(job.created_at).toLocaleDateString()}
        </TableCell>
        <TableCell className="text-sm text-muted-foreground">
          {new Date(job.updated_at).toLocaleDateString()}
        </TableCell>
        <TableCell className="text-right">
          <div className="flex items-center justify-end gap-1">
            {isFailed && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onRetry();
                }}
                disabled={retryPending}
                title="Retry"
              >
                <RotateCcw className="h-4 w-4 mr-1" />
                Retry
              </Button>
            )}
            {expanded ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={6} className="bg-muted/30 p-4">
            <div className="space-y-3">
              {isFailed && job.error && (
                <div>
                  <p className="text-sm font-medium text-destructive">Error</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {job.error}
                  </p>
                </div>
              )}
              {hasArtifacts && (
                <div>
                  <p className="text-sm font-medium mb-1">Artifact References</p>
                  <pre className="text-xs bg-muted rounded p-3 overflow-x-auto max-h-48">
                    {JSON.stringify(job.artifact_refs, null, 2)}
                  </pre>
                </div>
              )}
              {!isFailed && !hasArtifacts && (
                <p className="text-sm text-muted-foreground">
                  No additional details available.
                </p>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
