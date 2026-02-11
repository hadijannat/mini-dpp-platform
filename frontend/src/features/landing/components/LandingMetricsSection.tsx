import { Activity, Boxes, CalendarDays, Layers } from 'lucide-react';
import { landingContent } from '../content/landingContent';
import { useLandingSummary } from '../hooks/useLandingSummary';

interface LandingMetricsSectionProps {
  tenantSlug: string;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function formatDate(value: string | null): string {
  if (!value) {
    return 'No published records yet';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'No published records yet';
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(parsed);
}

export default function LandingMetricsSection({ tenantSlug }: LandingMetricsSectionProps) {
  const { data, isLoading, isError } = useLandingSummary(tenantSlug);

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
            Landing metrics are tenant-scoped aggregates from a dedicated public summary endpoint. No
            record-level IDs, no raw payloads, and no actor metadata are exposed.
          </p>
        </div>

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
                {formatDate(data.latest_publish_at)}
              </p>
              <p className="mt-3 text-sm text-landing-muted">
                Generated{' '}
                {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
                  new Date(data.generated_at),
                )}
              </p>
            </article>
          </div>
        )}
      </div>
    </section>
  );
}
