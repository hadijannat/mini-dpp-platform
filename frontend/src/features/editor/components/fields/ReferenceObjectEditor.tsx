import { Badge } from '@/components/ui/badge';

export type AASKey = { type?: string; value?: string };
export type AASReference = { type?: string; keys?: AASKey[] } | null;

type ReferenceObjectEditorProps = {
  label: string;
  value: AASReference;
  onChange: (value: AASReference) => void;
};

export function ReferenceObjectEditor({ label, value, onChange }: ReferenceObjectEditorProps) {
  const current = value ?? { type: 'ModelReference', keys: [] };
  const keys = Array.isArray(current.keys) ? current.keys : [];

  return (
    <div className="rounded-md border p-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">{label}</p>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px]">Type</Badge>
          <select
            className="w-full rounded-md border px-2 py-1 text-sm"
            value={current.type ?? 'ModelReference'}
            onChange={(event) =>
              onChange({
                ...current,
                type: event.target.value,
                keys,
              })
            }
          >
            <option value="ModelReference">ModelReference</option>
            <option value="ExternalReference">ExternalReference</option>
          </select>
        </div>

        {keys.map((key, index) => (
          <div key={`${label}-key-${index}`} className="flex items-center gap-2">
            <input
              type="text"
              className="w-32 rounded-md border px-2 py-1 text-xs"
              placeholder="Key type"
              value={key.type ?? ''}
              onChange={(event) => {
                const next = keys.map((entry, idx) =>
                  idx === index ? { ...entry, type: event.target.value } : entry,
                );
                onChange({ ...current, keys: next });
              }}
            />
            <input
              type="text"
              className="flex-1 rounded-md border px-2 py-1 text-xs"
              placeholder="Key value"
              value={key.value ?? ''}
              onChange={(event) => {
                const next = keys.map((entry, idx) =>
                  idx === index ? { ...entry, value: event.target.value } : entry,
                );
                onChange({ ...current, keys: next });
              }}
            />
            <button
              type="button"
              className="text-xs text-red-500 hover:text-red-600"
              onClick={() => {
                const next = keys.filter((_, idx) => idx !== index);
                onChange({ ...current, keys: next });
              }}
            >
              Remove
            </button>
          </div>
        ))}

        <button
          type="button"
          className="text-sm text-primary hover:text-primary/80"
          onClick={() => onChange({ ...current, keys: [...keys, { type: '', value: '' }] })}
        >
          Add key
        </button>
      </div>
    </div>
  );
}

