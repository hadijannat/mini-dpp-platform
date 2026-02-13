import { Fingerprint, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { landingContent } from '../content/landingContent';

export default function LandingFooter() {
  return (
    <footer className="border-t border-landing-ink/10 bg-landing-surface-1 px-4 py-14 sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-[1.2fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-landing-cyan/30 bg-landing-cyan/10 p-1.5 text-landing-cyan">
              <Fingerprint className="h-4 w-4" />
            </span>
            <span className="font-display text-xl font-semibold text-landing-ink">DPP Platform</span>
          </div>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-landing-muted">
            Open-source reference implementation for standards-linked Digital Product Passport
            workflows with conservative claims and evidence-first messaging.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="outline" size="sm" className="rounded-full px-4" asChild>
              <a href="#sample-passport">Open demo passport</a>
            </Button>
            <Button size="sm" className="rounded-full px-4" asChild>
              <a href="/login">Sign in</a>
            </Button>
          </div>
        </div>

        <div>
          <h3 className="font-display text-lg font-semibold text-landing-ink">Developers</h3>
          <ul className="mt-3 space-y-2">
            {landingContent.footer.developerLinks.map((link) => (
              <li key={link.label}>
                <a
                  href={link.href}
                  target={link.external ? '_blank' : undefined}
                  rel={link.external ? 'noopener noreferrer' : undefined}
                  className="inline-flex items-center gap-1.5 text-sm text-landing-muted transition-colors hover:text-landing-ink"
                >
                  {link.label}
                  {link.external && <ExternalLink className="h-3.5 w-3.5" />}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="font-display text-lg font-semibold text-landing-ink">Policy & Evidence</h3>
          <ul className="mt-3 space-y-2">
            {landingContent.footer.policyLinks.map((link) => (
              <li key={link.label}>
                <a
                  href={link.href}
                  target={link.external ? '_blank' : undefined}
                  rel={link.external ? 'noopener noreferrer' : undefined}
                  className="inline-flex items-center gap-1.5 text-sm text-landing-muted transition-colors hover:text-landing-ink"
                >
                  {link.label}
                  {link.external && <ExternalLink className="h-3.5 w-3.5" />}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mx-auto mt-10 flex max-w-6xl flex-col gap-2 border-t border-landing-ink/10 pt-6 text-xs text-landing-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          © {new Date().getFullYear()} DPP Platform. Public landing pages are aggregate-only by
          policy.
        </p>
        {import.meta.env.VITE_COMMIT_SHA && (
          <p className="font-mono text-[11px] text-landing-muted/80">
            build {import.meta.env.VITE_COMMIT_SHA.slice(0, 7)}
          </p>
        )}
      </div>
    </footer>
  );
}
