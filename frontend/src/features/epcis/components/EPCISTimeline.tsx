import { useState } from 'react';
import { Activity } from 'lucide-react';
import { EmptyState } from '@/components/empty-state';
import { EventCard } from './EventCard';
import { EventDetailDialog } from './EventDetailDialog';
import type { EPCISEvent } from '../lib/epcisApi';

interface EPCISTimelineProps {
  events: EPCISEvent[];
}

export function EPCISTimeline({ events }: EPCISTimelineProps) {
  const [selectedEvent, setSelectedEvent] = useState<EPCISEvent | null>(null);

  if (events.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No supply chain events"
        description="No EPCIS events have been recorded yet. Capture an event to start tracking."
      />
    );
  }

  return (
    <>
      <div className="space-y-0">
        {events.map((event, index) => (
          <EventCard
            key={event.id}
            event={event}
            isLast={index === events.length - 1}
            onClick={() => setSelectedEvent(event)}
          />
        ))}
      </div>

      <EventDetailDialog
        event={selectedEvent}
        open={selectedEvent !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedEvent(null);
        }}
      />
    </>
  );
}
