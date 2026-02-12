import { useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { ChevronLeft, ChevronRight, ListTree, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { DppOutlineNode } from '../types';
import { filterOutlineNodes } from '../utils/filterOutline';
import { useOutlinePaneState } from '../hooks/useOutlinePaneState';
import { DppOutlineTree } from './DppOutlineTree';

type OutlineContext = 'editor' | 'submodel' | 'viewer';

export type DppOutlinePaneProps = {
  context: OutlineContext;
  title?: string;
  nodes: DppOutlineNode[];
  selectedId?: string | null;
  onSelectNode?: (node: DppOutlineNode) => void;
  className?: string;
  mobile?: boolean;
};

function nodeCount(nodes: DppOutlineNode[]): number {
  let count = 0;
  const stack = [...nodes];
  while (stack.length > 0) {
    const current = stack.pop()!;
    count += 1;
    for (const child of current.children) {
      stack.push(child);
    }
  }
  return count;
}

export function DppOutlinePane({
  context,
  title = 'DPP Structure',
  nodes,
  selectedId,
  onSelectNode,
  className,
  mobile = false,
}: DppOutlinePaneProps) {
  const [query, setQuery] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const paneState = useOutlinePaneState(context);

  const filteredNodes = useMemo(
    () => filterOutlineNodes(nodes, query),
    [nodes, query],
  );

  const total = useMemo(() => nodeCount(nodes), [nodes]);
  const filtered = useMemo(() => nodeCount(filteredNodes), [filteredNodes]);

  const handleResizeStart = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (mobile || paneState.collapsed) return;
    event.preventDefault();

    const startX = event.clientX;
    const initialWidth = paneState.width;

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX;
      paneState.setWidth(initialWidth + delta);
    };

    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  const content = (
    <div className="rounded-md border bg-card" data-testid={`dpp-outline-${context}-${mobile ? 'mobile' : 'desktop'}`}>
      <div className="flex items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <ListTree className="h-4 w-4" />
          <h2 className="text-sm font-semibold">{title}</h2>
          <Badge variant="outline" className="text-[10px]">
            {filtered}/{total}
          </Badge>
        </div>

        {!mobile && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={paneState.toggleCollapsed}
            aria-label="Collapse outline"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="space-y-2 p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search structure"
            className="h-8 pl-8 text-xs"
            aria-label="Search structure outline"
          />
        </div>

        <DppOutlineTree
          nodes={filteredNodes}
          selectedId={selectedId}
          onSelectNode={onSelectNode}
          scrollClassName="max-h-[65vh]"
        />
      </div>
    </div>
  );

  if (mobile) {
    return (
      <Collapsible open={mobileOpen} onOpenChange={setMobileOpen} className={className}>
        <CollapsibleTrigger asChild>
          <Button type="button" variant="outline" size="sm" className="w-full justify-between">
            <span className="inline-flex items-center gap-2">
              <ListTree className="h-4 w-4" />
              {title}
            </span>
            <ChevronRight className={cn('h-4 w-4 transition-transform', mobileOpen && 'rotate-90')} />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2">{content}</CollapsibleContent>
      </Collapsible>
    );
  }

  if (paneState.collapsed) {
    return (
      <aside className={cn('sticky top-20 self-start', className)} style={{ width: 42 }}>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="h-10 w-10"
          onClick={paneState.toggleCollapsed}
          aria-label="Expand outline"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </aside>
    );
  }

  return (
    <aside
      className={cn('sticky top-20 self-start', className)}
      style={{ width: paneState.width }}
    >
      <div className="relative">
        {content}
        <div
          role="separator"
          aria-orientation="vertical"
          className="absolute -right-1 top-0 h-full w-2 cursor-col-resize"
          onMouseDown={handleResizeStart}
        />
      </div>
    </aside>
  );
}
