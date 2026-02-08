import { useState } from 'react';
import { ChevronDown, ChevronRight, Plus, Minus, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

type DiffEntry = {
  path: string;
  operation: string;
  old_value: unknown;
  new_value: unknown;
};

type DiffResult = {
  from_rev: number;
  to_rev: number;
  added: DiffEntry[];
  removed: DiffEntry[];
  changed: DiffEntry[];
};

type DiffViewerProps = {
  diff: DiffResult;
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '(empty)';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '[complex value]';
  }
}

function groupByTopLevel(entries: DiffEntry[]): Record<string, DiffEntry[]> {
  const groups: Record<string, DiffEntry[]> = {};
  for (const entry of entries) {
    const topKey = entry.path.split('.')[0] || 'root';
    if (!groups[topKey]) groups[topKey] = [];
    groups[topKey].push(entry);
  }
  return groups;
}

function DiffEntryRow({ entry }: { entry: DiffEntry }) {
  const bgClass =
    entry.operation === 'added'
      ? 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800'
      : entry.operation === 'removed'
        ? 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800'
        : 'bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200 dark:border-yellow-800';

  const icon =
    entry.operation === 'added' ? (
      <Plus className="h-3 w-3 text-green-600" />
    ) : entry.operation === 'removed' ? (
      <Minus className="h-3 w-3 text-red-600" />
    ) : (
      <RefreshCw className="h-3 w-3 text-yellow-600" />
    );

  const displayPath = entry.path.includes('.')
    ? entry.path.substring(entry.path.indexOf('.') + 1)
    : entry.path;

  return (
    <div className={`flex items-start gap-2 p-2 rounded border text-sm ${bgClass}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 flex-1">
        <span className="font-mono text-xs text-muted-foreground">{displayPath}</span>
        {entry.operation === 'changed' && (
          <div className="mt-1 grid grid-cols-2 gap-2">
            <div className="p-1.5 rounded bg-red-100/50 dark:bg-red-900/20">
              <span className="text-xs text-muted-foreground block">Old</span>
              <pre className="text-xs font-mono whitespace-pre-wrap break-all">
                {formatValue(entry.old_value)}
              </pre>
            </div>
            <div className="p-1.5 rounded bg-green-100/50 dark:bg-green-900/20">
              <span className="text-xs text-muted-foreground block">New</span>
              <pre className="text-xs font-mono whitespace-pre-wrap break-all">
                {formatValue(entry.new_value)}
              </pre>
            </div>
          </div>
        )}
        {entry.operation === 'added' && (
          <pre className="mt-1 text-xs font-mono whitespace-pre-wrap break-all">
            {formatValue(entry.new_value)}
          </pre>
        )}
        {entry.operation === 'removed' && (
          <pre className="mt-1 text-xs font-mono whitespace-pre-wrap break-all">
            {formatValue(entry.old_value)}
          </pre>
        )}
      </div>
    </div>
  );
}

export function DiffViewer({ diff }: DiffViewerProps) {
  const allEntries = [...diff.added, ...diff.removed, ...diff.changed];
  const groups = groupByTopLevel(allEntries);
  const groupKeys = Object.keys(groups).sort();
  const [expanded, setExpanded] = useState<Set<string>>(new Set(groupKeys));

  const totalChanges = allEntries.length;

  if (totalChanges === 0) {
    return (
      <div className="text-center py-4 text-sm text-muted-foreground">
        No differences between revision #{diff.from_rev} and #{diff.to_rev}
      </div>
    );
  }

  const toggleGroup = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium">
          Diff: #{diff.from_rev} → #{diff.to_rev}
        </span>
        <Badge variant="outline" className="text-green-600">
          +{diff.added.length}
        </Badge>
        <Badge variant="outline" className="text-red-600">
          -{diff.removed.length}
        </Badge>
        <Badge variant="outline" className="text-yellow-600">
          ~{diff.changed.length}
        </Badge>
      </div>

      {groupKeys.map((groupKey) => {
        const entries = groups[groupKey];
        const isExpanded = expanded.has(groupKey);
        return (
          <div key={groupKey} className="border rounded-lg">
            <button
              onClick={() => toggleGroup(groupKey)}
              className="w-full flex items-center justify-between p-3 text-left hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                <span className="font-mono text-sm font-medium">{groupKey}</span>
                <Badge variant="secondary" className="text-xs">
                  {entries.length}
                </Badge>
              </div>
            </button>
            {isExpanded && (
              <div className="px-3 pb-3 space-y-1">
                {entries.map((entry, idx) => (
                  <DiffEntryRow key={`${entry.path}-${idx}`} entry={entry} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
