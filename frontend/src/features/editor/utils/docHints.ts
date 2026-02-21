import type { DefinitionNode } from '../types/definition';
import type { DocHintsPayload } from '../contexts/DocHintsContext';

export type DocHintRecord = {
  semanticId?: string;
  idShortPath?: string;
  formTitle?: string;
  formInfo?: string;
  formUrl?: string;
  helpText?: string;
  pdfRef?: string;
  page?: string | number;
  source?: string;
};

function asNonEmptyString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim();
  return normalized || undefined;
}

function asStringOrNumber(value: unknown): string | number | undefined {
  if (typeof value === 'string') {
    const normalized = value.trim();
    return normalized || undefined;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return undefined;
}

export function normalizeSemanticId(value?: string | null): string {
  if (!value) return '';
  return value.trim().replace(/\/+$/, '').toLowerCase();
}

function normalizePathKey(value?: string | null): string {
  if (!value) return '';
  return value.trim().replace(/^\/+|\/+$/g, '');
}

function normalizeHintRecord(record: Record<string, unknown>): DocHintRecord {
  return {
    semanticId: asNonEmptyString(record.semanticId),
    idShortPath: asNonEmptyString(record.idShortPath),
    formTitle: asNonEmptyString(record.formTitle) ?? asNonEmptyString(record.form_title),
    formInfo: asNonEmptyString(record.formInfo) ?? asNonEmptyString(record.form_info),
    formUrl: asNonEmptyString(record.formUrl) ?? asNonEmptyString(record.form_url),
    helpText: asNonEmptyString(record.helpText),
    pdfRef: asNonEmptyString(record.pdfRef),
    page: asStringOrNumber(record.page),
    source: asNonEmptyString(record.source),
  };
}

function getPathHint(path: string, docHints?: DocHintsPayload): DocHintRecord | undefined {
  const normalizedPath = normalizePathKey(path);
  if (!normalizedPath) return undefined;

  const raw = docHints?.by_id_short_path?.[normalizedPath];
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
  return normalizeHintRecord(raw);
}

function getSemanticHint(semanticId: string, docHints?: DocHintsPayload): DocHintRecord | undefined {
  const key = normalizeSemanticId(semanticId);
  if (!key) return undefined;

  const raw = docHints?.by_semantic_id?.[key];
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
  return normalizeHintRecord(raw);
}

export function fieldPathToIdShortPath(fieldPath: string): string {
  const segments = fieldPath.split('.').filter(Boolean);
  const parts: string[] = [];

  for (const segment of segments) {
    if (/^\d+$/.test(segment)) {
      const last = parts.pop();
      if (last) {
        const withArrayMarker = last.endsWith('[]') ? last : `${last}[]`;
        parts.push(withArrayMarker);
      }
      continue;
    }
    parts.push(segment);
  }

  return parts.join('/');
}

export function buildDocHintDescription(hint: DocHintRecord): string | undefined {
  const base = hint.helpText ?? hint.formInfo;
  const pdfSegments: string[] = [];
  if (hint.pdfRef) {
    pdfSegments.push(`PDF: ${hint.pdfRef}`);
  }
  if (hint.page !== undefined) {
    pdfSegments.push(`p. ${hint.page}`);
  }
  if (!base && pdfSegments.length === 0) return undefined;
  if (pdfSegments.length === 0) return base;
  return [base, pdfSegments.join(', ')].filter(Boolean).join(' | ');
}

export function resolveDocHint(params: {
  node: DefinitionNode;
  fieldPath: string;
  docHints?: DocHintsPayload;
}): DocHintRecord | undefined {
  const semanticHint = getSemanticHint(params.node.semanticId ?? '', params.docHints);
  if (semanticHint) {
    return semanticHint;
  }

  const pathHint = getPathHint(fieldPathToIdShortPath(params.fieldPath), params.docHints);
  if (pathHint) {
    return pathHint;
  }

  return undefined;
}
