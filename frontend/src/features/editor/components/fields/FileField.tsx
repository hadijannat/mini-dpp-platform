import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

export function FileField({ name, control, node }: FieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;

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
              <input
                type="text"
                className="w-full border rounded-md px-3 py-2 text-sm"
                placeholder="Content type (e.g. application/pdf)"
                value={current.contentType ?? ''}
                onChange={(e) =>
                  field.onChange({ ...current, contentType: e.target.value })
                }
              />
              <input
                type="text"
                className="w-full border rounded-md px-3 py-2 text-sm"
                placeholder="File URL or reference"
                value={current.value ?? ''}
                onChange={(e) =>
                  field.onChange({ ...current, value: e.target.value })
                }
              />
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
