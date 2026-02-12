import { describe, expect, it } from 'vitest';
import { buildDppActionState } from './actionPolicy';

describe('buildDppActionState', () => {
  it('enables all read/update actions for owner draft with full access', () => {
    const state = buildDppActionState(
      {
        can_read: true,
        can_update: true,
        can_publish: true,
        can_archive: true,
        source: 'owner',
      },
      'draft',
    );

    expect(state).toEqual({
      canRead: true,
      canUpdate: true,
      canExport: true,
      canPublish: true,
      publishBlocked: false,
      canRefreshRebuild: true,
      canGenerateQr: false,
      canCaptureEvent: true,
      canViewEvents: true,
    });
  });

  it('disables update and publish actions for shared user with read-only access', () => {
    const state = buildDppActionState(
      {
        can_read: true,
        can_update: false,
        can_publish: false,
        can_archive: false,
        source: 'share',
      },
      'draft',
    );

    expect(state.canRead).toBe(true);
    expect(state.canExport).toBe(true);
    expect(state.canPublish).toBe(false);
    expect(state.publishBlocked).toBe(false);
    expect(state.canRefreshRebuild).toBe(false);
    expect(state.canCaptureEvent).toBe(false);
    expect(state.canUpdate).toBe(false);
  });

  it('enables QR only for published readable DPPs', () => {
    const published = buildDppActionState(
      {
        can_read: true,
        can_update: false,
        can_publish: false,
        can_archive: false,
        source: 'share',
      },
      'published',
    );
    const draft = buildDppActionState(
      {
        can_read: true,
        can_update: true,
        can_publish: true,
        can_archive: true,
        source: 'owner',
      },
      'draft',
    );

    expect(published.canGenerateQr).toBe(true);
    expect(draft.canGenerateQr).toBe(false);
    expect(published.publishBlocked).toBe(false);
  });

  it('keeps rebuild disabled for archived DPP even when can_update is true', () => {
    const state = buildDppActionState(
      {
        can_read: true,
        can_update: true,
        can_publish: true,
        can_archive: true,
        source: 'tenant_admin',
      },
      'archived',
    );

    expect(state.canUpdate).toBe(true);
    expect(state.canRefreshRebuild).toBe(false);
    expect(state.canCaptureEvent).toBe(false);
    expect(state.canPublish).toBe(false);
    expect(state.publishBlocked).toBe(false);
  });

  it('disables read-derived actions when can_read is false', () => {
    const state = buildDppActionState(
      {
        can_read: false,
        can_update: false,
        can_publish: false,
        can_archive: false,
        source: 'share',
      },
      'published',
    );

    expect(state.canRead).toBe(false);
    expect(state.canExport).toBe(false);
    expect(state.canViewEvents).toBe(false);
    expect(state.canGenerateQr).toBe(false);
    expect(state.publishBlocked).toBe(false);
  });

  it('blocks publish when additional publish blockers are present', () => {
    const state = buildDppActionState(
      {
        can_read: true,
        can_update: true,
        can_publish: true,
        can_archive: true,
        source: 'owner',
      },
      'draft',
      { publishBlocked: true },
    );

    expect(state.canPublish).toBe(false);
    expect(state.publishBlocked).toBe(true);
  });
});
