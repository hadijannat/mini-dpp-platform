import { useCallback, useEffect, useMemo, useRef } from 'react';
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
  const issuesCacheRef = useRef<Map<string, JsonValidationIssue[]>>(new Map());

  useEffect(() => {
    issuesCacheRef.current.clear();
  }, [schema]);

  const getIssuesForText = useCallback(
    (text: string): JsonValidationIssue[] => {
      const cached = issuesCacheRef.current.get(text);
      if (cached) return cached;

      const { issues } = buildJsonIssues(text, schema);
      issuesCacheRef.current.set(text, issues);

      // Keep cache small and bounded for active typing sessions.
      if (issuesCacheRef.current.size > 25) {
        const oldestKey = issuesCacheRef.current.keys().next().value;
        if (oldestKey !== undefined) {
          issuesCacheRef.current.delete(oldestKey);
        }
      }

      return issues;
    },
    [schema],
  );

  const extensions = useMemo(
    () => [
      json(),
      linter((view) => {
        const text = view.state.doc.toString();
        const issues = getIssuesForText(text);
        return issuesToDiagnostics(text, issues);
      }),
    ],
    [getIssuesForText],
  );

  useEffect(() => {
    if (!onIssuesChange) return;
    onIssuesChange(getIssuesForText(value));
  }, [getIssuesForText, onIssuesChange, value]);

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
