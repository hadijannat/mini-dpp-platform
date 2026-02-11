import { useMemo, useState } from 'react';
import { Controller } from 'react-hook-form';
import { uploadDppAttachment } from '@/lib/api';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

const DEFAULT_MIME_SUGGESTIONS = ['application/pdf', 'image/png'];

function sanitizeId(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]/g, '_');
}

export function FileField({ name, control, node, schema, editorContext }: FieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const [mode, setMode] = useState<'manual' | 'upload'>('manual');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const suggestions = useMemo(() => {
    const fromSchema = schema?.['x-file-content-type-suggestions'] ?? [];
    const ordered = [...fromSchema, ...DEFAULT_MIME_SUGGESTIONS];
    return Array.from(new Set(ordered.filter((entry) => entry && entry.trim() !== '')));
  }, [schema]);
  const accepts = useMemo(() => {
    const fromSchema = schema?.['x-file-accept'] ?? [];
    if (fromSchema.length > 0) {
      return fromSchema.join(',');
    }
    return suggestions.join(',');
  }, [schema, suggestions]);

  const hasUploadContext = Boolean(editorContext?.dppId && editorContext?.tenantSlug);
  const datalistId = `${sanitizeId(name)}_mime_suggestions`;

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const current =
          field.value && typeof field.value === 'object' && !Array.isArray(field.value)
            ? (field.value as Record<string, string>)
            : { contentType: '', value: '' };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
            fieldPath={name}
          >
            <div className="space-y-2">
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  className={`rounded border px-2 py-1 ${mode === 'manual' ? 'bg-accent' : ''}`}
                  onClick={() => setMode('manual')}
                >
                  Manual
                </button>
                <button
                  type="button"
                  className={`rounded border px-2 py-1 ${mode === 'upload' ? 'bg-accent' : ''}`}
                  onClick={() => setMode('upload')}
                  disabled={!hasUploadContext}
                  title={hasUploadContext ? undefined : 'Upload is available only in DPP editor context'}
                >
                  Upload
                </button>
              </div>

              <input
                type="text"
                className="w-full border rounded-md px-3 py-2 text-sm"
                placeholder="Content type (e.g. application/pdf)"
                list={suggestions.length > 0 ? datalistId : undefined}
                value={current.contentType ?? ''}
                onChange={(e) =>
                  field.onChange({ ...current, contentType: e.target.value })
                }
              />
              {suggestions.length > 0 && (
                <datalist id={datalistId}>
                  {suggestions.map((entry) => (
                    <option key={entry} value={entry} />
                  ))}
                </datalist>
              )}

              <input
                type="text"
                className="w-full border rounded-md px-3 py-2 text-sm"
                placeholder="File URL or reference"
                value={current.value ?? ''}
                onChange={(e) =>
                  field.onChange({ ...current, value: e.target.value })
                }
              />

              {mode === 'upload' && hasUploadContext && (
                <div className="rounded-md border border-dashed p-3 text-xs space-y-2">
                  <input
                    type="file"
                    className="block w-full text-xs"
                    accept={accepts || undefined}
                    disabled={uploading}
                    onChange={async (event) => {
                      const input = event.currentTarget;
                      const selected = event.target.files?.[0];
                      if (!selected || !editorContext) return;
                      setUploadError(null);
                      setUploading(true);
                      try {
                        const response = await uploadDppAttachment(editorContext.dppId, selected, {
                          token: editorContext.token,
                          tenantSlug: editorContext.tenantSlug,
                          contentType: current.contentType || selected.type || undefined,
                        });
                        field.onChange({
                          ...current,
                          contentType: response.content_type,
                          value: response.url,
                        });
                        setMode('manual');
                      } catch (error) {
                        const message =
                          error instanceof Error ? error.message : 'Attachment upload failed';
                        setUploadError(message);
                      } finally {
                        setUploading(false);
                        input.value = '';
                      }
                    }}
                  />
                  <p className="text-muted-foreground">
                    Uploaded files are stored privately. Downloads require authenticated tenant access.
                  </p>
                  {uploadError && <p className="text-destructive">{uploadError}</p>}
                </div>
              )}
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
