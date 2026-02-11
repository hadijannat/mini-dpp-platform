import { useEffect, useState } from 'react';
import { Activity, Boxes, CalendarDays, Layers } from 'lucide-react';
import { landingContent } from '../content/landingContent';
import {
  LANDING_SUMMARY_REFRESH_SLA_MS,
  type LandingSummaryScope,
  useLandingSummary,
} from '../hooks/useLandingSummary';

interface LandingMetricsSectionProps {
  tenantSlug?: string;
  scope?: LandingSummaryScope;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function parseIso(value: string | null): Date | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

function formatDateTime(value: string | null): string {
  const parsed = parseIso(value);
  if (!parsed) {
    return 'No published records yet';
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  }).format(parsed);
}

function formatFreshnessAge(value: string | null, nowMs: number): string {
  const parsed = parseIso(value);
  if (!parsed) {
    return 'Freshness unavailable';
  }
  const deltaMs = Math.max(0, nowMs - parsed.getTime());
  const totalSeconds = Math.floor(deltaMs / 1000);
  if (totalSeconds < 5) {
    return 'Updated just now';
  }
  if (totalSeconds < 60) {
    return `Updated ${totalSeconds}s ago`;
  }
  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) {
    return `Updated ${totalMinutes}m ago`;
  }
  const totalHours = Math.floor(totalMinutes / 60);
  if (totalHours < 24) {
    return `Updated ${totalHours}h ago`;
  }
  const totalDays = Math.floor(totalHours / 24);
  return `Updated ${totalDays}d ago`;
}

function formatScopeDescription(scope: string | null | undefined, tenantSlug?: string): string {
  if (scope === 'all') {
    return 'Scope: ecosystem-wide aggregate across all active tenants.';
  }
  if (scope === 'default') {
    return 'Scope: default tenant aggregate.';
  }
  if (tenantSlug) {
    return `Scope: ${tenantSlug} tenant aggregate.`;
  }
  return 'Scope: aggregate-only public summary.';
}

export default function LandingMetricsSection({ tenantSlug, scope = 'all' }: LandingMetricsSectionProps) {
  const { data, isLoading, isError } = useLandingSummary(tenantSlug, scope);
  const [nowMs, setNowMs] = useState<number>(() => Date.now());

  useEffect(() => {
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1_000);
    return () => window.clearInterval(intervalId);
  }, []);

  return (
    <section id="metrics" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-7 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
              Trust metrics strip
            </p>
            <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              Aggregate visibility, privacy by default
            </h2>
          </div>
          <p className="max-w-xl text-sm leading-relaxed text-landing-muted sm:text-base">
            Landing metrics are scope-aware aggregates from a dedicated public summary endpoint. No
            record-level IDs, no raw payloads, and no actor metadata are exposed.
          </p>
        </div>
        {!isLoading && !isError && data && (
          <p
            className="mb-5 text-sm font-medium text-landing-muted"
            data-testid="landing-metrics-scope-description"
          >
            {formatScopeDescription(data.scope, tenantSlug)}
          </p>
        )}

        {isLoading && (
          <div
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
            aria-live="polite"
            data-testid="landing-metrics-loading"
          >
            <p className="sr-only">Loading verified aggregate metrics...</p>
            {Array.from({ length: 4 }).map((_, idx) => (
              <div
                key={`loading-${idx}`}
                className="rounded-2xl border border-landing-ink/10 bg-white/70 p-5"
                data-testid="landing-metrics-loading-card"
              >
                <div className="h-4 w-2/5 animate-pulse rounded bg-landing-ink/10" />
                <div className="mt-4 h-8 w-4/5 animate-pulse rounded bg-landing-ink/15" />
                <div className="mt-3 h-4 w-full animate-pulse rounded bg-landing-ink/10" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <div className="grid gap-4 sm:grid-cols-3" aria-live="polite" data-testid="landing-metrics-fallback">
            {landingContent.fallbackMetrics.map((metric) => (
              <article
                key={metric.label}
                className="rounded-2xl border border-landing-ink/10 bg-white/78 p-5 shadow-[0_24px_40px_-36px_rgba(20,39,53,0.75)]"
              >
                <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                  {metric.label}
                </h3>
                <p className="mt-3 font-display text-xl font-semibold text-landing-ink">{metric.value}</p>
                <p className="mt-3 text-sm leading-relaxed text-landing-muted">{metric.detail}</p>
              </article>
            ))}
          </div>
        )}

        {!isLoading && !isError && data && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-live="polite" data-testid="landing-metrics-success">
            <article
              className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_24px_40px_-36px_rgba(20,39,53,0.75)]"
              data-testid="landing-metric-published-dpps"
            >
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                <Layers className="h-4 w-4" />
                Published DPPs
              </div>
              <p className="mt-4 font-display text-4xl font-semibold text-landing-ink">
                {formatNumber(data.published_dpps)}
              </p>
              <p className="mt-3 text-sm text-landing-muted">Published records only.</p>
            </article>

            <article
              className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_24px_40px_-36px_rgba(20,39,53,0.75)]"
              data-testid="landing-metric-product-families"
            >
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                <Boxes className="h-4 w-4" />
                Product Families
              </div>
              <p className="mt-4 font-display text-4xl font-semibold text-landing-ink">
                {formatNumber(data.active_product_families)}
              </p>
              <p className="mt-3 text-sm text-landing-muted">Distinct aggregate count.</p>
            </article>

            <article
              className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_24px_40px_-36px_rgba(20,39,53,0.75)]"
              data-testid="landing-metric-traceability"
            >
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                <Activity className="h-4 w-4" />
                With Traceability
              </div>
              <p className="mt-4 font-display text-4xl font-semibold text-landing-ink">
                {formatNumber(data.dpps_with_traceability)}
              </p>
              <p className="mt-3 text-sm text-landing-muted">Count only, no raw event payloads.</p>
            </article>

            <article
              className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_24px_40px_-36px_rgba(20,39,53,0.75)]"
              data-testid="landing-metric-latest-publish"
            >
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                <CalendarDays className="h-4 w-4" />
                Latest Publish
              </div>
              <p className="mt-4 font-display text-2xl font-semibold leading-tight text-landing-ink">
                {formatDateTime(data.latest_publish_at)}
              </p>
              {data.generated_at ? (
                <>
                  <p className="mt-3 text-sm text-landing-muted" data-testid="landing-metric-freshness-exact">
                    Generated {formatDateTime(data.generated_at)}
                  </p>
                  <p
                    className="mt-1 text-xs font-medium uppercase tracking-[0.1em] text-landing-muted"
                    data-testid="landing-metric-freshness-relative"
                  >
                    {formatFreshnessAge(data.generated_at, nowMs)} · Auto-refreshes every{' '}
                    {data.refresh_sla_seconds ?? Math.floor(LANDING_SUMMARY_REFRESH_SLA_MS / 1000)}s
                  </p>
                </>
              ) : (
                <p className="mt-3 text-sm text-landing-muted" data-testid="landing-metric-freshness-unavailable">
                  Freshness unavailable · Auto-refreshes every{' '}
                  {data.refresh_sla_seconds ?? Math.floor(LANDING_SUMMARY_REFRESH_SLA_MS / 1000)}s
                </p>
              )}
            </article>
          </div>
        )}
      </div>
    </section>
  );
}
