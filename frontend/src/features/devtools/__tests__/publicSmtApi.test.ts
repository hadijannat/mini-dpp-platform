import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  exportPublicTemplate,
  getPublicTemplateContract,
  listPublicTemplates,
  previewPublicTemplate,
} from '../lib/publicSmtApi';

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
    apiFetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ templates: [], count: 0, status_filter: 'published' }),
      blob: async () => new Blob(['{}'], { type: 'application/json' }),
      headers: new Headers(),
    });
  });

  it('uses apiFetch (not tenantApiFetch) for public SMT endpoints', async () => {
    await listPublicTemplates({ status: 'published' });
    await getPublicTemplateContract('digital-nameplate');
    await previewPublicTemplate({ template_key: 'digital-nameplate', data: {} });
    await exportPublicTemplate({ template_key: 'digital-nameplate', data: {}, format: 'json' });

    expect(apiFetchMock).toHaveBeenCalled();
    expect(tenantApiFetchMock).not.toHaveBeenCalled();
  });
});
