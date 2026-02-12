import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from 'react';
import { ChevronRight } from 'lucide-react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { DppOutlineNode } from '../types';

type VisibleOutlineRow = {
  node: DppOutlineNode;
  depth: number;
  hasChildren: boolean;
  parentId: string | null;
};

export type DppOutlineTreeProps = {
  nodes: DppOutlineNode[];
  selectedId?: string | null;
  onSelectNode?: (node: DppOutlineNode) => void;
  ariaLabel?: string;
  virtualizeThreshold?: number;
  scrollClassName?: string;
};

function collectExpandedDefaults(nodes: DppOutlineNode[]): Set<string> {
  const expanded = new Set<string>();

  const visit = (node: DppOutlineNode, depth: number) => {
    if (node.children.length > 0 && depth <= 1) {
      expanded.add(node.id);
    }
    for (const child of node.children) {
      visit(child, depth + 1);
    }
  };

  for (const node of nodes) {
    visit(node, 0);
  }
  return expanded;
}

function collectExpandableIds(nodes: DppOutlineNode[]): Set<string> {
  const ids = new Set<string>();
  const stack = [...nodes];
  while (stack.length > 0) {
    const current = stack.pop()!;
    if (current.children.length > 0) {
      ids.add(current.id);
      for (const child of current.children) {
        stack.push(child);
      }
    }
  }
  return ids;
}

function buildParentById(nodes: DppOutlineNode[]): Map<string, string | null> {
  const parentById = new Map<string, string | null>();
  const stack: Array<{ node: DppOutlineNode; parentId: string | null }> = nodes.map((node) => ({
    node,
    parentId: null,
  }));

  while (stack.length > 0) {
    const current = stack.pop()!;
    parentById.set(current.node.id, current.parentId);
    for (const child of current.node.children) {
      stack.push({ node: child, parentId: current.node.id });
    }
  }

  return parentById;
}

function flattenVisibleRows(
  nodes: DppOutlineNode[],
  expanded: Set<string>,
): VisibleOutlineRow[] {
  const rows: VisibleOutlineRow[] = [];

  const walk = (
    node: DppOutlineNode,
    depth: number,
    parentId: string | null,
  ) => {
    const hasChildren = node.children.length > 0;
    rows.push({ node, depth, hasChildren, parentId });

    if (!hasChildren || !expanded.has(node.id)) return;
    for (const child of node.children) {
      walk(child, depth + 1, node.id);
    }
  };

  for (const node of nodes) {
    walk(node, 0, null);
  }

  return rows;
}

function statusText(node: DppOutlineNode): string {
  const status = node.status;
  if (!status) return '';

  const completion = status.completion;
  if (status.requiredTotal && status.requiredTotal > 0) {
    return `${status.requiredCompleted ?? 0}/${status.requiredTotal}`;
  }
  if (completion === 'complete') return 'Complete';
  if (completion === 'partial') return 'Partial';
  if (completion === 'empty') return 'Empty';
  return '';
}

function findRowIndex(rows: VisibleOutlineRow[], id: string | null | undefined): number {
  if (!id) return -1;
  return rows.findIndex((row) => row.node.id === id);
}

