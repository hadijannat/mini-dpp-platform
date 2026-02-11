export type RefreshRebuildTask = {
  templateKey: string;
};

export type RefreshRebuildFailure = {
  templateKey: string;
  reason: string;
};

export type RefreshRebuildSummary = {
  succeeded: string[];
  failed: RefreshRebuildFailure[];
  skipped: string[];
};

function stringifyError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  try {
    return JSON.stringify(error);
  } catch {
    return 'Unknown error';
  }
}

export function summarizeRefreshRebuildSettled(
  tasks: RefreshRebuildTask[],
  settled: PromiseSettledResult<unknown>[],
  skipped: Iterable<string>,
): RefreshRebuildSummary {
  const succeeded: string[] = [];
  const failed: RefreshRebuildFailure[] = [];

  settled.forEach((result, index) => {
    const task = tasks[index];
    if (!task) return;
    if (result.status === 'fulfilled') {
      succeeded.push(task.templateKey);
      return;
    }
    failed.push({
      templateKey: task.templateKey,
      reason: stringifyError(result.reason),
    });
  });

  succeeded.sort((a, b) => a.localeCompare(b));
  failed.sort((a, b) => a.templateKey.localeCompare(b.templateKey));
  const skippedList = Array.from(new Set(skipped)).sort((a, b) => a.localeCompare(b));

  return {
    succeeded,
    failed,
    skipped: skippedList,
  };
}

