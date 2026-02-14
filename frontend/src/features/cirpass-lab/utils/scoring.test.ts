import { describe, expect, it } from 'vitest';
import { computeLoopForgeScore } from './scoring';

describe('computeLoopForgeScore', () => {
  it('uses deterministic formula and clamps to zero', () => {
    expect(
      computeLoopForgeScore({
        errors: 2,
        hints: 1,
        totalSeconds: 123,
        perfectLevels: 3,
      }),
    ).toBe(1049);

    expect(
      computeLoopForgeScore({
        errors: 999,
        hints: 999,
        totalSeconds: 9999,
        perfectLevels: 0,
      }),
    ).toBe(0);
  });
});
