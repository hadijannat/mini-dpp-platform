import { useId } from 'react';
import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

export function EnumField({ name, control, node, schema }: FieldProps) {
  const fieldId = useId();
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const options = node.smt?.form_choices ?? schema?.enum ?? [];

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <FieldWrapper
          label={label}
          required={required}
          description={description}
          formUrl={formUrl}
          error={fieldState.error?.message}
          fieldId={fieldId}
        >
          <select
            id={fieldId}
            aria-describedby={fieldState.error ? `${fieldId}-error` : undefined}
            aria-invalid={fieldState.error ? true : undefined}
            className={`w-full border rounded-md px-3 py-2 text-sm ${
              fieldState.error ? 'border-red-500' : ''
            }`}
            value={(field.value as string) ?? ''}
            onChange={(e) => field.onChange(e.target.value)}
          >
            <option value="">
              {node.smt?.example_value ? `e.g. ${node.smt.example_value}` : 'Select...'}
            </option>
            {options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </FieldWrapper>
      )}
    />
  );
}
