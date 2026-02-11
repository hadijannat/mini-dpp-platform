import { describe, expect, it } from 'vitest';

import {
  summarizeRefreshRebuildSettled,
  type RefreshRebuildTask,
} from '../utils/refreshRebuildSummary';

describe('summarizeRefreshRebuildSettled', () => {
  it('aggregates mixed successes and failures deterministically', () => {
    const tasks: RefreshRebuildTask[] = [
      { templateKey: 'carbon-footprint' },
      { templateKey: 'digital-nameplate' },
    ];
    const settled: PromiseSettledResult<unknown>[] = [
      { status: 'rejected', reason: new Error('bad payload') },
      { status: 'fulfilled', value: { ok: true } },
    ];

    const summary = summarizeRefreshRebuildSettled(
      tasks,
      settled,
      ['unknown-submodel', 'unknown-submodel'],
    );

    expect(summary.succeeded).toEqual(['digital-nameplate']);
    expect(summary.failed).toEqual([
      { templateKey: 'carbon-footprint', reason: 'bad payload' },
    ]);
    expect(summary.skipped).toEqual(['unknown-submodel']);
  });

  it('handles non-Error rejection reasons', () => {
    const tasks: RefreshRebuildTask[] = [{ templateKey: 'technical-data' }];
    const settled: PromiseSettledResult<unknown>[] = [{ status: 'rejected', reason: 42 }];

    const summary = summarizeRefreshRebuildSettled(tasks, settled, []);

    expect(summary.failed).toEqual([{ templateKey: 'technical-data', reason: '42' }]);
  });
});

