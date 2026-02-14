import { useState } from 'react';
import { ExternalLink, Info, Link2, Lock, ShieldCheck, Users } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  defaultDppModelNodeId,
  dppModelNodes,
  type AccessTier,
  type AudienceMode,
  type DppModelNode,
} from '../content/dppModelContent';

const ACCESS_COPY: Record<AccessTier, { label: string; detail: string; icon: typeof ShieldCheck }> = {
  public: {
    label: 'Public',
    detail:
      'Visible in curated public-safe routes with confidentiality filtering and sensitive key blocking.',
    icon: ShieldCheck,
  },
  partner: {
    label: 'Partner',
    detail: 'Shared with approved partner exchanges and contract-based business policy controls.',
    icon: Users,
  },
  restricted: {
    label: 'Restricted',
    detail: 'Intended for protected routes and policy-gated operational or handover contexts.',
    icon: Lock,
  },
};

const ACCESS_BADGE_CLASS: Record<AccessTier, string> = {
  public: 'landing-access-badge-public',
  partner: 'landing-access-badge-partner',
  restricted: 'landing-access-badge-restricted',
};

function AccessBadge({ accessTier }: { accessTier: AccessTier }) {
  const copy = ACCESS_COPY[accessTier];
  const Icon = copy.icon;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
            ACCESS_BADGE_CLASS[accessTier],
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {copy.label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-[280px] border-landing-ink/15 bg-white text-xs text-landing-muted">
        {copy.detail}
      </TooltipContent>
    </Tooltip>
  );
}

function actionTarget(href: string): '_blank' | undefined {
  return href.startsWith('http') ? '_blank' : undefined;
}

function actionRel(href: string): string | undefined {
  return href.startsWith('http') ? 'noopener noreferrer' : undefined;
}

