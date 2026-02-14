export interface ScoreInput {
  errors: number;
  hints: number;
  totalSeconds: number;
  perfectLevels: number;
}

export function computeLoopForgeScore(input: ScoreInput): number {
  const value =
    1000 -
    input.errors * 25 -
    input.hints * 40 -
    Math.floor(Math.max(0, input.totalSeconds) / 3) +
    input.perfectLevels * 60;

  return Math.max(0, value);
}
