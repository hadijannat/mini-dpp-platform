// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useForm, useWatch } from 'react-hook-form';
import { FileField } from './FileField';

const uploadDppAttachmentMock = vi.fn();

vi.mock('@/lib/api', () => ({
  uploadDppAttachment: (...args: unknown[]) => uploadDppAttachmentMock(...args),
}));

function RenderField() {
  const form = useForm<Record<string, unknown>>({
    defaultValues: { doc: { contentType: '', value: '' } },
  });
  const watched = useWatch({ control: form.control, name: 'doc' });

  return (
    <div>
      <FileField
        name="doc"
        control={form.control}
        node={{ modelType: 'File', idShort: 'doc', smt: {} }}
        depth={0}
        editorContext={{ dppId: 'dpp-1', tenantSlug: 'default', token: 'token-1' }}
      />
      <pre data-testid="doc-value">{JSON.stringify(watched)}</pre>
    </div>
  );
}

describe('FileField', () => {
  beforeEach(() => {
    uploadDppAttachmentMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('supports manual content type and value entry', async () => {
    render(<RenderField />);

    const contentTypeInput = screen.getByPlaceholderText(
      'Content type (e.g. application/pdf)',
    ) as HTMLInputElement;
    const valueInput = screen.getByPlaceholderText('File URL or reference') as HTMLInputElement;
    fireEvent.change(contentTypeInput, { target: { value: 'application/pdf' } });
    fireEvent.change(valueInput, { target: { value: 'https://example.com/doc.pdf' } });

    await waitFor(() => {
      expect(screen.getByTestId('doc-value').textContent).toContain('application/pdf');
      expect(screen.getByTestId('doc-value').textContent).toContain('https://example.com/doc.pdf');
    });
  });

  it('uploads file and hydrates form value from response', async () => {
    uploadDppAttachmentMock.mockResolvedValue({
      attachment_id: 'att-1',
      content_type: 'image/png',
      size_bytes: 42,
      url: '/api/v1/tenants/default/dpps/dpp-1/attachments/att-1',
    });

    render(<RenderField />);

    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(fileInput).toBeTruthy();

    const file = new File(['png-data'], 'image.png', { type: 'image/png' });
    fireEvent.change(fileInput!, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadDppAttachmentMock).toHaveBeenCalledWith(
        'dpp-1',
        expect.any(File),
        expect.objectContaining({ tenantSlug: 'default' }),
      );
    });

    await waitFor(() => {
      const serialized = screen.getByTestId('doc-value').textContent ?? '';
      expect(serialized).toContain('image/png');
      expect(serialized).toContain('/api/v1/tenants/default/dpps/dpp-1/attachments/att-1');
    });
  });
});
