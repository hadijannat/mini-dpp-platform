import type { ReactNode } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type SubmodelEditorShellProps = {
  title: string;
  activeViewLabel?: string;
  formDescription?: string;
  jsonDescription?: string;
  children: ReactNode;
};

export function SubmodelEditorShell({
  title,
  activeViewLabel = 'form',
  formDescription = 'Edit values using the schema-driven form.',
  jsonDescription = 'Edit raw JSON for advanced tweaks.',
  children,
}: SubmodelEditorShellProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {activeViewLabel === 'json' ? jsonDescription : formDescription}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}
