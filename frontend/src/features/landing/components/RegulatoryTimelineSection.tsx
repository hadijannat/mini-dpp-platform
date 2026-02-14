import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';
import type {
  RegulatoryTimelineEvent,
  RegulatoryTimelineTrackFilter,
  RegulatoryTimelineVerificationMethod,
} from '@/api/types';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
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

const DESKTOP_TIMELINE_CARD_WIDTH_PX = 280;
const DESKTOP_TIMELINE_CARD_GAP_PX = 12;
const DESKTOP_TIMELINE_NODE_OFFSET_PX = 30;

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function dateToMs(event: RegulatoryTimelineEvent): number | null {
  const parsed =
    event.date_precision === 'month'
      ? new Date(`${event.date}-01T00:00:00Z`)
      : new Date(`${event.date}T00:00:00Z`);

  return Number.isNaN(parsed.getTime()) ? null : parsed.getTime();
}

function computeTodayMarkerLeftPx(events: RegulatoryTimelineEvent[], now: Date): number | null {
  const values = events
    .map((event) => dateToMs(event))
    .filter((value): value is number => typeof value === 'number');

  if (values.length === 0) {
    return null;
  }

  const step = DESKTOP_TIMELINE_CARD_WIDTH_PX + DESKTOP_TIMELINE_CARD_GAP_PX;
  if (values.length === 1) {
    return DESKTOP_TIMELINE_NODE_OFFSET_PX;
  }

  const nowMs = now.getTime();
  const firstMs = values[0];
  const lastMs = values[values.length - 1];
  if (nowMs <= firstMs) {
    return DESKTOP_TIMELINE_NODE_OFFSET_PX;
  }
  if (nowMs >= lastMs) {
    return DESKTOP_TIMELINE_NODE_OFFSET_PX + (values.length - 1) * step;
  }

  for (let index = 0; index < values.length - 1; index += 1) {
    const leftMs = values[index];
    const rightMs = values[index + 1];

    if (nowMs < leftMs || nowMs > rightMs) {
      continue;
    }

    const segment = Math.max(1, rightMs - leftMs);
    const interpolation = clamp01((nowMs - leftMs) / segment);
    return DESKTOP_TIMELINE_NODE_OFFSET_PX + (index + interpolation) * step;
  }

  return DESKTOP_TIMELINE_NODE_OFFSET_PX + (values.length - 1) * step;
}

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

function confidenceClass(confidence: RegulatoryTimelineEvent['verification']['confidence']): string {
  if (confidence === 'high') {
    return 'border-landing-cyan/35 bg-landing-cyan/10 text-landing-cyan';
  }
  if (confidence === 'medium') {
    return 'border-amber-500/30 bg-amber-100 text-amber-900';
  }
  return 'border-landing-ink/20 bg-white text-landing-muted';
}

function confidenceLabel(confidence: RegulatoryTimelineEvent['verification']['confidence']): string {
  if (confidence === 'high') {
    return 'High';
  }
  if (confidence === 'medium') {
    return 'Medium';
  }
  return 'Low';
}

function verificationMethodLabel(method: RegulatoryTimelineVerificationMethod): string {
  if (method === 'content-match') {
    return 'Content match against official source text';
  }
  if (method === 'source-hash') {
    return 'Official source fetched and hashed';
  }
  return 'Manual fallback';
}

function trackNodeClass(track: RegulatoryTimelineEvent['track']): string {
  return track === 'standards' ? 'bg-amber-500' : 'bg-landing-cyan';
}

function filterFallback(track: RegulatoryTimelineTrackFilter): RegulatoryTimelineEvent[] {
  if (track === 'all') {
    return FALLBACK_EVENTS;
  }
  return FALLBACK_EVENTS.filter((event) => event.track === track);
}

interface TimelineCardProps {
  event: RegulatoryTimelineEvent;
  desktop: boolean;
  testId?: string;
  shouldReduceMotion: boolean;
  onSelect: (event: RegulatoryTimelineEvent) => void;
}

