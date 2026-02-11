import type { DppAccessSummary, DppActionState } from '../types';

type DppStatus = 'draft' | 'published' | 'archived' | string;

export function buildDppActionState(
  access: DppAccessSummary | undefined,
  status: DppStatus,
): DppActionState {
  const canRead = access?.can_read !== false;
  const canUpdate = access?.can_update === true;
  const canPublish = status === 'draft' && access?.can_publish === true;
  const canRefreshRebuild = status !== 'archived' && canUpdate;
  const canGenerateQr = status === 'published' && canRead;
  const canCaptureEvent = status === 'draft' && canUpdate;

  return {
    canRead,
    canUpdate,
    canExport: canRead,
    canPublish,
    canRefreshRebuild,
    canGenerateQr,
    canCaptureEvent,
    canViewEvents: canRead,
  };
}