export function DppOutlineTree({
  nodes,
  selectedId,
  onSelectNode,
  ariaLabel = 'DPP structure outline',
  virtualizeThreshold = 180,
  scrollClassName = 'max-h-[65vh]',
}: DppOutlineTreeProps) {
  const defaults = useMemo(() => collectExpandedDefaults(nodes), [nodes]);
  const expandableIds = useMemo(() => collectExpandableIds(nodes), [nodes]);
  const parentById = useMemo(() => buildParentById(nodes), [nodes]);
  const knownExpandableIdsRef = useRef<Set<string>>(new Set(expandableIds));

  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(defaults));
  const [activeId, setActiveId] = useState<string | null>(selectedId ?? null);

  const rowRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setExpanded((previous) => {
      // Keep user-managed state for nodes that still exist.
      const next = new Set<string>();
      for (const id of previous) {
        if (expandableIds.has(id)) {
          next.add(id);
        }
      }

      // Auto-expand only newly introduced top-level/default nodes.
      for (const id of defaults) {
        if (!knownExpandableIdsRef.current.has(id)) {
          next.add(id);
        }
      }

      knownExpandableIdsRef.current = new Set(expandableIds);
      return next;
    });
  }, [defaults, expandableIds]);

  useEffect(() => {
    if (!selectedId) return;
    if (!parentById.has(selectedId)) return;

    setExpanded((previous) => {
      const next = new Set(previous);
      let parentId = parentById.get(selectedId) ?? null;
      while (parentId) {
        if (expandableIds.has(parentId)) {
          next.add(parentId);
        }
        parentId = parentById.get(parentId) ?? null;
      }
      return next;
    });
  }, [expandableIds, parentById, selectedId]);

  const rows = useMemo(() => flattenVisibleRows(nodes, expanded), [expanded, nodes]);

  useEffect(() => {
    const rowIds = new Set(rows.map((row) => row.node.id));

    if (selectedId && rowIds.has(selectedId)) {
      setActiveId(selectedId);
      return;
    }

    if (activeId && rowIds.has(activeId)) {
      return;
    }

    if (rows.length > 0) {
      setActiveId(rows[0].node.id);
      return;
    }

    setActiveId(null);
  }, [activeId, rows, selectedId]);

  const focusRow = useCallback((id: string) => {
    const element = rowRefs.current.get(id);
    if (element) {
      element.focus();
    }
  }, []);

  const toggleNode = useCallback((nodeId: string) => {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const handleSelect = useCallback(
    (node: DppOutlineNode) => {
      setActiveId(node.id);
      onSelectNode?.(node);
    },
    [onSelectNode],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, row: VisibleOutlineRow) => {
      const index = findRowIndex(rows, row.node.id);
      if (index < 0) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        const next = rows[Math.min(rows.length - 1, index + 1)];
        if (next) {
          setActiveId(next.node.id);
          focusRow(next.node.id);
        }
        return;
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        const previous = rows[Math.max(0, index - 1)];
        if (previous) {
          setActiveId(previous.node.id);
          focusRow(previous.node.id);
        }
        return;
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault();
        if (row.hasChildren && !expanded.has(row.node.id)) {
          toggleNode(row.node.id);
          return;
        }

        if (row.hasChildren) {
          const child = rows[index + 1];
          if (child) {
            setActiveId(child.node.id);
            focusRow(child.node.id);
          }
        }
        return;
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        if (row.hasChildren && expanded.has(row.node.id)) {
          toggleNode(row.node.id);
          return;
        }
        if (row.parentId) {
          setActiveId(row.parentId);
          focusRow(row.parentId);
        }
        return;
      }

      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleSelect(row.node);
      }
    },
    [expanded, focusRow, handleSelect, rows, toggleNode],
  );

  const virtualize = rows.length > virtualizeThreshold;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 34,
    overscan: 14,
    enabled: virtualize,
  });

  useEffect(() => {
    if (virtualize) {
      virtualizer.measure();
    }
  }, [virtualize, virtualizer, rows.length]);

  const renderRow = (row: VisibleOutlineRow, style?: CSSProperties) => {
    const isExpanded = expanded.has(row.node.id);
    const isSelected = selectedId ? selectedId === row.node.id : activeId === row.node.id;
    const completion = row.node.status?.completion;
    const risk = row.node.status?.risk;
    const errorCount = row.node.status?.errors ?? 0;
    const warningCount = row.node.status?.warnings ?? 0;

    return (
      <div
        key={row.node.id}
        style={style}
        className={cn('w-full', virtualize && 'absolute left-0')}
      >
        <button
          type="button"
          role="treeitem"
          aria-level={row.depth + 1}
          aria-expanded={row.hasChildren ? isExpanded : undefined}
          aria-selected={isSelected}
          ref={(element) => {
            if (element) {
              rowRefs.current.set(row.node.id, element);
            } else {
              rowRefs.current.delete(row.node.id);
            }
          }}
          tabIndex={isSelected ? 0 : -1}
          className={cn(
            'flex w-full items-center gap-1 rounded px-2 py-1 text-left text-xs transition-colors',
            isSelected ? 'bg-accent text-accent-foreground' : 'hover:bg-muted',
          )}
          style={{ paddingLeft: `${row.depth * 14 + 8}px` }}
          onClick={() => handleSelect(row.node)}
          onFocus={() => setActiveId(row.node.id)}
          onKeyDown={(event) => handleKeyDown(event, row)}
        >
          {row.hasChildren ? (
            <span
              className="inline-flex h-4 w-4 items-center justify-center"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                toggleNode(row.node.id);
              }}
            >
              <ChevronRight
                className={cn('h-3 w-3 text-muted-foreground transition-transform', isExpanded && 'rotate-90')}
              />
            </span>
          ) : (
            <span className="inline-flex h-4 w-4" aria-hidden="true" />
          )}

          <span className="truncate">{row.node.label}</span>

          {risk && (
            <Badge variant={risk === 'high' || risk === 'critical' ? 'destructive' : 'outline'} className="ml-auto text-[10px]">
              {risk}
            </Badge>
          )}

          {!risk && completion && (
            <Badge
              variant={completion === 'complete' ? 'outline' : completion === 'partial' ? 'secondary' : 'outline'}
              className="ml-auto text-[10px]"
            >
              {statusText(row.node)}
            </Badge>
          )}

          {errorCount > 0 && (
            <Badge variant="destructive" className="text-[10px]">
              {errorCount}e
            </Badge>
          )}

          {warningCount > 0 && (
            <Badge variant="secondary" className="text-[10px]">
              {warningCount}w
            </Badge>
          )}
        </button>
      </div>
    );
  };

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
        No outline nodes match the current filter.
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      role="tree"
      aria-label={ariaLabel}
      className={cn(scrollClassName, 'overflow-auto pr-1')}
    >
      {!virtualize ? (
        <div className="space-y-1">{rows.map((row) => renderRow(row))}</div>
      ) : (
        <div
          className="relative"
          style={{ height: `${virtualizer.getTotalSize()}px` }}
        >
          {virtualizer.getVirtualItems().map((item) => {
            const row = rows[item.index];
            return renderRow(row, {
              transform: `translateY(${item.start}px)`,
              height: `${item.size}px`,
            });
          })}
        </div>
      )}
    </div>
  );
}
