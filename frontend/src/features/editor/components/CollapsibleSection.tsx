import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

type CollapsibleSectionProps = {
  title: string;
  required?: boolean;
  description?: string;
  depth: number;
  fieldPath?: string;
  childCount?: number;
  children: React.ReactNode;
};

const depthStyles = [
  'rounded-lg border bg-card shadow-sm',
  'border-l-4 border-l-primary/40 bg-muted/30 rounded-md',
  'border-dashed border bg-muted/10 ml-2 rounded-md',
  'border-dotted border bg-transparent ml-4 rounded-md',
] as const;

function getDepthClass(depth: number): string {
  if (depth >= depthStyles.length) return depthStyles[depthStyles.length - 1];
  return depthStyles[depth];
}

export function CollapsibleSection({
  title,
  required,
  description,
  depth,
  fieldPath,
  childCount,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(depth <= 1);

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={cn(getDepthClass(depth))}
      data-field-path={fieldPath}
    >
      <CollapsibleTrigger className="flex w-full items-center gap-2 p-4 text-left hover:bg-accent/50 rounded-t-md">
        <ChevronRight
          className={cn(
            'h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200',
            open && 'rotate-90',
          )}
        />
        <span className="text-sm font-medium">
          {title}
          {required && (
            <span className="inline-block ml-1.5 h-1.5 w-1.5 rounded-full bg-destructive align-middle" />
          )}
        </span>
        {childCount !== undefined && (
          <Badge variant="secondary" className="ml-auto">
            {childCount} {childCount === 1 ? 'item' : 'items'}
          </Badge>
        )}
      </CollapsibleTrigger>
      {description && (
        <p className="px-4 pb-2 text-xs text-muted-foreground">{description}</p>
      )}
      <CollapsibleContent className="px-4 pb-4">
        <div className="space-y-4">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}
