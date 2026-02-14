/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import { assign, createMachine } from 'xstate';

export type CirpassLevelKey = 'create' | 'access' | 'update' | 'transfer' | 'deactivate';

export interface CreateLevelPayload {
  identifier: string;
  materialComposition: string;
  carbonFootprint: number | null;
}

export interface AccessLevelPayload {
  consumerViewEnabled: boolean;
  authorityCredentialValidated: boolean;
  restrictedFieldsHiddenFromConsumer: boolean;
}

export interface UpdateLevelPayload {
  previousHash: string;
  newEventHash: string;
  repairEvent: string;
}

export interface TransferLevelPayload {
  fromActor: string;
  toActor: string;
  confidentialityMaintained: boolean;
}

export interface DeactivateLevelPayload {
  lifecycleStatus: string;
  recoveredMaterials: string;
  spawnNextPassport: boolean;
}

export interface CirpassMachineContext {
  errors: number;
  hints: number;
  perfectLevels: number;
  lastMessage: string;
  levelStats: Record<
    CirpassLevelKey,
    {
      errors: number;
      hints: number;
      completed: boolean;
    }
  >;
}

export type CirpassMachineEvent =
  | {
      type: 'SUBMIT_LEVEL';
      level: CirpassLevelKey;
      data:
        | CreateLevelPayload
        | AccessLevelPayload
        | UpdateLevelPayload
        | TransferLevelPayload
        | DeactivateLevelPayload;
    }
  | { type: 'HINT_USED'; level: CirpassLevelKey }
  | { type: 'RESET' };

function emptyStats() {
  return {
    create: { errors: 0, hints: 0, completed: false },
    access: { errors: 0, hints: 0, completed: false },
    update: { errors: 0, hints: 0, completed: false },
    transfer: { errors: 0, hints: 0, completed: false },
    deactivate: { errors: 0, hints: 0, completed: false },
  };
}

function validateCreate(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const source = payload as Record<string, unknown>;
  const identifier = typeof source.identifier === 'string' ? source.identifier.trim() : '';
  const material = typeof source.materialComposition === 'string' ? source.materialComposition.trim() : '';
  const carbon = source.carbonFootprint;
  return identifier.length > 0 && material.length > 0 && typeof carbon === 'number' && carbon > 0;
}

function validateAccess(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const source = payload as Record<string, unknown>;
  return (
    source.consumerViewEnabled === true &&
    source.authorityCredentialValidated === true &&
    source.restrictedFieldsHiddenFromConsumer === true
  );
}

function validateUpdate(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const source = payload as Record<string, unknown>;
  const previousHash = typeof source.previousHash === 'string' ? source.previousHash.trim() : '';
  const newEventHash = typeof source.newEventHash === 'string' ? source.newEventHash.trim() : '';
  const repairEvent = typeof source.repairEvent === 'string' ? source.repairEvent.trim() : '';
  return previousHash.length > 6 && newEventHash.length > 6 && previousHash !== newEventHash && repairEvent.length > 0;
}

function validateTransfer(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const source = payload as Record<string, unknown>;
  const fromActor = typeof source.fromActor === 'string' ? source.fromActor.trim() : '';
  const toActor = typeof source.toActor === 'string' ? source.toActor.trim() : '';
  return fromActor.length > 0 && toActor.length > 0 && fromActor !== toActor && source.confidentialityMaintained === true;
}

function validateDeactivate(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const source = payload as Record<string, unknown>;
  const status = typeof source.lifecycleStatus === 'string' ? source.lifecycleStatus.trim() : '';
  const recovered = typeof source.recoveredMaterials === 'string' ? source.recoveredMaterials.trim() : '';
  return status === 'end_of_life' && recovered.length > 0 && source.spawnNextPassport === true;
}

const registerHint = assign(({ context, event }: { context: CirpassMachineContext; event: any }) => {
  if (event.type !== 'HINT_USED') {
    return {};
  }
  return {
    hints: context.hints + 1,
    levelStats: {
      ...context.levelStats,
      [event.level]: {
        ...context.levelStats[event.level],
        hints: context.levelStats[event.level].hints + 1,
      },
    },
    lastMessage: `Hint used for ${event.level.toUpperCase()}.`,
  };
});

