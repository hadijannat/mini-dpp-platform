import { useEffect, useMemo } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { linter, type Diagnostic } from '@codemirror/lint';
import type { UISchema } from '../types/uiSchema';
import { buildJsonIssues, type JsonValidationIssue } from '../utils/jsonIssues';

type JsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  schema?: UISchema;
  onIssuesChange?: (issues: JsonValidationIssue[]) => void;
};

function issuesToDiagnostics(text: string, issues: JsonValidationIssue[]): Diagnostic[] {
  return issues.map((issue) => ({
    from: 0,
    to: Math.min(1, text.length),
    severity: issue.path === 'root' ? 'warning' : 'error',
    message: issue.path === 'root' ? issue.message : `${issue.path}: ${issue.message}`,
  }));
}

export function JsonEditor({
  value,
  onChange,
  readOnly = false,
  schema,
  onIssuesChange,
}: JsonEditorProps) {
  const extensions = useMemo(
    () => [
      json(),
      linter((view) => {
        const { issues } = buildJsonIssues(view.state.doc.toString(), schema);
        return issuesToDiagnostics(view.state.doc.toString(), issues);
      }),
    ],
    [schema],
  );

  useEffect(() => {
    if (!onIssuesChange) return;
    const { issues } = buildJsonIssues(value, schema);
    onIssuesChange(issues);
  }, [onIssuesChange, schema, value]);

  return (
    <CodeMirror
      value={value}
      editable={!readOnly}
      basicSetup={{
        lineNumbers: true,
        foldGutter: true,
        bracketMatching: true,
      }}
      extensions={extensions}
      theme="light"
      aria-label="Submodel JSON editor"
      className="rounded-md border text-xs"
      minHeight="300px"
      onChange={onChange}
    />
  );
}
