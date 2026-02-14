import { useMemo, useState } from 'react';
import { CalendarClock, Clock3, ExternalLink, ShieldCheck } from 'lucide-react';
import type {
  RegulatoryTimelineEvent,
  RegulatoryTimelineTrackFilter,
} from '@/api/types';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { useRegulatoryTimeline } from '../hooks/useRegulatoryTimeline';

const FALLBACK_EVENTS: RegulatoryTimelineEvent[] = [
  {
    id: 'fallback-espr-entry-into-force',
    date: '2024-07-18',
    date_precision: 'day',
    track: 'regulation',
    title: 'ESPR entered into force',
    plain_summary: 'Regulation (EU) 2024/1781 established the core legal baseline for DPP rollout.',
    audience_tags: ['brands', 'compliance'],
    status: 'past',
    verified: false,
    verification: {
      checked_at: '2026-02-14T00:00:00Z',
      method: 'manual',
      confidence: 'low',
    },
    sources: [],
  },
  {
    id: 'fallback-dpp-registry-deadline',
    date: '2026-07-19',
    date_precision: 'day',
    track: 'regulation',
    title: 'DPP registry deadline',
    plain_summary: 'The Commission must have registry infrastructure in place for DPP implementation.',
    audience_tags: ['authorities', 'platform-teams'],
    status: 'upcoming',
    verified: false,
    verification: {
      checked_at: '2026-02-14T00:00:00Z',
      method: 'manual',
      confidence: 'low',
    },
    sources: [],
  },
  {
    id: 'fallback-battery-passport',
    date: '2027-02-18',
    date_precision: 'day',
    track: 'regulation',
    title: 'Battery passport obligation starts',
    plain_summary: 'Specified batteries must provide an electronic battery passport record.',
    audience_tags: ['battery-manufacturers'],
    status: 'upcoming',
    verified: false,
    verification: {
      checked_at: '2026-02-14T00:00:00Z',
      method: 'manual',
      confidence: 'low',
    },
    sources: [],
  },
];

function formatMilestoneDate(event: RegulatoryTimelineEvent): string {
  if (event.date_precision === 'month') {
    const parsed = new Date(`${event.date}-01T00:00:00Z`);
    if (!Number.isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat(undefined, { month: 'short', year: 'numeric' }).format(parsed);
    }
    return event.date;
  }

  const parsed = new Date(`${event.date}T00:00:00Z`);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    }).format(parsed);
  }

  return event.date;
}

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'Unavailable';
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(parsed);
}

function toEventDate(event: RegulatoryTimelineEvent): Date | null {
  if (event.date_precision === 'month') {
    const parsedMonth = new Date(`${event.date}-01T00:00:00Z`);
    return Number.isNaN(parsedMonth.getTime()) ? null : parsedMonth;
  }

  const parsedDay = new Date(`${event.date}T00:00:00Z`);
  return Number.isNaN(parsedDay.getTime()) ? null : parsedDay;
}

function daysUntil(event: RegulatoryTimelineEvent, now: Date): string {
  const eventDate = toEventDate(event);
  if (!eventDate) {
    return 'Date unavailable';
  }

  const dayMs = 24 * 60 * 60 * 1000;
  const deltaDays = Math.ceil((eventDate.getTime() - now.getTime()) / dayMs);
  if (deltaDays <= 0) {
    return 'Happening now';
  }
  if (deltaDays === 1) {
    return '1 day left';
  }
  return `${deltaDays} days left`;
}

function statusBadgeClass(status: RegulatoryTimelineEvent['status']): string {
  if (status === 'today') {
    return 'border-amber-500/40 bg-amber-100 text-amber-900';
  }
  if (status === 'past') {
    return 'border-landing-ink/20 bg-white text-landing-muted';
  }
  return 'border-landing-cyan/35 bg-landing-cyan/10 text-landing-cyan';
}

function filterFallback(track: RegulatoryTimelineTrackFilter): RegulatoryTimelineEvent[] {
  if (track === 'all') {
    return FALLBACK_EVENTS;
  }
  return FALLBACK_EVENTS.filter((event) => event.track === track);
}

