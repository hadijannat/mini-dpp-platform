import { useAuth } from 'react-oidc-context';
import { Fingerprint, ExternalLink } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

const standardLinks = [
  {
    label: 'EU ESPR Regulation',
    href: 'https://commission.europa.eu/energy-climate-change-environment/standards-tools-and-labels/products-labelling-rules-and-requirements/sustainable-products/ecodesign-sustainable-products-regulation_en',
  },
  {
    label: 'IDTA Specifications',
    href: 'https://industrialdigitaltwin.org/en/content-hub/submodels',
  },
  {
    label: 'Asset Administration Shell',
    href: 'https://industrialdigitaltwin.org/en/content-hub/aasspecifications',
  },
  {
    label: 'Catena-X',
    href: 'https://catena-x.net/en/',
  },
];

const regulationLinks = [
  {
    label: 'ESPR Full Text (EU 2024/1781)',
    href: 'https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng',
  },
  {
    label: 'Battery Regulation (EU 2023/1542)',
    href: 'https://eur-lex.europa.eu/EN/legal-content/summary/sustainability-rules-for-batteries-and-waste-batteries.html',
  },
  {
    label: 'ESPR Working Plan 2025–2030',
    href: 'https://green-forum.ec.europa.eu/implementing-ecodesign-sustainable-products-regulation_en',
  },
];

export default function LandingFooter() {
  const auth = useAuth();

  return (
    <footer className="border-t bg-card py-12">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 font-semibold">
              <Fingerprint className="h-5 w-5 text-primary" />
              DPP Platform
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Open-source Digital Product Passport management based on IDTA DPP4.0
              and the Asset Administration Shell standard.
            </p>
          </div>

          {/* Standards */}
          <div>
            <h3 className="mb-3 text-sm font-semibold">Standards</h3>
            <ul className="space-y-2">
              {standardLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Regulations */}
          <div>
            <h3 className="mb-3 text-sm font-semibold">EU Regulations</h3>
            <ul className="space-y-2">
              {regulationLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Platform */}
          <div>
            <h3 className="mb-3 text-sm font-semibold">Platform</h3>
            <ul className="space-y-2">
              <li>
                <button
                  onClick={() =>
                    auth.isAuthenticated
                      ? window.location.assign('/console')
                      : auth.signinRedirect()
                  }
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {auth.isAuthenticated ? 'Dashboard' : 'Sign in'}
                </button>
              </li>
              <li>
                <a
                  href="/api/v1/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  API Documentation
                  <ExternalLink className="h-3 w-3" />
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/hadijannat/mini-dpp-platform"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  GitHub
                  <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            </ul>
          </div>
        </div>

        <Separator className="my-8" />

        <p className="text-center text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} Mini DPP Platform. Built with IDTA
          DPP4.0 and Asset Administration Shell standards.
          {import.meta.env.VITE_COMMIT_SHA && (
            <span className="ml-2 font-mono text-xs text-muted-foreground/60">
              &middot; {import.meta.env.VITE_COMMIT_SHA.slice(0, 7)}
            </span>
          )}
        </p>
      </div>
    </footer>
  );
}
