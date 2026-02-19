import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const STATUS_CONFIG: Record<string, { className: string; label: string }> = {
  healthy: { className: 'bg-green-100 text-green-800', label: 'Connected' },
  degraded: { className: 'bg-yellow-100 text-yellow-800', label: 'Degraded' },
  error: { className: 'bg-red-100 text-red-800', label: 'Error' },
};

const DEFAULT_CONFIG = { className: 'bg-gray-100 text-gray-800', label: 'Unknown' };

interface ConnectionStatusBadgeProps {
  status: string;
}

export function ConnectionStatusBadge({ status }: ConnectionStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? DEFAULT_CONFIG;

  return (
    <Badge variant="outline" className={cn('border-transparent', config.className)}>
      {config.label}
    </Badge>
  );
}
