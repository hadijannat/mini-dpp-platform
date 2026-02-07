type JsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
};

export function JsonEditor({ value, onChange }: JsonEditorProps) {
  return (
    <textarea
      className="w-full min-h-[300px] border rounded-md p-3 font-mono text-xs"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
