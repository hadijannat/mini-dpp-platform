import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';
import { ReferenceObjectEditor, type AASReference } from './ReferenceObjectEditor';

export function RelationshipField({ name, control, node }: FieldProps) {
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
            ? (field.value as Record<string, unknown>)
            : { first: { type: 'ModelReference', keys: [] }, second: { type: 'ModelReference', keys: [] } };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
            fieldPath={name}
          >
            <div className="space-y-3">
              <ReferenceObjectEditor
                label="First Reference"
                value={(current.first as AASReference) ?? null}
                onChange={(value) => field.onChange({ ...current, first: value })}
              />
              <ReferenceObjectEditor
                label="Second Reference"
                value={(current.second as AASReference) ?? null}
                onChange={(value) => field.onChange({ ...current, second: value })}
              />
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
