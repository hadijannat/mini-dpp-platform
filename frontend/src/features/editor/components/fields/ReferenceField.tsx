import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

type ReferenceKey = { type?: string; value?: string };
type ReferenceValue = { type?: string; keys?: ReferenceKey[] };

export function ReferenceField({ name, control, node, schema }: FieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const typeOptions =
    schema?.properties?.type?.enum ?? ['ModelReference', 'ExternalReference'];

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const current: ReferenceValue =
          field.value && typeof field.value === 'object' && !Array.isArray(field.value)
            ? (field.value as ReferenceValue)
            : { type: 'ModelReference', keys: [] };
        const keys = Array.isArray(current.keys) ? current.keys : [];

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500">Reference Type</label>
                <select
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                  value={current.type ?? 'ModelReference'}
                  onChange={(e) => {
                    field.onChange({ ...current, type: e.target.value, keys });
                  }}
                >
                  {typeOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                {keys.map((key, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="text"
                      className="w-32 border rounded-md px-2 py-1 text-sm"
                      placeholder="Type"
                      value={key?.type ?? ''}
                      onChange={(e) => {
                        const next = keys.map((entry, idx) =>
                          idx === index ? { ...entry, type: e.target.value } : entry,
                        );
                        field.onChange({ ...current, keys: next });
                      }}
                    />
                    <input
                      type="text"
                      className="flex-1 border rounded-md px-2 py-1 text-sm"
                      placeholder="Value"
                      value={key?.value ?? ''}
                      onChange={(e) => {
                        const next = keys.map((entry, idx) =>
                          idx === index ? { ...entry, value: e.target.value } : entry,
                        );
                        field.onChange({ ...current, keys: next });
                      }}
                    />
                    <button
                      type="button"
                      className="text-xs text-red-500 hover:text-red-600"
                      onClick={() => {
                        const next = keys.filter((_, idx) => idx !== index);
                        field.onChange({ ...current, keys: next });
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="text-sm text-primary hover:text-primary/80"
                  onClick={() => {
                    const next = [...keys, { type: '', value: '' }];
                    field.onChange({ ...current, keys: next });
                  }}
                >
                  Add key
                </button>
              </div>
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
