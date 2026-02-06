import { useState } from 'react';
import * as Collapsible from '@radix-ui/react-collapsible';
import { ChevronRight } from 'lucide-react';

type CollapsibleSectionProps = {
  title: string;
  required?: boolean;
  description?: string;
  depth: number;
  childCount?: number;
  children: React.ReactNode;
};

export function CollapsibleSection({
  title,
  required,
  description,
  depth,
  childCount,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(depth <= 1);

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="border rounded-md">
      <Collapsible.Trigger className="flex w-full items-center gap-2 p-4 text-left hover:bg-gray-50">
        <ChevronRight
          className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${
            open ? 'rotate-90' : ''
          }`}
        />
        <span className="text-sm font-medium text-gray-800">
          {title}
          {required && <span className="text-red-500 ml-1">*</span>}
        </span>
        {childCount !== undefined && (
          <span className="ml-auto text-xs text-gray-400">{childCount} items</span>
        )}
      </Collapsible.Trigger>
      {description && (
        <p className="px-4 pb-2 text-xs text-gray-500">{description}</p>
      )}
      <Collapsible.Content className="px-4 pb-4">
        <div className="space-y-4">{children}</div>
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
