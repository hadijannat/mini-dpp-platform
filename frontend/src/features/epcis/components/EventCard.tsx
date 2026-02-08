import {
  Box,
  GitMerge,
  ArrowRightLeft,
  RefreshCw,
  Link2,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { EventTypeBadge, ActionBadge } from './EventTypeBadge';
import type { EPCISEvent, EPCISEventType } from '../lib/epcisApi';

const EVENT_ICONS: Record<EPCISEventType, LucideIcon> = {
  ObjectEvent: Box,
  AggregationEvent: GitMerge,
  TransactionEvent: ArrowRightLeft,
  TransformationEvent: RefreshCw,
  AssociationEvent: Link2,
};

const EVENT_COLORS: Record<EPCISEventType, string> = {
  ObjectEvent: 'bg-blue-500',
  AggregationEvent: 'bg-purple-500',
  TransactionEvent: 'bg-amber-500',
  TransformationEvent: 'bg-green-500',
  AssociationEvent: 'bg-cyan-500',
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = Date.now();
  const diff = now - date.getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return date.toLocaleDateString();
}

interface EventCardProps {
  event: EPCISEvent;
  isLast?: boolean;
  onClick?: () => void;
}

export function EventCard({ event, isLast, onClick }: EventCardProps) {
  const Icon = EVENT_ICONS[event.event_type] ?? Box;
  const color = EVENT_COLORS[event.event_type] ?? 'bg-gray-500';

  return (
    <div
      className={cn(
        'relative flex gap-4 pb-6 cursor-pointer group',
        isLast && 'pb-0',
      )}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.();
        }
      }}
    >
      {/* Timeline line + icon */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white',
            color,
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        {!isLast && <div className="mt-1 w-px flex-1 bg-border" />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pt-0.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <EventTypeBadge type={event.event_type} />
          <ActionBadge action={event.action} />
          {event.biz_step && (
            <span className="text-xs text-muted-foreground">{event.biz_step}</span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>{formatRelativeTime(event.event_time)}</span>
          {event.disposition && (
            <>
              <span className="text-border">|</span>
              <span>{event.disposition.replace(/_/g, ' ')}</span>
            </>
          )}
          {event.biz_location && (
            <>
              <span className="text-border">|</span>
              <span className="truncate max-w-[200px]">{event.biz_location}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
