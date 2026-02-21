export type PublicSmtRateLimitMeta = {
  limit?: number;
  remaining?: number;
  retryAfterSeconds?: number;
};

export type PublicSmtIssueType = 'schema' | 'metamodel' | 'instance' | 'warning' | 'unknown';

export type PublicSmtIssue = {
  path: string;
  message: string;
  type: PublicSmtIssueType;
};

export type PublicSmtErrorDetail = {
  code?: string;
  message?: string;
  errors?: PublicSmtIssue[];
  warnings?: PublicSmtIssue[];
};

export class PublicSmtApiError extends Error {
  status: number;
  detail?: PublicSmtErrorDetail | string;
  rateLimit?: PublicSmtRateLimitMeta;

  constructor(
    message: string,
    init: {
      status: number;
      detail?: PublicSmtErrorDetail | string;
      rateLimit?: PublicSmtRateLimitMeta;
    },
  ) {
    super(message);
    this.name = 'PublicSmtApiError';
    this.status = init.status;
    this.detail = init.detail;
    this.rateLimit = init.rateLimit;
  }
}

function parseIntHeader(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function extractPublicSmtRateLimit(headers: Headers): PublicSmtRateLimitMeta {
  return {
    limit: parseIntHeader(headers.get('x-ratelimit-limit')),
    remaining: parseIntHeader(headers.get('x-ratelimit-remaining')),
    retryAfterSeconds: parseIntHeader(headers.get('retry-after')),
  };
}

function issueTypeFromCode(code?: string): PublicSmtIssueType {
  if (!code) return 'unknown';
  if (code === 'schema_validation_failed') return 'schema';
  if (code === 'metamodel_validation_failed') return 'metamodel';
  if (code === 'instance_build_failed' || code === 'instance_serialization_failed') {
    return 'instance';
  }
  return 'unknown';
}

function normalizeIssuePath(path: unknown): string {
  if (typeof path === 'string' && path.trim()) {
    return path.trim();
  }
  return 'root';
}

function normalizeIssueMessage(message: unknown): string | null {
  if (typeof message === 'string') {
    const normalized = message.trim();
    return normalized || null;
  }
  return null;
}

function normalizeIssueRecord(
  entry: unknown,
  fallbackType: PublicSmtIssueType,
): PublicSmtIssue | null {
  if (typeof entry === 'string') {
    const message = normalizeIssueMessage(entry);
    if (!message) return null;
    return { path: 'root', message, type: fallbackType };
  }

  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
    return null;
  }

  const record = entry as Record<string, unknown>;
  const message = normalizeIssueMessage(record.message);
  if (!message) return null;

  return {
    path: normalizeIssuePath(record.path),
    message,
    type: fallbackType,
  };
}

function normalizeDetail(detail: unknown): PublicSmtErrorDetail | string | undefined {
  if (typeof detail === 'string') {
    const message = detail.trim();
    return message || undefined;
  }
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) {
    return undefined;
  }

  const record = detail as Record<string, unknown>;
  const code = typeof record.code === 'string' ? record.code : undefined;
  const message = normalizeIssueMessage(record.message);
  const fallbackType = issueTypeFromCode(code);

  const errorEntries = Array.isArray(record.errors)
    ? record.errors
        .map((entry) => normalizeIssueRecord(entry, fallbackType))
        .filter((entry): entry is PublicSmtIssue => entry !== null)
    : [];

  const warningEntries = Array.isArray(record.warnings)
    ? record.warnings
        .map((entry) => normalizeIssueRecord(entry, 'warning'))
        .filter((entry): entry is PublicSmtIssue => entry !== null)
    : [];

  return {
    code,
    message: message ?? undefined,
    errors: errorEntries,
    warnings: warningEntries,
  };
}

function fallbackErrorMessage(
  status: number,
  fallback: string,
  detail?: PublicSmtErrorDetail | string,
  rawText?: string,
): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }
  if (detail && typeof detail === 'object') {
    if (detail.message && detail.message.trim()) {
      return detail.message.trim();
    }
    if (detail.errors && detail.errors.length > 0) {
      const first = detail.errors[0];
      return first.path === 'root' ? first.message : `${first.path}: ${first.message}`;
    }
  }
  if (rawText && rawText.trim()) {
    return rawText.trim();
  }
  if (status === 429) {
    return 'Rate limit exceeded. Please retry later.';
  }
  return fallback;
}

export async function parsePublicSmtApiError(
  response: Response,
  fallback: string,
): Promise<PublicSmtApiError> {
  const rateLimit = extractPublicSmtRateLimit(response.headers);
  const contentType = response.headers.get('content-type') ?? '';
  const rawText = await response.text();

  let detail: PublicSmtErrorDetail | string | undefined;

  if (contentType.includes('application/json')) {
    try {
      const payload = JSON.parse(rawText) as { detail?: unknown };
      detail = normalizeDetail(payload?.detail);
    } catch {
      detail = undefined;
    }
  }

  const message = fallbackErrorMessage(response.status, fallback, detail, rawText);
  return new PublicSmtApiError(message, {
    status: response.status,
    detail,
    rateLimit,
  });
}

export function collectIssues(detail: PublicSmtErrorDetail | string | undefined): PublicSmtIssue[] {
  if (!detail || typeof detail === 'string') return [];
  const errors = detail.errors ?? [];
  const warnings = detail.warnings ?? [];
  return [...errors, ...warnings];
}
