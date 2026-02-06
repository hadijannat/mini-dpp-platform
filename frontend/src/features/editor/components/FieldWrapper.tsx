import { Info } from 'lucide-react';
import { Label } from '@/components/ui/label';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
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
      <div className="flex items-center gap-1.5">
        <Label>
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
      {formUrl && (
        <a
          className="text-xs text-primary hover:text-primary/80 inline-block"
          href={formUrl}
          target="_blank"
          rel="noreferrer"
        >
          Learn more
        </a>
      )}
      {children}
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
