import { useMemo } from 'react';
import { CalendarClock, ExternalLink, ShieldAlert } from 'lucide-react';
import type { RegulatoryTimelineEvent } from '@/api/types';
import { useRegulatoryTimeline } from '../hooks/useRegulatoryTimeline';
import ClaimLevelBadge from './ClaimLevelBadge';
import { landingContent } from '../content/landingContent';

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

function parseEventDate(event: RegulatoryTimelineEvent): Date | null {
  const parsed =
    event.date_precision === 'month'
      ? new Date(`${event.date}-01T00:00:00Z`)
      : new Date(`${event.date}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatEventDate(event: RegulatoryTimelineEvent): string {
  const parsed = parseEventDate(event);
  if (!parsed) {
    return event.date;
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: event.date_precision === 'month' ? 'long' : 'short',
    day: event.date_precision === 'month' ? undefined : '2-digit',
  }).format(parsed);
}

function sortByDate(events: RegulatoryTimelineEvent[]): RegulatoryTimelineEvent[] {
  return [...events].sort((left, right) => {
    const leftMs = parseEventDate(left)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    const rightMs = parseEventDate(right)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    return leftMs - rightMs;
  });
}

function pickHighlights(events: RegulatoryTimelineEvent[]): RegulatoryTimelineEvent[] {
  if (events.length === 0) {
    return [];
  }
  const sorted = sortByDate(events);
  const upcoming = sorted.filter((event) => event.status === 'upcoming' || event.status === 'today');
  const recentPast = [...sorted].reverse().find((event) => event.status === 'past');

  const highlights = [...upcoming.slice(0, 2)];
  if (recentPast) {
    highlights.push(recentPast);
  }

  if (highlights.length < 3) {
    for (const event of sorted) {
      if (!highlights.some((entry) => entry.id === event.id)) {
        highlights.push(event);
      }
      if (highlights.length >= 3) {
        break;
      }
    }
  }

  return highlights.slice(0, 3);
}

function milestoneTone(status: RegulatoryTimelineEvent['status']): string {
  if (status === 'today') {
    return 'border-amber-400/40 bg-amber-50 text-amber-900';
  }
  if (status === 'past') {
    return 'border-emerald-500/30 bg-emerald-50 text-emerald-900';
  }
  return 'border-landing-cyan/30 bg-cyan-50 text-cyan-900';
}

export default function EvidenceGovernanceSection() {
  const timelineQuery = useRegulatoryTimeline('all');
  const timelineEvents = useMemo(() => {
    if (timelineQuery.data?.events && timelineQuery.data.events.length > 0) {
      return timelineQuery.data.events;
    }
    if (timelineQuery.isError) {
      return FALLBACK_EVENTS;
    }
    return [];
  }, [timelineQuery.data?.events, timelineQuery.isError]);
  const highlights = useMemo(() => pickHighlights(timelineEvents), [timelineEvents]);

  return (
    <section id="evidence-governance" className="scroll-mt-24 bg-landing-surface-1/40 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-4xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            {landingContent.evidenceRail.eyebrow}
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            {landingContent.evidenceRail.title}
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
            {landingContent.evidenceRail.subtitle}
          </p>
        </div>

        <div className="mt-7 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <article className="rounded-2xl border border-landing-ink/12 bg-white/85 p-5 shadow-[0_24px_44px_-34px_rgba(12,36,49,0.75)]">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.11em] text-landing-muted">
              <CalendarClock className="h-4 w-4 text-landing-cyan" />
              Regulatory timeline highlights
            </p>
            <p className="mt-2 text-sm leading-relaxed text-landing-muted">
              {landingContent.evidenceRail.timelineSummary}
            </p>

            {timelineQuery.isLoading && (
              <div className="mt-4 grid gap-3" data-testid="evidence-timeline-loading">
                {Array.from({ length: 3 }).map((_, idx) => (
                  <div key={`timeline-loading-${idx}`} className="rounded-xl border border-landing-ink/10 bg-landing-surface-0/70 p-3">
                    <div className="h-3 w-1/3 animate-pulse rounded bg-landing-ink/10" />
                    <div className="mt-2 h-4 w-5/6 animate-pulse rounded bg-landing-ink/12" />
                  </div>
                ))}
              </div>
            )}

            {!timelineQuery.isLoading && highlights.length > 0 && (
              <div className="mt-4 grid gap-3">
                {highlights.map((event) => (
                  <article key={event.id} className="rounded-xl border border-landing-ink/10 bg-landing-surface-0/70 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-landing-ink">{event.title}</p>
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] ${milestoneTone(event.status)}`}>
                        {event.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.08em] text-landing-muted">
                      {formatEventDate(event)}
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-landing-muted">{event.plain_summary}</p>
                  </article>
                ))}
              </div>
            )}

            {timelineQuery.isError && (
              <p className="mt-3 text-xs font-semibold uppercase tracking-[0.1em] text-amber-700" data-testid="evidence-timeline-fallback">
                Live timeline unavailable, showing fallback milestones
              </p>
            )}
          </article>

          <article className="rounded-2xl border border-landing-ink/12 bg-white/85 p-5 shadow-[0_24px_44px_-34px_rgba(12,36,49,0.75)]">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.11em] text-landing-muted">
              <ShieldAlert className="h-4 w-4 text-landing-cyan" />
              {landingContent.evidenceRail.policyTitle}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-landing-muted">
              {landingContent.evidenceRail.policySummary}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {landingContent.evidenceRail.blockedKeys.map((blockedKey) => (
                <code
                  key={blockedKey}
                  className="rounded border border-landing-ink/12 bg-landing-surface-0/85 px-2 py-1 text-[11px] text-landing-ink"
                >
                  {blockedKey}
                </code>
              ))}
            </div>
            <a
              href={landingContent.evidenceRail.policyLink.href}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
            >
              {landingContent.evidenceRail.policyLink.label}
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </article>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-3" data-testid="evidence-standards-cards">
          {landingContent.evidenceRail.standardsCards.map((card) => (
            <article
              key={card.title}
              className="rounded-2xl border border-landing-ink/12 bg-white/85 p-5 shadow-[0_20px_36px_-32px_rgba(16,35,50,0.8)]"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-display text-lg font-semibold text-landing-ink">{card.title}</h3>
                <ClaimLevelBadge level={card.claimLevel} />
              </div>
              <p className="mt-3 text-sm leading-relaxed text-landing-muted">{card.summary}</p>
              <a
                href={card.evidence.href}
                target={card.evidence.href.startsWith('http') ? '_blank' : undefined}
                rel={card.evidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
              >
                {card.evidence.label}
                {card.evidence.href.startsWith('http') && <ExternalLink className="h-3.5 w-3.5" />}
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
