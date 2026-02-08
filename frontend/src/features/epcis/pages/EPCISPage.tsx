import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { EventTypeBadge, ActionBadge } from '../components/EventTypeBadge';
import { EventFilters } from '../components/EventFilters';
import { EventDetailDialog } from '../components/EventDetailDialog';
import { CaptureDialog } from '../components/CaptureDialog';
import { fetchEPCISEvents } from '../lib/epcisApi';
import type { EPCISEvent, EPCISQueryFilters } from '../lib/epcisApi';

const PAGE_SIZE = 25;

export default function EPCISPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [filters, setFilters] = useState<EPCISQueryFilters>({ limit: PAGE_SIZE, offset: 0 });
  const [selectedEvent, setSelectedEvent] = useState<EPCISEvent | null>(null);
  const [captureOpen, setCaptureOpen] = useState(false);
  const [captureDppId, setCaptureDppId] = useState('');
  const [dppIdPromptOpen, setDppIdPromptOpen] = useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['epcis-events', filters],
    queryFn: () => fetchEPCISEvents(filters, token),
    enabled: Boolean(token),
  });

  const events = data?.eventList ?? [];
  const offset = filters.offset ?? 0;
  const hasMore = events.length === PAGE_SIZE;

  const pageError = isError ? (error as Error) : undefined;
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  const handleCaptureClick = () => {
    setDppIdPromptOpen(true);
  };

  const handleDppIdSubmit = (id: string) => {
    setCaptureDppId(id);
    setDppIdPromptOpen(false);
    setCaptureOpen(true);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supply Chain Events"
        description="EPCIS 2.0 event capture and query"
        actions={
          <Button onClick={handleCaptureClick}>
            <Plus className="h-4 w-4 mr-2" />
            Capture Event
          </Button>
        }
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      <EventFilters filters={filters} onChange={setFilters} />

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Business Step</TableHead>
                <TableHead>Disposition</TableHead>
                <TableHead className="hidden md:table-cell">DPP</TableHead>
                <TableHead>Event Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => (
                <TableRow
                  key={event.id}
                  className="cursor-pointer"
                  onClick={() => setSelectedEvent(event)}
                >
                  <TableCell>
                    <EventTypeBadge type={event.event_type} />
                  </TableCell>
                  <TableCell>
                    <ActionBadge action={event.action} />
                  </TableCell>
                  <TableCell className="text-sm">
                    {event.biz_step?.replace(/_/g, ' ') ?? '-'}
                  </TableCell>
                  <TableCell className="text-sm">
                    {event.disposition?.replace(/_/g, ' ') ?? '-'}
                  </TableCell>
                  <TableCell className="hidden md:table-cell font-mono text-xs text-muted-foreground">
                    {event.dpp_id.slice(0, 8)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {new Date(event.event_time).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {events.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No EPCIS events found. Adjust filters or capture a new event.
            </div>
          )}

          {/* Pagination */}
          <div className="flex items-center justify-between border-t px-4 py-3">
            <p className="text-sm text-muted-foreground">
              Showing {events.length} event{events.length !== 1 ? 's' : ''}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setFilters((f) => ({ ...f, offset: Math.max(0, (f.offset ?? 0) - PAGE_SIZE) }))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!hasMore}
                onClick={() => setFilters((f) => ({ ...f, offset: (f.offset ?? 0) + PAGE_SIZE }))}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}

      <EventDetailDialog
        event={selectedEvent}
        open={selectedEvent !== null}
        onOpenChange={(open) => { if (!open) setSelectedEvent(null); }}
      />

      {/* DPP ID prompt dialog */}
      <DppIdPrompt
        open={dppIdPromptOpen}
        onOpenChange={setDppIdPromptOpen}
        onSubmit={handleDppIdSubmit}
      />

      {/* Capture dialog */}
      {captureOpen && captureDppId && (
        <CaptureDialog
          open={captureOpen}
          onOpenChange={(v) => {
            setCaptureOpen(v);
            if (!v) setCaptureDppId('');
          }}
          dppId={captureDppId}
        />
      )}
    </div>
  );
}

function DppIdPrompt({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (id: string) => void;
}) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) {
      onSubmit(trimmed);
      setValue('');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Select DPP</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="dpp-id-input">DPP ID</Label>
            <Input
              id="dpp-id-input"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Enter DPP UUID"
              required
            />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!value.trim()}>
              Continue
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