const registerError = assign(({ context, event }: { context: CirpassMachineContext; event: any }) => {
  if (event.type !== 'SUBMIT_LEVEL') {
    return {};
  }
  return {
    errors: context.errors + 1,
    levelStats: {
      ...context.levelStats,
      [event.level]: {
        ...context.levelStats[event.level],
        errors: context.levelStats[event.level].errors + 1,
      },
    },
    lastMessage: `Validation failed for ${event.level.toUpperCase()}.`,
  };
});

const completeLevel = assign(({ context, event }: { context: CirpassMachineContext; event: any }) => {
  if (event.type !== 'SUBMIT_LEVEL') {
    return {};
  }

  const stats = context.levelStats[event.level];
  const isPerfect = !stats.completed && stats.errors === 0 && stats.hints === 0;

  return {
    perfectLevels: isPerfect ? context.perfectLevels + 1 : context.perfectLevels,
    levelStats: {
      ...context.levelStats,
      [event.level]: {
        ...context.levelStats[event.level],
        completed: true,
      },
    },
    lastMessage: `${event.level.toUpperCase()} completed successfully.`,
  };
});

const resetContext = assign((): CirpassMachineContext => ({
  errors: 0,
  hints: 0,
  perfectLevels: 0,
  lastMessage: '',
  levelStats: emptyStats(),
}));

export const cirpassMachine = createMachine(
  {
    id: 'cirpassLifecycle',
    initial: 'create',
    context: {
      errors: 0,
      hints: 0,
      perfectLevels: 0,
      lastMessage: '',
      levelStats: emptyStats(),
    } as CirpassMachineContext,
    on: {
      HINT_USED: {
        actions: 'registerHint',
      },
      RESET: {
        target: '.create',
        actions: 'resetContext',
      },
    },
    states: {
      create: {
        on: {
          SUBMIT_LEVEL: [
            {
              guard: ({ event }) =>
                event.type === 'SUBMIT_LEVEL' &&
                event.level === 'create' &&
                validateCreate(event.data),
              target: 'access',
              actions: 'completeLevel',
            },
            {
              guard: ({ event }) => event.type === 'SUBMIT_LEVEL' && event.level === 'create',
              actions: 'registerError',
            },
          ],
        },
      },
      access: {
        on: {
          SUBMIT_LEVEL: [
            {
              guard: ({ event }) =>
                event.type === 'SUBMIT_LEVEL' &&
                event.level === 'access' &&
                validateAccess(event.data),
              target: 'update',
              actions: 'completeLevel',
            },
            {
              guard: ({ event }) => event.type === 'SUBMIT_LEVEL' && event.level === 'access',
              actions: 'registerError',
            },
          ],
        },
      },
      update: {
        on: {
          SUBMIT_LEVEL: [
            {
              guard: ({ event }) =>
                event.type === 'SUBMIT_LEVEL' &&
                event.level === 'update' &&
                validateUpdate(event.data),
              target: 'transfer',
              actions: 'completeLevel',
            },
            {
              guard: ({ event }) => event.type === 'SUBMIT_LEVEL' && event.level === 'update',
              actions: 'registerError',
            },
          ],
        },
      },
      transfer: {
        on: {
          SUBMIT_LEVEL: [
            {
              guard: ({ event }) =>
                event.type === 'SUBMIT_LEVEL' &&
                event.level === 'transfer' &&
                validateTransfer(event.data),
              target: 'deactivate',
              actions: 'completeLevel',
            },
            {
              guard: ({ event }) => event.type === 'SUBMIT_LEVEL' && event.level === 'transfer',
              actions: 'registerError',
            },
          ],
        },
      },
      deactivate: {
        on: {
          SUBMIT_LEVEL: [
            {
              guard: ({ event }) =>
                event.type === 'SUBMIT_LEVEL' &&
                event.level === 'deactivate' &&
                validateDeactivate(event.data),
              target: 'completed',
              actions: 'completeLevel',
            },
            {
              guard: ({ event }) =>
                event.type === 'SUBMIT_LEVEL' && event.level === 'deactivate',
              actions: 'registerError',
            },
          ],
        },
      },
      completed: {
        type: 'final',
      },
    },
  },
  {
    actions: {
      registerHint,
      registerError,
      completeLevel,
      resetContext,
    },
  },
);
