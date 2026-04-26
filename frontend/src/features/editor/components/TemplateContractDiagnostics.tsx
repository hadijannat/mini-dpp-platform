import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { TemplateContractResponse } from '../types/definition';

type UnsupportedNode = NonNullable<TemplateContractResponse['unsupported_nodes']>[number];
type DropInReportEntry = Record<string, unknown>;

type TemplateContractDiagnosticsProps = {
  unsupportedNodes?: TemplateContractResponse['unsupported_nodes'];
  dropinResolutionReport?: TemplateContractResponse['dropin_resolution_report'];
  mode?: 'dpp' | 'sandbox';
  maxItems?: number;
  className?: string;
};

function normalizeReason(reason: unknown): string {
  if (typeof reason !== 'string' || !reason.trim()) return 'unsupported';
  return reason
    .replace(/^unsupported_model_type:/, 'Unsupported model type: ')
    .replace(/^schema_/, 'Schema issue: ')
    .replace(/^dropin_/, 'Drop-in issue: ')
    .replace(/_/g, ' ');
}

function pathLabel(value: unknown): string {
  return typeof value === 'string' && value.trim() ? value : 'root';
}

function statusLabel(value: unknown): string {
  return typeof value === 'string' && value.trim() ? normalizeReason(value) : 'unresolved';
}

function unresolvedDropIns(
  report?: TemplateContractResponse['dropin_resolution_report'],
): DropInReportEntry[] {
  if (!Array.isArray(report)) return [];
  return report.filter((entry): entry is DropInReportEntry => {
    if (!entry || typeof entry !== 'object') return false;
    const status = String((entry as DropInReportEntry).status ?? '').toLowerCase();
    return Boolean(status) && status !== 'resolved' && status !== 'skipped';
  });
}

function unsupportedReason(node: UnsupportedNode): string {
  const reasons = Array.isArray(node.reasons) ? node.reasons : [];
  return reasons.map(normalizeReason).join(', ') || 'unsupported';
}

export function TemplateContractDiagnostics({
  unsupportedNodes = [],
  dropinResolutionReport = [],
  mode = 'dpp',
  maxItems = 4,
  className,
}: TemplateContractDiagnosticsProps) {
  const unsupported = Array.isArray(unsupportedNodes) ? unsupportedNodes : [];
  const unresolved = unresolvedDropIns(dropinResolutionReport);
  const hasIssues = unsupported.length > 0 || unresolved.length > 0;
  const hiddenCount =
    Math.max(unsupported.length - maxItems, 0) + Math.max(unresolved.length - maxItems, 0);
  const impactText =
    mode === 'sandbox'
      ? 'Preview and export may fail or require JSON edits for the listed paths.'
      : 'Draft save remains available. Publishing can be blocked until the listed paths are supported.';

  return (
    <section
      aria-label="Template contract diagnostics"
      className={cn(
        'rounded-md border p-3 text-xs',
        hasIssues ? 'border-amber-300 bg-amber-50 text-amber-950' : 'bg-muted/25',
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        {hasIssues ? (
          <AlertTriangle className="h-4 w-4 text-amber-700" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
        )}
        <p className="font-medium">
          {hasIssues ? 'Template contract needs review' : 'Template contract ready'}
        </p>
        <Badge variant={unsupported.length > 0 ? 'destructive' : 'secondary'}>
          Unsupported nodes: {unsupported.length}
        </Badge>
        <Badge variant={unresolved.length > 0 ? 'destructive' : 'secondary'}>
          Unresolved drop-ins: {unresolved.length}
        </Badge>
      </div>

      {hasIssues ? (
        <>
          <p className="mt-2 text-amber-900/80">{impactText}</p>
          <div className="mt-2 space-y-1">
            {unsupported.slice(0, maxItems).map((entry, index) => (
              <p
                key={`unsupported-${pathLabel(entry.path)}-${index}`}
                className="break-words font-mono text-[11px] text-amber-900/80"
              >
                {pathLabel(entry.path)}: {unsupportedReason(entry)}
              </p>
            ))}
            {unresolved.slice(0, maxItems).map((entry, index) => (
              <p
                key={`unresolved-${pathLabel(entry.path)}-${index}`}
                className="break-words font-mono text-[11px] text-amber-900/80"
              >
                {pathLabel(entry.path)}: {statusLabel(entry.reason ?? entry.status)}
              </p>
            ))}
          </div>
          {hiddenCount > 0 && (
            <p className="mt-2 text-amber-900/80">
              {hiddenCount} more diagnostics hidden.
            </p>
          )}
        </>
      ) : (
        <p className="mt-2 text-muted-foreground">
          All loaded template paths have editor coverage.
        </p>
      )}
    </section>
  );
}
