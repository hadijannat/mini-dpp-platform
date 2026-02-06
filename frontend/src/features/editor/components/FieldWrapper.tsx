import type { FieldWrapperProps } from '../types/formTypes';

export function FieldWrapper({
  label,
  required,
  description,
  formUrl,
  error,
  unit,
  children,
}: FieldWrapperProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {unit && (
          <span className="ml-1 font-normal text-gray-500">({unit})</span>
        )}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {description && (
        <p className="text-xs text-gray-500">{description}</p>
      )}
      {formUrl && (
        <a
          className="text-xs text-primary-600 hover:text-primary-700 inline-block"
          href={formUrl}
          target="_blank"
          rel="noreferrer"
        >
          Learn more
        </a>
      )}
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
