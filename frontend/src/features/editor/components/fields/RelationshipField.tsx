import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';
import { Badge } from '@/components/ui/badge';

type AASKey = { type?: string; value?: string };
type AASReference = { type?: string; keys?: AASKey[] } | null;

function ReferenceDisplay({ reference }: { reference: AASReference }) {
  if (!reference) {
    return <span className="text-xs text-muted-foreground italic">Not set</span>;
  }
  return (
    <div className="space-y-1">
      {reference.type && (
        <Badge variant="outline" className="text-xs">{reference.type}</Badge>
      )}
      {reference.keys && reference.keys.length > 0 ? (
        <ul className="space-y-1">
          {reference.keys.map((key, i) => (
            <li key={i} className="flex gap-2 text-xs">
              <span className="text-muted-foreground font-medium">{key.type}:</span>
              <span className="font-mono break-all">{key.value}</span>
            </li>
          ))}
        </ul>
      ) : (
        <span className="text-xs text-muted-foreground italic">No keys</span>
      )}
    </div>
  );
}

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
          const ref = current[refKey] as AASReference;
          return (
            <div className="border rounded-md p-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">{refLabel}</p>
              {ref ? (
                <ReferenceDisplay reference={ref} />
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
