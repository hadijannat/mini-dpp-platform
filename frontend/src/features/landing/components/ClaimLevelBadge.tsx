import type { ClaimLevel } from '../content/landingContent';

const levelStyles: Record<ClaimLevel, string> = {
  implements:
    'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  aligned: 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  roadmap: 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300',
};

const levelLabel: Record<ClaimLevel, string> = {
  implements: 'Implements',
  aligned: 'Aligned',
  roadmap: 'Roadmap',
};

interface ClaimLevelBadgeProps {
  level: ClaimLevel;
}

export default function ClaimLevelBadge({ level }: ClaimLevelBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.11em] ${levelStyles[level]}`}
      data-testid={`claim-level-${level}`}
    >
      {levelLabel[level]}
    </span>
  );
}