function SubmodelContent({ node, audienceMode }: { node: DppModelNode; audienceMode: AudienceMode }) {
  const templateValue = node.templateKey ?? 'recyclability-extension';

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold text-landing-ink">{node.label}</h3>
        <AccessBadge accessTier={node.accessTier} />
      </div>

      {node.idtaTemplateName ? (
        <p className="text-xs text-landing-muted">
          IDTA: <span className="font-semibold text-landing-ink">{node.idtaTemplateName}</span>
        </p>
      ) : (
        <p className="text-xs text-landing-muted">
          Lane: <span className="font-semibold text-landing-ink">Business-policy extension</span>
        </p>
      )}

      {audienceMode === 'general' ? (
        <p className="text-sm leading-relaxed text-landing-muted">{node.descriptionPublic}</p>
      ) : (
        <div className="space-y-2 text-sm leading-relaxed text-landing-muted">
          <p>{node.descriptionImpl}</p>
          <dl className="grid gap-1.5 rounded-xl border border-landing-ink/12 bg-landing-surface-1/70 p-2.5">
            <div className="flex items-center justify-between gap-2">
              <dt className="font-mono text-[11px] uppercase tracking-[0.08em] text-landing-muted">
                template_key
              </dt>
              <dd className="font-mono text-[11px] text-landing-ink">{templateValue}</dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="font-mono text-[11px] uppercase tracking-[0.08em] text-landing-muted">
                semantic_id
              </dt>
              <dd className="break-all text-right font-mono text-[11px] text-landing-ink">
                {node.semanticId ?? 'n/a'}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="font-mono text-[11px] uppercase tracking-[0.08em] text-landing-muted">
                api_hint
              </dt>
              <dd className="font-mono text-[11px] text-landing-ink">{node.apiHintPath}</dd>
            </div>
          </dl>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">Typical fields</p>
        <ul className="mt-1.5 flex flex-wrap gap-1.5">
          {node.typicalFields.slice(0, 4).map((field) => (
            <li
              key={field}
              className="rounded-full border border-landing-ink/12 bg-white px-2 py-0.5 text-[11px] font-medium text-landing-ink"
            >
              {field}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <a
          href={node.actions.demoHref}
          className="inline-flex items-center gap-1 rounded-full border border-landing-cyan/35 bg-landing-cyan/10 px-3 py-1 text-[11px] font-semibold text-landing-cyan transition-colors hover:border-landing-cyan/55 hover:bg-landing-cyan/15"
        >
          <Link2 className="h-3 w-3" />
          Demo
        </a>
        <a
          href={node.actions.evidenceHref}
          target={actionTarget(node.actions.evidenceHref)}
          rel={actionRel(node.actions.evidenceHref)}
          className="inline-flex items-center gap-1 rounded-full border border-landing-ink/18 bg-white px-3 py-1 text-[11px] font-semibold text-landing-ink transition-colors hover:border-landing-ink/35"
        >
          <ExternalLink className="h-3 w-3" />
          Spec
        </a>
        <a
          href={node.actions.apiHref}
          className="inline-flex items-center gap-1 rounded-full border border-landing-ink/18 bg-white px-3 py-1 text-[11px] font-semibold text-landing-ink transition-colors hover:border-landing-ink/35"
        >
          <Info className="h-3 w-3" />
          API
        </a>
      </div>
    </div>
  );
}

export default function DppCompactModel() {
  const [activeSubmodel, setActiveSubmodel] = useState<string>(defaultDppModelNodeId);
  const [audienceMode, setAudienceMode] = useState<AudienceMode>('general');

  return (
    <TooltipProvider delayDuration={180}>
      <section className="rounded-2xl border border-landing-ink/10 bg-gradient-to-b from-white to-landing-surface-1/65 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-lg font-semibold text-landing-ink">
            Asset Administration Shell (IEC 63278)
          </h2>
          <div className="inline-flex items-center gap-2 rounded-full border border-landing-ink/15 bg-white/90 px-3 py-1.5">
            <span
              className={cn(
                'text-xs font-semibold uppercase tracking-[0.08em]',
                audienceMode === 'general' ? 'text-landing-ink' : 'text-landing-muted',
              )}
            >
              General
            </span>
            <Switch
              checked={audienceMode === 'implementer'}
              onCheckedChange={(checked) => setAudienceMode(checked ? 'implementer' : 'general')}
              aria-label="Implementer mode"
            />
            <span
              className={cn(
                'text-xs font-semibold uppercase tracking-[0.08em]',
                audienceMode === 'implementer' ? 'text-landing-ink' : 'text-landing-muted',
              )}
            >
              Implementer
            </span>
          </div>
        </div>

        <Tabs value={activeSubmodel} onValueChange={setActiveSubmodel}>
          <div className="landing-aas-arch mt-4">
            <div className="landing-aas-arch-label">AAS &middot; DPP4.0</div>

            <div className="landing-aas-arch-body">
              <TabsList className="flex h-auto gap-1 bg-transparent p-0">
                {dppModelNodes.map((node) => (
                  <TabsTrigger
                    key={node.id}
                    value={node.id}
                    className={cn(
                      'landing-aas-card flex h-[120px] flex-1 flex-col items-center justify-center',
                      'rounded-lg border border-landing-ink/12 bg-white px-1 py-2',
                      'text-[10px] font-semibold text-landing-ink shadow-none',
                      'data-[state=active]:border-landing-cyan/60 data-[state=active]:bg-landing-cyan/8',
                      node.lane === 'extension' &&
                        'data-[state=active]:border-landing-amber/60 data-[state=active]:bg-landing-amber/8',
                    )}
                  >
                    {node.tabLabel}
                    <span
                      className={cn(
                        'mt-auto h-1.5 w-1.5 shrink-0 rounded-full',
                        node.lane === 'core' ? 'bg-landing-cyan/60' : 'bg-landing-amber/60',
                      )}
                    />
                  </TabsTrigger>
                ))}
              </TabsList>

              <div className="mt-2 flex items-center gap-3">
                <span className="inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-landing-muted">
                  <span className="h-1.5 w-1.5 rounded-full bg-landing-cyan/60" /> ESPR core
                </span>
                <span className="inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-landing-muted">
                  <span className="h-1.5 w-1.5 rounded-full bg-landing-amber/60" /> Extension
                </span>
              </div>
            </div>
          </div>

          <div className="mt-3 max-h-[260px] overflow-y-auto rounded-xl border border-landing-ink/12 bg-white/90 p-3.5">
            {dppModelNodes.map((node) => (
              <TabsContent key={node.id} value={node.id} className="mt-0">
                <SubmodelContent node={node} audienceMode={audienceMode} />
              </TabsContent>
            ))}
          </div>
        </Tabs>
      </section>
    </TooltipProvider>
  );
}
