import { describe, expect, it } from 'vitest';
import { createActor } from 'xstate';
import { cirpassMachine } from './cirpassMachine';

describe('cirpassMachine', () => {
  it('blocks skipping and progresses in ordered valid submissions', () => {
    const actor = createActor(cirpassMachine);
    actor.start();

    actor.send({
      type: 'INIT',
      steps: [
        { id: 'create-passport', level: 'create' },
        { id: 'access-routing', level: 'access' },
      ],
    });

    actor.send({
      type: 'SUBMIT_STEP',
      stepId: 'access-routing',
      level: 'access',
      isValid: true,
    });

    expect(actor.getSnapshot().value).toBe('running');
    expect(actor.getSnapshot().context.errors).toBe(1);

    actor.send({
      type: 'SUBMIT_STEP',
      stepId: 'create-passport',
      level: 'create',
      isValid: true,
    });

    expect(actor.getSnapshot().context.currentStepIndex).toBe(1);

    actor.send({ type: 'HINT_USED', stepId: 'access-routing', level: 'access' });
    expect(actor.getSnapshot().context.hints).toBe(1);

    actor.send({
      type: 'SUBMIT_STEP',
      stepId: 'access-routing',
      level: 'access',
      isValid: true,
    });
    expect(actor.getSnapshot().value).toBe('completed');
  });
});
