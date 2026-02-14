import type { CirpassLabStep } from '../../schema/storySchema';

interface ArtifactDiffInspectorProps {
  artifacts: CirpassLabStep['artifacts'] | undefined;
}

export default function ArtifactDiffInspector({ artifacts }: ArtifactDiffInspectorProps) {
  if (!artifacts?.before && !artifacts?.after) {
    return (
      <section className="rounded-2xl border border-landing-ink/12 bg-white/75 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">
          Artifact Inspector
        </p>
        <p className="mt-2 text-sm text-landing-muted">No before/after artifacts available.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-landing-ink/12 bg-white/75 p-4" data-testid="cirpass-artifact-inspector">
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">
        Artifact Inspector
      </p>
      {artifacts?.diff_hint && <p className="mt-2 text-sm text-landing-muted">{artifacts.diff_hint}</p>}
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-landing-muted">Before</p>
          <pre className="mt-1 max-h-44 overflow-auto rounded-lg bg-slate-950 p-2 text-xs text-rose-200">
            {JSON.stringify(artifacts.before ?? {}, null, 2)}
          </pre>
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-landing-muted">After</p>
          <pre className="mt-1 max-h-44 overflow-auto rounded-lg bg-slate-950 p-2 text-xs text-emerald-200">
            {JSON.stringify(artifacts.after ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </section>
  );
}
