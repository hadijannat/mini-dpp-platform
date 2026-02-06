import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

export function ReadOnlyField({ name, control, node }: FieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <div className="border rounded-md p-4 bg-gray-50">
          <p className="text-sm font-medium text-gray-800">
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </p>
          {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
          <pre className="mt-3 text-xs text-gray-600 whitespace-pre-wrap">
            {field.value === undefined || field.value === null || field.value === ''
              ? 'Read-only'
              : JSON.stringify(field.value, null, 2)}
          </pre>
        </div>
      )}
    />
  );
}
