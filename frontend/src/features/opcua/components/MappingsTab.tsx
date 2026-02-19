import { useState, useMemo } from 'react';
import { Plus, GitBranch, Pencil, Trash2, CheckCircle, Play } from 'lucide-react';
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
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ConfirmDialog } from '@/components/confirm-dialog';
import { FeatureDisabledBanner } from './FeatureDisabledBanner';
import { MappingFormDialog } from './MappingFormDialog';
import {
  useOpcuaMappings,
  useCreateMapping,
  useUpdateMapping,
  useDeleteMapping,
  useValidateMapping,
  useDryRunMapping,
} from '../hooks/useOpcuaMappings';
import { useOpcuaSources } from '../hooks/useOpcuaSources';
import {
  FeatureDisabledError,
  OPCUAMappingType,
  type OPCUAMappingResponse,
  type OPCUAMappingCreateInput,
  type MappingValidationResult,
  type MappingDryRunResult,
} from '../lib/opcuaApi';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mappingTypeBadge(type: string) {
  if (type === OPCUAMappingType.EPCIS_EVENT) {
    return <Badge variant="secondary">EPCIS Event</Badge>;
  }
  return <Badge variant="default">AAS Patch</Badge>;
}

function targetPathDisplay(mapping: OPCUAMappingResponse): string {
  if (mapping.mapping_type === OPCUAMappingType.AAS_PATCH) {
    return mapping.target_aas_path ?? '-';
  }
  if (mapping.mapping_type === OPCUAMappingType.EPCIS_EVENT) {
    return mapping.epcis_event_type ?? '-';
  }
  return '-';
}

// ---------------------------------------------------------------------------
// Inline validation result
// ---------------------------------------------------------------------------

