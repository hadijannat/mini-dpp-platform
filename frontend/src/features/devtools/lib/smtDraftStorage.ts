export const SMT_DRAFT_STORAGE_KEY = 'smtDrafts.v1';

export type SmtDraftRecord = {
  draftId: string;
  name: string;
  templateKey: string;
  version: string;
  updatedAt: string;
  data: Record<string, unknown>;
};

type DraftMap = Record<string, SmtDraftRecord>;

function readMap(): DraftMap {
  if (typeof window === 'undefined') return {};
  const raw = window.localStorage.getItem(SMT_DRAFT_STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {};
    }
    const entries = Object.entries(parsed as Record<string, unknown>);
    const map: DraftMap = {};
    for (const [draftId, value] of entries) {
      if (!value || typeof value !== 'object' || Array.isArray(value)) continue;
      const record = value as Partial<SmtDraftRecord>;
      if (
        typeof record.name !== 'string' ||
        typeof record.templateKey !== 'string' ||
        typeof record.version !== 'string' ||
        !record.data ||
        typeof record.data !== 'object' ||
        Array.isArray(record.data)
      ) {
        continue;
      }
      map[draftId] = {
        draftId,
        name: record.name,
        templateKey: record.templateKey,
        version: record.version,
        updatedAt: typeof record.updatedAt === 'string' ? record.updatedAt : new Date().toISOString(),
        data: record.data as Record<string, unknown>,
      };
    }
    return map;
  } catch {
    return {};
  }
}

function writeMap(map: DraftMap): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(SMT_DRAFT_STORAGE_KEY, JSON.stringify(map));
}

export function listSmtDrafts(): SmtDraftRecord[] {
  const map = readMap();
  return Object.values(map).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getSmtDraft(draftId: string): SmtDraftRecord | null {
  const map = readMap();
  return map[draftId] ?? null;
}

export function saveSmtDraft(
  draft: Omit<SmtDraftRecord, 'updatedAt'> & { updatedAt?: string },
): SmtDraftRecord {
  const map = readMap();
  const record: SmtDraftRecord = {
    ...draft,
    updatedAt: draft.updatedAt ?? new Date().toISOString(),
  };
  map[record.draftId] = record;
  writeMap(map);
  return record;
}

export function renameSmtDraft(draftId: string, name: string): SmtDraftRecord | null {
  const map = readMap();
  const record = map[draftId];
  if (!record) return null;
  const updated: SmtDraftRecord = {
    ...record,
    name,
    updatedAt: new Date().toISOString(),
  };
  map[draftId] = updated;
  writeMap(map);
  return updated;
}

export function deleteSmtDraft(draftId: string): void {
  const map = readMap();
  if (!map[draftId]) return;
  delete map[draftId];
  writeMap(map);
}

export function createSmtDraftId(templateKey: string, version: string): string {
  const sanitizedTemplate = templateKey.replace(/[^A-Za-z0-9_-]/g, '-');
  const sanitizedVersion = version.replace(/[^A-Za-z0-9._-]/g, '-');
  return `${sanitizedTemplate}-${sanitizedVersion}-${Date.now()}`;
}

export function exportSmtDraftRecord(draft: SmtDraftRecord): string {
  return JSON.stringify(draft, null, 2);
}

export function parseSmtDraftRecord(raw: string): SmtDraftRecord {
  const parsed = JSON.parse(raw) as Partial<SmtDraftRecord>;
  if (
    !parsed ||
    typeof parsed !== 'object' ||
    typeof parsed.draftId !== 'string' ||
    typeof parsed.name !== 'string' ||
    typeof parsed.templateKey !== 'string' ||
    typeof parsed.version !== 'string' ||
    !parsed.data ||
    typeof parsed.data !== 'object' ||
    Array.isArray(parsed.data)
  ) {
    throw new Error('Invalid draft payload');
  }
  return {
    draftId: parsed.draftId,
    name: parsed.name,
    templateKey: parsed.templateKey,
    version: parsed.version,
    updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : new Date().toISOString(),
    data: parsed.data as Record<string, unknown>,
  };
}
