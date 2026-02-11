type JsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
};

export function JsonEditor({ value, onChange, readOnly = false }: JsonEditorProps) {
  return (
    <textarea
      className="w-full min-h-[300px] border rounded-md p-3 font-mono text-xs"
      value={value}
      readOnly={readOnly}
      aria-readonly={readOnly}
      aria-label="Submodel JSON editor"
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
