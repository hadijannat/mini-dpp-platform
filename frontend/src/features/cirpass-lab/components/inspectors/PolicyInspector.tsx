import type { CirpassLabStep } from '../../schema/storySchema';

interface PolicyInspectorProps {
  policy: CirpassLabStep['policy'] | undefined;
  variant: 'happy' | 'unauthorized' | 'not_found';
}

const VARIANT_EXPLANATIONS: Record<'happy' | 'unauthorized' | 'not_found', string> = {
  happy: 'Happy path: policy and data-flow checks are expected to pass.',
  unauthorized: 'Unauthorized path: expect policy denial with restricted data withheld.',
  not_found: 'Resolver miss path: expect not-found handling with safe failure messaging.',
};

export default function PolicyInspector({ policy, variant }: PolicyInspectorProps) {
  return (
    <section className="rounded-2xl border border-landing-ink/12 bg-white/75 p-4" data-testid="cirpass-policy-inspector">
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">
        Policy Inspector
      </p>
      <p className="mt-2 text-sm text-landing-muted">{VARIANT_EXPLANATIONS[variant]}</p>

      {policy ? (
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-lg border border-landing-ink/10 bg-white p-2">
            <dt className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Required role</dt>
            <dd className="mt-1 font-medium text-landing-ink">{policy.required_role ?? 'n/a'}</dd>
          </div>
          <div className="rounded-lg border border-landing-ink/10 bg-white p-2">
            <dt className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">OPA policy</dt>
            <dd className="mt-1 font-medium text-landing-ink">{policy.opa_policy ?? 'n/a'}</dd>
          </div>
          <div className="rounded-lg border border-landing-ink/10 bg-white p-2">
            <dt className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Expected decision</dt>
            <dd className="mt-1 font-medium text-landing-ink">{policy.expected_decision ?? 'n/a'}</dd>
          </div>
          <div className="rounded-lg border border-landing-ink/10 bg-white p-2">
            <dt className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Notes</dt>
            <dd className="mt-1 text-landing-muted">{policy.note ?? 'n/a'}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-3 text-sm text-landing-muted">No policy metadata for this step.</p>
      )}
    </section>
  );
}
