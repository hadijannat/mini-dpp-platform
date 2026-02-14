import type { CirpassLevelKey } from '../machines/cirpassMachine';

const LEVEL_ORDER: CirpassLevelKey[] = ['create', 'access', 'update', 'transfer', 'deactivate'];

const LEVEL_COLORS: Record<CirpassLevelKey, string> = {
  create: 'from-cyan-500/35 to-blue-500/20',
  access: 'from-emerald-500/35 to-cyan-500/20',
  update: 'from-amber-500/35 to-orange-500/20',
  transfer: 'from-sky-500/30 to-indigo-500/20',
  deactivate: 'from-lime-500/35 to-emerald-500/20',
};

interface JoyfulLayerProps {
  currentLevel: CirpassLevelKey;
  completedLevels: Record<CirpassLevelKey, boolean>;
  latestMessage: string;
}

export default function JoyfulLayer({
  currentLevel,
  completedLevels,
  latestMessage,
}: JoyfulLayerProps) {
  return (
    <div className="relative h-full p-5">
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(680px 360px at 15% 8%, rgba(36, 178, 222, 0.22), transparent 65%), radial-gradient(720px 400px at 90% 95%, rgba(250, 204, 21, 0.15), transparent 68%)',
        }}
      />

      <div className="relative z-10 grid h-full gap-4 md:grid-cols-2">
        {LEVEL_ORDER.map((level) => {
          const isCurrent = currentLevel === level;
          const isComplete = completedLevels[level];
          return (
            <article
              key={level}
              className={`rounded-2xl border p-4 transition-all ${
                isCurrent
                  ? 'border-cyan-300/70 bg-white/15 shadow-[0_16px_30px_-18px_rgba(34,211,238,0.65)]'
                  : 'border-white/10 bg-white/5'
              }`}
              data-testid={`cirpass-joyful-${level}`}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-200/80">
                {level}
              </p>
              <div className={`mt-3 h-2 rounded-full bg-gradient-to-r ${LEVEL_COLORS[level]}`} />
              <p className="mt-4 text-sm leading-relaxed text-slate-100">
                {isComplete
                  ? 'Lifecycle objective resolved. Passport flow remains consistent.'
                  : 'Pending interaction. Complete this mission to unlock the next stage.'}
              </p>
              <p className="mt-3 text-xs font-medium text-slate-300/90">
                Status: {isComplete ? 'Complete' : isCurrent ? 'In Progress' : 'Locked'}
              </p>
            </article>
          );
        })}
      </div>

      <div className="relative z-10 mt-4 rounded-xl border border-white/10 bg-black/35 px-4 py-3 text-sm text-slate-200">
        {latestMessage || 'Start with CREATE and complete each stage in sequence.'}
      </div>
    </div>
  );
}
