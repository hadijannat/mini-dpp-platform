import { assign, createMachine } from 'xstate';

export type CirpassLevelKey = 'create' | 'access' | 'update' | 'transfer' | 'deactivate';

export interface CirpassMachineStep {
  id: string;
  level: CirpassLevelKey;
}

export interface CirpassStepStats {
  errors: number;
  hints: number;
  completed: boolean;
  level: CirpassLevelKey;
}

export interface CirpassLevelStats {
  errors: number;
  hints: number;
  completed: boolean;
}

export interface CirpassMachineContext {
  steps: CirpassMachineStep[];
  currentStepIndex: number;
  errors: number;
  hints: number;
  perfectLevels: number;
  lastMessage: string;
  levelStats: Record<CirpassLevelKey, CirpassLevelStats>;
  stepStats: Record<string, CirpassStepStats>;
}

export type CirpassMachineEvent =
  | {
      type: 'INIT';
      steps: CirpassMachineStep[];
      startStepId?: string | null;
      completedLevels?: CirpassLevelKey[];
    }
  | {
      type: 'SUBMIT_STEP';
      stepId: string;
      level: CirpassLevelKey;
      isValid: boolean;
    }
  | {
      type: 'HINT_USED';
      stepId: string;
      level: CirpassLevelKey;
    }
  | { type: 'RESET' };

function emptyLevelStats(): Record<CirpassLevelKey, CirpassLevelStats> {
  return {
    create: { errors: 0, hints: 0, completed: false },
    access: { errors: 0, hints: 0, completed: false },
    update: { errors: 0, hints: 0, completed: false },
    transfer: { errors: 0, hints: 0, completed: false },
    deactivate: { errors: 0, hints: 0, completed: false },
  };
}

function buildStepStats(
  steps: CirpassMachineStep[],
  currentStepIndex: number,
): Record<string, CirpassStepStats> {
  const stats: Record<string, CirpassStepStats> = {};
  for (const [index, step] of steps.entries()) {
    stats[step.id] = {
      errors: 0,
      hints: 0,
      completed: index < currentStepIndex,
      level: step.level,
    };
  }
  return stats;
}

function getExpectedStep(context: CirpassMachineContext): CirpassMachineStep | null {
  if (context.steps.length === 0) {
    return null;
  }
  return context.steps[context.currentStepIndex] ?? context.steps[context.steps.length - 1] ?? null;
}

function deriveStartIndex(steps: CirpassMachineStep[], startStepId: string | null | undefined): number {
  if (steps.length === 0) {
    return 0;
  }
  if (!startStepId) {
    return 0;
  }
  const index = steps.findIndex((step) => step.id === startStepId);
  return index >= 0 ? index : 0;
}

function buildLevelStatsFromCompletedLevels(
  completedLevels: CirpassLevelKey[] | undefined,
): Record<CirpassLevelKey, CirpassLevelStats> {
  const levelStats = emptyLevelStats();
  if (!completedLevels) {
    return levelStats;
  }
  for (const level of completedLevels) {
    if (level in levelStats) {
      levelStats[level].completed = true;
    }
  }
  return levelStats;
}

const initializeContext = assign(({ event }) => {
  if (event.type !== 'INIT') {
    return {};
  }

  const steps = event.steps;
  const startIndex = deriveStartIndex(steps, event.startStepId);
  const levelStats = buildLevelStatsFromCompletedLevels(event.completedLevels);

  let perfectLevels = 0;
  for (const level of Object.keys(levelStats) as CirpassLevelKey[]) {
    if (levelStats[level].completed && levelStats[level].errors === 0 && levelStats[level].hints === 0) {
      perfectLevels += 1;
    }
  }

  return {
    steps,
    currentStepIndex: startIndex,
    errors: 0,
    hints: 0,
    perfectLevels,
    lastMessage: '',
    levelStats,
    stepStats: buildStepStats(steps, startIndex),
  };
});

const resetRun = assign(({ context }) => {
  const levelStats = emptyLevelStats();
  return {
    ...context,
    currentStepIndex: 0,
    errors: 0,
    hints: 0,
    perfectLevels: 0,
    lastMessage: '',
    levelStats,
    stepStats: buildStepStats(context.steps, 0),
  };
});

const registerHint = assign(({ context, event }) => {
  if (event.type !== 'HINT_USED') {
    return {};
  }

  const stateContext = context as CirpassMachineContext;
  const expected = getExpectedStep(stateContext);
  if (!expected || expected.id !== event.stepId || expected.level !== event.level) {
    return {};
  }
  const levelKey = event.level as CirpassLevelKey;

  const currentStepStats = stateContext.stepStats[event.stepId] ?? {
    errors: 0,
    hints: 0,
    completed: false,
    level: levelKey,
  };
  return {
    hints: stateContext.hints + 1,
    levelStats: {
      ...stateContext.levelStats,
      [levelKey]: {
        ...stateContext.levelStats[levelKey],
        hints: stateContext.levelStats[levelKey].hints + 1,
      },
    },
    stepStats: {
      ...stateContext.stepStats,
      [event.stepId]: {
        ...currentStepStats,
        hints: currentStepStats.hints + 1,
      },
    },
    lastMessage: `Hint used for ${event.level.toUpperCase()}.`,
  };
});

