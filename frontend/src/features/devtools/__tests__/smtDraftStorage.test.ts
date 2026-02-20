// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import {
  SMT_DRAFT_STORAGE_KEY,
  createSmtDraftId,
  deleteSmtDraft,
  getSmtDraft,
  listSmtDrafts,
  parseSmtDraftRecord,
  renameSmtDraft,
  saveSmtDraft,
} from '../lib/smtDraftStorage';

describe('smtDraftStorage', () => {
  beforeEach(() => {
    window.localStorage.removeItem(SMT_DRAFT_STORAGE_KEY);
  });

  it('saves, lists, renames, and deletes drafts', () => {
    const draftId = createSmtDraftId('digital-nameplate', '3.0.1');
    const saved = saveSmtDraft({
      draftId,
      name: 'My Draft',
      templateKey: 'digital-nameplate',
      version: '3.0.1',
      data: { ManufacturerName: 'ACME' },
    });

    expect(saved.draftId).toBe(draftId);
    expect(listSmtDrafts()).toHaveLength(1);

    const renamed = renameSmtDraft(draftId, 'Renamed Draft');
    expect(renamed?.name).toBe('Renamed Draft');
    expect(getSmtDraft(draftId)?.name).toBe('Renamed Draft');

    deleteSmtDraft(draftId);
    expect(getSmtDraft(draftId)).toBeNull();
    expect(listSmtDrafts()).toHaveLength(0);
  });

  it('parses imported draft payload', () => {
    const parsed = parseSmtDraftRecord(
      JSON.stringify({
        draftId: 'draft-1',
        name: 'Imported Draft',
        templateKey: 'digital-nameplate',
        version: '3.0.1',
        data: { ManufacturerName: 'ACME' },
      }),
    );

    expect(parsed.name).toBe('Imported Draft');
    expect(parsed.templateKey).toBe('digital-nameplate');
  });
});
