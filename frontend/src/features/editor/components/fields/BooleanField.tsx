import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

export function BooleanField({ name, control, node }: FieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={Boolean(field.value)}
            onChange={(e) => field.onChange(e.target.checked)}
          />
          <div>
            <span className="text-sm text-gray-800">
              {label}
              {required && <span className="text-red-500 ml-1">*</span>}
            </span>
            {description && <p className="text-xs text-gray-500">{description}</p>}
          </div>
          {fieldState.error && (
            <p className="text-xs text-red-600">{fieldState.error.message}</p>
          )}
        </div>
      )}
    />
  );
}
