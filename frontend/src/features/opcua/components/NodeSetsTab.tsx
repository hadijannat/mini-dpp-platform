import { Fragment, useRef, useState, useDeferredValue } from 'react';
import { Upload, FileCode, Trash2, Search, Download, X } from 'lucide-react';
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
import { ConfirmDialog } from '@/components/confirm-dialog';
import { FeatureDisabledBanner } from './FeatureDisabledBanner';
import {
  useOpcuaNodesets,
  useUploadNodeset,
  useDownloadNodeset,
  useSearchNodesetNodes,
  useDeleteNodeset,
} from '../hooks/useOpcuaNodesets';
import { useOpcuaSources } from '../hooks/useOpcuaSources';
import {
  FeatureDisabledError,
  type OPCUANodeSetResponse,
} from '../lib/opcuaApi';

const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return 'N/A';
  }
}

function formatFileSize(bytes: number): string {
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

// ---------------------------------------------------------------------------
// Upload Dialog
// ---------------------------------------------------------------------------

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (params: {
    file: File;
    sourceId?: string;
    companionSpecName?: string;
    companionSpecVersion?: string;
  }) => void;
  isPending: boolean;
}

function UploadDialog({ open, onOpenChange, onSubmit, isPending }: UploadDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sourceId, setSourceId] = useState<string>('');
  const [companionSpecName, setCompanionSpecName] = useState('');
  const [companionSpecVersion, setCompanionSpecVersion] = useState('');
  const [sizeError, setSizeError] = useState<string | null>(null);

  const { data: sourcesData } = useOpcuaSources();
  const sources = sourcesData?.items ?? [];

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setSizeError(null);
    if (selected && selected.size > MAX_FILE_SIZE_BYTES) {
      setSizeError(
        `File size (${formatFileSize(selected.size)}) exceeds the ${MAX_FILE_SIZE_MB} MB limit.`,
      );
      setFile(null);
      return;
    }
    setFile(selected);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    onSubmit({
      file,
      sourceId: sourceId || undefined,
      companionSpecName: companionSpecName || undefined,
      companionSpecVersion: companionSpecVersion || undefined,
    });
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setFile(null);
      setSourceId('');
      setCompanionSpecName('');
      setCompanionSpecVersion('');
      setSizeError(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
    onOpenChange(nextOpen);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Upload NodeSet</DialogTitle>
            <DialogDescription>
              Upload an OPC UA NodeSet XML file to browse its information model.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nodeset-file">NodeSet XML File</Label>
              <Input
                ref={fileInputRef}
                id="nodeset-file"
                type="file"
                accept=".xml"
                onChange={handleFileChange}
              />
              {file && !sizeError && (
                <p className="text-xs text-muted-foreground">
                  {file.name} ({formatFileSize(file.size)})
                </p>
              )}
              {sizeError && <p className="text-xs text-destructive">{sizeError}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="source-select">Source (optional)</Label>
              <Select value={sourceId} onValueChange={setSourceId}>
                <SelectTrigger id="source-select">
                  <SelectValue placeholder="No source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No source</SelectItem>
                  {sources.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="companion-spec-name">Companion Spec Name (optional)</Label>
              <Input
                id="companion-spec-name"
                value={companionSpecName}
                onChange={(e) => setCompanionSpecName(e.target.value)}
                placeholder="e.g. OPC 40001-1"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="companion-spec-version">Companion Spec Version (optional)</Label>
              <Input
                id="companion-spec-version"
                value={companionSpecVersion}
                onChange={(e) => setCompanionSpecVersion(e.target.value)}
                placeholder="e.g. 1.02"
              />
            </div>
          </div>

          <DialogFooter className="mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !file || !!sizeError}>
              {isPending ? 'Uploading...' : 'Upload'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Expanded row: Node search
// ---------------------------------------------------------------------------

interface NodeSearchPanelProps {
  nodesetId: string;
}

function NodeSearchPanel({ nodesetId }: NodeSearchPanelProps) {
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query);
  const { data: results, isLoading } = useSearchNodesetNodes(nodesetId, {
    q: deferredQuery,
    limit: 50,
  });

  return (
    <div className="space-y-3 p-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9 pr-9"
          placeholder="Search nodes by name or ID..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button
            type="button"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setQuery('')}
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {!query && (
        <p className="text-sm text-muted-foreground">Type to search nodes...</p>
      )}

      {query && isLoading && <LoadingSpinner size="sm" />}

      {query && !isLoading && results && results.length === 0 && (
        <p className="text-sm text-muted-foreground">No nodes found.</p>
      )}

      {query && !isLoading && results && results.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>NodeId</TableHead>
                <TableHead>Browse Name</TableHead>
                <TableHead>Node Class</TableHead>
                <TableHead>Data Type</TableHead>
                <TableHead>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((node) => (
                <TableRow key={node.nodeId}>
                  <TableCell className="font-mono text-xs">{node.nodeId}</TableCell>
                  <TableCell className="font-medium">{node.browseName}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{node.nodeClass}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {node.dataType ?? '-'}
                  </TableCell>
                  <TableCell className="max-w-[250px] truncate text-sm text-muted-foreground">
                    {node.description ?? '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main NodeSetsTab
// ---------------------------------------------------------------------------

export function NodeSetsTab() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteNodeset, setDeleteNodeset] = useState<OPCUANodeSetResponse | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, error } = useOpcuaNodesets();
  const uploadMutation = useUploadNodeset();
  const downloadMutation = useDownloadNodeset();
  const deleteMutation = useDeleteNodeset();

  const isFeatureDisabled = error instanceof FeatureDisabledError;
  const nodesets = data?.items ?? [];

  function handleUpload(params: {
    file: File;
    sourceId?: string;
    companionSpecName?: string;
    companionSpecVersion?: string;
  }) {
    // Normalize the "__none__" sentinel back to undefined
    const sourceId = params.sourceId === '__none__' ? undefined : params.sourceId;
    uploadMutation.mutate(
      { ...params, sourceId },
      { onSuccess: () => setUploadOpen(false) },
    );
  }

  async function handleDownload(nodesetId: string) {
    try {
      const result = await downloadMutation.mutateAsync(nodesetId);
      window.open(result.download_url, '_blank', 'noopener,noreferrer');
    } catch {
      // Error is surfaced via mutation state if needed
    }
  }

  function handleDelete() {
    if (!deleteNodeset) return;
    deleteMutation.mutate(deleteNodeset.id, {
      onSuccess: () => {
        setDeleteNodeset(null);
        if (expandedId === deleteNodeset.id) {
          setExpandedId(null);
        }
      },
    });
  }

  function handleRowClick(nodesetId: string) {
    setExpandedId((prev) => (prev === nodesetId ? null : nodesetId));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <Button onClick={() => setUploadOpen(true)} disabled={isFeatureDisabled}>
          <Upload className="h-4 w-4 mr-2" />
          Upload NodeSet
        </Button>
      </div>

      {isFeatureDisabled && <FeatureDisabledBanner />}

      {error && !isFeatureDisabled && (
        <ErrorBanner message={error.message} />
      )}

      {isLoading && <LoadingSpinner size="lg" />}

      {!isLoading && !isFeatureDisabled && nodesets.length === 0 && (
        <EmptyState
          icon={FileCode}
          title="No NodeSets uploaded"
          description="Upload an OPC UA NodeSet XML to browse server information models."
          action={
            <Button onClick={() => setUploadOpen(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Upload NodeSet
            </Button>
          }
        />
      )}

      {!isLoading && nodesets.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Namespace URI</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Pub Date</TableHead>
                <TableHead>Companion Spec</TableHead>
                <TableHead className="text-right">Nodes</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nodesets.map((ns) => (
                <Fragment key={ns.id}>
                  <TableRow
                    className="cursor-pointer"
                    onClick={() => handleRowClick(ns.id)}
                    data-state={expandedId === ns.id ? 'selected' : undefined}
                  >
                    <TableCell className="font-mono text-xs max-w-[300px] truncate">
                      {ns.namespace_uri}
                    </TableCell>
                    <TableCell className="text-sm">
                      {ns.nodeset_version ?? 'N/A'}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(ns.publication_date)}
                    </TableCell>
                    <TableCell>
                      {ns.companion_spec_name ? (
                        <Badge variant="secondary">
                          {ns.companion_spec_name}
                          {ns.companion_spec_version
                            ? ` v${ns.companion_spec_version}`
                            : ''}
                        </Badge>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {ns.node_count.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div
                        className="flex items-center justify-end gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => void handleDownload(ns.id)}
                          disabled={downloadMutation.isPending}
                          title="Download NodeSet XML"
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteNodeset(ns)}
                          title="Delete NodeSet"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  {expandedId === ns.id && (
                    <TableRow key={`${ns.id}-detail`}>
                      <TableCell colSpan={6} className="bg-muted/50 p-0">
                        <NodeSearchPanel nodesetId={ns.id} />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onSubmit={handleUpload}
        isPending={uploadMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteNodeset}
        onOpenChange={(open) => {
          if (!open) setDeleteNodeset(null);
        }}
        title="Delete NodeSet"
        description={`This will permanently remove the NodeSet "${deleteNodeset?.namespace_uri ?? ''}" and its parsed node graph. This action cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        loading={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
