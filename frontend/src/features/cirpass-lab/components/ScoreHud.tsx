interface ScoreHudProps {
  currentLevelLabel: string;
  elapsedSeconds: number;
  errors: number;
  hints: number;
  perfectLevels: number;
  scorePreview: number;
}

function formatSeconds(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60)
    .toString()
    .padStart(2, '0');
  const rem = (safe % 60).toString().padStart(2, '0');
  return `${minutes}:${rem}`;
}

export default function ScoreHud({
  currentLevelLabel,
  elapsedSeconds,
  errors,
  hints,
  perfectLevels,
  scorePreview,
}: ScoreHudProps) {
  return (
    <section className="rounded-3xl border border-landing-ink/15 bg-white/80 p-5 shadow-[0_24px_40px_-34px_rgba(17,37,49,0.65)]">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">Mission HUD</p>
      <h2 className="mt-2 font-display text-2xl font-semibold text-landing-ink">{currentLevelLabel}</h2>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl border border-landing-ink/12 bg-white px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Elapsed</p>
          <p className="mt-1 font-mono text-lg font-semibold text-landing-ink">
            {formatSeconds(elapsedSeconds)}
          </p>
        </div>
        <div className="rounded-xl border border-landing-ink/12 bg-white px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Score</p>
          <p className="mt-1 font-display text-lg font-semibold text-landing-ink">{scorePreview}</p>
        </div>
        <div className="rounded-xl border border-landing-ink/12 bg-white px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Errors</p>
          <p className="mt-1 font-display text-lg font-semibold text-rose-600">{errors}</p>
        </div>
        <div className="rounded-xl border border-landing-ink/12 bg-white px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.1em] text-landing-muted">Hints</p>
          <p className="mt-1 font-display text-lg font-semibold text-amber-600">{hints}</p>
        </div>
      </div>

      <p className="mt-3 text-sm text-landing-muted">Perfect levels: {perfectLevels} / 5</p>
    </section>
  );
}
