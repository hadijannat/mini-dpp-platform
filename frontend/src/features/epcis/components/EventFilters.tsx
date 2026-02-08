import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EVENT_TYPES, BIZ_STEPS, DISPOSITIONS } from '../lib/epcisApi';
import type { EPCISQueryFilters } from '../lib/epcisApi';

function capitalize(s: string): string {
  return s
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface EventFiltersProps {
  filters: EPCISQueryFilters;
  onChange: (filters: EPCISQueryFilters) => void;
}

export function EventFilters({ filters, onChange }: EventFiltersProps) {
  const update = (patch: Partial<EPCISQueryFilters>) => {
    onChange({ ...filters, ...patch, offset: 0 });
  };

  return (
    <div className="flex flex-wrap gap-3">
      {/* Event Type */}
      <div className="w-44">
        <Select
          value={filters.event_type ?? 'all'}
          onValueChange={(v) => update({ event_type: v === 'all' ? undefined : (v as EPCISQueryFilters['event_type']) })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Event type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {EVENT_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{t.replace('Event', '')}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Business Step */}
      <div className="w-44">
        <Select
          value={filters.EQ_bizStep ?? 'all'}
          onValueChange={(v) => update({ EQ_bizStep: v === 'all' ? undefined : v })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Business step" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All steps</SelectItem>
            {BIZ_STEPS.map((s) => (
              <SelectItem key={s} value={s}>{capitalize(s)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Disposition */}
      <div className="w-44">
        <Select
          value={filters.EQ_disposition ?? 'all'}
          onValueChange={(v) => update({ EQ_disposition: v === 'all' ? undefined : v })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Disposition" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All dispositions</SelectItem>
            {DISPOSITIONS.map((d) => (
              <SelectItem key={d} value={d}>{capitalize(d)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Date range */}
      <Input
        type="datetime-local"
        className="w-48"
        value={filters.GE_eventTime ?? ''}
        onChange={(e) => update({ GE_eventTime: e.target.value || undefined })}
        placeholder="From"
        aria-label="Events from"
      />
      <Input
        type="datetime-local"
        className="w-48"
        value={filters.LT_eventTime ?? ''}
        onChange={(e) => update({ LT_eventTime: e.target.value || undefined })}
        placeholder="To"
        aria-label="Events to"
      />
    </div>
  );
}
