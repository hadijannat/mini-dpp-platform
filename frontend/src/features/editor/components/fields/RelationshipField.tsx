import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

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
            : { first: null, second: null };

        const renderRef = (refKey: 'first' | 'second', refLabel: string) => {
          const ref = current[refKey] as Record<string, unknown> | null;
          return (
            <div className="border rounded-md p-3">
              <p className="text-xs font-medium text-gray-600 mb-2">{refLabel}</p>
              {ref ? (
                <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                  {JSON.stringify(ref, null, 2)}
                </pre>
              ) : (
                <input
                  type="text"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  placeholder={`${refLabel} reference (JSON)`}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      field.onChange({ ...current, [refKey]: parsed });
                    } catch {
                      // Wait for valid JSON
                    }
                  }}
                />
              )}
            </div>
          );
        };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            <div className="space-y-3">
              {renderRef('first', 'First Reference')}
              {renderRef('second', 'Second Reference')}
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
