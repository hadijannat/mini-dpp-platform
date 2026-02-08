import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { EPCISEventType } from '../lib/epcisApi';

const EVENT_TYPE_STYLES: Record<EPCISEventType, string> = {
  ObjectEvent: 'bg-blue-100 text-blue-800 hover:bg-blue-100',
  AggregationEvent: 'bg-purple-100 text-purple-800 hover:bg-purple-100',
  TransactionEvent: 'bg-amber-100 text-amber-800 hover:bg-amber-100',
  TransformationEvent: 'bg-green-100 text-green-800 hover:bg-green-100',
  AssociationEvent: 'bg-cyan-100 text-cyan-800 hover:bg-cyan-100',
};

const EVENT_TYPE_LABELS: Record<EPCISEventType, string> = {
  ObjectEvent: 'Object',
  AggregationEvent: 'Aggregation',
  TransactionEvent: 'Transaction',
  TransformationEvent: 'Transformation',
  AssociationEvent: 'Association',
};

export function EventTypeBadge({ type }: { type: string }) {
  const style = EVENT_TYPE_STYLES[type as EPCISEventType];
  const label = EVENT_TYPE_LABELS[type as EPCISEventType] ?? type;

  return (
    <Badge variant="secondary" className={cn('text-xs font-medium', style)}>
      {label}
    </Badge>
  );
}

export function ActionBadge({ action }: { action: string | null }) {
  if (!action) return null;
  const style =
    action === 'ADD'
      ? 'bg-green-50 text-green-700'
      : action === 'DELETE'
        ? 'bg-red-50 text-red-700'
        : 'bg-gray-50 text-gray-700';

  return (
    <Badge variant="outline" className={cn('text-xs', style)}>
      {action}
    </Badge>
  );
}
