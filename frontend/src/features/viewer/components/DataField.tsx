interface DataFieldProps {
  label: string;
  value: unknown;
  unit?: string;
}

export function DataField({ label, value, unit }: DataFieldProps) {
  const formatted = formatValue(value);
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">
        {formatted}
        {unit && <span className="ml-1 text-muted-foreground">{unit}</span>}
      </p>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') return value.toLocaleString();
  if (typeof value === 'string') {
    // Try to detect and format dates
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
      try { return new Date(value).toLocaleDateString(); } catch { /* fall through */ }
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '-';
    // Multi-language property
    if (value.every(v => v && typeof v === 'object' && 'language' in v && 'text' in v)) {
      return value.map((v: Record<string, unknown>) => `${v.text} (${v.language})`).join(', ');
    }
    return `[${value.length} items]`;
  }
  try { return JSON.stringify(value); } catch { return '[object]'; }
}
