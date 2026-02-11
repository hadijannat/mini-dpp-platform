import { useMemo, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { SubmodelNode } from '../types';
import { flattenSubmodelNodes } from '../utils/treeBuilder';

type SubmodelNodeTreeProps = {
  root: SubmodelNode;
  showSemanticMeta?: boolean;
  preferVirtualized?: boolean;
  virtualizeThreshold?: number;
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `[${value.length} items]`;
  try {
    return JSON.stringify(value);
  } catch {
    return '[object]';
  }
}

function NodeItem({
  node,
  depth,
  showSemanticMeta,
}: {
  node: SubmodelNode;
  depth: number;
  showSemanticMeta: boolean;
}) {
  const [open, setOpen] = useState(depth < 1);
  const hasChildren = node.children.length > 0;

  if (!hasChildren) {
    return (
      <div className={cn('rounded-md border bg-card p-3', depth > 0 && 'ml-4')}>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-medium">{node.label}</p>
            <p className="text-xs text-muted-foreground">{node.path}</p>
          </div>
          <Badge variant="outline" className="text-[10px]">
            {node.modelType}
          </Badge>
        </div>
        <p className="mt-2 text-sm break-all">{formatValue(node.value)}</p>
        {showSemanticMeta && node.meta.semanticId && (
          <p className="mt-2 text-[11px] text-muted-foreground break-all">
            semantic: {node.meta.semanticId}
          </p>
        )}
      </div>
    );
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={cn('rounded-md border bg-card', depth > 0 && 'ml-4')}>
      <CollapsibleTrigger className="flex w-full items-center gap-2 p-3 text-left hover:bg-accent/40">
        <ChevronRight className={cn('h-4 w-4 text-muted-foreground transition-transform', open && 'rotate-90')} />
        <div className="min-w-0">
          <p className="text-sm font-medium">{node.label}</p>
          <p className="text-xs text-muted-foreground">{node.path}</p>
        </div>
        <Badge variant="secondary" className="ml-auto text-[10px]">
          {node.children.length} {node.children.length === 1 ? 'child' : 'children'}
        </Badge>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-2 px-3 pb-3">
        {showSemanticMeta && node.meta.semanticId && (
          <p className="text-[11px] text-muted-foreground break-all">
            semantic: {node.meta.semanticId}
          </p>
        )}
        {node.children.map((child) => (
          <NodeItem
            key={child.id}
            node={child}
            depth={depth + 1}
            showSemanticMeta={showSemanticMeta}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

function VirtualizedFlatTree({ root }: { root: SubmodelNode }) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const nodes = useMemo(() => flattenSubmodelNodes(root), [root]);
  const virtualizer = useVirtualizer({
    count: nodes.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 8,
  });

  return (
    <div ref={parentRef} className="max-h-[34rem] overflow-auto rounded-md border">
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((item) => {
          const node = nodes[item.index];
          return (
            <div
              key={item.key}
              className="absolute left-0 w-full border-b px-3 py-2"
              style={{ transform: `translateY(${item.start}px)` }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{node.label}</p>
                  <p className="text-xs text-muted-foreground truncate">{node.path}</p>
                </div>
                <Badge variant="outline" className="text-[10px]">
                  {node.modelType}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground break-all">{formatValue(node.value)}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SubmodelNodeTree({
  root,
  showSemanticMeta = false,
  preferVirtualized = true,
  virtualizeThreshold = 120,
}: SubmodelNodeTreeProps) {
  const flattenedCount = useMemo(() => flattenSubmodelNodes(root).length, [root]);
  if (preferVirtualized && flattenedCount > virtualizeThreshold) {
    return <VirtualizedFlatTree root={root} />;
  }

  return (
    <div className="space-y-2">
      {root.children.map((child) => (
        <NodeItem
          key={child.id}
          node={child}
          depth={0}
          showSemanticMeta={showSemanticMeta}
        />
      ))}
    </div>
  );
}

