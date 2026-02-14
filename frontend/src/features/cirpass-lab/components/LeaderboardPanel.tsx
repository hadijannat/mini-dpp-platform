import { useState } from 'react';
import type {
  CirpassLeaderboardEntry,
  CirpassLeaderboardSubmitResponse,
} from '@/api/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface LeaderboardPanelProps {
  completed: boolean;
  score: number;
  elapsedSeconds: number;
  entries: CirpassLeaderboardEntry[];
  submitting: boolean;
  submitResult: CirpassLeaderboardSubmitResponse | null;
  submitError: string | null;
  onSubmit: (nickname: string) => void;
}

export default function LeaderboardPanel({
  completed,
  score,
  elapsedSeconds,
  entries,
  submitting,
  submitResult,
  submitError,
  onSubmit,
}: LeaderboardPanelProps) {
  const [nickname, setNickname] = useState('');

  return (
    <section className="rounded-3xl border border-landing-ink/15 bg-white/85 p-5 shadow-[0_24px_40px_-34px_rgba(17,37,49,0.65)]">
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">Leaderboard</p>
      <h3 className="mt-2 font-display text-2xl font-semibold text-landing-ink">Public Architects</h3>

      {completed ? (
        <div className="mt-4 space-y-3 rounded-2xl border border-emerald-500/30 bg-emerald-50 px-4 py-3">
          <p className="text-sm text-emerald-900">
            Mission complete. Score <strong>{score}</strong> in {elapsedSeconds}s.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              placeholder="nickname_123"
              maxLength={20}
              data-testid="cirpass-leaderboard-nickname"
            />
            <Button
              type="button"
              disabled={submitting || nickname.trim().length < 3}
              onClick={() => onSubmit(nickname.trim())}
              data-testid="cirpass-leaderboard-submit"
            >
              {submitting ? 'Submitting...' : 'Submit Score'}
            </Button>
          </div>
          {submitResult && submitResult.accepted && (
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700" data-testid="cirpass-submit-success">
              Saved. Current rank #{submitResult.rank ?? '-'}.
            </p>
          )}
          {submitError && (
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-rose-600" data-testid="cirpass-submit-error">
              {submitError}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-4 text-sm text-landing-muted">
          Complete all five levels to submit your score.
        </p>
      )}

      <ol className="mt-5 space-y-2" data-testid="cirpass-leaderboard-list">
        {entries.length === 0 && <li className="text-sm text-landing-muted">No submissions yet.</li>}
        {entries.map((entry) => (
          <li
            key={`${entry.rank}-${entry.nickname}-${entry.created_at}`}
            className="flex items-center justify-between rounded-xl border border-landing-ink/12 bg-white px-3 py-2 text-sm"
          >
            <span className="font-semibold text-landing-ink">#{entry.rank} {entry.nickname}</span>
            <span className="font-mono text-landing-muted">
              {entry.score} pts · {entry.completion_seconds}s
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
