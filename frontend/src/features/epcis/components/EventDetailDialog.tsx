import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EventTypeBadge, ActionBadge } from './EventTypeBadge';
import type { EPCISEvent } from '../lib/epcisApi';

interface EventDetailDialogProps {
  event: EPCISEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EventDetailDialog({ event, open, onOpenChange }: EventDetailDialogProps) {
  if (!event) return null;

  const fields: Array<{ label: string; value: string | null }> = [
    { label: 'Event ID', value: event.event_id },
    { label: 'Event Time', value: new Date(event.event_time).toLocaleString() },
    { label: 'Timezone', value: event.event_time_zone_offset },
    { label: 'Business Step', value: event.biz_step },
    { label: 'Disposition', value: event.disposition },
    { label: 'Read Point', value: event.read_point },
    { label: 'Business Location', value: event.biz_location },
    { label: 'DPP ID', value: event.dpp_id },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <EventTypeBadge type={event.event_type} />
            <ActionBadge action={event.action} />
            <span className="text-sm font-mono text-muted-foreground">
              {event.event_id.length > 40
                ? `${event.event_id.slice(0, 40)}...`
                : event.event_id}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Fields grid */}
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {fields.map(({ label, value }) => (
              <div key={label}>
                <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                <dd className="mt-0.5 text-sm break-all">{value ?? '-'}</dd>
              </div>
            ))}
          </dl>

          {/* Payload JSON */}
          <div>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">Event Payload</h4>
            <pre className="rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto max-h-64">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </div>

          {/* Error Declaration */}
          {event.error_declaration && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                Error Declaration
              </h4>
              <pre className="rounded-md bg-red-50 p-3 text-xs font-mono overflow-x-auto max-h-32">
                {JSON.stringify(event.error_declaration, null, 2)}
              </pre>
            </div>
          )}

          {/* Footer metadata */}
          <div className="flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
            <span>Created by: {event.created_by_subject}</span>
            <span>{new Date(event.created_at).toLocaleString()}</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
