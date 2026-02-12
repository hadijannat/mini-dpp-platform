import { Lock, ShieldCheck } from 'lucide-react';
import { landingContent } from '../content/landingContent';

export default function DataExposureSection() {
  return (
    <section id="data-policy" className="scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 max-w-3xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Security and privacy disclosure
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            What is public vs what stays protected
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
            Landing responses are intentionally conservative: aggregate metrics and curated evidence
            links only. Product identifiers, event payloads, and actor metadata are blocked.
          </p>
          <a
            href="https://github.com/hadijannat/mini-dpp-platform/blob/main/docs/public/operations/public-data-exposure-policy.md"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-flex text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
          >
            Read full public data exposure policy
          </a>
        </div>

        <div className="overflow-hidden rounded-3xl border border-landing-ink/12 bg-white/80 shadow-[0_24px_50px_-38px_rgba(13,39,50,0.75)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] table-auto border-collapse text-left">
            <thead className="bg-landing-surface-2/70">
              <tr>
                <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                  Data item
                </th>
                <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                  Landing visibility
                </th>
                <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                  Rule
                </th>
              </tr>
            </thead>
            <tbody>
              {landingContent.dataExposureRules.map((rule) => (
                <tr key={rule.item} className="border-t border-landing-ink/10 align-top">
                  <td className="px-5 py-4 text-sm text-landing-ink">{rule.item}</td>
                  <td className="px-5 py-4">
                    <span
                      className={
                        rule.showOnLanding
                          ? 'inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.1em] text-emerald-700'
                          : 'inline-flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.1em] text-rose-700'
                      }
                    >
                      {rule.showOnLanding ? <ShieldCheck className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                      {rule.showOnLanding ? 'Allowed' : 'Blocked'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-sm text-landing-muted">{rule.rule}</td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-landing-muted">
          Blocked keys include <code className="rounded bg-landing-surface-2 px-1.5 py-0.5">serialNumber</code>,{' '}
          <code className="rounded bg-landing-surface-2 px-1.5 py-0.5">batchId</code>,{' '}
          <code className="rounded bg-landing-surface-2 px-1.5 py-0.5">globalAssetId</code>,{' '}
          <code className="rounded bg-landing-surface-2 px-1.5 py-0.5">payload</code>,{' '}
          <code className="rounded bg-landing-surface-2 px-1.5 py-0.5">read_point</code>, and actor
          identifiers.
        </p>
      </div>
    </section>
  );
}
