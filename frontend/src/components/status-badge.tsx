import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

type DPPStatus = 'draft' | 'published' | 'archived' | string;

const statusStyles: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
  published: 'bg-green-100 text-green-800 hover:bg-green-100',
  archived: 'bg-gray-100 text-gray-800 hover:bg-gray-100',
};

interface StatusBadgeProps {
  status: DPPStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge
      variant="secondary"
      className={cn(
        'capitalize',
        statusStyles[status] ?? 'bg-gray-100 text-gray-800 hover:bg-gray-100',
        className,
      )}
    >
      {status}
    </Badge>
  );
}