const registerSubmissionError = assign(({ context, event }) => {
  if (event.type !== 'SUBMIT_STEP') {
    return {};
  }

  const stateContext = context as CirpassMachineContext;
  const expected = getExpectedStep(stateContext);
  const level = (expected?.level ?? event.level) as CirpassLevelKey;
  const stepId = expected?.id ?? event.stepId;
  const currentStepStats = stateContext.stepStats[stepId] ?? {
    errors: 0,
    hints: 0,
    completed: false,
    level,
  };

  const orderMessage =
    expected && (event.stepId !== expected.id || event.level !== expected.level)
      ? `Complete ${expected.level.toUpperCase()} before attempting this step.`
      : `Validation failed for ${event.level.toUpperCase()}.`;

  return {
    errors: stateContext.errors + 1,
    levelStats: {
      ...stateContext.levelStats,
      [level]: {
        ...stateContext.levelStats[level],
        errors: stateContext.levelStats[level].errors + 1,
      },
    },
    stepStats: {
      ...stateContext.stepStats,
      [stepId]: {
        ...currentStepStats,
        errors: currentStepStats.errors + 1,
      },
    },
    lastMessage: orderMessage,
  };
});

const completeStep = assign(({ context, event }) => {
  if (event.type !== 'SUBMIT_STEP') {
    return {};
  }
  const stateContext = context as CirpassMachineContext;
  const expected = getExpectedStep(stateContext);
  if (!expected) {
    return {};
  }

  const stepStats = { ...stateContext.stepStats };
  stepStats[expected.id] = {
    ...(stepStats[expected.id] ?? {
      errors: 0,
      hints: 0,
      level: expected.level,
      completed: false,
    }),
    completed: true,
  };

  const levelStats = { ...stateContext.levelStats };
  let perfectLevels = stateContext.perfectLevels;
  const nextIndex = stateContext.currentStepIndex + 1;
  const isLastStepForLevel = !stateContext.steps
    .slice(nextIndex)
    .some((step: CirpassMachineStep) => step.level === expected.level);
  if (isLastStepForLevel && !levelStats[expected.level].completed) {
    levelStats[expected.level] = {
      ...levelStats[expected.level],
      completed: true,
    };
    if (levelStats[expected.level].errors === 0 && levelStats[expected.level].hints === 0) {
      perfectLevels += 1;
    }
  }

  return {
    currentStepIndex:
      nextIndex < stateContext.steps.length ? nextIndex : Math.max(stateContext.steps.length - 1, 0),
    perfectLevels,
    levelStats,
    stepStats,
    lastMessage: `${expected.level.toUpperCase()} completed successfully.`,
  };
});

export const cirpassMachine = createMachine(
  {
    types: {} as {
      context: CirpassMachineContext;
      events: CirpassMachineEvent;
    },
    id: 'cirpassStepRunner',
    initial: 'idle',
    context: {
      steps: [],
      currentStepIndex: 0,
      errors: 0,
      hints: 0,
      perfectLevels: 0,
      lastMessage: '',
      levelStats: emptyLevelStats(),
      stepStats: {},
    },
    states: {
      idle: {
        on: {
          INIT: {
            target: 'running',
            actions: 'initializeContext',
          },
        },
      },
      running: {
        on: {
          INIT: {
            actions: 'initializeContext',
          },
          RESET: {
            actions: 'resetRun',
          },
          HINT_USED: {
            actions: 'registerHint',
          },
          SUBMIT_STEP: [
            {
              guard: 'isStepOrderViolation',
              actions: 'registerSubmissionError',
            },
            {
              guard: 'isValidFinalSubmission',
              target: 'completed',
              actions: 'completeStep',
            },
            {
              guard: 'isValidExpectedSubmission',
              actions: 'completeStep',
            },
            {
              guard: 'isExpectedStepSubmission',
              actions: 'registerSubmissionError',
            },
          ],
        },
      },
      completed: {
        on: {
          INIT: {
            target: 'running',
            actions: 'initializeContext',
          },
          RESET: {
            target: 'running',
            actions: 'resetRun',
          },
        },
      },
    },
  },
  {
    guards: {
      isStepOrderViolation: ({ context, event }) => {
        if (event.type !== 'SUBMIT_STEP') {
          return false;
        }
        const expected = getExpectedStep(context);
        if (!expected) {
          return true;
        }
        return expected.id !== event.stepId || expected.level !== event.level;
      },
      isExpectedStepSubmission: ({ context, event }) => {
        if (event.type !== 'SUBMIT_STEP') {
          return false;
        }
        const expected = getExpectedStep(context);
        if (!expected) {
          return false;
        }
        return expected.id === event.stepId && expected.level === event.level;
      },
      isValidExpectedSubmission: ({ context, event }) => {
        if (event.type !== 'SUBMIT_STEP' || !event.isValid) {
          return false;
        }
        const expected = getExpectedStep(context);
        if (!expected) {
          return false;
        }
        const isExpected = expected.id === event.stepId && expected.level === event.level;
        const isFinal = context.currentStepIndex >= context.steps.length - 1;
        return isExpected && !isFinal;
      },
      isValidFinalSubmission: ({ context, event }) => {
        if (event.type !== 'SUBMIT_STEP' || !event.isValid) {
          return false;
        }
        const expected = getExpectedStep(context);
        if (!expected) {
          return false;
        }
        const isExpected = expected.id === event.stepId && expected.level === event.level;
        const isFinal = context.currentStepIndex >= context.steps.length - 1;
        return isExpected && isFinal;
      },
    },
    actions: {
      initializeContext: initializeContext as any,
      resetRun: resetRun as any,
      registerHint: registerHint as any,
      registerSubmissionError: registerSubmissionError as any,
      completeStep: completeStep as any,
    },
  },
);