function TimelineCard({
  event,
  desktop,
  testId,
  shouldReduceMotion,
  onSelect,
}: TimelineCardProps) {
  const motionProps = shouldReduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: 14 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -10 },
        transition: { type: 'spring' as const, stiffness: 420, damping: 34 },
      };

  return (
    <motion.button
      type="button"
      layout
      onClick={() => onSelect(event)}
      whileHover={shouldReduceMotion ? undefined : { y: -4 }}
      whileTap={shouldReduceMotion ? undefined : { scale: 0.99 }}
      className={cn(
        'group rounded-2xl border border-landing-ink/12 bg-white/90 text-left shadow-[0_16px_30px_-24px_rgba(12,31,46,0.84)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-landing-cyan',
        desktop ? 'h-full w-[280px] p-4' : 'w-full p-4',
      )}
      data-testid={testId}
      {...motionProps}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={cn('font-display font-semibold text-landing-ink', desktop ? 'text-xl' : 'text-lg')}>
            {formatMilestoneDate(event)}
          </p>
          <p className="mt-1 text-sm font-semibold leading-snug text-landing-ink">{event.title}</p>
        </div>
        <Badge
          variant="outline"
          className={cn('text-[11px] uppercase tracking-[0.08em]', statusBadgeClass(event.status))}
        >
          {event.status}
        </Badge>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-landing-muted">{event.plain_summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {event.verified ? (
          <Badge variant="outline" className={cn('gap-1.5', confidenceClass(event.verification.confidence))}>
            <ShieldCheck className="h-3.5 w-3.5" />
            Verified ({confidenceLabel(event.verification.confidence)})
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1.5 border-landing-ink/15 bg-white text-landing-muted">
            <Clock3 className="h-3.5 w-3.5" />
            Unverified
          </Badge>
        )}
      </div>
    </motion.button>
  );
}

