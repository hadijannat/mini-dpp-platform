import { useId } from 'react';
import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { BooleanField } from './BooleanField';
import { EnumField } from './EnumField';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

function resolveInputType(
  valueType?: string,
  format?: string,
): { type: string; step?: string } {
  if (format === 'date') return { type: 'date' };
  if (format === 'date-time') return { type: 'datetime-local' };

  switch (valueType) {
    case 'xs:integer':
    case 'xs:long':
    case 'xs:short':
    case 'xs:int':
      return { type: 'number', step: '1' };
    case 'xs:decimal':
    case 'xs:double':
    case 'xs:float':
      return { type: 'number', step: '0.01' };
    case 'xs:date':
      return { type: 'date' };
    case 'xs:dateTime':
      return { type: 'datetime-local' };
    case 'xs:anyURI':
      return { type: 'url' };
    case 'xs:boolean':
      return { type: 'boolean' };
    default:
      return { type: 'text' };
  }
}

export function PropertyField(props: FieldProps) {
  const { name, control, node, schema } = props;
  const fieldId = useId();

  // Delegate to BooleanField
  if (node.valueType === 'xs:boolean' || schema?.type === 'boolean') {
    return <BooleanField {...props} />;
  }

  // Delegate to EnumField
  const hasChoices = (node.smt?.form_choices && node.smt.form_choices.length > 0) ||
    (schema?.enum && schema.enum.length > 0);
  if (hasChoices) {
    return <EnumField {...props} />;
  }

  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const { type: inputType, step } = resolveInputType(node.valueType, schema?.format);
  const isNumber = inputType === 'number';

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const displayValue = isNumber
          ? (typeof field.value === 'number' ? field.value : field.value ?? '')
          : (field.value ?? '');

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
            fieldId={fieldId}
          >
            <input
              id={fieldId}
              type={inputType}
              step={step}
              aria-describedby={fieldState.error ? `${fieldId}-error` : undefined}
              aria-invalid={fieldState.error ? true : undefined}
              className={`w-full border rounded-md px-3 py-2 text-sm ${
                fieldState.error ? 'border-red-500' : ''
              }`}
              value={displayValue as string | number}
              onChange={(e) => {
                if (isNumber) {
                  const raw = e.target.value;
                  field.onChange(raw === '' ? null : Number(raw));
                } else {
                  field.onChange(e.target.value);
                }
              }}
            />
          </FieldWrapper>
        );
      }}
    />
  );
}
