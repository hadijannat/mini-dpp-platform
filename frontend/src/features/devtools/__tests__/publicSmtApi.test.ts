import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  exportPublicTemplate,
  exportPublicTemplateWithMeta,
  getPublicTemplateContract,
  listPublicTemplates,
  previewPublicTemplate,
  previewPublicTemplateWithMeta,
} from '../lib/publicSmtApi';
import { PublicSmtApiError } from '../lib/publicSmtErrors';

const apiFetchMock = vi.fn();
const tenantApiFetchMock = vi.fn();

vi.mock('@/lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  tenantApiFetch: (...args: unknown[]) => tenantApiFetchMock(...args),
  getApiErrorMessage: vi.fn().mockResolvedValue('Request failed'),
}));

describe('publicSmtApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiFetchMock.mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ templates: [], count: 0, status_filter: 'published' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
  });

  it('uses apiFetch (not tenantApiFetch) for public SMT endpoints', async () => {
    await listPublicTemplates({ status: 'published' });
    await getPublicTemplateContract('digital-nameplate');
    await previewPublicTemplate({ template_key: 'digital-nameplate', data: {} });
    await exportPublicTemplate({ template_key: 'digital-nameplate', data: {}, format: 'json' });

    expect(apiFetchMock).toHaveBeenCalled();
    expect(tenantApiFetchMock).not.toHaveBeenCalled();
  });

  it('captures preview rate-limit headers on success', async () => {
    apiFetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          template_key: 'digital-nameplate',
          version: '3.0.1',
          aas_environment: {},
          warnings: [],
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'X-RateLimit-Limit': '60',
            'X-RateLimit-Remaining': '42',
          },
        },
      ),
    );

    const result = await previewPublicTemplateWithMeta({
      template_key: 'digital-nameplate',
      data: {},
    });

    expect(result.meta.limit).toBe(60);
    expect(result.meta.remaining).toBe(42);
  });

  it('captures export rate-limit headers on success', async () => {
    apiFetchMock.mockResolvedValueOnce(
      new Response('file-content', {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Content-Disposition': 'attachment; filename="digital-nameplate.json"',
          'X-RateLimit-Limit': '10',
          'X-RateLimit-Remaining': '8',
        },
      }),
    );

    const result = await exportPublicTemplateWithMeta({
      template_key: 'digital-nameplate',
      data: {},
      format: 'json',
    });

    expect(result.meta.limit).toBe(10);
    expect(result.meta.remaining).toBe(8);
    expect(result.result.filename).toBe('digital-nameplate.json');
  });

  it('parses structured errors and retry metadata on 429', async () => {
    apiFetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            code: 'schema_validation_failed',
            message: 'Template data failed validation',
            errors: [{ path: 'ManufacturerName', message: 'Required' }],
          },
        }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'X-RateLimit-Limit': '60',
            'X-RateLimit-Remaining': '0',
            'Retry-After': '60',
          },
        },
      ),
    );

    const error = (await previewPublicTemplateWithMeta({
      template_key: 'digital-nameplate',
      data: {},
    }).catch((err) => err)) as PublicSmtApiError;

    expect(error).toBeInstanceOf(PublicSmtApiError);
    expect(error.status).toBe(429);
    expect(error.rateLimit?.retryAfterSeconds).toBe(60);
    const detail = error.detail;
    expect(typeof detail).toBe('object');
    if (detail && typeof detail === 'object') {
      expect(detail.code).toBe('schema_validation_failed');
      expect(detail.errors?.[0]?.path).toBe('ManufacturerName');
    }
  });
});