function ValidationResultPanel({ result }: { result: MappingValidationResult }) {
  if (result.isValid) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 text-sm text-green-700 dark:text-green-400">
        <CheckCircle className="h-4 w-4" />
        <span>Valid</span>
        {result.warnings.length > 0 && (
          <span className="text-yellow-600 dark:text-yellow-400">
            ({result.warnings.length} warning{result.warnings.length > 1 ? 's' : ''})
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1 px-4 py-2">
      <div className="flex items-center gap-2 text-sm text-destructive">
        <span className="font-medium">Validation failed</span>
      </div>
      <ul className="list-inside list-disc text-xs text-destructive">
        {result.errors.map((err, i) => (
          <li key={i}>{err}</li>
        ))}
      </ul>
      {result.warnings.length > 0 && (
        <ul className="list-inside list-disc text-xs text-yellow-600 dark:text-yellow-400">
          {result.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline dry-run result
// ---------------------------------------------------------------------------

function DryRunResultPanel({ result }: { result: MappingDryRunResult }) {
  if (result.diff.length === 0) {
    return (
      <div className="px-4 py-2 text-sm text-muted-foreground">
        Dry run produced no changes.
      </div>
    );
  }

  return (
    <div className="px-4 py-2">
      <p className="mb-2 text-xs font-medium text-muted-foreground">
        Dry-run diff{result.dppId ? ` for DPP ${result.dppId}` : ''}
      </p>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">Op</TableHead>
              <TableHead>Path</TableHead>
              <TableHead>Old Value</TableHead>
              <TableHead>New Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.diff.map((entry, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Badge variant="outline" className="text-xs">
                    {entry.op}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{entry.path}</TableCell>
                <TableCell className="max-w-[180px] truncate text-xs text-muted-foreground">
                  {entry.oldValue != null ? String(entry.oldValue) : '-'}
                </TableCell>
                <TableCell className="max-w-[180px] truncate text-xs font-medium">
                  {entry.newValue != null ? String(entry.newValue) : '-'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main MappingsTab
// ---------------------------------------------------------------------------

export function MappingsTab() {
  // Dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [editMapping, setEditMapping] = useState<OPCUAMappingResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<OPCUAMappingResponse | null>(null);

  // Inline result state (keyed by mapping id)
  const [validationResults, setValidationResults] = useState<
    Record<string, MappingValidationResult>
  >({});
  const [dryRunResults, setDryRunResults] = useState<Record<string, MappingDryRunResult>>({});

  // Data hooks
  const { data, isLoading, error } = useOpcuaMappings();
  const { data: sourcesData } = useOpcuaSources();
  const createMutation = useCreateMapping();
  const updateMutation = useUpdateMapping();
  const deleteMutation = useDeleteMapping();
  const validateMutation = useValidateMapping();
  const dryRunMutation = useDryRunMapping();

  const isFeatureDisabled = error instanceof FeatureDisabledError;
  const mappings = data?.items ?? [];

  // Build a lookup map of source id -> source name
  const sourceNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of sourcesData?.items ?? []) {
      map.set(s.id, s.name);
    }
    return map;
  }, [sourcesData]);

  // ---- Handlers ----

  function handleOpenCreate() {
    setEditMapping(null);
    setFormOpen(true);
  }

  function handleOpenEdit(mapping: OPCUAMappingResponse) {
    setEditMapping(mapping);
    setFormOpen(true);
  }

  function handleFormSubmit(formData: OPCUAMappingCreateInput) {
    if (editMapping) {
      // Update: strip sourceId (not allowed in update), send remaining fields
      const { sourceId: _, ...updateData } = formData;
      void _;
      updateMutation.mutate(
        { mappingId: editMapping.id, data: updateData },
        {
          onSuccess: () => {
            setFormOpen(false);
            setEditMapping(null);
          },
        },
      );
    } else {
      createMutation.mutate(formData, {
        onSuccess: () => {
          setFormOpen(false);
        },
      });
    }
  }

  function handleDelete() {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => {
        setDeleteTarget(null);
        // Clear inline results for the deleted mapping
        setValidationResults((prev) => {
          const next = { ...prev };
          delete next[deleteTarget.id];
          return next;
        });
        setDryRunResults((prev) => {
          const next = { ...prev };
          delete next[deleteTarget.id];
          return next;
        });
      },
    });
  }

  async function handleValidate(mappingId: string) {
    try {
      const result = await validateMutation.mutateAsync(mappingId);
      setValidationResults((prev) => ({ ...prev, [mappingId]: result }));
      // Clear any existing dry-run result for this mapping
      setDryRunResults((prev) => {
        const next = { ...prev };
        delete next[mappingId];
        return next;
      });
    } catch {
      // Error surfaced via mutation state
    }
  }

  async function handleDryRun(mappingId: string) {
    try {
      const result = await dryRunMutation.mutateAsync({ mappingId });
      setDryRunResults((prev) => ({ ...prev, [mappingId]: result }));
      // Clear any existing validation result for this mapping
      setValidationResults((prev) => {
        const next = { ...prev };
        delete next[mappingId];
        return next;
      });
    } catch {
      // Error surfaced via mutation state
    }
  }

  function handleToggleEnabled(mapping: OPCUAMappingResponse) {
    updateMutation.mutate({
      mappingId: mapping.id,
      data: { isEnabled: !mapping.is_enabled },
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <Button onClick={handleOpenCreate} disabled={isFeatureDisabled}>
          <Plus className="h-4 w-4 mr-2" />
          Add Mapping
        </Button>
      </div>

      {isFeatureDisabled && <FeatureDisabledBanner />}

      {error && !isFeatureDisabled && <ErrorBanner message={error.message} />}

      {isLoading && <LoadingSpinner size="lg" />}

      {!isLoading && !isFeatureDisabled && mappings.length === 0 && (
        <EmptyState
          icon={GitBranch}
          title="No mappings configured"
          description="Create a mapping to connect OPC UA variables to DPP targets."
          action={
            <Button onClick={handleOpenCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Add Mapping
            </Button>
          }
        />
      )}

      {!isLoading && mappings.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Node ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Target Path</TableHead>
                <TableHead>DPP</TableHead>
                <TableHead className="text-center">Enabled</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mappings.map((m) => (
                <>
                  <TableRow key={m.id}>
                    <TableCell className="text-sm">
                      {sourceNameMap.get(m.source_id) ?? m.source_id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">
                      {m.opcua_node_id}
                    </TableCell>
                    <TableCell>{mappingTypeBadge(m.mapping_type)}</TableCell>
                    <TableCell className="text-sm max-w-[180px] truncate">
                      {targetPathDisplay(m)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[140px] truncate">
                      {m.dpp_id ?? '-'}
                    </TableCell>
                    <TableCell className="text-center">
                      <button
                        type="button"
                        className="inline-block cursor-pointer"
                        onClick={() => handleToggleEnabled(m)}
                        title={m.is_enabled ? 'Disable mapping' : 'Enable mapping'}
                        aria-label={m.is_enabled ? 'Disable mapping' : 'Enable mapping'}
                      >
                        <span
                          className={`inline-block h-2.5 w-2.5 rounded-full ${
                            m.is_enabled
                              ? 'bg-green-500'
                              : 'bg-gray-400 dark:bg-gray-600'
                          }`}
                        />
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => void handleValidate(m.id)}
                          disabled={validateMutation.isPending}
                          title="Validate mapping"
                        >
                          <CheckCircle className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => void handleDryRun(m.id)}
                          disabled={dryRunMutation.isPending}
                          title="Dry run"
                        >
                          <Play className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenEdit(m)}
                          title="Edit mapping"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteTarget(m)}
                          title="Delete mapping"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>

                  {/* Inline validation result */}
                  {validationResults[m.id] && (
                    <TableRow key={`${m.id}-validation`}>
                      <TableCell colSpan={7} className="bg-muted/50 p-0">
                        <ValidationResultPanel result={validationResults[m.id]} />
                      </TableCell>
                    </TableRow>
                  )}

                  {/* Inline dry-run result */}
                  {dryRunResults[m.id] && (
                    <TableRow key={`${m.id}-dryrun`}>
                      <TableCell colSpan={7} className="bg-muted/50 p-0">
                        <DryRunResultPanel result={dryRunResults[m.id]} />
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create / Edit dialog */}
      <MappingFormDialog
        open={formOpen}
        onOpenChange={(nextOpen) => {
          setFormOpen(nextOpen);
          if (!nextOpen) setEditMapping(null);
        }}
        onSubmit={handleFormSubmit}
        initialData={editMapping}
        isPending={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete Mapping"
        description={`This will permanently remove the mapping for node "${deleteTarget?.opcua_node_id ?? ''}". This action cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        loading={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
