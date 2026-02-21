import { useId } from 'react';
import { Info } from 'lucide-react';
import { Label } from '@/components/ui/label';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { FieldWrapperProps } from '../types/formTypes';

function sanitizeFormUrl(formUrl?: string): string | null {
  if (!formUrl) return null;
  const normalized = formUrl.trim();
  if (!normalized) return null;

  // Allow only safe relative links (not protocol-relative).
  if (normalized.startsWith('/') && !normalized.startsWith('//')) {
    return normalized;
  }

  try {
    const parsed = new URL(normalized);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.toString();
    }
  } catch {
    return null;
  }

  return null;
}

export function FieldWrapper({
  label,
  required,
  description,
  formUrl,
  error,
  unit,
  fieldId,
  fieldPath,
  children,
}: FieldWrapperProps) {
  const generatedId = useId();
  const inputId = fieldId ?? generatedId;
  const safeFormUrl = sanitizeFormUrl(formUrl);

  return (
    <div className="space-y-2" data-field-path={fieldPath}>
      <div className="flex items-center gap-1.5">
        <Label htmlFor={inputId}>
          {label}
          {unit && (
            <span className="ml-1 font-normal text-muted-foreground">({unit})</span>
          )}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
        {description && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs">
                <p className="text-xs">{description}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      {safeFormUrl && (
        <a
          className="text-xs text-primary hover:text-primary/80 inline-block"
          href={safeFormUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn more
        </a>
      )}
      {children}
      {error && (
        <p id={`${inputId}-error`} className="text-xs text-destructive" role="alert">{error}</p>
      )}
    </div>
  );
}
