import { useQuery } from '@tanstack/react-query';
import type {
  RegulatoryTimelineConfidence,
  RegulatoryTimelineDatePrecision,
  RegulatoryTimelineEvent,
  RegulatoryTimelineEventStatus,
  RegulatoryTimelineResponse,
  RegulatoryTimelineTrack,
  RegulatoryTimelineTrackFilter,
  RegulatoryTimelineVerificationMethod,
} from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

const REGULATORY_TIMELINE_STALE_MS = 5 * 60 * 1000;
const REGULATORY_TIMELINE_GC_MS = 60 * 60 * 1000;

function toIsoOrNow(value: unknown): string {
  if (typeof value !== 'string' || value.trim() === '') {
    return new Date().toISOString();
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return new Date().toISOString();
  }
  return parsed.toISOString();
}

function toNonNegativeInt(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value >= 0 ? Math.floor(value) : fallback;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed) && parsed >= 0) {
      return parsed;
    }
  }
  return fallback;
}

function toTrack(value: unknown): RegulatoryTimelineTrack {
  return value === 'standards' ? 'standards' : 'regulation';
}

function toDatePrecision(value: unknown): RegulatoryTimelineDatePrecision {
  return value === 'month' ? 'month' : 'day';
}

function toStatus(value: unknown): RegulatoryTimelineEventStatus {
  if (value === 'past' || value === 'today' || value === 'upcoming') {
    return value;
  }
  return 'upcoming';
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function sanitizeEvent(value: unknown): RegulatoryTimelineEvent | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const source = value as Record<string, unknown>;
  const date = typeof source.date === 'string' ? source.date.trim() : '';
  const title = typeof source.title === 'string' ? source.title.trim() : '';

  if (!date || !title) {
    return null;
  }

  const sourcesRaw = Array.isArray(source.sources) ? source.sources : [];
  const sources = sourcesRaw
    .map((entry) => {
      if (!entry || typeof entry !== 'object') {
        return null;
      }
      const sourceEntry = entry as Record<string, unknown>;
      const url = typeof sourceEntry.url === 'string' ? sourceEntry.url.trim() : '';
      const label = typeof sourceEntry.label === 'string' ? sourceEntry.label.trim() : '';
      const publisher =
        typeof sourceEntry.publisher === 'string' ? sourceEntry.publisher.trim() : '';
      if (!url || !label || !publisher) {
        return null;
      }
      return {
        label,
        url,
        publisher,
        retrieved_at: toIsoOrNow(sourceEntry.retrieved_at),
        sha256:
          typeof sourceEntry.sha256 === 'string' && sourceEntry.sha256.trim() !== ''
            ? sourceEntry.sha256.trim()
            : null,
      };
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

  const verificationRaw =
    source.verification && typeof source.verification === 'object'
      ? (source.verification as Record<string, unknown>)
      : {};

  const method: RegulatoryTimelineVerificationMethod =
    verificationRaw.method === 'content-match' ||
    verificationRaw.method === 'source-hash' ||
    verificationRaw.method === 'manual'
      ? verificationRaw.method
      : 'manual';

  const confidence: RegulatoryTimelineConfidence =
    verificationRaw.confidence === 'high' ||
    verificationRaw.confidence === 'medium' ||
    verificationRaw.confidence === 'low'
      ? verificationRaw.confidence
      : 'low';

  const verification = {
    checked_at: toIsoOrNow(verificationRaw.checked_at),
    method,
    confidence,
  };

  return {
    id:
      typeof source.id === 'string' && source.id.trim() !== ''
        ? source.id.trim()
        : `${toTrack(source.track)}-${date}-${title}`.toLowerCase().replace(/\s+/g, '-'),
    date,
    date_precision: toDatePrecision(source.date_precision),
    track: toTrack(source.track),
    title,
    plain_summary:
      typeof source.plain_summary === 'string' && source.plain_summary.trim() !== ''
        ? source.plain_summary.trim()
        : title,
    audience_tags: toStringList(source.audience_tags),
    status: toStatus(source.status),
    verified: source.verified === true,
    verification,
    sources,
  };
}

function toEventSortKey(event: RegulatoryTimelineEvent): number {
  if (event.date_precision === 'month') {
    const monthDate = new Date(`${event.date}-01T00:00:00Z`);
    if (!Number.isNaN(monthDate.getTime())) {
      return monthDate.getTime();
    }
  }

  const dayDate = new Date(`${event.date}T00:00:00Z`);
  if (!Number.isNaN(dayDate.getTime())) {
    return dayDate.getTime();
  }

  return Number.MAX_SAFE_INTEGER;
}

export function sanitizeRegulatoryTimeline(payload: unknown): RegulatoryTimelineResponse {
  const source = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};

  const eventsRaw = Array.isArray(source.events) ? source.events : [];
  const events = eventsRaw
    .map((entry) => sanitizeEvent(entry))
    .filter((entry): entry is RegulatoryTimelineEvent => entry !== null)
    .sort((left, right) => toEventSortKey(left) - toEventSortKey(right));

  return {
    generated_at: toIsoOrNow(source.generated_at),
    fetched_at: toIsoOrNow(source.fetched_at),
    source_status: source.source_status === 'stale' ? 'stale' : 'fresh',
    refresh_sla_seconds: toNonNegativeInt(source.refresh_sla_seconds, 82_800),
    digest_sha256:
      typeof source.digest_sha256 === 'string' && source.digest_sha256.trim() !== ''
        ? source.digest_sha256.trim()
        : '',
    events,
  };
}

async function fetchRegulatoryTimeline(
  track: RegulatoryTimelineTrackFilter,
): Promise<RegulatoryTimelineResponse> {
  const query = track === 'all' ? '' : `?track=${encodeURIComponent(track)}`;
  const response = await apiFetch(`/api/v1/public/landing/regulatory-timeline${query}`);

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Unable to load verified regulatory timeline.'));
  }

  return sanitizeRegulatoryTimeline((await response.json()) as unknown);
}

export function useRegulatoryTimeline(track: RegulatoryTimelineTrackFilter = 'all', enabled = true) {
  const normalizedTrack: RegulatoryTimelineTrackFilter =
    track === 'regulation' || track === 'standards' ? track : 'all';

  return useQuery<RegulatoryTimelineResponse>({
    queryKey: ['regulatory-timeline', normalizedTrack],
    queryFn: () => fetchRegulatoryTimeline(normalizedTrack),
    enabled,
    staleTime: REGULATORY_TIMELINE_STALE_MS,
    gcTime: REGULATORY_TIMELINE_GC_MS,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}
