import { describe, expect, it } from 'vitest';
import { createActor } from 'xstate';
import { cirpassMachine } from './cirpassMachine';

describe('cirpassMachine', () => {
  it('blocks invalid transitions and progresses on valid submissions', () => {
    const actor = createActor(cirpassMachine);
    actor.start();

    actor.send({
      type: 'SUBMIT_LEVEL',
      level: 'create',
      data: {
        identifier: '',
        materialComposition: '',
        carbonFootprint: null,
      },
    });

    expect(actor.getSnapshot().value).toBe('create');
    expect(actor.getSnapshot().context.errors).toBe(1);

    actor.send({
      type: 'SUBMIT_LEVEL',
      level: 'create',
      data: {
        identifier: 'did:web:dpp.eu:product:test',
        materialComposition: 'aluminum',
        carbonFootprint: 12.4,
      },
    });

    expect(actor.getSnapshot().value).toBe('access');

    actor.send({ type: 'HINT_USED', level: 'access' });
    expect(actor.getSnapshot().context.hints).toBe(1);
  });
});