export default function RegulatoryTimelineSection() {
  const shouldReduceMotion = useReducedMotion();
  const [track, setTrack] = useState<RegulatoryTimelineTrackFilter>('all');
  const [selectedEvent, setSelectedEvent] = useState<RegulatoryTimelineEvent | null>(null);
  const [now, setNow] = useState<Date>(() => new Date());
  const [desktopScrollProgress, setDesktopScrollProgress] = useState(0);
  const desktopScrollRef = useRef<HTMLDivElement | null>(null);
  const { data, isLoading, isError } = useRegulatoryTimeline(track);

  useEffect(() => {
    const intervalId = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(intervalId);
  }, []);

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

  const todayMarkerLeftPx = useMemo(() => computeTodayMarkerLeftPx(events, now), [events, now]);

  useEffect(() => {
    const scrollEl = desktopScrollRef.current;
    if (!scrollEl) {
      return;
    }

    const updateProgress = () => {
      const maxScrollable = scrollEl.scrollWidth - scrollEl.clientWidth;
      if (maxScrollable <= 0) {
        setDesktopScrollProgress(1);
        return;
      }
      setDesktopScrollProgress(clamp01(scrollEl.scrollLeft / maxScrollable));
    };

    updateProgress();
    scrollEl.addEventListener('scroll', updateProgress, { passive: true });
    window.addEventListener('resize', updateProgress);

    return () => {
      scrollEl.removeEventListener('scroll', updateProgress);
      window.removeEventListener('resize', updateProgress);
    };
  }, [events, track]);

  const freshnessStatus =
    data?.source_status ?? (isError || isLoading ? 'stale' : ('fresh' as const));
  const isFresh = freshnessStatus === 'fresh';

  const scrollDesktop = (direction: -1 | 1) => {
    const scrollEl = desktopScrollRef.current;
    if (!scrollEl) {
      return;
    }

    const step = Math.max(120, Math.floor(scrollEl.clientWidth * 0.8));
    scrollEl.scrollBy({
      left: step * direction,
      behavior: shouldReduceMotion ? 'auto' : 'smooth',
    });
  };

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
              Verified from official sources (Commission, EUR-Lex, and standards bodies). Built for
              one-glance understanding across compliance, product, and engineering audiences.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-landing-muted">
              <Badge variant="outline" className="border-landing-cyan/35 bg-landing-cyan/10 text-landing-cyan">
                <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                Official sources only
              </Badge>
              <Badge
                variant="outline"
                className={cn(
                  'gap-1.5',
                  isFresh
                    ? 'border-landing-cyan/35 bg-landing-cyan/10 text-landing-cyan'
                    : 'border-amber-500/30 bg-amber-100 text-amber-900',
                )}
              >
                <span
                  className={cn(
                    'inline-block h-2 w-2 rounded-full',
                    isFresh ? 'bg-landing-cyan' : 'bg-amber-500',
                  )}
                  aria-hidden="true"
                />
                {isFresh ? 'Live verified feed' : 'Refreshing...'}
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
              <div
                key={`timeline-loading-${index}`}
                className="rounded-2xl border border-landing-ink/10 bg-white/80 p-4"
              >
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
            <div className="mt-6 hidden md:block">
              <div className="relative">
                <div
                  ref={desktopScrollRef}
                  className="overflow-x-auto snap-x snap-mandatory pb-4 [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]"
                  data-testid="timeline-scroll-container"
                >
                  <div className="relative min-w-max px-1 pt-12">
                    <div
                      className="pointer-events-none absolute left-1 right-1 top-14 h-px bg-gradient-to-r from-transparent via-landing-ink/20 to-transparent"
                      data-testid="timeline-axis-rail"
                    />
                    {todayMarkerLeftPx !== null && (
                      <div
                        className="pointer-events-none absolute top-0 z-[1] flex -translate-x-1/2 flex-col items-center"
                        style={{ left: `${todayMarkerLeftPx}px` }}
                        data-testid="timeline-now-marker"
                      >
                        <div className="rounded-full border border-amber-500/30 bg-amber-100 px-2.5 py-0.5 text-[11px] font-semibold text-amber-900">
                          Today
                        </div>
                        <div className="h-8 w-px bg-amber-500/60" />
                      </div>
                    )}
                    <div className="flex gap-3">
                      <AnimatePresence initial={false} mode="popLayout">
                        {events.map((event) => (
                          <motion.div key={event.id} layout className="relative w-[280px] snap-start pt-2">
                            <span
                              className={cn(
                                'pointer-events-none absolute left-6 top-[0.10rem] h-3 w-3 rounded-full border-2 border-white shadow-[0_0_0_2px_rgba(12,31,46,0.12)]',
                                trackNodeClass(event.track),
                              )}
                              aria-hidden="true"
                            />
                            <TimelineCard
                              event={event}
                              desktop
                              testId={`timeline-card-${event.id}`}
                              shouldReduceMotion={!!shouldReduceMotion}
                              onSelect={setSelectedEvent}
                            />
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </div>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => scrollDesktop(-1)}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-landing-ink/15 bg-white text-landing-muted transition-colors hover:text-landing-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-landing-cyan"
                    aria-label="Scroll timeline left"
                    data-testid="timeline-scroll-left"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <Progress
                    value={Math.round(desktopScrollProgress * 100)}
                    className="h-1.5 bg-landing-ink/10 [&>div]:bg-landing-cyan"
                    data-testid="timeline-scroll-progress"
                  />
                  <button
                    type="button"
                    onClick={() => scrollDesktop(1)}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-landing-ink/15 bg-white text-landing-muted transition-colors hover:text-landing-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-landing-cyan"
                    aria-label="Scroll timeline right"
                    data-testid="timeline-scroll-right"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
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
              <AnimatePresence initial={false} mode="popLayout">
                {events.map((event) => (
                  <motion.div key={`mobile-${event.id}`} layout>
                    <TimelineCard
                      event={event}
                      desktop={false}
                      shouldReduceMotion={!!shouldReduceMotion}
                      onSelect={setSelectedEvent}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
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
                  {formatMilestoneDate(selectedEvent)} ·{' '}
                  {selectedEvent.track === 'regulation' ? 'Regulation track' : 'Standards track'}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 text-sm leading-relaxed text-landing-muted">
                <p>{selectedEvent.plain_summary}</p>
                <ul className="space-y-1">
                  <li>Verification method: {verificationMethodLabel(selectedEvent.verification.method)}</li>
                  <li>
                    Verification confidence: {confidenceLabel(selectedEvent.verification.confidence)}
                  </li>
                  <li>Last checked: {formatDateTime(selectedEvent.verification.checked_at)}</li>
                </ul>
              </div>

              <div className="rounded-xl border border-landing-ink/12 bg-white/75 p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-landing-muted">
                  Official citations
                </p>
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