export default function RegulatoryTimelineSection() {
  const [track, setTrack] = useState<RegulatoryTimelineTrackFilter>('all');
  const [selectedEvent, setSelectedEvent] = useState<RegulatoryTimelineEvent | null>(null);
  const { data, isLoading, isError } = useRegulatoryTimeline(track);

  const now = new Date();
  const events = useMemo(
    () => data?.events ?? (isError ? filterFallback(track) : []),
    [data?.events, isError, track],
  );

  const nextMilestone = useMemo(
    () => events.find((event) => event.status === 'today' || event.status === 'upcoming') ?? null,
    [events],
  );

  const lastVerified = useMemo(() => {
    const verified = events
      .filter((event) => event.verified)
      .map((event) => new Date(event.verification.checked_at))
      .filter((date) => !Number.isNaN(date.getTime()))
      .sort((left, right) => right.getTime() - left.getTime());

    if (verified.length > 0) {
      return verified[0].toISOString();
    }

    return data?.fetched_at ?? null;
  }, [data?.fetched_at, events]);

  return (
    <section id="timeline" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-3xl border border-landing-cyan/30 bg-white/86 p-6 shadow-[0_30px_54px_-42px_rgba(8,35,50,0.85)] sm:p-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="max-w-3xl">
            <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
              Regulatory intelligence
            </p>
            <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              Verified DPP Timeline
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-landing-muted sm:text-base">
              Verified against official EU and standards-body sources. Updated daily and rendered for
              one-glance understanding across technical and non-technical audiences.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-landing-muted">
              <Badge variant="outline" className="border-landing-cyan/35 bg-landing-cyan/10 text-landing-cyan">
                <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                Official sources only
              </Badge>
              <Badge variant="outline" className="border-landing-ink/20 bg-white text-landing-ink">
                <CalendarClock className="mr-1 h-3.5 w-3.5" />
                Last verified {lastVerified ? formatDateTime(lastVerified) : 'Unavailable'}
              </Badge>
            </div>
          </div>

          <div className="rounded-2xl border border-landing-cyan/30 bg-gradient-to-r from-landing-cyan/12 via-white to-landing-amber/12 p-4 md:max-w-xs">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">Today marker</p>
            <p className="mt-2 font-display text-xl font-semibold text-landing-ink">
              {new Intl.DateTimeFormat(undefined, {
                year: 'numeric',
                month: 'short',
                day: '2-digit',
              }).format(now)}
            </p>
            {nextMilestone ? (
              <p className="mt-2 text-sm leading-relaxed text-landing-muted" data-testid="timeline-next-milestone">
                Next: <span className="font-semibold text-landing-ink">{nextMilestone.title}</span> ·{' '}
                {daysUntil(nextMilestone, now)}
              </p>
            ) : (
              <p className="mt-2 text-sm leading-relaxed text-landing-muted">No upcoming milestones.</p>
            )}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between gap-4">
          <Tabs
            value={track}
            onValueChange={(value) => setTrack(value as RegulatoryTimelineTrackFilter)}
            className="w-full md:w-auto"
          >
            <TabsList className="grid w-full grid-cols-3 bg-landing-surface-1/70 md:w-[360px]">
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="regulation">Regulations</TabsTrigger>
              <TabsTrigger value="standards">Standards</TabsTrigger>
            </TabsList>
          </Tabs>
          {isError && (
            <p className="hidden text-xs font-medium uppercase tracking-[0.1em] text-amber-700 md:block">
              Live feed unavailable · showing fallback milestones
            </p>
          )}
        </div>

        {isLoading && (
          <div className="mt-6 grid gap-3 md:grid-cols-3" data-testid="regulatory-timeline-loading">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={`timeline-loading-${index}`} className="rounded-2xl border border-landing-ink/10 bg-white/80 p-4">
                <div className="h-4 w-20 animate-pulse rounded bg-landing-ink/10" />
                <div className="mt-3 h-6 w-4/5 animate-pulse rounded bg-landing-ink/15" />
                <div className="mt-3 h-4 w-full animate-pulse rounded bg-landing-ink/10" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && events.length === 0 && (
          <div className="mt-6 rounded-2xl border border-dashed border-landing-ink/20 bg-white/70 p-5 text-sm text-landing-muted">
            Timeline events are currently unavailable.
          </div>
        )}

        {!isLoading && events.length > 0 && (
          <>
            <div className="mt-6 hidden overflow-x-auto pb-2 md:block">
              <div className="flex min-w-max snap-x snap-mandatory gap-3">
                {events.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    onClick={() => setSelectedEvent(event)}
                    className="group w-[280px] snap-start rounded-2xl border border-landing-ink/12 bg-white/88 p-4 text-left shadow-[0_16px_30px_-24px_rgba(12,31,46,0.84)] transition-transform hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-landing-cyan"
                    data-testid={`timeline-card-${event.id}`}
                  >
                    <p className="font-display text-xl font-semibold text-landing-ink">{formatMilestoneDate(event)}</p>
                    <p className="mt-2 text-sm font-semibold leading-snug text-landing-ink">{event.title}</p>
                    <p className="mt-2 text-sm leading-relaxed text-landing-muted">{event.plain_summary}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="outline" className={cn('text-[11px] uppercase tracking-[0.08em]', statusBadgeClass(event.status))}>
                        {event.status}
                      </Badge>
                      {event.verified && (
                        <Badge variant="outline" className="border-emerald-600/35 bg-emerald-100 text-emerald-900">
                          Verified
                        </Badge>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6 space-y-3 md:hidden">
              {nextMilestone && (
                <div className="sticky top-16 z-10">
                  <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-landing-cyan/35 bg-white/95 px-3 py-1.5 text-xs font-semibold tracking-[0.06em] text-landing-ink shadow-[0_10px_20px_-16px_rgba(9,34,49,0.8)] backdrop-blur">
                    <span className="inline-block h-2 w-2 rounded-full bg-landing-cyan" aria-hidden="true" />
                    <span className="truncate">Next up: {nextMilestone.title}</span>
                  </div>
                </div>
              )}
              {events.map((event) => (
                <button
                  key={`mobile-${event.id}`}
                  type="button"
                  onClick={() => setSelectedEvent(event)}
                  className="w-full rounded-2xl border border-landing-ink/12 bg-white/90 p-4 text-left shadow-[0_12px_24px_-20px_rgba(10,32,46,0.8)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-landing-cyan"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-display text-lg font-semibold text-landing-ink">{formatMilestoneDate(event)}</p>
                      <p className="mt-1 text-sm font-semibold text-landing-ink">{event.title}</p>
                    </div>
                    <Badge variant="outline" className={cn('text-[11px] uppercase tracking-[0.08em]', statusBadgeClass(event.status))}>
                      {event.status}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-landing-muted">{event.plain_summary}</p>
                  {event.verified && (
                    <Badge variant="outline" className="mt-3 border-emerald-600/35 bg-emerald-100 text-emerald-900">
                      Verified
                    </Badge>
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <Dialog
        open={selectedEvent !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedEvent(null);
          }
        }}
      >
        <DialogContent className="max-w-xl border-landing-ink/15 bg-[hsl(var(--landing-surface-0))]">
          {selectedEvent && (
            <>
              <DialogHeader>
                <DialogTitle className="font-display text-2xl font-semibold text-landing-ink">
                  {selectedEvent.title}
                </DialogTitle>
                <DialogDescription className="text-sm text-landing-muted">
                  {formatMilestoneDate(selectedEvent)} · {selectedEvent.track === 'regulation' ? 'Regulation track' : 'Standards track'}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 text-sm leading-relaxed text-landing-muted">
                <p>{selectedEvent.plain_summary}</p>
                <ul className="space-y-1">
                  <li>Verification method: {selectedEvent.verification.method}</li>
                  <li>Verification confidence: {selectedEvent.verification.confidence}</li>
                  <li>Last checked: {formatDateTime(selectedEvent.verification.checked_at)}</li>
                </ul>
              </div>

              <div className="rounded-xl border border-landing-ink/12 bg-white/75 p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-landing-muted">Official citations</p>
                <ul className="mt-2 space-y-2 text-sm">
                  {selectedEvent.sources.length === 0 ? (
                    <li className="text-landing-muted">No citations available for fallback data.</li>
                  ) : (
                    selectedEvent.sources.map((source) => (
                      <li key={`${selectedEvent.id}-${source.url}`}>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 font-medium text-landing-cyan transition-colors hover:text-landing-ink"
                        >
                          {source.label}
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                        <p className="text-xs text-landing-muted">
                          {source.publisher} · Retrieved {formatDateTime(source.retrieved_at)}
                        </p>
                      </li>
                    ))
                  )}
                </ul>
              </div>

              <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.1em] text-landing-muted">
                <Clock3 className="h-3.5 w-3.5" />
                Digest-backed verification metadata is provided by the public API.
              </p>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
