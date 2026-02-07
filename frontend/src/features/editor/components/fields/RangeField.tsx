import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

export function RangeField({ name, control, node }: FieldProps) {
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
            ? (field.value as Record<string, number | null>)
            : { min: null, max: null };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="text-xs text-gray-500">Min</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={current.min ?? ''}
                  onChange={(e) => {
                    const next = e.target.value === '' ? null : Number(e.target.value);
                    field.onChange({ ...current, min: next });
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Max</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={current.max ?? ''}
                  onChange={(e) => {
                    const next = e.target.value === '' ? null : Number(e.target.value);
                    field.onChange({ ...current, max: next });
                  }}
                />
              </div>
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
